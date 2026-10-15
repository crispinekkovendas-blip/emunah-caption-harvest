#!/usr/bin/env bash
# dub-handover.sh <id> — the lesson's dub files to the draft release dub-queue (only the owner sees a
# draft) and the marker dub/done/<id> committed, so no lane makes it again. The owner's computer takes
# the files to E:\shiur-dub (scripts/dub-fetch.sh) and deletes them from the queue.
set -u
id="$1"
files=$(ls out/dub/"$id".* 2>/dev/null)
[ -z "$files" ] && exit 0
# the audio first, the .json last: a lesson whose .json is in the queue is complete
audio=$(ls out/dub/"$id".*.opus 2>/dev/null)
ok=0
for i in 1 2 3; do gh release upload dub-queue $audio --repo "$GITHUB_REPOSITORY" --clobber && gh release upload dub-queue "out/dub/$id.json" --repo "$GITHUB_REPOSITORY" --clobber && ok=1 && break; sleep 10; done
[ $ok = 1 ] || exit 1
rm -f $files
mkdir -p dub/done && date -u +%FT%TZ > "dub/done/$id"
git add "dub/done/$id"
git commit -q -m "dub: $id" || exit 0
for i in 1 2 3 4 5; do git pull --rebase -q && git push -q && break; sleep $((RANDOM % 10 + 3)); done
