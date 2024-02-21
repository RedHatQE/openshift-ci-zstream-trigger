import json
import os
from multiprocessing import Process

import requests
import yaml


def get_config(os_environ):
    with open(os.environ.get(os_environ, "config.yaml")) as fd:
        return yaml.safe_load(fd)


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


def run_in_process(target, **kwargs):
    proc = Process(target=target, **kwargs)
    proc.start()
