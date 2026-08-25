#!/bin/sh
set -eu

target=/custom_components/healthsync
staged=/custom_components/.healthsync-next

rm -rf "${staged}"
cp -a /source/healthsync "${staged}"
rm -rf "${target}"
mv "${staged}" "${target}"

echo "Installed HealthSync $(sed -n 's/.*\"version\": \"\([^\"]*\)\".*/\1/p' "${target}/manifest.json")"
