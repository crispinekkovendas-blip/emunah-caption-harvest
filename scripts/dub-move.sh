#!/usr/bin/env bash
# dub-move.sh — once (2026-10-19): every whole lesson in the old draft dub-queue to its public release
# dub-NN, one lesson at a time (a runner's disk holds a few, not 6 GB), then deleted from the queue.
set -u
R="${GITHUB_REPOSITORY:-crispinekkovendas-blip/emunah-caption-harvest}"
names=$(gh release view dub-queue -R "$R" --json assets -q '.assets[].name')
mkdir -p mv
n=0
for j in $(echo "$names" | grep '\.json$'); do
  id="${j%.json}"
  rel=$(python scripts/dub-shard.py "$id")
  files=""
  for f in "$id.pt.opus" "$id.en.opus" "$id.json"; do echo "$names" | grep -qx "$f" && files="$files $f"; done
  rm -f mv/*
  ok=1
  for f in $files; do gh release download dub-queue -R "$R" -p "$f" -D mv --clobber || ok=0; done
  [ $ok = 1 ] || { echo "$id: download failed"; continue; }
  audio=$(ls mv/*.opus 2>/dev/null)
  gh release upload "$rel" $audio -R "$R" --clobber && gh release upload "$rel" "mv/$id.json" -R "$R" --clobber || { echo "$id: upload failed"; continue; }
  for f in $files; do gh release delete-asset dub-queue "$f" -R "$R" --yes >/dev/null; done
  n=$((n + 1))
  echo "$id → $rel"
done
echo "$n lessons moved"
