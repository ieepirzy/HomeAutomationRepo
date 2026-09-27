#!/bin/sh
set -eu

target=/custom_components/hass_agent
staged=/custom_components/.hass_agent-next

rm -rf "${staged}"
cp -a /source/hass_agent "${staged}"
rm -rf "${target}"
mv "${staged}" "${target}"

echo "Installed HASS.Agent integration $(sed -n 's/.*\"version\": \"\([^\"]*\)\".*/\1/p' "${target}/manifest.json")"
