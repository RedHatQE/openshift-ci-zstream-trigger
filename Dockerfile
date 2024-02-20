FROM python:3.12
EXPOSE 5000

ENV PRE_COMMIT_HOME=/tmp
COPY pyproject.toml poetry.lock README.md /openshift-ci-zstream-trigger/
COPY openshift-ci-zstream-trigger/ /openshift-ci-zstream-trigger/openshift-ci-zstream-trigger/
WORKDIR /openshift-ci-zstream-trigger
RUN python3 -m pip install pip --upgrade \
    && python3 -m pip install poetry pre-commit \
    && poetry config cache-dir /app \
    && poetry config virtualenvs.in-project true \
    && poetry config installer.max-workers 10 \
    && poetry config --list \
    && poetry install

ENTRYPOINT ["poetry", "run", "python3", "openshift-ci-zstream-trigger/app.py"]
