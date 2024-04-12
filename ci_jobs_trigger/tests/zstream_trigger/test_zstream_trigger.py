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
GET_ACCEPTED_CLUSTER_VERSIONS_PATH = f"{LIBS_ZSTREAM_TRIGGER_PATH}.get_accepted_cluster_versions"
TRIGGER_JOBS_PATH = f"{LIBS_ZSTREAM_TRIGGER_PATH}.openshift_ci_trigger_job"


pytestmark = pytest.mark.usefixtures("send_slack_message_mock")


@pytest.fixture
def job_trigger_and_get_versions_mocker(mocker):
    mocker.patch(
        GET_ACCEPTED_CLUSTER_VERSIONS_PATH,
        return_value=VERSIONS,
    )
    openshift_ci_trigger_job_mocker = mocker.patch(TRIGGER_JOBS_PATH)
    openshift_ci_trigger_job_mocker.ok = True


@pytest.fixture
def send_slack_message_mock(mocker):
    return mocker.patch(f"{LIBS_ZSTREAM_TRIGGER_PATH}.send_slack_message", return_value=None)


@pytest.fixture()
def base_config_dict(tmp_path_factory):
    return {
        "trigger_token": "123456",
        "slack_webhook_url": "https://webhook",
        "slack_errors_webhook_url": "https://webhook-error",
        "processed_versions_file_path": tmp_path_factory.getbasetemp() / "processed_versions.json",
    }


@pytest.fixture
def get_config_mocker(mocker):
    return mocker.patch(f"{LIBS_ZSTREAM_TRIGGER_PATH}.get_config")


@pytest.fixture()
def config_dict(get_config_mocker, base_config_dict):
    base_config_dict["versions"] = {
        "4.13": ["<openshift-ci-test-name-4.13>"],
    }
    get_config_mocker.return_value = base_config_dict


@pytest.fixture()
def config_dict_no_versions(get_config_mocker, base_config_dict):
    base_config_dict["versions"] = {}
    get_config_mocker.return_value = base_config_dict


@pytest.fixture()
def config_dict_empty_version(get_config_mocker, base_config_dict):
    base_config_dict["versions"] = {"4.15": None}
    get_config_mocker.return_value = base_config_dict


def test_process_and_trigger_jobs_no_config():
    if os.environ.get(OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR):
        pytest.xfail(f"{OPENSHIFT_CI_ZSTREAM_TRIGGER_CONFIG_OS_ENV_STR} is set")

    assert not process_and_trigger_jobs(logger=LOGGER)


def test_process_and_trigger_jobs_config_with_no_versions(config_dict_no_versions):
    assert not process_and_trigger_jobs(logger=LOGGER)


def test_process_and_trigger_jobs_config_with_empty_version(config_dict_empty_version):
    assert process_and_trigger_jobs(logger=LOGGER) == {"4.15": "No jobs found"}


def test_process_and_trigger_jobs(config_dict, job_trigger_and_get_versions_mocker):
    assert process_and_trigger_jobs(logger=LOGGER)


def test_process_and_trigger_jobs_already_triggered(mocker, config_dict, job_trigger_and_get_versions_mocker):
    mocker.patch(
        f"{LIBS_ZSTREAM_TRIGGER_PATH}.processed_versions_file",
        return_value={"4.13": ["4.13.34", "4.13.33"]},
    )

    assert process_and_trigger_jobs(logger=LOGGER) == {"4.13": "Already processed"}


def test_process_and_trigger_jobs_new_version(mocker, config_dict, job_trigger_and_get_versions_mocker):
    mocker.patch(
        f"{LIBS_ZSTREAM_TRIGGER_PATH}.processed_versions_file",
        return_value={"4.13": ["4.13.33", "4.13.32"]},
    )

    assert process_and_trigger_jobs(logger=LOGGER)


def test_process_and_trigger_jobs_set_version(config_dict, job_trigger_and_get_versions_mocker):
    assert process_and_trigger_jobs(version="4.13", logger=LOGGER)


def test_process_and_trigger_jobs_pass_version(mocker, config_dict, job_trigger_and_get_versions_mocker):
    mocker.patch(
        f"{LIBS_ZSTREAM_TRIGGER_PATH}.processed_versions_file",
        return_value={"4.13": ["4.13.33", "4.13.32"]},
    )

    assert process_and_trigger_jobs(logger=LOGGER, version="4.13")


def test_process_and_trigger_jobs_pass_version_not_in_config(mocker, config_dict, job_trigger_and_get_versions_mocker):
    mocker.patch(
        f"{LIBS_ZSTREAM_TRIGGER_PATH}.processed_versions_file",
        return_value={"4.13": ["4.13.33", "4.13.32"]},
    )
    with pytest.raises(ValueError):
        process_and_trigger_jobs(logger=LOGGER, version="4.14")
