import json
import time

import requests
from ocp_utilities.cluster_versions import get_accepted_cluster_versions
from semver import Version

from ci_jobs_trigger.utils.general import get_config, send_slack_message

OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR = "OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG"


def processed_versions_file():
    try:
        with open(
            get_config(os_environ=OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR)["processed_versions_file_path"]
        ) as fd:
            return json.load(fd)
    except Exception:
        return {}


def update_processed_version(base_version, version):
    processed_versions_file_content = processed_versions_file()
    processed_versions_file_content.setdefault(base_version, []).append(version)
    processed_versions_file_content[base_version] = list(set(processed_versions_file_content[base_version]))
    with open(
        get_config(os_environ=OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR)["processed_versions_file_path"], "w"
    ) as fd:
        json.dump(processed_versions_file_content, fd)


def already_processed_version(base_version, version):
    if base_versions := processed_versions_file().get(base_version):
        return Version(base_versions[0]) <= Version(version)
    return False


def trigger_jobs(config, jobs, logger):
    failed_triggers_jobs = []
    successful_triggers_jobs = []
    trigger_url = config["trigger_url"]
    for job in jobs:
        res = requests.post(
            url=f"{trigger_url}/{job}",
            headers={"Authorization": f"Bearer {config['trigger_token']}"},
            data='{"job_execution_type": "1"}',
        )
        if res.ok:
            successful_triggers_jobs.append(job)
        else:
            failed_triggers_jobs.append(job)

    if successful_triggers_jobs:
        success_msg = f"Triggered {len(successful_triggers_jobs)} jobs: {successful_triggers_jobs}"
        logger.info(success_msg)
        send_slack_message(message=success_msg, webhook_url=config["slack_webhook_url"], logger=logger)
        return True

    if failed_triggers_jobs:
        err_msg = f"Failed to trigger {len(failed_triggers_jobs)} jobs: {failed_triggers_jobs}"
        logger.info(err_msg)
        send_slack_message(message=err_msg, webhook_url=config["slack_errors_webhook_url"], logger=logger)
        return False


def process_and_trigger_jobs(logger, version=None):
    config = get_config(os_environ=OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR)
    if not config:
        return False

    stable_versions = get_accepted_cluster_versions()["stable"]
    versions_from_config = config["versions"]

    if version:
        version_from_config = versions_from_config.get(version)
        if not version_from_config:
            raise ValueError(f"Version {version} not found in config.yaml")

        logger.info(f"Triggering all jobs from config file under version {version}")
        return trigger_jobs(config=config, jobs=versions_from_config[version], logger=logger)

    else:
        for version, jobs in versions_from_config.items():
            version_str = str(version)
            _latest_version = stable_versions[version_str][0]
            if already_processed_version(base_version=version, version=_latest_version):
                continue

            logger.info(f"New Z-stream version {_latest_version} found, triggering jobs: {jobs}")
            if trigger_jobs(config=config, jobs=jobs, logger=logger):
                update_processed_version(base_version=version_str, version=str(_latest_version))
                return True


def monitor_and_trigger(logger):
    while True:
        try:
            process_and_trigger_jobs(logger=logger)
            time.sleep(60 * 60 * 24)  # 1 day

        except Exception as ex:
            logger.warnning(f"Error: {ex}")
