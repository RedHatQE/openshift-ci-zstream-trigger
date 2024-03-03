from flask import Flask
from flask import request
from simple_logger.logger import get_logger
from flask.logging import default_handler

from ci_jobs_trigger.libs.addons_webhook_trigger.addons_webhook_trigger import (
    process_hook,
    ADDONS_WEBHOOK_JOBS_TRIGGER_CONFIG_STR,
)
from ci_jobs_trigger.libs.openshift_ci.re_trigger.re_trigger import JobTriggering
from ci_jobs_trigger.libs.openshift_ci.ztream_trigger.zstream_trigger import (
    OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR,
    monitor_and_trigger,
    process_and_trigger_jobs,
)
from ci_jobs_trigger.libs.operators_iib_trigger.iib_trigger import run_iib_update
from ci_jobs_trigger.utils.general import (
    get_config,
    process_webhook_exception,
    run_in_process,
)

APP = Flask("ci-jobs-trigger")
APP.logger.removeHandler(default_handler)
APP.logger.addHandler(get_logger(APP.logger.name).handlers[0])


@APP.route("/healthcheck")
def healthcheck():
    return "alive"


@APP.route("/openshift-ci-zstream-trigger", methods=["POST"])
def zstream_trigger():
    try:
        version = request.query_string.decode()
        APP.logger.info(f"Processing version: {version}")
        return process_and_trigger_jobs(version=version, logger=APP.logger)
    except Exception as ex:
        return process_webhook_exception(
            logger=APP.logger,
            ex=ex,
            route="openshift-ci-zstream-trigger",
            slack_errors_webhook_url=get_config(
                os_environ=OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR, logger=APP.logger
            ).get("slack_errors_webhook_url"),
        )


@APP.route("/openshift-ci-re-trigger", methods=["POST"])
def openshift_ci_job_re_trigger():
    hook_data = request.json
    try:
        job_triggering = JobTriggering(hook_data=hook_data, logger=APP.logger)
        return job_triggering.execute_trigger()

    except Exception as ex:
        return process_webhook_exception(
            logger=APP.logger,
            ex=ex,
            route="openshift-ci-re-trigger",
            slack_errors_webhook_url=hook_data.get("slack_errors_webhook_url"),
        )


@APP.route("/addons-trigger", methods=["POST"])
def process():
    try:
        hook_data = request.json
        APP.logger.info(f"{hook_data['repository']['name']}: Event type: {hook_data['event_type']}")
        return process_hook(data=hook_data, logger=APP.logger)
    except Exception as ex:
        return process_webhook_exception(
            logger=APP.logger,
            ex=ex,
            route="addons-trigger",
            slack_errors_webhook_url=get_config(
                os_environ=ADDONS_WEBHOOK_JOBS_TRIGGER_CONFIG_STR, logger=APP.logger
            ).get("slack_errors_webhook_url"),
        )


if __name__ == "__main__":
    run_in_process(
        targets={
            monitor_and_trigger: {"logger": APP.logger},
            run_iib_update: {"logger": APP.logger},
        }
    )
    APP.logger.info(f"Starting {APP.name} app")
    APP.run(port=5000, host="0.0.0.0", use_reloader=False)
