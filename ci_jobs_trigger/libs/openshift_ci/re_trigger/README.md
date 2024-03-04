# re-trigger

A webhook server for re-triggering [openshift-ci](https://github.com/openshift/release) jobs.  
Only periodic jobs can be re-triggered (openShift-ci API limitation).  
Re-triggering is done only if a job fails during setup (`pre phase`).  
The job will be re-triggered only once.  

## Supported platforms
- openshift ci

## How to call the server

```bash
curl -X POST  http://<url>:5000/openshift-ci-re-trigger -d '{"job_name":"'"$JOB_NAME"'", "build_id": "'"$BUILD_ID"'", "prow_job_id":"'"$PROW_JOB_ID"'", "trigger_token":  "'"$OPENSHIFT_CI_TOKEN"'"}' -H "Content-Type: application/json"

```

- JOB_NAME - openshift-ci job name
- BUILD_ID - openshift-ci job build id
- PROW_JOB_ID - openshift-ci prow build id
- OPENSHIFT_CI_TOKEN - openshift-ci gangway API token

## Slack support
Add `slack_webhook_url` and `slack_errors_webhook_url` to receive Slack notifications.

```bash
curl -X POST  http://<url>:5000/openshift-ci-re-trigger -d \
  '{"job_name":"'"$JOB_NAME"'", "build_id": "'"$BUILD_ID"'", "prow_job_id":"'"$PROW_JOB_ID"'", "trigger_token": "'"$OPENSHIFT_CI_TOKEN"'", "slack_webhook_url": "'"$SLACK_URL"'", "slack_errors_webhook_url": "'"$SLACK_ERRORS_URL"'"}}' \
  -H "Content-Type: application/json"
```

- SLACK_URL - Slack URL for informational notifications
- SLACK_ERRORS_URL - Slack URL for error notifications
