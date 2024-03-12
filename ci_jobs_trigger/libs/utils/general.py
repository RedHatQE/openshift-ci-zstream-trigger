from ci_jobs_trigger.libs.openshift_ci.utils.constants import GANGWAY_API_URL
from ci_jobs_trigger.libs.openshift_ci.utils.general import openshift_ci_trigger_job
from ci_jobs_trigger.libs.jenkins.utils.general import jenkins_trigger_job
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
    operator_iib=False,
):
    openshift_ci_response = None
    logger.info(f"Triggering {ci} job for {product} [{_type}]: {job}")
    job_dict = trigger_dict[[*trigger_dict][0]] if trigger_dict else None
    openshift_ci = ci == "openshift-ci"
    jenkins_ci = ci == "jenkins"

    if openshift_ci:
        openshift_ci_response = openshift_ci_trigger_job(job_name=job, trigger_token=config_data["trigger_token"])
        rc = openshift_ci_response.ok
        res = openshift_ci_response.json() if rc else openshift_ci_response.text

    elif jenkins_ci:
        rc, res = jenkins_trigger_job(job=job, config_data=config_data, logger=logger, operator_iib=operator_iib)

    else:
        raise ValueError(f"Unknown ci: {ci}")

    if not rc:
        msg = f"Failed to trigger {ci} job: {job} for addon {product}, "
        if openshift_ci_response:
            msg += f"response: {openshift_ci_response.headers.get('grpc-message')}"

        logger.error(msg)
        send_slack_message(
            message=msg,
            webhook_url=config_data.get("slack_errors_webhook_url"),
            logger=logger,
        )
        raise AddonsWebhookTriggerError(msg=msg)

    if openshift_ci:
        openshift_ci_response = {dict_to_str(_dict=res)}
        status_info_command = f"""
curl -X GET -d -H "Authorization: Bearer $OPENSHIFT_CI_TOKEN" {GANGWAY_API_URL}/{res["id"]}
"""

    elif jenkins_ci:
        openshift_ci_response = ""
        status_info_command = res["url"]

    message = f"""
```
{ci}: New product {product} [{_type}] was merged/updated.
triggering job {job}
response:
    {openshift_ci_response}


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
