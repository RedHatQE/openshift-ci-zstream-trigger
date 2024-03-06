import os

import jenkins
from timeout_sampler import TimeoutExpiredError, TimeoutSampler


def jenkins_trigger_job(job, config_data, logger, operator_iib=False):
    os.environ["PYTHONHTTPSVERIFY"] = "0"

    api = jenkins.Jenkins(
        url=config_data["jenkins_url"],
        username=config_data["jenkins_username"],
        password=config_data["jenkins_token"],
    )

    if not api.job_exists(name=job):
        logger.error(f"Jenkins job {job} not found.")
        return False, None

    try:
        last_build_number = api.get_job_info(job)["lastBuild"]["number"]
    except TypeError:
        last_build_number = 0

    api.build_job(name=job, parameters=set_job_params(api=api, job=job, operator_iib=operator_iib))

    return wait_for_job_in_jenkins(api=api, job=job, last_build_number=last_build_number, logger=logger)


def set_job_params(api, job, operator_iib):
    job_params = {}
    install_from_iib_job_param_str = "INSTALL_FROM_IIB"

    for _property in api.get_job_info(name=job)["property"]:
        for param in _property.get("parameterDefinitions", []):
            if operator_iib and param["name"] == install_from_iib_job_param_str:
                job_params[install_from_iib_job_param_str] = True
                continue

            job_params[param["defaultParameterValue"]["name"]] = param["defaultParameterValue"]["value"]

    return job_params


def wait_for_job_in_jenkins(api, job, last_build_number, logger):
    for job_info in TimeoutSampler(
        wait_timeout=3,
        sleep=1,
        func=api.get_job_info,
        name=job,
    ):
        try:
            if (job_info_last_build := job_info["lastBuild"]) and job_info_last_build["number"] > last_build_number:
                return True, job_info_last_build

        except TimeoutExpiredError:
            logger.error(f"Jenkins job {job} new build not triggered.")
            return False, None
