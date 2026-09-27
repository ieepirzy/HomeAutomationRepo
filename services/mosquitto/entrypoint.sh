#!/bin/sh
# Build the broker's password file from environment variables, then hand off
# to the upstream image entrypoint. The file lives only in the container's
# writable layer and is recreated on every start, so rotating a password is
# a Portainer env-var change plus a redeploy.
set -eu

: "${MQTT_HA_USERNAME:?set MQTT_HA_USERNAME}"
: "${MQTT_HA_PASSWORD:?set MQTT_HA_PASSWORD}"
: "${MQTT_AGENT_USERNAME:?set MQTT_AGENT_USERNAME}"
: "${MQTT_AGENT_PASSWORD:?set MQTT_AGENT_PASSWORD}"

if [ "$MQTT_HA_USERNAME" = "$MQTT_AGENT_USERNAME" ]; then
  echo "MQTT_HA_USERNAME and MQTT_AGENT_USERNAME must differ" >&2
  exit 1
fi

passwd_file=/mosquitto/auth/passwd
umask 077
mkdir -p "$(dirname "$passwd_file")"
rm -f "$passwd_file"
mosquitto_passwd -c -b "$passwd_file" "$MQTT_HA_USERNAME" "$MQTT_HA_PASSWORD"
mosquitto_passwd -b "$passwd_file" "$MQTT_AGENT_USERNAME" "$MQTT_AGENT_PASSWORD"
chown -R mosquitto:mosquitto /mosquitto/auth

exec /docker-entrypoint.sh "$@"
