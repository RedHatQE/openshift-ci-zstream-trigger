import json
import os
from multiprocessing import Process

import requests
import yaml


class OpenshiftCiReTriggerError(Exception):
    def __init__(self, log_prefix, msg):
        self.log_prefix = log_prefix
        self.msg = msg

    def __str__(self):
        return f"{self.log_prefix} Openshift CI job re-trigger failed: {self.msg}"


def get_config(os_environ, logger, config_dict=None):
    if config_dict:
        return config_dict

    try:
        with open(os.environ.get(os_environ)) as fd:
            return yaml.safe_load(fd)
    except Exception:
        logger.error(f"Failed to get config from {os_environ}")
        return {}


def send_slack_message(message, webhook_url, logger):
    if webhook_url:
        slack_data = {"text": message}
        logger.info(f"Sending message to slack: {message}")
        response = requests.post(
            webhook_url,
            data=json.dumps(slack_data),
            headers={"Content-Type": "application/json"},
        )
        if response.status_code != 200:
            raise ValueError(
                f"Request to slack returned an error {response.status_code} with the following message: {response.text}"
            )


def run_in_process(targets):
    for target, _kwargs in targets.items():
        proc = Process(target=target, kwargs=_kwargs)
        proc.start()


def process_webhook_exception(logger, ex, route, slack_errors_webhook_url=None):
    err_msg = f"{route}: Failed to process hook{f': {ex}' if ex else ''}"
    logger.error(err_msg)

    if not isinstance(ex, OpenshiftCiReTriggerError):
        send_slack_message(message=err_msg, webhook_url=slack_errors_webhook_url, logger=logger)

    return "Process failed"
