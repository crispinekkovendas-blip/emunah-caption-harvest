#!/usr/bin/env bash
# dub-upload-local.sh [dir] — the dubs already on this computer (E:\shiur-dub) up to their public
# release dub-NN (2026-10-19), skipping what is there already
set -u
R=crispinekkovendas-blip/emunah-caption-harvest
D="${1:-/e/shiur-dub}"
cd "$(dirname "$0")/.."
for j in "$D"/json/*.json; do
  id=$(basename "$j" .json)
  rel=$(python scripts/dub-shard.py "$id")
  gh release view "$rel" -R $R --json assets -q '.assets[].name' | grep -qx "$id.json" && continue
  gh release upload "$rel" "$D/pt/$id.pt.opus" "$D/en/$id.en.opus" -R $R --clobber && gh release upload "$rel" "$j" -R $R --clobber && echo "$id → $rel"
done
