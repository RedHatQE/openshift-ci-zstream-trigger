import requests

from ci_jobs_trigger.libs.openshift_ci.utils.constants import GANGWAY_API_URL


def openshift_ci_trigger_job(job_name, trigger_token):
    return requests.post(
        url=f"{GANGWAY_API_URL}/{job_name}",
        headers=get_authorization_header(trigger_token=trigger_token),
        json={"job_execution_type": "1"},
    )


def get_authorization_header(trigger_token):
    return {"Authorization": f"Bearer {trigger_token}"}
