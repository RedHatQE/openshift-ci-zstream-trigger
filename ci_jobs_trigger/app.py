from flask import Flask
from flask import request
from simple_logger.logger import get_logger
from flask.logging import default_handler

from ci_jobs_trigger.libs.openshift_ci_re_trigger.openshift_ci_re_trigger import (
    JobTriggering,
    OPENSHIFT_CI_RE_TRIGGER_CONFIG_OS_ENV_STR,
)
from ci_jobs_trigger.libs.zstream_trigger import (
    OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR,
    process_and_trigger_jobs,
    monitor_and_trigger,
)

from ci_jobs_trigger.utils.general import (
    get_config,
    process_webhook_exception,
    run_in_process,
)

APP = Flask("ci-jobs-trigger")
APP.logger.removeHandler(default_handler)
APP.logger.addHandler(get_logger(APP.logger.name).handlers[0])


@APP.route("/zstream-trigger", methods=["POST"])
def zstream_trigger():
    try:
        version = request.query_string.decode("utf-8")
        APP.logger.info(f"Processing version: {version}")
        process_and_trigger_jobs(version=version, logger=APP.logger)
        return "Process done"
    except Exception as ex:
        process_webhook_exception(
            logger=APP.logger,
            ex=ex,
            slack_errors_webhook_url=get_config(os_environ=OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR).get(
                "slack_errors_webhook_url"
            ),
        )


@APP.route("/openshift_ci_job_re_trigger", methods=["POST"])
def openshift_ci_job_re_trigger():
    try:
        job_triggering = JobTriggering(hook_data=request.json, flask_logger=APP.logger)
        job_triggering.execute_trigger()
        return "Process ended successfully."

    except Exception as ex:
        process_webhook_exception(
            logger=APP.logger,
            ex=ex,
            slack_errors_webhook_url=get_config(os_environ=OPENSHIFT_CI_RE_TRIGGER_CONFIG_OS_ENV_STR).get(
                "slack_errors_webhook_url"
            ),
        )


if __name__ == "__main__":
    run_in_process(targets={monitor_and_trigger: {"logger": APP.logger}})
    APP.logger.info(f"Starting {APP.name} app")
    APP.run(port=5000, host="0.0.0.0", use_reloader=False)
