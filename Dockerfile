# syntax=docker/dockerfile:1
# OCI image for the vdb-flow CLI. Qdrant and embedding services are expected to be reachable via config/env.
FROM python:3.14-slim-bookworm AS builder

ARG VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}

WORKDIR /src
COPY pyproject.toml README.md MANIFEST.in LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir build \
    && pip wheel --no-cache-dir -w /out .

FROM python:3.14-slim-bookworm

RUN useradd --create-home --uid 1000 appuser

COPY --from=builder /out/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

USER appuser
WORKDIR /home/appuser

ENTRYPOINT ["vdb-flow"]
CMD ["--help"]
