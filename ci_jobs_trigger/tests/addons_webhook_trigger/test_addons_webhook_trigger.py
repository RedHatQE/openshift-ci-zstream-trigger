import pytest
from gitlab import Gitlab
from gitlab.v4.objects import ProjectManager, ProjectMergeRequestManager

from simple_logger.logger import get_logger

from ci_jobs_trigger.libs.addons_webhook_trigger.addons_webhook_trigger import process_hook

LOGGER = get_logger("test_addons_webhook_trigger")


class MockGitlabProjectManager:
    @property
    def name(self):
        return "managed-tenants"

    @property
    def mergerequests(self):
        return {123456: MockProjectMergeRequestManager()}


class MockProjectMergeRequestManager:
    @property
    def iid(self):
        return "123456"

    @property
    def title(self):
        return "Merge request 123456"

    @staticmethod
    def changes():
        return {
            "changes": [
                {
                    "new_path": "addons/addon/addonimagesets/stage/addon.yaml",
                }
            ]
        }

    @staticmethod
    def get():
        return MockProjectMergeRequestManager()


@pytest.fixture
def webhook_data():
    return {
        "object_attributes": {"action": "merge", "iid": 123456},
        "repository": {"name": "managed-tenants"},
        "project": {"id": 1},
    }


@pytest.fixture()
def config_dict(tmp_path_factory):
    return {
        "trigger_token": "token",
        "jenkins_token": "token",
        "jenkins_username": "user",
        "jenkins_url": "https://jenkins",
        "repositories": {
            "managed-tenants": {
                "name": "service/managed-tenants",
                "gitlab_url": "https://gitlab",
                "gitlab_token": "token",
                "slack_webhook_url": "https://slack",
                "products_jobs_mapping": {
                    "openshift-ci": {
                        "addon": {"stage": ["openshift-ci-job-name"]},
                    },
                    "jenkins": {
                        "addon": {"stage": ["jenkins-job-name"]},
                    },
                },
            }
        },
    }


@pytest.fixture
def get_config_mocker(mocker):
    return mocker.patch("ci_jobs_trigger.libs.addons_webhook_trigger.addons_webhook_trigger.get_config")


def test_process_hook(mocker, functions_mocker, webhook_data, config_dict, get_config_mocker):
    mocker.patch.object(Gitlab, "auth", return_value=True)
    mocker.patch.object(ProjectManager, "get", return_value=MockGitlabProjectManager())
    mocker.patch.object(ProjectMergeRequestManager, "get", return_value=MockProjectMergeRequestManager())
    get_config_mocker.return_value = config_dict

    process_hook(data=webhook_data, logger=LOGGER)
