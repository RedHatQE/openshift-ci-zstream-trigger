import hashlib
import json
import time
from urllib.request import urlopen, Request

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
        if not res.ok:
            failed_triggers_jobs.append(job)
        else:
            successful_triggers_jobs.append(job)

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

    return bool(failed_triggers_jobs)


def process_and_trigger_jobs(logger, version=None):
    stable_versions = get_accepted_cluster_versions()["stable"]
    config = get_config(os_environ=OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR)

    versions_from_config = config["versions"]
    if version:
        version_from_config = versions_from_config.get(version)
        if not version_from_config:
            raise ValueError(f"Version {version} not found in config.yaml")

        logger.info(f"Triggering all jobs from config file under version {version}")
        trigger_jobs(config=config, jobs=versions_from_config[version], logger=logger)

    else:
        for version, jobs in versions_from_config.items():
            version_str = str(version)
            _version = stable_versions[version_str][0]
            if already_processed_version(base_version=version, version=_version):
                continue

            logger.info(f"New Z-stream version {_version} found, triggering jobs: {jobs}")
            if trigger_jobs(config=config, jobs=jobs, logger=logger):
                update_processed_version(base_version=version_str, version=str(_version))


def monitor_and_trigger(logger):
    url = Request("https://openshift-release.apps.ci.l2s4.p1.openshiftapps.com", headers={"User-Agent": "Mozilla/5.0"})
    logger.info("Website monitoring started!")
    time.sleep(10)
    while True:
        try:
            response = urlopen(url).read()
            current_hash = hashlib.sha224(response).hexdigest()
            time.sleep(30)
            response = urlopen(url).read()
            new_hash = hashlib.sha224(response).hexdigest()

            if new_hash == current_hash:
                continue

            logger.info("Website changed!")
            process_and_trigger_jobs(logger=logger)
            time.sleep(30)
            continue

        except Exception as ex:
            logger.warnning(f"Error: {ex}")
