import re

from ci_jobs_trigger.libs.utils.general import trigger_ci_job
from ci_jobs_trigger.utils.general import get_config, get_gitlab_api, AddonsWebhookTriggerError

ADDONS_WEBHOOK_JOBS_TRIGGER_CONFIG_STR = "ADDONS_WEBHOOK_JOBS_TRIGGER_CONFIG"


class RepositoryNotFoundError(Exception):
    pass


def repo_data_from_config(repository_name, config_data):
    data = config_data["repositories"].get(repository_name)
    if not data:
        raise RepositoryNotFoundError(f"Repository {repository_name} not found in config file")

    return data


def get_merge_request(repository_data, object_attributes, project, logger):
    api = get_gitlab_api(url=repository_data["gitlab_url"], token=repository_data["gitlab_token"])
    project = api.projects.get(project)
    merge_request = project.mergerequests.get(object_attributes["iid"])
    logger.info(f"{project.name}: New merge request [{merge_request.iid}] {merge_request.title}")
    return merge_request


def process_hook(data, logger):
    def _trigger_jobs(
        _addon,
        _ocm_env,
        _repository_data,
        _config_data,
        _logger,
        _project,
    ):
        openshift_ci = "openshift-ci"
        jenkins_ci = "jenkins"
        _openshift_ci_jobs = []
        _jenkins_ci_jobs = []
        openshift_ci_jobs_from_config = _repository_data["products_jobs_mapping"].get(openshift_ci, {})
        jenkins_ci_jobs_from_config = _repository_data["products_jobs_mapping"].get(jenkins_ci, {})

        for key, val in openshift_ci_jobs_from_config.items():
            if key == _addon and [*val][0] == _ocm_env:
                _openshift_ci_jobs.extend(val[_ocm_env])

        for key, val in jenkins_ci_jobs_from_config.items():
            if key == _addon and [*val][0] == _ocm_env:
                _jenkins_ci_jobs.extend(val[_ocm_env])

        if not _openshift_ci_jobs and not _jenkins_ci_jobs:
            logger.info(f"{_project}: No job found for product: {_addon}")
            return False

        failed_triggered_jobs = {}
        for _job in _openshift_ci_jobs:
            try:
                trigger_ci_job(
                    job=_job,
                    product=_addon,
                    _type="addon",
                    ci=openshift_ci,
                    config_data=_config_data,
                    logger=_logger,
                )
            except AddonsWebhookTriggerError:
                failed_triggered_jobs.setdefault(openshift_ci, []).append(_job)
                continue

        for _job in _jenkins_ci_jobs:
            try:
                trigger_ci_job(
                    job=_job,
                    product=_addon,
                    _type="addon",
                    ci=jenkins_ci,
                    config_data=_config_data,
                    logger=_logger,
                )
            except AddonsWebhookTriggerError:
                failed_triggered_jobs.setdefault(jenkins_ci, []).append(_job)
                continue

        return failed_triggered_jobs

    object_attributes = data["object_attributes"]
    if object_attributes.get("action") == "merge":
        config_data = get_config(os_environ=ADDONS_WEBHOOK_JOBS_TRIGGER_CONFIG_STR, logger=logger)
        repository_name = data["repository"]["name"]
        repository_data = repo_data_from_config(repository_name=repository_name, config_data=config_data)
        project = data["project"]["id"]
        merge_request = get_merge_request(
            repository_data=repository_data, object_attributes=object_attributes, project=project, logger=logger
        )

        for change in merge_request.changes().get("changes", []):
            changed_file = change.get("new_path")
            # TODO: Get product version from changed_file and send it to slack
            matches = re.match(
                r"addons/(?P<product>.*)/addonimagesets/(?P<env>production|stage)/.*.yaml",
                changed_file,
            )
            if matches:
                return _trigger_jobs(
                    _addon=matches.group("product"),
                    _ocm_env=matches.group("env"),
                    _repository_data=repository_data,
                    _config_data=config_data,
                    _logger=logger,
                    _project=project,
                )

    return True
