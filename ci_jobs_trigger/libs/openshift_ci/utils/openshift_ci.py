import requests

from ci_jobs_trigger.libs.openshift_ci.utils.constants import AUTHORIZATION_HEADER, GANGWAY_API_URL


def trigger_job(job_name, trigger_token):
    return requests.post(
        url=f"{GANGWAY_API_URL}/{job_name}",
        headers=AUTHORIZATION_HEADER.fomat(trigger_token=trigger_token),
        json={"job_execution_type": "1"},
    )
