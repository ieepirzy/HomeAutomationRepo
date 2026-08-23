FROM alpine:3.22 AS fetch

ARG LOCALTUYA_VERSION
ARG LOCALTUYA_SHA256

RUN test -n "${LOCALTUYA_VERSION}" \
    && test -n "${LOCALTUYA_SHA256}" \
    && wget -q \
      "https://github.com/xZetsubou/hass-localtuya/archive/refs/tags/${LOCALTUYA_VERSION}.tar.gz" \
      -O /tmp/localtuya.tar.gz \
    && echo "${LOCALTUYA_SHA256}  /tmp/localtuya.tar.gz" | sha256sum -c - \
    && mkdir -p /payload \
    && tar -xzf /tmp/localtuya.tar.gz \
      -C /payload \
      --strip-components=2 \
      "hass-localtuya-${LOCALTUYA_VERSION}/custom_components/localtuya"

FROM alpine:3.22

COPY --from=fetch /payload/localtuya /source/localtuya
COPY install.sh /usr/local/bin/install-localtuya

ENTRYPOINT ["/usr/local/bin/install-localtuya"]
