ARG K6_IMAGE=grafana/k6@sha256:3ddc8b1a33a2c3d8edc6e99b6a762ae36cba08788463458f5e6a7703e14eb77d
ARG PYTHON_IMAGE=python@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89
FROM ${K6_IMAGE} AS k6
FROM ${PYTHON_IMAGE}

COPY --from=k6 /usr/bin/k6 /usr/local/bin/k6
COPY src/perfagent/runner/process_environment.py \
     src/perfagent/runner/worker_bridge.py \
     src/perfagent/runner/worker_http.py \
     src/perfagent/runner/worker_job.py \
     src/perfagent/runner/worker_protocol.py /opt/worker/perfagent/runner/

ENV PYTHONPATH=/opt/worker PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "-m", "perfagent.runner.worker_job", "--k6", "/usr/local/bin/k6"]
