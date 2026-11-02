# Airflow 3.3 with the paleo project in its own virtualenv (ALCANCE.md §7, Fase 2).
# Airflow and paleo never share dependencies: tasks call /opt/paleo/.venv/bin/paleo,
# the same commands GitHub Actions runs (decision D4).
FROM apache/airflow:3.3.2-python3.14

USER root
# git for the data clone; gcc for mwparserfromhell, which has no wheel for this Python.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/paleo/.venv \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PALEO_HOME=/opt/paleo
WORKDIR /opt/paleo
COPY pyproject.toml uv.lock README.md LICENSE LICENSE-CONTENT.md ./
COPY src ./src
# The image's Python 3.14 instead of a downloaded one (pyproject asks for managed
# interpreters only because CachyOS is a rolling distro).
RUN uv sync --locked --no-dev --python-preference only-system --python python3.14
COPY . .
ARG GIT_SHA=unknown
ENV PALEO_COMMIT=${GIT_SHA}
# dbt writes target/ and logs/ next to the project; any user in group 0 can run tasks.
RUN chown -R airflow:0 /opt/paleo && chmod -R g+rwX /opt/paleo

USER airflow
WORKDIR /opt/airflow
