#!/usr/bin/env bash
# push-retry.sh [mine|branch] — push the commit just made: up to 15 tries with random waits (20 lanes push at once).
#
# When the same file was added on the branch meanwhile (a helping lane and the owner translated the same piece):
#   mine    this commit's version wins   (the owner's publish: it is the text just published to the site)
#   branch  the branch's version stays   (a piece pushed by a lane: the one already there may be published)
#
# 2026-11-16 (the big run): five publish jobs died on such an add/add conflict. `git pull --rebase` stopped in the
# middle of the rebase, the 14 tries after it all failed on "you have unmerged files", and the job ended in an error.
# The lessons were on the site, but the batch stayed open in the repo: its pieces were translated a second time
# (about 65 pieces) and the lessons published again. Now a stuck rebase is undone before every try and the conflict
# is settled by rule.
keep=${1:-branch}
# in a rebase "theirs" is the commit being replayed (ours), "ours" is the branch it is replayed onto
opt=$([ "$keep" = mine ] && echo theirs || echo ours)
for i in $(seq 1 15); do
  git rebase --abort 2> /dev/null || true
  if git pull --rebase -X "$opt" -q && git push -q; then exit 0; fi
  sleep $((RANDOM % 10 + i * 2))
done
git rebase --abort 2> /dev/null || true
exit 1
