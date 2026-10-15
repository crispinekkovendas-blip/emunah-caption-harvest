#!/usr/bin/env bash
# dub-fetch.sh [dest] — on the owner's computer: take every file waiting in the draft release dub-queue
# to E:\shiur-dub (pt/, en/, json/) and delete it from the queue. Run it again whenever; it only moves
# what is complete (the .json is written last by the lane, so a lesson with its .json is whole).
set -u
R=crispinekkovendas-blip/emunah-caption-harvest
D="${1:-/e/shiur-dub}"
mkdir -p "$D/pt" "$D/en" "$D/json"
names=$(gh release view dub-queue -R $R --json assets -q '.assets[].name' 2>/dev/null)
for j in $(echo "$names" | grep '\.json$'); do
  id="${j%.json}"
  for f in "$id.pt.opus" "$id.en.opus" "$id.json"; do
    echo "$names" | grep -qx "$f" || continue
    case "$f" in *.pt.opus) sub=pt ;; *.en.opus) sub=en ;; *) sub=json ;; esac
    gh release download dub-queue -R $R -p "$f" -D "$D/$sub" --clobber && gh release delete-asset dub-queue "$f" -R $R --yes >/dev/null
  done
  echo "$id"
done
