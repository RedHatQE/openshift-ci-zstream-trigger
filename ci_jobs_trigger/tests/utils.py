class MockJenkinsJob:
    @staticmethod
    def get_parameters():
        return []

    @staticmethod
    def build_job():
        return MockJenkinsBuild()

    @staticmethod
    def get_job_info(name="test-job"):
        return {"lastBuild": {"number": 123456}}

    @staticmethod
    def job_exists():
        return True


class MockJenkinsBuild:
    @staticmethod
    def build_job():
        return MockJenkinsBuild()

    @property
    def url(self):
        return "https://test-jenkins-url"


class MockRequestPost:
    @property
    def ok(self):
        return True

    @staticmethod
    def json():
        return {"id": 123456}
