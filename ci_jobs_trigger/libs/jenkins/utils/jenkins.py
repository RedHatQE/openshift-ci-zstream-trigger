from api4jenkins import Jenkins


def trigger_job(job, config_data):
    api = Jenkins(
        url=config_data["jenkins_url"],
        auth=(config_data["jenkins_username"], config_data["jenkins_token"]),
        verify=False,
    )
    job = api.get_job(full_name=job)
    job_params = {}
    for param in job.get_parameters():
        job_params[param["defaultParameterValue"]["name"]] = param["defaultParameterValue"]["value"]

    try:
        res = job.build(parameters=job_params)
        return res.get_build().exists(), res.get_build()
    except Exception:
        return False, None
