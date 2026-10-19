#!/usr/bin/env bash
# dub-fetch.sh [dest] — on the owner's computer: a backup on E:\shiur-dub (pt/, en/, json/) of every
# whole lesson in the public releases dub-00 … dub-15 that is not there yet. Since 2026-10-19 the
# releases are where the site plays the dubs from, so nothing is deleted from GitHub any more.
set -u
R=crispinekkovendas-blip/emunah-caption-harvest
D="${1:-/e/shiur-dub}"
mkdir -p "$D/pt" "$D/en" "$D/json"
for i in $(seq -w 0 15); do
  rel="dub-$i"
  names=$(gh release view "$rel" -R $R --json assets -q '.assets[].name' 2>/dev/null)
  for j in $(echo "$names" | grep '\.json$'); do
    id="${j%.json}"
    [ -f "$D/json/$id.json" ] && continue
    for f in "$id.pt.opus" "$id.en.opus" "$id.json"; do
      echo "$names" | grep -qx "$f" || continue
      case "$f" in *.pt.opus) sub=pt ;; *.en.opus) sub=en ;; *) sub=json ;; esac
      # the .json last, so a lesson with its .json on E: is whole
      gh release download "$rel" -R $R -p "$f" -D "$D/$sub" --clobber
    done
    echo "$id"
  done
done
