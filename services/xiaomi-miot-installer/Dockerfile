FROM alpine:3.22 AS fetch

ARG XIAOMI_MIOT_VERSION
ARG XIAOMI_MIOT_SHA256

RUN test -n "${XIAOMI_MIOT_VERSION}" \
    && test -n "${XIAOMI_MIOT_SHA256}" \
    && wget -q \
      "https://github.com/al-one/hass-xiaomi-miot/archive/refs/tags/v${XIAOMI_MIOT_VERSION}.tar.gz" \
      -O /tmp/xiaomi-miot.tar.gz \
    && echo "${XIAOMI_MIOT_SHA256}  /tmp/xiaomi-miot.tar.gz" | sha256sum -c - \
    && mkdir -p /payload \
    && tar -xzf /tmp/xiaomi-miot.tar.gz \
      -C /payload \
      --strip-components=2 \
      "hass-xiaomi-miot-${XIAOMI_MIOT_VERSION}/custom_components/xiaomi_miot"

FROM alpine:3.22

COPY --from=fetch /payload/xiaomi_miot /source/xiaomi_miot
COPY install.sh /usr/local/bin/install-xiaomi-miot

ENTRYPOINT ["/usr/local/bin/install-xiaomi-miot"]
