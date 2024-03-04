FROM python:3.12
EXPOSE 5000

ENV PRE_COMMIT_HOME=/tmp
ENV GOCACHE=/tmp/.cache/go-build
COPY pyproject.toml poetry.lock README.md /ci-jobs-trigger/
COPY ci_jobs_trigger/ /ci-jobs-trigger/ci_jobs_trigger/
WORKDIR /ci-jobs-trigger
RUN python3 -m pip install pip --upgrade \
    && python3 -m pip install poetry pre-commit \
    && poetry config cache-dir /ci-jobs-trigger \
    && poetry config virtualenvs.in-project true \
    && poetry config installer.max-workers 10 \
    && poetry config --list \
    && poetry install

ENTRYPOINT ["poetry", "run", "python3", "ci_jobs_trigger/app.py"]
