# operators_iib_trigger

A process which runs every 24 hours and checks for operator(s) new index images (IIB).
If a new index image is released, a job will be triggered.
Index image can be written to:
- AWS S3 bucket
- Local directory
- Local tmp directory

## Supported platforms
- openshift ci
- jenkins

## Configuration

- Create a yaml file [example](../../../config-examples/ci-iib-jobs-trigger-config.example.yaml) and update the relevant fields.
- S3 configuration:
  - aws_access_key_id
  - aws_secret_access_key
  - s3_bucket_operators_latest_iib_path - path to S3 bucket and filename
- To use a local file, set:
  - operators_latest_iib_filepath
- S3 and local file are mutually exclusive
- If none are provided, a tmp file will be created in /tmp
- Export `CI_IIB_JOBS_TRIGGER_CONFIG` environment variable which points to the configuration yaml file

```bash
export CI_IIB_JOBS_TRIGGER_CONFIG="<path to yaml file>"
```
