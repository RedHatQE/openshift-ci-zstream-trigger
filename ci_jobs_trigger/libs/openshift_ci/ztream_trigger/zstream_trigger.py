import json
import time

from ocp_utilities.cluster_versions import get_accepted_cluster_versions
from semver import Version
import packaging.version

from ci_jobs_trigger.utils.constant import DAYS_TO_SECONDS
from ci_jobs_trigger.utils.general import get_config, send_slack_message
from ci_jobs_trigger.libs.openshift_ci.utils.general import openshift_ci_trigger_job

OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR = "OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG"
LOG_PREFIX = "Zstream trigger:"


def processed_versions_file(processed_versions_file_path, logger):
    try:
        with open(processed_versions_file_path) as fd:
            return json.load(fd)
    except Exception as exp:
        logger.error(
            f"{LOG_PREFIX} Failed to load processed versions file: {processed_versions_file_path}. error: {exp}"
        )
        return {}


def update_processed_version(base_version, version, processed_versions_file_path, logger):
    processed_versions_file_content = processed_versions_file(
        processed_versions_file_path=processed_versions_file_path, logger=logger
    )
    processed_versions_file_content.setdefault(base_version, []).append(version)
    processed_versions_file_content[base_version].sort(key=packaging.version.Version, reverse=True)
    processed_versions_file_content[base_version] = list(set(processed_versions_file_content[base_version]))
    with open(processed_versions_file_path, "w") as fd:
        json.dump(processed_versions_file_content, fd)


def already_processed_version(base_version, new_version, processed_versions_file_path, logger):
    if all_versions := processed_versions_file(
        processed_versions_file_path=processed_versions_file_path, logger=logger
    ).get(base_version):
        return Version.parse(new_version) <= Version.parse(all_versions[0])
    return False


def trigger_jobs(config, jobs, logger):
    failed_triggers_jobs = []
    successful_triggers_jobs = []
    for job in jobs:
        res = openshift_ci_trigger_job(job_name=job, trigger_token=config["trigger_token"])

        if res.ok:
            successful_triggers_jobs.append(job)
        else:
            failed_triggers_jobs.append(job)

    if successful_triggers_jobs:
        success_msg = f"Triggered {len(successful_triggers_jobs)} jobs: {successful_triggers_jobs}"
        logger.info(f"{LOG_PREFIX} {success_msg}")
        send_slack_message(
            message=success_msg,
            webhook_url=config.get("slack_webhook_url"),
            logger=logger,
        )
        return True

    if failed_triggers_jobs:
        err_msg = f"Failed to trigger {len(failed_triggers_jobs)} jobs: {failed_triggers_jobs}"
        logger.info(f"{LOG_PREFIX} {err_msg}")
        send_slack_message(
            message=err_msg,
            webhook_url=config.get("slack_errors_webhook_url"),
            logger=logger,
        )
        return False


def process_and_trigger_jobs(logger, version=None, config_dict=None):
    config = get_config(
        os_environ=OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR,
        logger=logger,
        config_dict=config_dict,
    )
    if not config:
        logger.error(f"{LOG_PREFIX} Could not get config.")
        return False

    stable_versions = get_accepted_cluster_versions()["stable"]
    if (versions_from_config := config.get("versions")) is None:
        logger.error(f"{LOG_PREFIX} No versions found in config.yaml")
        return False

    if version:
        version_from_config = versions_from_config.get(version)
        if not version_from_config:
            raise ValueError(f"Version {version} not found in config.yaml")

        logger.info(f"{LOG_PREFIX} Triggering all jobs from config file under version {version}")
        return trigger_jobs(config=config, jobs=versions_from_config[version], logger=logger)

    else:
        _processed_versions_file_path = config["processed_versions_file_path"]
        for version, jobs in versions_from_config.items():
            if not jobs:
                slack_error_url = config.get("slack_webhook_error_url")
                logger.error(f"{LOG_PREFIX} No jobs found for version {version}")
                if slack_error_url:
                    send_slack_message(
                        message=f"ZSTREAM-TRIGGER: No jobs found for version {version}",
                        webhook_url=slack_error_url,
                        logger=logger,
                    )
                continue

            version_str = str(version)
            _latest_version = stable_versions[version_str][0]
            if already_processed_version(
                base_version=version,
                new_version=_latest_version,
                processed_versions_file_path=_processed_versions_file_path,
                logger=logger,
            ):
                logger.info(f"{LOG_PREFIX} Version {version_str} already processed, skipping")
                continue

            logger.info(f"{LOG_PREFIX} New Z-stream version {_latest_version} found, triggering jobs: {jobs}")
            if trigger_jobs(config=config, jobs=jobs, logger=logger):
                update_processed_version(
                    base_version=version_str,
                    version=str(_latest_version),
                    processed_versions_file_path=_processed_versions_file_path,
                    logger=logger,
                )
                return True

        return False


def monitor_and_trigger(logger):
    while True:
        try:
            process_and_trigger_jobs(logger=logger)
            logger.info(f"{LOG_PREFIX} Sleeping for {int(DAYS_TO_SECONDS / 3600)} hours")
            time.sleep(DAYS_TO_SECONDS)

        except Exception as ex:
            logger.warning(f"{LOG_PREFIX} Error: {ex}")
            time.sleep(DAYS_TO_SECONDS)
