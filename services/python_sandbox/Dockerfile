# Base digest is supplied by build_image.py; mutable tags are rejected there.
ARG PYTHON_BASE
FROM ${PYTHON_BASE}
# Freeze OS-library resolution too. RDKit's Cairo drawing wheel needs Xrender/Xext.
RUN set -eu; \
    retry_download() { download_attempt=0; until "$@"; do download_attempt=$((download_attempt + 1)); [ "$download_attempt" -lt 3 ] || return 1; sleep "$download_attempt"; done; }; \
    rm -f /etc/apt/sources.list.d/debian.sources; \
    printf '%s\n' 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261111T000000Z/ bookworm main' > /etc/apt/sources.list; \
    retry_download apt-get -o Acquire::Retries=0 -o APT::Update::Error-Mode=any update; \
    retry_download apt-get -o Acquire::Retries=0 install --download-only -y --no-install-recommends libxrender1 libxext6 libexpat1 libstdc++6; \
    apt-get install --no-download -y --no-install-recommends libxrender1 libxext6 libexpat1 libstdc++6; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
COPY requirements.lock /opt/requirements.lock
RUN --mount=type=bind,source=wheelhouse,target=/opt/wheels,readonly \
    if [ -n "$(find /opt/wheels -name '*.whl' -print -quit)" ]; then \
      python -m pip install --no-cache-dir --no-index --find-links=/opt/wheels --require-hashes --only-binary=:all: -r /opt/requirements.lock; \
    else \
      python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /opt/requirements.lock; \
    fi
COPY --chmod=0444 bootstrap.py /opt/bootstrap.py
COPY --chmod=0444 science_smoke.py /opt/science_smoke.py
USER 10001:10001
RUN test -r /opt/bootstrap.py && MPLCONFIGDIR=/tmp/mpl python /opt/science_smoke.py && rm -rf /tmp/mpl
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/python", "-I", "-B", "/opt/bootstrap.py"]
