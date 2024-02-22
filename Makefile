IMAGE_BUILD_CMD = $(shell which podman 2>/dev/null || which docker)
IMAGE_REPOSITORY = "quay.io/redhat_msi/ci-jobs-trigger"

tests:
	poetry install && tox

build:
	$(IMAGE_BUILD_CMD) build . -t $(IMAGE_REPOSITORY):latest

push:
	build push $(IMAGE_REPOSITORY):latest

PHONY: tests build push
