#!/usr/bin/env bash
# dub-handover.sh <id> — the lesson's dub files to its PUBLIC release dub-NN (scripts/dub-shard.py; the
# site plays them from there since 2026-10-19 — the old draft dub-queue filled up at 1,000 files) and the
# marker dub/done/<id> committed, so no lane makes it again. scripts/dub-fetch.sh copies them to E:.
set -u
id="$1"
rel=$(python scripts/dub-shard.py "$id")
files=$(ls out/dub/"$id".* 2>/dev/null)
[ -z "$files" ] && exit 0
# the audio first, the .json last: a lesson whose .json is in the queue is complete
audio=$(ls out/dub/"$id".*.opus 2>/dev/null)
ok=0
for i in 1 2 3; do gh release upload "$rel" $audio --repo "$GITHUB_REPOSITORY" --clobber && gh release upload "$rel" "out/dub/$id.json" --repo "$GITHUB_REPOSITORY" --clobber && ok=1 && break; sleep 10; done
[ $ok = 1 ] || exit 1
rm -f $files
mkdir -p dub/done && date -u +%FT%TZ > "dub/done/$id"
git add "dub/done/$id"
git commit -q -m "dub: $id" || exit 0
for i in 1 2 3 4 5; do git pull --rebase -q && git push -q && break; sleep $((RANDOM % 10 + 3)); done
