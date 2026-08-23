#!/bin/sh
set -eu

target=/custom_components/localtuya
staged=/custom_components/.localtuya-next

rm -rf "${staged}"
cp -a /source/localtuya "${staged}"
rm -rf "${target}"
mv "${staged}" "${target}"

echo "Installed LocalTuya $(sed -n 's/.*\"version\": \"\([^\"]*\)\".*/\1/p' "${target}/manifest.json")"
