FROM alpine:3.22 AS fetch

ARG HEALTHSYNC_VERSION
ARG HEALTHSYNC_SHA256

RUN test -n "${HEALTHSYNC_VERSION}" \
    && test -n "${HEALTHSYNC_SHA256}" \
    && wget -q \
      "https://github.com/mannotfood/healthsync/archive/refs/tags/v${HEALTHSYNC_VERSION}.tar.gz" \
      -O /tmp/healthsync.tar.gz \
    && echo "${HEALTHSYNC_SHA256}  /tmp/healthsync.tar.gz" | sha256sum -c - \
    && mkdir -p /payload \
    && tar -xzf /tmp/healthsync.tar.gz \
      -C /payload \
      --strip-components=2 \
      "healthsync-${HEALTHSYNC_VERSION}/custom_components/healthsync"

FROM alpine:3.22

COPY --from=fetch /payload/healthsync /source/healthsync
COPY install.sh /usr/local/bin/install-healthsync

ENTRYPOINT ["/usr/local/bin/install-healthsync"]
