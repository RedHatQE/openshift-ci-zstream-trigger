import json
import os
from multiprocessing import Process

import requests
import yaml


def get_config(os_environ):
    try:
        with open(os.environ.get(os_environ)) as fd:
            return yaml.safe_load(fd)
    except Exception:
        return {}


def send_slack_message(message, webhook_url, logger):
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
        proc = Process(target=target, **_kwargs)
        proc.start()


def process_webhook_exception(logger, ex, slack_errors_webhook_url=None):
    err_msg = f"Failed to process hook: {ex}"
    logger.error(err_msg)

    if slack_errors_webhook_url:
        send_slack_message(message=err_msg, webhook_url=slack_errors_webhook_url, logger=logger)

    return "Process failed"
