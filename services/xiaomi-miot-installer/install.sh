#!/bin/sh
set -eu

target=/custom_components/xiaomi_miot
staged=/custom_components/.xiaomi-miot-next

rm -rf "${staged}"
cp -a /source/xiaomi_miot "${staged}"
rm -rf "${target}"
mv "${staged}" "${target}"

echo "Installed Xiaomi Miot $(sed -n 's/.*\"version\": \"\([^\"]*\)\".*/\1/p' "${target}/manifest.json")"
