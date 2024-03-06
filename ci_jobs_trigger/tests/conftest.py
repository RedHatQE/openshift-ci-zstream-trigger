import jenkins
import pytest
import requests

from ci_jobs_trigger.tests.utils import MockJenkinsBuild, MockJenkinsJob, MockRequestPost


@pytest.fixture()
def functions_mocker(mocker):
    mocker.patch.object(requests, "post", return_value=MockRequestPost())

    mocker.patch.object(jenkins.Jenkins, "get_job_info", return_value=MockJenkinsJob())
    mocker.patch.object(jenkins.Jenkins, "job_exists", return_value=MockJenkinsJob())
    mocker.patch.object(jenkins.Jenkins, "build_job", return_value=MockJenkinsBuild())

    mocker.patch(
        "ci_jobs_trigger.libs.operators_iib_trigger.iib_trigger.push_changes",
        return_value=True,
    )
    mocker.patch("ci_jobs_trigger.libs.jenkins.utils.general.set_job_params", return_value={})
    mocker.patch(
        "ci_jobs_trigger.libs.jenkins.utils.general.wait_for_job_in_jenkins",
        return_value=(True, {"url": "url"}),
    )

    yield
