FROM python:3.12
EXPOSE 5000

ENV PRE_COMMIT_HOME=/tmp
ENV GOCACHE=/tmp/.cache/go-build

# Install the Rosa CLI
RUN curl -L https://mirror.openshift.com/pub/openshift-v4/clients/rosa/latest/rosa-linux.tar.gz --output /tmp/rosa-linux.tar.gz \
    && tar xvf /tmp/rosa-linux.tar.gz --no-same-owner \
    && mv rosa /usr/bin/rosa \
    && chmod +x /usr/bin/rosa \
    && rosa version

COPY pyproject.toml poetry.lock README.md /ci-jobs-trigger/
COPY ci_jobs_trigger/ /ci-jobs-trigger/ci_jobs_trigger/
WORKDIR /ci-jobs-trigger

# Set OCM_CONFIG to save ocm credentials for login
RUN mkdir -p config/ocm \
    && chmod 755 /ci-jobs-trigger/config/ocm
ENV OCM_CONFIG=/ci-jobs-trigger/config/ocm/ocm.json

RUN python3 -m pip install pip --upgrade \
    && python3 -m pip install poetry pre-commit \
    && poetry config cache-dir /ci-jobs-trigger \
    && poetry config virtualenvs.in-project true \
    && poetry config installer.max-workers 10 \
    && poetry config --list \
    && poetry install

ENTRYPOINT ["poetry", "run", "python3", "ci_jobs_trigger/app.py"]
