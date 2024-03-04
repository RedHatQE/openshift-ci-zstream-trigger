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


class MockRequestPost:
    @property
    def ok(self):
        return True

    @staticmethod
    def json():
        return {"id": 123456}
