import copy
import json
import os
import shutil
from contextlib import contextmanager
from json import JSONDecodeError
from time import sleep

import requests
from git import Repo

from ci_jobs_trigger.libs.utils.general import trigger_ci_job
from ci_jobs_trigger.utils.constant import DAYS_TO_SECONDS
from ci_jobs_trigger.utils.general import send_slack_message, get_config, AddonsWebhookTriggerError

LOCAL_REPO_PATH = "/tmp/ci-jobs-trigger"
OPERATORS_DATA_FILE_NAME = "operators-latest-iib.json"
OPERATORS_DATA_FILE = os.path.join(LOCAL_REPO_PATH, OPERATORS_DATA_FILE_NAME)


def read_data_file():
    try:
        with open(OPERATORS_DATA_FILE, "r") as fd:
            return json.load(fd)

    except (FileNotFoundError, JSONDecodeError):
        return {}


def get_operator_data_from_url(operator_name, ocp_version, logger):
    logger.info(f"Getting IIB data for {operator_name}")
    datagrepper_query_url = (
        "https://datagrepper.engineering.redhat.com/raw?topic=/topic/"
        "VirtualTopic.eng.ci.redhat-container-image.index.built"
    )

    res = requests.get(
        f"{datagrepper_query_url}&contains={operator_name}",
        verify=False,
    )
    logger.info(f"Done getting IIB data for {operator_name}")
    json_res = res.json()
    for raw_msg in json_res["raw_messages"]:
        _index = raw_msg["msg"]["index"]
        if _index["ocp_version"] == ocp_version:
            yield _index


def get_new_iib(operator_config_data, logger):
    new_trigger_data = False
    data_from_file = read_data_file()
    new_data = copy.deepcopy(data_from_file)
    ci_jobs = operator_config_data.get("ci_jobs", {})

    for _ocp_version, _jobs_data in ci_jobs.items():
        if _jobs_data:
            for _ci_job in [*_jobs_data["jobs"]]:
                job_name = _ci_job["name"]
                job_products = _ci_job["products"]
                new_data.setdefault(_ocp_version, {}).setdefault(job_name, {})
                new_data[_ocp_version][job_name]["operators"] = {}
                new_data[_ocp_version][job_name]["ci"] = _ci_job["ci"]
                for _operator, _operator_name in job_products.items():
                    new_data[_ocp_version][job_name]["operators"].setdefault(_operator_name, {})
                    _operator_data = new_data[_ocp_version][job_name]["operators"][_operator_name]
                    _operator_data["triggered"] = False
                    logger.info(f"Parsing new IIB data for {_operator_name}")
                    for iib_data in get_operator_data_from_url(
                        operator_name=_operator,
                        ocp_version=_ocp_version,
                        logger=logger,
                    ):
                        index_image = iib_data["index_image"]

                        iib_data_from_file = _operator_data.get("iib")
                        if iib_data_from_file:
                            iib_from_url = iib_data["index_image"].split("iib:")[-1]
                            iib_from_file = iib_data_from_file.split("iib:")[-1]
                            if iib_from_file < iib_from_url:
                                _operator_data["iib"] = index_image
                                _operator_data["triggered"] = True
                                new_trigger_data = True

                        else:
                            _operator_data["iib"] = index_image
                            _operator_data["triggered"] = True
                            new_trigger_data = True

            logger.info(f"Done parsing new IIB data for {_jobs_data}")

    if new_trigger_data:
        logger.info(f"New IIB data found: {new_data}\nOld IIB data: {data_from_file}")
        with open(OPERATORS_DATA_FILE, "w") as fd:
            fd.write(json.dumps(new_data))

    return new_data


def clone_repo(repo_url):
    shutil.rmtree(path=LOCAL_REPO_PATH, ignore_errors=True)
    Repo.clone_from(url=repo_url, to_path=LOCAL_REPO_PATH)


@contextmanager
def change_directory(directory, logger):
    logger.info(f"Changing directory to {directory}")
    old_cwd = os.getcwd()
    yield os.chdir(directory)
    logger.info(f"Changing back to directory {old_cwd}")
    os.chdir(old_cwd)


def push_changes(repo_url, slack_webhook_url, logger):
    logger.info(f"Check if {OPERATORS_DATA_FILE} was changed")
    with change_directory(directory=LOCAL_REPO_PATH, logger=logger):
        try:
            _git_repo = Repo(LOCAL_REPO_PATH)
            _git_repo.git.config("user.email", "ci-jobs-trigger@local")
            _git_repo.git.config("user.name", "ci-jobs-trigger")
            os.system("pre-commit install")

            if OPERATORS_DATA_FILE_NAME in _git_repo.git.status():
                logger.info(f"Found changes for {OPERATORS_DATA_FILE_NAME}, pushing new changes")
                logger.info(f"Run pre-commit on {OPERATORS_DATA_FILE_NAME}")
                os.system(f"pre-commit run --files {OPERATORS_DATA_FILE_NAME}")
                logger.info(f"Adding {OPERATORS_DATA_FILE_NAME} to git")
                _git_repo.git.add(OPERATORS_DATA_FILE_NAME)
                logger.info(f"Committing changes for {OPERATORS_DATA_FILE_NAME}")
                _git_repo.git.commit("-m", f"'Auto update: {OPERATORS_DATA_FILE_NAME}'")
                logger.info(f"Push new changes for {OPERATORS_DATA_FILE}")
                _git_repo.git.push(repo_url)
                logger.info(f"New changes for {OPERATORS_DATA_FILE_NAME} pushed")
        except Exception as ex:
            err_msg = f"Failed to update {OPERATORS_DATA_FILE_NAME}. {ex}"
            logger.error(err_msg)
            send_slack_message(message=err_msg, webhook_url=slack_webhook_url, logger=logger)

    logger.info(f"Done check if {OPERATORS_DATA_FILE} was changed")


def fetch_update_iib_and_trigger_jobs(logger, config_dict=None):
    logger.info("Check for new operators IIB")
    config_data = get_config(os_environ="CI_IIB_JOBS_TRIGGER_CONFIG", logger=logger, config_dict=config_dict)
    slack_errors_webhook_url = config_data.get("slack_errors_webhook_url")
    token = config_data["github_token"]
    repo_url = f"https://{token}@github.com/RedHatQE/ci-jobs-trigger.git"
    clone_repo(repo_url=repo_url)
    trigger_dict = get_new_iib(operator_config_data=config_data, logger=logger)
    push_changes(repo_url=repo_url, slack_webhook_url=slack_errors_webhook_url, logger=logger)

    failed_triggered_jobs = {}
    for _, _job_data in trigger_dict.items():
        for _job_name, _job_dict in _job_data.items():
            operators = _job_dict["operators"]
            if any([_value["triggered"] for _value in operators.values()]):
                try:
                    trigger_ci_job(
                        job=_job_name,
                        product=", ".join(operators.keys()),
                        _type="operator",
                        trigger_dict=trigger_dict,
                        ci=_job_dict["ci"],
                        logger=logger,
                        config_data=config_data,
                    )
                except AddonsWebhookTriggerError:
                    failed_triggered_jobs.setdefault(_job_dict["ci"], []).append(_job_name)
                    continue
    return failed_triggered_jobs


def run_iib_update(logger):
    slack_errors_webhook_url = None
    while True:
        try:
            failed_triggered_jobs = fetch_update_iib_and_trigger_jobs(logger=logger)
            if failed_triggered_jobs:
                logger.info(f"Failed triggered jobs: {failed_triggered_jobs}")

        except Exception as ex:
            err_msg = f"Fail to run run_iib_update function. {ex}"
            logger.error(err_msg)
            send_slack_message(message=err_msg, webhook_url=slack_errors_webhook_url, logger=logger)

        finally:
            logger.info("Done check for new operators IIB, sleeping for 1 day")
            sleep(DAYS_TO_SECONDS)
