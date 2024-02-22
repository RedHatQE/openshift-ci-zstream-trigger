import json
import xml

import requests
import shortuuid
import xmltodict
import yaml
from timeout_sampler import TimeoutSampler

from ci_jobs_trigger.libs.openshift_ci.re_trigger.job_db import DB
from ci_jobs_trigger.libs.openshift_ci.utils.constants import GANGWAY_API_URL
from ci_jobs_trigger.utils.general import OpenshiftCiReTriggerError, send_slack_message
from ci_jobs_trigger.libs.openshift_ci.utils.openshift_ci import (
    get_authorization_header,
    trigger_job,
)


class JobTriggering:
    def __init__(self, hook_data, logger):
        self.logger = logger

        self.log_prefix = f"[{shortuuid.random(length=10)}]"
        self.hook_data = hook_data
        self.trigger_token = self.hook_data.get("trigger_token")
        self.trigger_url = GANGWAY_API_URL
        self.build_id = self.hook_data.get("build_id")
        self.job_name = self.hook_data.get("job_name")
        self.prow_job_id = self.hook_data.get("prow_job_id")
        self.slack_webhook_url = self.hook_data.get("slack_webhook_url")
        self.slack_errors_webhook_url = self.hook_data.get("slack_errors_webhook_url")
        self.verify_hook_data()

        self.slack_msg_prefix = self.generate_slack_msg_prefix()

        self.logger.info(
            f"{self.log_prefix} Start processing flow for Job {self.job_name}|build {self.build_id}|prow {self.prow_job_id}"
        )

    def verify_hook_data(self):
        if not self.trigger_token:
            self.logger.error(f"{self.log_prefix} openshift ci token is mandatory.")

        if not self.job_name:
            self.logger.error(f"{self.log_prefix} openshift ci job name is mandatory.")

        if not self.build_id:
            self.logger.error(f"{self.log_prefix} openshift ci build id is mandatory.")

        if not self.prow_job_id:
            self.logger.error(f"{self.log_prefix} openshift ci prow job id is mandatory.")

        if not all((self.trigger_token, self.job_name, self.build_id, self.prow_job_id)):
            raise ValueError(f"{self.log_prefix} Missing parameters")

    def execute_trigger(self, job_db_path=None):
        with DB(job_db_path=job_db_path) as database:
            if database.check_prow_job_id_in_db(job_name=self.job_name, prow_job_id=self.prow_job_id):
                self.logger.warning(f"{self.log_prefix} Job was already auto-triggered. Exiting.")
                send_slack_message(
                    message=f"{self.slack_msg_prefix}already auto-triggered, will not re-trigger",
                    webhook_url=self.slack_webhook_url,
                    logger=self.logger,
                )
                return False

        if not self.wait_for_job_completed():
            err_msg = "Timeout waiting for job to complete, not re-triggering"
            send_slack_message(
                message=f"{self.slack_msg_prefix}{err_msg}",
                webhook_url=self.slack_errors_webhook_url,
                logger=self.logger,
            )

            raise OpenshiftCiReTriggerError(log_prefix=self.log_prefix, msg=err_msg)

        tests_dict = self.get_testsuites_testcase_from_junit_operator(
            junit_xml=self.get_tests_from_junit_operator_by_build_id()
        )
        if self.is_build_failed_on_setup(tests_dict=tests_dict):
            prow_job_id = self._trigger_job()
            send_slack_message(
                message=f"{self.slack_msg_prefix}Job failed during `pre phase`, re-triggering job",
                webhook_url=self.slack_webhook_url,
                logger=self.logger,
            )

            with DB(job_db_path=job_db_path) as database:
                database.write(job_name=self.job_name, prow_job_id=prow_job_id)
                self.logger.info(f"{self.log_prefix} Save job data to DB")

        return True

    def get_prow_job_status(self):
        self.logger.info(f"{self.log_prefix}  Get job status.")
        try:
            response = self.get_url_content(
                url=f"{self.trigger_url}/{self.prow_job_id}",
                headers=get_authorization_header(trigger_token=self.trigger_token),
            )

            return yaml.safe_load(response).get("job_status")

        except requests.exceptions.RequestException:
            return ""

    def wait_for_job_completed(self):
        self.logger.info(f"{self.log_prefix} Waiting for build to end.")
        sampler = TimeoutSampler(
            wait_timeout=600,
            sleep=60,
            print_log=False,
            func=self.get_prow_job_status,
        )
        for job_status in sampler:
            if not job_status:
                self.logger.error(f"{self.log_prefix} Prow build not found")
                return False
            if job_status != "PENDING":
                self.logger.info(f"{self.log_prefix} Job ended. Status: {job_status}")
                return True

    def _trigger_job(self):
        self.logger.info(f"{self.log_prefix} Trigger job.")
        response = trigger_job(job_name=self.job_name, trigger_token=self.trigger_token)

        if not response.ok:
            err_msg = f"Failed to get job status: {response.headers.get('grpc-message')}"
            send_slack_message(
                message=err_msg,
                webhook_url=self.slack_errors_webhook_url,
                logger=self.logger,
            )
            raise OpenshiftCiReTriggerError(
                log_prefix={self.log_prefix},
                msg=err_msg,
            )

        prow_job_id = json.loads(response.content.decode())["id"]
        self.logger.info(f"{self.log_prefix} Successfully triggered job.")

        return prow_job_id

    def get_tests_from_junit_operator_by_build_id(self):
        self.logger.info(f"{self.log_prefix} Get tests from junit_operator.xml")
        url = (
            "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/"
            f"{self.job_name}/{self.build_id}/artifacts/junit_operator.xml"
        )
        response = self.get_url_content(url=url)

        try:
            return xmltodict.parse(response)
        except xml.parsers.expat.ExpatError as _:
            self.logger.error(f"{self.log_prefix} Failed to read {url}. Response: {response}")
            raise

    @staticmethod
    def get_testsuites_testcase_from_junit_operator(junit_xml):
        return junit_xml["testsuites"]["testsuite"]["testcase"]

    def is_build_failed_on_setup(self, tests_dict):
        for test in tests_dict:
            if test.get("failure") and test["@name"] == "Run multi-stage test pre phase":
                self.logger.info(f"{self.log_prefix} Job failed during `pre phase`.")
                return True

        self.logger.info(f"{self.log_prefix} Job did not fail during `pre phase` and will not be re-triggered.")
        return False

    def get_url_content(self, **kwargs):
        url = kwargs["url"]
        self.logger.info(f"{self.log_prefix} Get content from {url}")
        response = requests.get(**kwargs)

        response_text = response.text
        if response.ok:
            return response_text

        raise requests.exceptions.RequestException(
            f"Failed to retrieve url {url} on {response_text}. Status {response.status_code}"
        )

    def generate_slack_msg_prefix(self):
        return f"""
Job: {self.job_name}
Build ID: {self.build_id}
Prow ID: {self.prow_job_id}
"""
