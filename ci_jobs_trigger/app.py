from flask import Flask
from flask import request
from simple_logger.logger import get_logger
from flask.logging import default_handler

from ci_jobs_trigger.libs.zstream_trigger import (
    OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR,
    process_and_trigger_jobs,
    monitor_and_trigger,
)
from ci_jobs_trigger.utils.general import get_config, send_slack_message, run_in_process

APP = Flask("ci-jobs-trigger")
APP.logger.removeHandler(default_handler)
APP.logger.addHandler(get_logger(APP.logger.name).handlers[0])


@APP.route("/zstream-trigger", methods=["POST"])
def process_webhook():
    slack_errors_webhook_url = get_config(os_environ=OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR).get(
        "slack_errors_webhook_url"
    )
    try:
        version = request.query_string.decode("utf-8")
        APP.logger.info(f"Processing version: {version}")
        process_and_trigger_jobs(version=version, logger=APP.logger)
        return "Process done"
    except Exception as ex:
        err_msg = f"Failed to process hook: {ex}"
        APP.logger.error(err_msg)
        send_slack_message(message=err_msg, webhook_url=slack_errors_webhook_url, logger=APP.logger)
        return "Process failed"


if __name__ == "__main__":
    run_in_process(target=monitor_and_trigger, kwargs={"logger": APP.logger})
    APP.logger.info(f"Starting {APP.name} app")
    APP.run(port=5000, host="0.0.0.0", use_reloader=False)
