import json
import os

import requests
import yaml
from flask import Flask
from ocp_utilities.cluster_versions import get_accepted_cluster_versions
from semver import Version
import time
import hashlib
from urllib.request import urlopen, Request
from multiprocessing import Process
from flask import request
from simple_logger.logger import get_logger
from flask.logging import default_handler


APP = Flask("openshift-ci-zstream-trigger")
APP.logger.removeHandler(default_handler)
APP.logger.addHandler(get_logger(APP.logger.name).handlers[0])


def get_config():
    with open(os.environ.get("OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG", "config.yaml")) as fd:
        return yaml.safe_load(fd)


def send_slack_message(message, webhook_url):
    slack_data = {"text": message}
    APP.logger.info(f"Sending message to slack: {message}")
    response = requests.post(
        webhook_url,
        data=json.dumps(slack_data),
        headers={"Content-Type": "application/json"},
    )
    if response.status_code != 200:
        raise ValueError(
            f"Request to slack returned an error {response.status_code} with the following message: {response.text}"
        )


def run_in_process(target):
    proc = Process(target=target)
    proc.start()


def processed_versions_file():
    try:
        with open(get_config()["processed_versions_file_path"]) as fd:
            return json.load(fd)
    except Exception:
        return {}


def update_processed_version(base_version, version):
    processed_versions_file_content = processed_versions_file()
    processed_versions_file_content.setdefault(base_version, []).append(version)
    processed_versions_file_content[base_version] = list(set(processed_versions_file_content[base_version]))
    with open(get_config()["processed_versions_file_path"], "w") as fd:
        json.dump(processed_versions_file_content, fd)


def already_processed_version(base_version, version):
    if base_versions := processed_versions_file().get(base_version):
        return Version(base_versions[0]) <= Version(version)
    return False


def trigger_jobs(config, jobs):
    failed_triggers_jobs = []
    successful_triggers_jobs = []
    trigger_url = config["trigger_url"]
    for job in jobs:
        res = requests.post(
            url=f"{trigger_url}/{job}",
            headers={"Authorization": f"Bearer {config['trigger_token']}"},
            data='{"job_execution_type": "1"}',
        )
        if not res.ok:
            failed_triggers_jobs.append(job)
        else:
            successful_triggers_jobs.append(job)

    if successful_triggers_jobs:
        success_msg = f"Triggered {len(successful_triggers_jobs)} jobs: {successful_triggers_jobs}"
        APP.logger.info(success_msg)
        send_slack_message(message=success_msg, webhook_url=config["slack_webhook_url"])
        return True

    if failed_triggers_jobs:
        err_msg = f"Failed to trigger {len(failed_triggers_jobs)} jobs: {failed_triggers_jobs}"
        APP.logger.info(err_msg)
        send_slack_message(message=err_msg, webhook_url=config["slack_errors_webhook_url"])
        return False

    return bool(failed_triggers_jobs)


def process_and_trigger_jobs(version=None):
    stable_versions = get_accepted_cluster_versions()["stable"]
    config = get_config()

    versions_from_config = config["versions"]
    if version:
        version_from_config = versions_from_config.get(version)
        if not version_from_config:
            raise ValueError(f"Version {version} not found in config.yaml")

        APP.logger.info(f"Triggering all jobs from config file under version {version}")
        trigger_jobs(config=config, jobs=versions_from_config[version])

    else:
        for version, jobs in versions_from_config.items():
            version_str = str(version)
            _version = stable_versions[version_str][0]
            if already_processed_version(base_version=version, version=_version):
                continue

            APP.logger.info(f"New Z-stream version {_version} found, triggering jobs: {jobs}")
            if trigger_jobs(config=config, jobs=jobs):
                update_processed_version(base_version=version_str, version=str(_version))


def monitor_and_trigger():
    url = Request("https://openshift-release.apps.ci.l2s4.p1.openshiftapps.com", headers={"User-Agent": "Mozilla/5.0"})
    APP.logger.info("Website monitoring started!")
    time.sleep(10)
    while True:
        try:
            response = urlopen(url).read()
            current_hash = hashlib.sha224(response).hexdigest()
            time.sleep(30)
            response = urlopen(url).read()
            new_hash = hashlib.sha224(response).hexdigest()

            if new_hash == current_hash:
                continue

            APP.logger.info("Website changed!")
            process_and_trigger_jobs()
            time.sleep(30)
            continue

        except Exception as ex:
            APP.logger.info(f"Error: {ex}")


@APP.route("/process", methods=["POST"])
def process_webhook():
    slack_errors_webhook_url = get_config().get("slack_errors_webhook_url")
    try:
        version = request.query_string.decode("utf-8")
        APP.logger.info(f"Processing version: {version}")
        process_and_trigger_jobs(version=version)
        return "Process done"
    except Exception as ex:
        err_msg = f"Failed to process hook: {ex}"
        APP.logger.error(err_msg)
        send_slack_message(message=err_msg, webhook_url=slack_errors_webhook_url)
        return "Process failed"


if __name__ == "__main__":
    run_in_process(target=monitor_and_trigger)
    APP.logger.info(f"Starting {APP.name} app")
    APP.run(port=5000, host="0.0.0.0", use_reloader=False)
