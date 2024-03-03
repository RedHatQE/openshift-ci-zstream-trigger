import json

from ci_jobs_trigger.libs.openshift_ci.utils.constants import GANGWAY_API_URL
from ci_jobs_trigger.libs.openshift_ci.utils.openshift_ci import trigger_job as trigger_job_openshift
from ci_jobs_trigger.libs.jenkins.utils.jenkins import trigger_job as trigger_job_jenkins
from ci_jobs_trigger.utils.general import send_slack_message, AddonsWebhookTriggerError


def dict_to_str(_dict):
    dict_str = ""
    for key, value in _dict.items():
        dict_str += f"{key}: {value}\n\t\t"
    return dict_str


def operators_triggered_for_slack(job_dict):
    res = ""
    for vals in job_dict.values():
        for operator, data in vals["operators"].items():
            if not isinstance(data, dict):
                continue

            if data.get("triggered"):
                res += f"{operator}: {data.get('iib')}\n\t"

    return res


def trigger_ci_job(
    job,
    product,
    _type,
    ci,
    logger,
    config_data,
    trigger_dict=None,
):
    logger.info(f"Triggering openshift-ci job for {product} [{_type}]: {job}")
    job_dict = trigger_dict[[*trigger_dict][0]] if trigger_dict else None
    openshift_ci = ci == "openshift-ci"
    jenkins_ci = ci == "jenkins"

    if openshift_ci:
        out = trigger_job_openshift(job_name=job, trigger_token=config_data["trigger_token"])
        rc, res = out.ok, json.loads(out.text)

    elif jenkins_ci:
        rc, res = trigger_job_jenkins(job=job, config_data=config_data)

    else:
        raise ValueError(f"Unknown ci: {ci}")

    if not rc:
        msg = f"Failed to trigger {ci} job: {job} for addon {product}, "
        logger.error(msg)
        send_slack_message(
            message=msg,
            webhook_url=config_data.get("slack_errors_webhook_url"),
            logger=logger,
        )
        raise AddonsWebhookTriggerError(msg=msg)

    if openshift_ci:
        response = {dict_to_str(_dict=res)}
        status_info_command = f"""
curl -X GET -d -H "Authorization: Bearer $OPENSHIFT_CI_TOKEN" {GANGWAY_API_URL}/{res['id']}
"""

    elif jenkins_ci:
        response = ""
        status_info_command = res.url

    message = f"""
```
{ci}: New product {product} [{_type}] was merged/updated.
triggering job {job}
response:
    {response}


Get the status of the job run:
{status_info_command}

"""
    if job_dict:
        message += f"""

Triggered using data:
    {operators_triggered_for_slack(job_dict=job_dict)}
```

"""
    send_slack_message(
        message=message,
        webhook_url=config_data.get("slack_webhook_url"),
        logger=logger,
    )
    return res
