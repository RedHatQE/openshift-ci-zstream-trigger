# ci-jobs-trigger


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

To run locally you need to export some os environment variables

```bash
poetry install

export FLASK_DEBUG=1  # Optional; to output flask logs to console.
export CI_JOBS_TRIGGER_PORT=5003  # Optional; to set a different port than 5000.
export CI_JOBS_TRIGGER_USE_RELOAD=1  # Optional; to re-load configuration when code is saved.

poetry run python  ci_jobs_trigger/app.py
```
