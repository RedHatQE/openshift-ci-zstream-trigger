import requests

from ci_jobs_trigger.utils.constants import AUTHORIZATION_HEADER


def trigger_job(trigger_url, job_name, trigger_token):
    return requests.post(
        url=f"{trigger_url}/{job_name}",
        headers=AUTHORIZATION_HEADER.fomat(trigger_token=trigger_token),
        json={"job_execution_type": "1"},
    )
