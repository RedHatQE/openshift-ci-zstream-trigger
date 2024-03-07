import os

import pytest
from simple_logger.logger import get_logger

from ci_jobs_trigger.libs.openshift_ci.ztream_trigger.zstream_trigger import (
    OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR,
    process_and_trigger_jobs,
)
from ci_jobs_trigger.tests.zstream_trigger.manifests.versions import VERSIONS

LOGGER = get_logger("test_zstream_trigger")

LIBS_ZSTREAM_TRIGGER_PATH = "ci_jobs_trigger.libs.openshift_ci.ztream_trigger.zstream_trigger"
GET_ACCEPTED_CLUSTER_VERSIONS_PATH = "ocp_utilities.cluster_versions.get_accepted_cluster_versions"
TRIGGER_JOBS_PATH = f"{LIBS_ZSTREAM_TRIGGER_PATH}.trigger_jobs"


@pytest.fixture()
def base_config_dict(tmp_path_factory):
    return {
        "trigger_token": "123456",
        "slack_webhook_url": "https://webhook",
        "slack_errors_webhook_url": "https://webhook-error",
        "processed_versions_file_path": tmp_path_factory.getbasetemp() / "processed_versions.json",
    }


@pytest.fixture()
def config_dict(base_config_dict):
    base_config_dict["versions"] = {
        "4.13": ["<openshift-ci-test-name-4.13>"],
    }
    return base_config_dict


@pytest.fixture()
def config_dict_no_versions(base_config_dict):
    base_config_dict["versions"] = {}
    return base_config_dict


def test_process_and_trigger_jobs_no_config():
    if os.environ.get(OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR):
        pytest.xfail(f"{OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR} is set")

    assert not process_and_trigger_jobs(logger=LOGGER)


def test_process_and_trigger_jobs_config_with_no_versions(config_dict_no_versions):
    assert not process_and_trigger_jobs(config_dict=config_dict_no_versions, logger=LOGGER)


def test_process_and_trigger_jobs(mocker, config_dict):
    mocker.patch(
        GET_ACCEPTED_CLUSTER_VERSIONS_PATH,
        return_value=VERSIONS,
    )
    mocker.patch(TRIGGER_JOBS_PATH, return_value=True)
    assert process_and_trigger_jobs(config_dict=config_dict, logger=LOGGER)


def test_process_and_trigger_jobs_already_triggered(mocker, config_dict):
    mocker.patch(
        GET_ACCEPTED_CLUSTER_VERSIONS_PATH,
        return_value=VERSIONS,
    )
    mocker.patch(TRIGGER_JOBS_PATH, return_value=False)
    mocker.patch(
        f"{LIBS_ZSTREAM_TRIGGER_PATH}.processed_versions_file",
        return_value={"4.13": ["4.13.34"]},
    )

    assert not process_and_trigger_jobs(config_dict=config_dict, logger=LOGGER)


def test_process_and_trigger_jobs_set_version(mocker, config_dict):
    mocker.patch(
        GET_ACCEPTED_CLUSTER_VERSIONS_PATH,
        return_value=VERSIONS,
    )
    mocker.patch(TRIGGER_JOBS_PATH, return_value=True)
    assert process_and_trigger_jobs(version="4.13", config_dict=config_dict, logger=LOGGER)
