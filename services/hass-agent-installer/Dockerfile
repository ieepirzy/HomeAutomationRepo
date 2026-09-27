FROM alpine:3.22 AS fetch

ARG HASS_AGENT_VERSION
ARG HASS_AGENT_COMMIT

# Pinned by release tag plus the exact commit it must resolve to. The clone
# fails the build if the tag is ever moved to different code.
RUN test -n "${HASS_AGENT_VERSION}" \
    && test -n "${HASS_AGENT_COMMIT}" \
    && apk add --no-cache git \
    && git clone -q --depth 1 --branch "${HASS_AGENT_VERSION}" \
      https://github.com/hass-agent/HASS.Agent-Integration /tmp/hass-agent \
    && test "$(git -C /tmp/hass-agent rev-parse HEAD)" = "${HASS_AGENT_COMMIT}" \
    && mkdir -p /payload \
    && cp -a /tmp/hass-agent/custom_components/hass_agent /payload/hass_agent

FROM alpine:3.22

COPY --from=fetch /payload/hass_agent /source/hass_agent
COPY install.sh /usr/local/bin/install-hass-agent

ENTRYPOINT ["/usr/local/bin/install-hass-agent"]
