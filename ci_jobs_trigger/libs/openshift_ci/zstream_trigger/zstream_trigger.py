from __future__ import annotations
import json
import logging
import time
import datetime
import yaml

from croniter import CroniterBadCronError, croniter
from pyhelper_utils.general import stt, tts
from typing import Dict, List

from ocp_utilities.cluster_versions import get_accepted_cluster_versions
from ocm_python_wrapper.ocm_client import OCMPythonClient
from semver import Version
import packaging.version

from ci_jobs_trigger.utils.constant import DAYS_TO_SECONDS
from ci_jobs_trigger.utils.general import get_config, get_gitlab_api, send_slack_message
from ci_jobs_trigger.libs.openshift_ci.utils.general import openshift_ci_trigger_job
from ci_jobs_trigger.libs.openshift_ci.zstream_trigger.rosa_utils import get_rosa_versions


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


def is_rosa_version_enabed(config: Dict, version: str, channel: str, ocm_env: str, logger: logging.Logger) -> bool:
    processed_versions_file_path = config["processed_versions_file_path"]
    processed_versions_file_content = processed_versions_file(
        processed_versions_file_path=processed_versions_file_path, logger=logger
    )
    channel_version = f"{channel}-{version}"
    enable_channel_version_key = f"{channel_version}-{ocm_env}-enable"
    if processed_versions_file_content.get(enable_channel_version_key):
        return True

    api = get_gitlab_api(url=config["gitlab_url"], token=config["gitlab_token"])
    project = api.projects.get(config["gitlab_project"])
    project_file_content = project.files.get(file_path=f"config/{'prod' if ocm_env=='production' else ocm_env}.yaml", ref="master")
    file_yaml_content = yaml.safe_load(project_file_content.decode().decode('utf-8'))
    for channel_groups in file_yaml_content.get("channel_groups", []):
        if channel_version in channel_groups.get("channels", []):
            processed_versions_file_content[enable_channel_version_key] = True
            with open(processed_versions_file_path, "w") as fd:
                json.dump(processed_versions_file_content, fd)
            return True

    return False



def get_all_rosa_versions(ocm_token: str, ocm_env: str, channel:str, aws_region: str) -> Dict[str, Dict[str, List[str]]]:
    ocm_client = OCMPythonClient(
        token=ocm_token,
        endpoint="https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token",
        api_host=ocm_env,
        discard_unknown_keys=True,
        ).client
    return get_rosa_versions(ocm_client=ocm_client, aws_region=aws_region, channel_group=channel)


def trigger_jobs(config: Dict, jobs: List, logger: logging.Logger, zstream_version: str) -> bool:
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
            success_msg: str = f"Triggered {len(successful_triggers_jobs)} jobs: {successful_triggers_jobs} for version {zstream_version}"
            logger.info(f"{LOG_PREFIX} {success_msg}")
            send_slack_message(
                message=success_msg,
                webhook_url=config.get("slack_webhook_url"),
                logger=logger,
            )
            return True

        if failed_triggers_jobs:
            err_msg: str = f"Failed to trigger {len(failed_triggers_jobs)} jobs: {failed_triggers_jobs} for version {zstream_version}"
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
        triggered = trigger_jobs(
            config=config, jobs=versions_from_config[version], logger=logger, zstream_version=version
        )
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

            _rosa_env: str = ""
            if "___" in _version:
                _version, _rosa_env = _version.split("___")[:2]

            if "-" in _version:
                _wanted_version, _version_channel = _version.split("-")
                _version_channel = "candidate" if _rosa_env and _version_channel in ['rc', 'ec'] else _version_channel
            else:
                _wanted_version = _version
                _version_channel = "stable"

            _base_version = f"{_version}-{_rosa_env}" if _rosa_env else _version

            if _rosa_env and config.get("gitlab_project"):
                if not is_rosa_version_enabed(config=config, version=_wanted_version, channel=_version_channel, ocm_env=_rosa_env, logger=logger):
                    logger.info(
                        f"{LOG_PREFIX} Version {_wanted_version}:{_version_channel} not enabled for ROSA {_rosa_env}, skipping")
                    trigger_res[_base_version] = "Not enabled for ROsA"
                    continue

            _all_versions = get_all_rosa_versions(ocm_env=_rosa_env, ocm_token=config["ocm_token"], channel=_version_channel, aws_region=config["aws_region"]) if _rosa_env else get_accepted_cluster_versions()
            _latest_version = _all_versions.get(_version_channel)[_wanted_version][0]
            if already_processed_version(
                base_version=_base_version,
                new_version=_latest_version,
                processed_versions_file_path=_processed_versions_file_path,
                logger=logger,
            ):
                logger.info(f"{LOG_PREFIX} Version {_wanted_version}:{_version_channel} already processed, skipping")
                trigger_res[_base_version] = "Already processed"
                continue

            logger.info(
                f"{LOG_PREFIX} New Z-stream version {_latest_version}:{_version_channel} found, triggering jobs: {_jobs}"
            )
            if trigger_jobs(config=config, jobs=_jobs, logger=logger, zstream_version=_latest_version):
                update_processed_version(
                    base_version=_base_version,
                    version=str(_latest_version),
                    processed_versions_file_path=_processed_versions_file_path,
                    logger=logger,
                )
                trigger_res[_base_version] = "Triggered"
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
