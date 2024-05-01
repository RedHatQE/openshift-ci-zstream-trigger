from __future__ import annotations
import json
import logging
import time
import datetime

from croniter import CroniterBadCronError, croniter
from pyhelper_utils.general import stt, tts
from typing import Dict, List

from ocp_utilities.cluster_versions import get_accepted_cluster_versions
from semver import Version
import packaging.version

from ci_jobs_trigger.utils.constant import DAYS_TO_SECONDS
from ci_jobs_trigger.utils.general import get_config, send_slack_message
from ci_jobs_trigger.libs.openshift_ci.utils.general import openshift_ci_trigger_job


OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR: str = "OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG"
LOG_PREFIX: str = "Zstream trigger:"


def processed_versions_file(processed_versions_file_path: str, logger: logging.Logger) -> Dict:
    try:
        with open(processed_versions_file_path) as fd:
            return json.load(fd)
    except Exception as exp:
        logger.error(
            f"{LOG_PREFIX} Failed to load processed versions file: {processed_versions_file_path}. error: {exp}"
        )
        return {}


def update_processed_version(
    base_version: str, version: str, processed_versions_file_path: str, logger: logging.Logger
) -> None:
    processed_versions_file_content = processed_versions_file(
        processed_versions_file_path=processed_versions_file_path, logger=logger
    )
    processed_versions_file_content.setdefault(base_version, []).append(version)
    processed_versions_file_content[base_version] = list(set(processed_versions_file_content[base_version]))
    processed_versions_file_content[base_version].sort(key=packaging.version.Version, reverse=True)
    with open(processed_versions_file_path, "w") as fd:
        json.dump(processed_versions_file_content, fd)


def already_processed_version(
    base_version: str, new_version: str, processed_versions_file_path: str, logger: logging.Logger
) -> bool:
    if all_versions := processed_versions_file(
        processed_versions_file_path=processed_versions_file_path, logger=logger
    ).get(base_version):
        return Version.parse(new_version) <= Version.parse(all_versions[0])
    return False


def trigger_jobs(config: Dict, jobs: List, logger: logging.Logger) -> bool:
    failed_triggers_jobs: List = []
    successful_triggers_jobs: List = []
    if not jobs:
        no_jobs_mgs: str = f"{LOG_PREFIX} No jobs to trigger"
        logger.info(no_jobs_mgs)
        send_slack_message(
            message=no_jobs_mgs,
            webhook_url=config.get("slack_errors_webhook_url"),
            logger=logger,
        )
        return False

    else:
        for job in jobs:
            res = openshift_ci_trigger_job(job_name=job, trigger_token=config["trigger_token"])

            if res.ok:
                successful_triggers_jobs.append(job)
            else:
                failed_triggers_jobs.append(job)

        if successful_triggers_jobs:
            success_msg: str = f"Triggered {len(successful_triggers_jobs)} jobs: {successful_triggers_jobs}"
            logger.info(f"{LOG_PREFIX} {success_msg}")
            send_slack_message(
                message=success_msg,
                webhook_url=config.get("slack_webhook_url"),
                logger=logger,
            )
            return True

        if failed_triggers_jobs:
            err_msg: str = f"Failed to trigger {len(failed_triggers_jobs)} jobs: {failed_triggers_jobs}"
            logger.info(f"{LOG_PREFIX} {err_msg}")
            send_slack_message(
                message=err_msg,
                webhook_url=config.get("slack_errors_webhook_url"),
                logger=logger,
            )
            return False

    return False


def process_and_trigger_jobs(logger: logging.Logger, version: str | None = None) -> Dict:
    trigger_res: Dict = {}
    config = get_config(
        os_environ=OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR,
        logger=logger,
    )
    if not config:
        logger.error(f"{LOG_PREFIX} Could not get config.")
        return trigger_res

    if not (versions_from_config := config.get("versions")):
        logger.error(f"{LOG_PREFIX} No versions found in config.yaml")
        return trigger_res

    if version:
        version_from_config = versions_from_config.get(version)
        if not version_from_config:
            raise ValueError(f"Version {version} not found in config.yaml")

        logger.info(f"{LOG_PREFIX} Triggering all jobs from config file under version {version}")
        triggered = trigger_jobs(config=config, jobs=versions_from_config[version], logger=logger)
        trigger_res[version] = triggered
        return trigger_res

    else:
        _processed_versions_file_path = config["processed_versions_file_path"]
        for _version, _jobs in versions_from_config.items():
            if not _jobs:
                slack_error_url = config.get("slack_webhook_error_url")
                logger.error(f"{LOG_PREFIX} No jobs found for version {_version}")
                if slack_error_url:
                    send_slack_message(
                        message=f"ZSTREAM-TRIGGER: No jobs found for version {_version}",
                        webhook_url=slack_error_url,
                        logger=logger,
                    )
                trigger_res[_version] = "No jobs found"
                continue

            if "-" in _version:
                _wanted_version, _version_channel = _version.split("-")
            else:
                _wanted_version = _version
                _version_channel = "stable"

            _all_versions = get_accepted_cluster_versions()
            _latest_version = _all_versions.get(_version_channel)[_wanted_version][0]
            if already_processed_version(
                base_version=_version,
                new_version=_latest_version,
                processed_versions_file_path=_processed_versions_file_path,
                logger=logger,
            ):
                logger.info(f"{LOG_PREFIX} Version {_wanted_version} already processed, skipping")
                trigger_res[_version] = "Already processed"
                continue

            logger.info(f"{LOG_PREFIX} New Z-stream version {_latest_version} found, triggering jobs: {_jobs}")
            if trigger_jobs(config=config, jobs=_jobs, logger=logger):
                update_processed_version(
                    base_version=_wanted_version,
                    version=str(_latest_version),
                    processed_versions_file_path=_processed_versions_file_path,
                    logger=logger,
                )
                trigger_res[_version] = "Triggered"
                continue

        return trigger_res


def monitor_and_trigger(logger: logging.Logger) -> None:
    cron = None
    run_interval = 0
    _config = get_config(
        os_environ=OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR,
        logger=logger,
    )

    if cron_schedule := _config.get("cron_schedule"):
        cron = get_cron_iter(cron_schedule=cron_schedule, config=_config, logger=logger)
        if not cron:
            return

    else:
        run_interval = tts(ts=_config.get("run_interval", "24h"))

    while True:
        try:
            if cron:
                run_interval = int((cron.get_next(datetime.datetime) - datetime.datetime.now()).total_seconds())

            if run_interval > 0:
                logger.info(f"{LOG_PREFIX} Sleeping for {stt(seconds=run_interval)}...")
                time.sleep(run_interval)

            process_and_trigger_jobs(logger=logger)

        except Exception as ex:
            logger.warning(f"{LOG_PREFIX} Error: {ex}")
            time.sleep(DAYS_TO_SECONDS)


def get_cron_iter(cron_schedule: str, config: Dict, logger: logging.Logger) -> croniter | None:
    try:
        return croniter(cron_schedule, start_time=datetime.datetime.now(), day_or=False)
    except CroniterBadCronError:
        err_msg: str = f"Invalid cron schedule: {cron_schedule}"
        logger.error(f"{LOG_PREFIX} {err_msg}")
        send_slack_message(
            message=err_msg,
            webhook_url=config.get("slack_errors_webhook_url"),
            logger=logger,
        )

        return None
