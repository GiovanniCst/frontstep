# Frontstep in a container. Two stages: the wheel is built in the first and only
# the wheel crosses into the second, so no build tool ends up in the image that
# runs.
#
# ⚠️ This app reads and WRITES inside the folders you mount, and has no
# authentication of any kind. It is meant to listen on localhost. Publishing the
# port on a network is a decision, and `writable = false` is how you make that
# decision safer.

FROM python:3.13-slim AS build
WORKDIR /src
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src/ ./src/
RUN pip wheel --no-cache-dir --no-deps -w /wheels .


FROM python:3.13-slim

# Dates on the page are read by a person in their own timezone, and a container
# on UTC quietly shifts "today" by a couple of hours at the ends of the day —
# which is exactly when a status document gets written.
ENV TZ=Etc/UTC \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl gunicorn>=22.0 \
 && rm -rf /wheels

# Not root: the writes copy the owner of the file being rewritten, and a process
# running as root leaves status documents owned by root the first time it fails
# to. The uid is fixed so that a bind-mounted home folder can be matched to it.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin frontstep
USER frontstep

# Where the configuration is looked for. Mount yours over this path, or point
# FRONTSTEP_CONFIG somewhere else.
ENV FRONTSTEP_CONFIG=/config/config.toml

EXPOSE 9015

# `create_app()` — the factory: it reads the configuration at start-up, so a
# missing or broken config fails here, loudly, instead of on the first request.
# One worker: this is a single-user local app, and two workers would only mean
# two processes reading the same disk.
CMD ["gunicorn", "--bind", "0.0.0.0:9015", "--workers", "1", "--threads", "4", \
     "--access-logfile", "-", "frontstep.web:app_from_environment()"]
