import pytest
import requests
from simple_logger.logger import get_logger

from ci_jobs_trigger.libs.operators_iib_trigger.iib_trigger import fetch_update_iib_and_trigger_jobs

LOGGER = get_logger("test_operators_iib_trigger")


class MockRequest:
    @staticmethod
    def json():
        return {
            "raw_messages": [
                {
                    "msg": {
                        "index": {
                            "ocp_version": "4.15",
                            "index_image": "iib:quay.io/index-image",
                        }
                    }
                }
            ]
        }


@pytest.fixture()
def config_dict(tmp_path_factory):
    return {
        "trigger_token": "token",
        "github_token": "token",
        "jenkins_token": "token",
        "jenkins_username": "user",
        "jenkins_url": "https://jenkins",
        "ci_jobs": {
            "v4.15": {
                "jobs": [
                    {
                        "name": "openshift-ci-job-name",
                        "ci": "openshift-ci",
                        "products": {
                            "product": "operator",
                        },
                    }
                ],
                "v4.15": {
                    "jobs": [
                        {
                            "name": "jenkins-job-name",
                            "ci": "jenkins",
                            "products": {
                                "product": "operator",
                            },
                        }
                    ]
                },
            }
        },
    }


def test_fetch_update_iib_and_trigger_jobs(mocker, config_dict):
    mocker.patch.object(requests, "get", return_value=MockRequest())
    mocker.patch("ci_jobs_trigger.libs.operators_iib_trigger.iib_trigger.push_changes", return_value=True)

    fetch_update_iib_and_trigger_jobs(config_dict=config_dict, logger=LOGGER)
