import re

import gitlab

from ci_jobs_trigger.libs.utils.general import trigger_ci_job
from ci_jobs_trigger.utils.general import get_config


ADDONS_WEBHOOK_TRIGGER_CONFIG_STR = "ADDONS_WEBHOOK_TRIGGER_CONFIG"


class RepositoryNotFoundError(Exception):
    pass


def get_gitlab_api(url, token):
    gitlab_api = gitlab.Gitlab(url=url, private_token=token, ssl_verify=False)
    gitlab_api.auth()
    return gitlab_api


def repo_data_from_config(repository_name, config_data):
    data = config_data["repositories"].get(repository_name)
    if not data:
        raise RepositoryNotFoundError(f"Repository {repository_name} not found in config file")

    return data


def process_hook(data, logger):
    def _trigger_jobs(
        _addon,
        _ocm_env,
        _repository_data,
        _config_data,
        _logger,
    ):
        _jobs = _repository_data["products_jobs_mapping"][_addon][_ocm_env]
        if not _jobs:
            logger.info(f"{project.name}: No job found for product: {_addon}")
            return

        for _job in _jobs:
            trigger_ci_job(
                job=_job,
                product=_addon,
                _type="addon",
                ci="openshift-ci",
                config_data=_config_data,
                logger=_logger,
            )
        return True

    object_attributes = data["object_attributes"]
    if object_attributes.get("action") == "merge":
        config_data = get_config(os_environ=ADDONS_WEBHOOK_TRIGGER_CONFIG_STR, logger=logger)
        repository_name = data["repository"]["name"]
        repository_data = repo_data_from_config(repository_name=repository_name, config_data=config_data)
        api = get_gitlab_api(url=repository_data["gitlab_url"], token=repository_data["gitlab_token"])
        project = api.projects.get(data["project"]["id"])
        merge_request = project.mergerequests.get(object_attributes["iid"])
        logger.info(f"{project.name}: New merge request [{merge_request.iid}] {merge_request.title}")
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
                )

    return True
