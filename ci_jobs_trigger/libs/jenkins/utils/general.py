from api4jenkins import Jenkins


def jenkins_trigger_job(job, config_data):
    api = Jenkins(
        url=config_data["jenkins_url"],
        auth=(config_data["jenkins_username"], config_data["jenkins_token"]),
        verify=False,
    )
    job = api.get_job(full_name=job)
    if not job:
        return False, None

    job_params = {}
    for param in job.get_parameters():
        job_params[param["defaultParameterValue"]["name"]] = param["defaultParameterValue"]["value"]

    try:
        res = job.build(parameters=job_params)
        build = res.get_build()
        return build.exists(), build
    except Exception:
        return False, None
