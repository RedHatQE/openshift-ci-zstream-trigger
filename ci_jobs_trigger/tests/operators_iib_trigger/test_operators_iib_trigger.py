import pytest
import requests
from simple_logger.logger import get_logger

from ci_jobs_trigger.libs.operators_iib_trigger.iib_trigger import (
    fetch_update_iib_and_trigger_jobs,
)

LOGGER = get_logger("test_operators_iib_trigger")


class MockRequestGet:
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
def base_config_dict():
    return {
        "trigger_token": "token",
        "jenkins_token": "token",
        "jenkins_username": "user",
        "jenkins_url": "https://jenkins",
    }


@pytest.fixture()
def config_dict(base_config_dict):
    base_config_dict["ci_jobs"] = {
        "v4.15": [
            {
                "name": "openshift-ci-job-name",
                "ci": "openshift-ci",
                "products": {
                    "product": "operator",
                },
            }
        ],
        "v4.16": [
            {
                "name": "jenkins-job-name",
                "ci": "jenkins",
                "products": {
                    "product": "operator",
                },
            }
        ],
    }

    return base_config_dict


@pytest.fixture()
def config_dict_no_ci_jobs(base_config_dict):
    base_config_dict["ci_jobs"] = None
    return base_config_dict


def test_fetch_update_iib_and_trigger_jobs_no_ci_jobs_config(mocker, functions_mocker, config_dict_no_ci_jobs):
    mocker.patch.object(requests, "get", return_value=MockRequestGet())
    assert not fetch_update_iib_and_trigger_jobs(config_dict=config_dict_no_ci_jobs, logger=LOGGER)


def test_fetch_update_iib_and_trigger_jobs(mocker, functions_mocker, config_dict):
    mocker.patch.object(requests, "get", return_value=MockRequestGet())
    fetch_update_iib_and_trigger_jobs(config_dict=config_dict, logger=LOGGER)
