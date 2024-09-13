import json
import os
from multiprocessing import Process

import requests
import gitlab
from pyaml_env import parse_config


class AddonsWebhookTriggerError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f"Addons webhook trigger failed: {self.msg}"


class OpenshiftCiReTriggerError(Exception):
    def __init__(self, log_prefix, msg):
        self.log_prefix = log_prefix
        self.msg = msg

    def __str__(self):
        return f"{self.log_prefix} Openshift CI job re-trigger failed: {self.msg}"


def get_config(os_environ, logger):
    try:
        return parse_config(path=os.environ.get(os_environ), default_value="")
    except Exception as ex:
        logger.error(f"Failed to get config from {os_environ}. error: {ex}")
        return {}


def send_slack_message(message, webhook_url, logger):
    try:
        if webhook_url:
            slack_data = {"text": message}
            logger.info(f"Sending message to slack: {message}")
            response = requests.post(
                webhook_url,
                data=json.dumps(slack_data),
                headers={"Content-Type": "application/json"},
            )
            if response.status_code != 200:
                logger.error(
                    f"Request to slack returned an error {response.status_code} with the following message: {response.text}"
                )
    except Exception as ex:
        logger.error(f"Failed to send slack message. error: {ex}")


def run_in_process(targets):
    for target, _kwargs in targets.items():
        proc = Process(target=target, kwargs=_kwargs)
        proc.start()


def process_webhook_exception(logger, ex, route, slack_errors_webhook_url=None):
    err_msg = f"{route}: Failed to process hook{f': {ex}' if ex else ''}"
    logger.error(err_msg)

    if not isinstance(ex, OpenshiftCiReTriggerError) or not isinstance(ex, AddonsWebhookTriggerError):
        send_slack_message(message=err_msg, webhook_url=slack_errors_webhook_url, logger=logger)

    return "Process failed"


def get_gitlab_api(url, token):
    gitlab_api = gitlab.Gitlab(url=url, private_token=token, ssl_verify=False)
    gitlab_api.auth()
    return gitlab_api
