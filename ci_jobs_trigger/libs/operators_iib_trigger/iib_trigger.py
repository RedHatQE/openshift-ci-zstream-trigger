import copy
import json
import os
from json import JSONDecodeError
from time import sleep

import requests

from ci_jobs_trigger.libs.utils.general import trigger_ci_job
from ci_jobs_trigger.utils.constant import DAYS_TO_SECONDS
from ci_jobs_trigger.utils.general import (
    send_slack_message,
    get_config,
    AddonsWebhookTriggerError,
)
from clouds.aws.session_clients import s3_client

LOG_PREFIX = "iib-trigger:"


def get_operator_data_from_url(operator_name, ocp_version, logger):
    logger.info(f"{LOG_PREFIX} Getting IIB data for {operator_name}")
    datagrepper_query_url = (
        "https://datagrepper.engineering.redhat.com/raw?topic=/topic/"
        "VirtualTopic.eng.ci.redhat-container-image.index.built"
    )

    res = requests.get(
        f"{datagrepper_query_url}&contains={operator_name}",
        verify=False,
    )
    logger.info(f"{LOG_PREFIX} Done getting IIB data for {operator_name}")
    json_res = res.json()
    for raw_msg in json_res["raw_messages"]:
        _index = raw_msg["msg"]["index"]
        if _index["ocp_version"] == ocp_version:
            yield _index


def upload_download_s3_bucket_file(
    action,
    filename,
    s3_bucket_file_full_path,
    region,
    logger,
    slack_errors_webhook_url,
    boto_s3_client=None,
):
    supported_actions = ("upload", "download")
    if action not in supported_actions:
        raise ValueError(f"{LOG_PREFIX} Invalid action: {action}. Supported actions: {supported_actions}")

    try:
        bucket, key = s3_bucket_file_full_path.split("/", 1)

    except ValueError:
        error_msg = (
            f"{LOG_PREFIX} Invalid s3_bucket_file_full_path: {s3_bucket_file_full_path}. Must be in format 'bucket/key'"
        )
        logger.error(error_msg)
        send_slack_message(
            message=error_msg,
            webhook_url=slack_errors_webhook_url,
            logger=logger,
        )
        return False

    try:
        client = boto_s3_client or s3_client(region_name=region)

        if action == "upload":
            logger.info(f"{LOG_PREFIX} Uploading IIB file to s3 {s3_bucket_file_full_path}")
            return client.upload_file(Filename=filename, Bucket=bucket, Key=key)

        elif action == "download":
            logger.info(f"{LOG_PREFIX} Downloading IIB file from s3 {s3_bucket_file_full_path}")
            return client.download_file(Bucket=bucket, Key=key, Filename=filename)

    except Exception as ex:
        error_msg = f"{LOG_PREFIX} S3 {action} failed: {ex}"
        logger.error(error_msg)
        send_slack_message(
            message=error_msg,
            webhook_url=slack_errors_webhook_url,
            logger=logger,
        )
        return False


def write_new_data_to_file_and_upload_to_s3(config_data, new_data, logger):
    iib_file = config_data["local_operators_latest_iib_filepath"]

    with open(iib_file, "w") as fd:
        fd.write(json.dumps(new_data))

    if s3_bucket_operators_latest_iib_path := config_data.get("s3_bucket_operators_latest_iib_path"):
        return upload_download_s3_bucket_file(
            action="upload",
            filename=iib_file,
            s3_bucket_file_full_path=s3_bucket_operators_latest_iib_path,
            region=config_data["aws_region"],
            logger=logger,
            slack_errors_webhook_url=config_data.get("slack_errors_webhook_url"),
        )


def get_new_iib(config_data, logger):
    new_trigger_data = False
    data_from_file = get_iib_data_from_file(config_data=config_data)
    new_data = copy.deepcopy(data_from_file)

    for _ocp_version, _jobs_data in config_data.get("ci_jobs", {}).items():
        if _jobs_data:
            for _ci_job in _jobs_data:
                job_name = _ci_job["name"]
                job_products = _ci_job["products"]
                new_data.setdefault(_ocp_version, {}).setdefault(job_name, {})
                new_data[_ocp_version][job_name].setdefault("operators", {})
                new_data[_ocp_version][job_name].setdefault("ci", _ci_job["ci"])
                for _operator, _operator_name in job_products.items():
                    new_data[_ocp_version][job_name]["operators"].setdefault(_operator_name, {})
                    _operator_data = new_data[_ocp_version][job_name]["operators"][_operator_name]
                    _operator_data["new-iib"] = False
                    logger.info(f"{LOG_PREFIX} Parsing new IIB data for {_operator_name}")
                    for data_from_file in get_operator_data_from_url(
                        operator_name=_operator,
                        ocp_version=_ocp_version,
                        logger=logger,
                    ):
                        index_image = data_from_file["index_image"]

                        iib_data_from_file = _operator_data.get("iib")
                        if iib_data_from_file:
                            iib_from_url = data_from_file["index_image"].split("iib:")[-1]
                            iib_from_file = iib_data_from_file.split("iib:")[-1]
                            if iib_from_file < iib_from_url:
                                _operator_data["iib"] = index_image
                                _operator_data["new-iib"] = True
                                new_trigger_data = True

                        else:
                            _operator_data["iib"] = index_image
                            _operator_data["new-iib"] = True
                            new_trigger_data = True

            logger.info(f"{LOG_PREFIX} Done parsing new IIB data for {_jobs_data}")

    if new_trigger_data:
        logger.info(f"{LOG_PREFIX} New IIB data found: {new_data}\nOld IIB data: {data_from_file}")

        write_new_data_to_file_and_upload_to_s3(config_data=config_data, new_data=new_data, logger=logger)

    return new_data


def download_iib_file_from_s3_bucket(
    s3_bucket_operators_latest_iib_path,
    aws_region,
    slack_errors_webhook_url,
    logger,
    target_file_path,
):
    if not aws_region:
        error_msg = f"{LOG_PREFIX} aws_region is required if s3_bucket_operators_latest_iib_path is set"
        logger.error(error_msg)
        send_slack_message(
            message=error_msg,
            webhook_url=slack_errors_webhook_url,
            logger=logger,
        )
        return False

    try:
        upload_download_s3_bucket_file(
            action="download",
            filename=target_file_path,
            s3_bucket_file_full_path=s3_bucket_operators_latest_iib_path,
            region=aws_region,
            logger=logger,
            slack_errors_webhook_url=slack_errors_webhook_url,
        )

        return True

    except Exception as ex:
        error_msg = (
            f"{LOG_PREFIX} Failed to download IIB file from s3_bucket_operators_latest_iib_path: "
            f"{s3_bucket_operators_latest_iib_path}. error: {ex}"
        )
        logger.error(error_msg)
        send_slack_message(
            message=error_msg,
            webhook_url=slack_errors_webhook_url,
            logger=logger,
        )
        return False


def get_iib_data_from_file(config_data):
    try:
        with open(config_data["local_operators_latest_iib_filepath"]) as fd:
            return json.load(fd)

    except (JSONDecodeError, FileNotFoundError):
        return {}


def get_jobs_name_from_config(ci_jobs):
    ci_jobs_name = []
    for _, _jobs_data in ci_jobs.items():
        if _jobs_data:
            for _ci_job in _jobs_data:
                ci_jobs_name.append(_ci_job["name"])

    return ci_jobs_name


def verify_s3_or_local_file(
    s3_bucket_operators_latest_iib_path,
    user_local_operators_latest_iib_filepath,
    slack_errors_webhook_url,
    logger,
):
    if s3_bucket_operators_latest_iib_path and user_local_operators_latest_iib_filepath:
        error_msg = (
            f"{LOG_PREFIX} Cannot set both s3_bucket_operators_latest_iib_path and local_operators_latest_iib_filepath"
        )
        logger.error(error_msg)
        send_slack_message(
            message=error_msg,
            webhook_url=slack_errors_webhook_url,
            logger=logger,
        )
        return False

    return True


def fetch_update_iib_and_trigger_jobs(logger, tmp_dir, config_dict=None):
    logger.info(f"{LOG_PREFIX} Check for new operators IIB")
    config_data = get_config(os_environ="CI_IIB_JOBS_TRIGGER_CONFIG", logger=logger)

    s3_bucket_operators_latest_iib_path = config_data.get("s3_bucket_operators_latest_iib_path")
    user_local_operators_latest_iib_filepath = config_data.get("local_operators_latest_iib_filepath")

    if not verify_s3_or_local_file(
        s3_bucket_operators_latest_iib_path=s3_bucket_operators_latest_iib_path,
        user_local_operators_latest_iib_filepath=user_local_operators_latest_iib_filepath,
        slack_errors_webhook_url=config_data.get("slack_errors_webhook_url"),
        logger=logger,
    ):
        return False

    # When using S3 or running locally with a tmp file
    if not user_local_operators_latest_iib_filepath:
        local_operators_latest_iib_filepath = os.path.join(tmp_dir, "operators_latest_iib.json")
        logger.info(f"{LOG_PREFIX} Created temp dir: {local_operators_latest_iib_filepath}")
        config_data["local_operators_latest_iib_filepath"] = local_operators_latest_iib_filepath

        if s3_bucket_operators_latest_iib_path:
            if not download_iib_file_from_s3_bucket(
                s3_bucket_operators_latest_iib_path=s3_bucket_operators_latest_iib_path,
                aws_region=config_data.get("aws_region"),
                slack_errors_webhook_url=config_data.get("slack_errors_webhook_url"),
                logger=logger,
                target_file_path=local_operators_latest_iib_filepath,
            ):
                return False

    if (ci_jobs := config_data.get("ci_jobs", {})) is None:
        logger.error(f"{LOG_PREFIX} No ci_jobs found in config")
        return {}

    trigger_dict = get_new_iib(config_data=config_data, logger=logger)
    ci_jobs_name = get_jobs_name_from_config(ci_jobs=ci_jobs)

    failed_triggered_jobs = {}
    for _, _job_data in trigger_dict.items():
        for _job_name, _job_dict in _job_data.items():
            if _job_name in ci_jobs_name:
                operators = _job_dict["operators"]
                if any([_value["new-iib"] for _value in operators.values()]):
                    try:
                        trigger_ci_job(
                            job=_job_name,
                            product=", ".join(operators.keys()),
                            _type="operator",
                            trigger_dict=trigger_dict,
                            ci=_job_dict["ci"],
                            logger=logger,
                            config_data=config_data,
                            operator_iib=True,
                        )
                    except AddonsWebhookTriggerError:
                        failed_triggered_jobs.setdefault(_job_dict["ci"], []).append(_job_name)
                        continue
    return failed_triggered_jobs


def run_iib_update(logger, tmp_dir):
    while True:
        try:
            failed_triggered_jobs = fetch_update_iib_and_trigger_jobs(logger=logger, tmp_dir=tmp_dir)
            if failed_triggered_jobs:
                logger.info(f"{LOG_PREFIX} Failed triggered jobs: {failed_triggered_jobs}")

        except Exception as ex:
            err_msg = f"{LOG_PREFIX} Fail to run run_iib_update function. {ex}"
            logger.error(err_msg)
            slack_errors_webhook_url = get_config(os_environ="CI_IIB_JOBS_TRIGGER_CONFIG", logger=logger).get(
                "slack_errors_webhook_url"
            )
            send_slack_message(message=err_msg, webhook_url=slack_errors_webhook_url, logger=logger)

        finally:
            logger.info(f"{LOG_PREFIX} Done check for new operators IIB, sleeping for 1 day")
            sleep(DAYS_TO_SECONDS)
