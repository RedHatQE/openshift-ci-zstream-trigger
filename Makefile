IMAGE_BUILD_CMD ?= $(shell which podman 2>/dev/null || which docker)
IMAGE_TAG ?= "latest"
IMAGE_REPOSITORY ?= "quay.io/redhat_msi/ci-jobs-trigger"

tests:
	tox

build:
	$(IMAGE_BUILD_CMD) build . -t $(IMAGE_REPOSITORY):$(IMAGE_TAG)

push:
	build push $(IMAGE_REPOSITORY):$(IMAGE_TAG)

PHONY: tests build push
