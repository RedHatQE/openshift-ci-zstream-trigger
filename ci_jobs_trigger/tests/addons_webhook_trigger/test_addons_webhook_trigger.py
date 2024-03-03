import pytest
import requests
from api4jenkins.job import Project
from api4jenkins import Jenkins
from gitlab import Gitlab
from gitlab.v4.objects import ProjectManager, ProjectMergeRequestManager

from simple_logger.logger import get_logger

from ci_jobs_trigger.libs.addons_webhook_trigger.addons_webhook_trigger import process_hook

LOGGER = get_logger("test_addons_webhook_trigger")
#
#
# class MockMergeRequest:
#     @staticmethod
#     def changes():
#         return {"changes": [
#             {
#                 "new_path": "addons/addon/addonimagesets/stage/addon.yaml",
#             }
#         ]
#         }


class MockRequest:
    @property
    def ok(self):
        return True

    @staticmethod
    def json():
        return {"id": 123456}


class MockJenkinsJob:
    @staticmethod
    def get_parameters():
        return []

    @staticmethod
    def build(parameters=None):
        return MockJenkinsBuild()


class MockJenkinsBuild:
    @staticmethod
    def exists():
        return True

    @staticmethod
    def get_build():
        return MockJenkinsBuild()

    @property
    def url(self):
        return "https://test-jenkins-url"


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


def test_process_hook(mocker, webhook_data, config_dict):
    mocker.patch.object(Gitlab, "auth", return_value=True)
    mocker.patch.object(ProjectManager, "get", return_value=MockGitlabProjectManager())
    mocker.patch.object(ProjectMergeRequestManager, "get", return_value=MockProjectMergeRequestManager())

    mocker.patch.object(requests, "post", return_value=MockRequest())
    mocker.patch.object(Jenkins, "get_job", return_value=MockJenkinsJob())
    mocker.patch.object(Project, "build", return_value=MockJenkinsBuild())

    process_hook(data=webhook_data, logger=LOGGER, config_dict=config_dict)
