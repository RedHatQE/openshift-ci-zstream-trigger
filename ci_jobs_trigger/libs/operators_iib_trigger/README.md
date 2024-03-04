# operators_iib_trigger

A process which runs every 24 hours and checks for new operator(s) index image (IIB).
If a new index image is released, a job will be triggered.

## Supported platforms
- openshift ci
- jenkins

## Configuration

- Create a yaml file [example](../../../config-examples/ci-iib-jobs-trigger-config.example.yaml) and update the relevant fields.
- Export `CI_IIB_JOBS_TRIGGER_CONFIG` environment variable which points to the configuration yaml file

```bash
export CI_IIB_JOBS_TRIGGER_CONFIG="<path to yaml file>"
```
