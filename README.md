# ci-jobs-trigger
A Flask-based webhook server to trigger ci jobs.


## Supported triggering flows:

- [ztream_trigger](ci_jobs_trigger/libs/openshift_ci/ztream_trigger) - Trigger ci jobs on release of new OCP z-stream
- [re_trigger](ci_jobs_trigger/libs/openshift_ci/re_trigger) - Re-trigger ci job on failure
- [operators_iib_trigger](ci_jobs_trigger/libs/operators_iib_trigger) - Trigger ci job on new operator index image
- [addons_webhook_trigger](ci_jobs_trigger/libs/addons_webhook_trigger) - Trigger ci job when a new addon is released

## Build container

Using podman:

```bash
podman build -t ci-jobs-trigger .
```

Using docker:

```bash
docker build -t ci-jobs-trigger .
```

## Main Functionalities

### Development

To run locally you can export the following environment variables:

```bash
poetry install

export FLASK_DEBUG=1  # Optional; to output flask logs to console.
export CI_JOBS_TRIGGER_PORT=5003  # Optional; to set a different port than 5000.
export CI_JOBS_TRIGGER_USE_RELOAD=1  # Optional; to re-load configuration when code is saved.

poetry run python  ci_jobs_trigger/app.py
```
