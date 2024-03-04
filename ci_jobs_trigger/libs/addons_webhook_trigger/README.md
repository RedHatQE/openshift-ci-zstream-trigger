# addons_webhook_trigger

A webhook to trigger ci jobs when a new addon is available (i.e. merged) in GitLab.

## Supported platforms
- openshift ci
- jenkins

## Configuration

### GitLab webhook

Add a webhook and mark `Merge request events`

### Jobs configuration
- Create a yaml file [example](config-examples/addons-webhook-trigger-config.example.yaml) and update the relevant fields.
- Export `ADDONS_WEBHOOK_JOBS_TRIGGER_CONFIG` environment variable which points to the configuration yaml file

```bash
export ADDONS_WEBHOOK_JOBS_TRIGGER_CONFIG="<path to yaml file>"
```
