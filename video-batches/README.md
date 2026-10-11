# video-batches

Claude Sonnet translates the subtitles of the Emunah Shlemah video lessons from the Hebrew into English
and Portuguese, line by line, with each lesson's study (summary, moments, sources) as context. It
replaces the Google translation lesson by lesson; the result is marked `by: claude-sonnet-5-5` and the
Google job never overwrites it.

Everything runs on GitHub (`.github/workflows/translate-batch.yml`), back to back until the library is
done; the owner's computer can be off.

## A batch

```
batch-NNN/
  manifest.json      the lessons (the week's parashá first, then the richest), the chunks, status, tries
  in/<id>.p<k>.txt   the work file: the study + ≤450 numbered Hebrew lines
  out/<id>.p<k>.txt  the agent's output: N<TAB>English<TAB>Portuguese
  out/*.usage.json   tokens per agent
  report.md          what was published, what is waiting, tokens
```

`PROMPT.md` holds the translation rules every agent reads.

## Running

- **By itself:** a finished batch starts the next; every 2 hours the schedule resumes an unfinished one
  (agents stopped by the plan's usage limit are simply retried).
- **By hand:** Actions → "Translate a video batch (Claude)" → Run workflow, or
  `gh workflow run translate-batch.yml --repo crispinekkovendas-blip/emunah-caption-harvest`.
- **Stop:** disable the workflow in Actions (or `gh workflow disable translate-batch.yml`).

## The secret (once)

The agents run as the owner's Claude subscription. On the owner's computer:

```
claude setup-token
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo crispinekkovendas-blip/emunah-caption-harvest
```

(paste the token when `gh` asks). Repository secrets stay hidden in a public repo and are not given
to runs from forks.

## Checks before publishing

Every line 0…n-1 present exactly once in both languages and no Divine Name written out. A lesson that
fails is translated again (up to 3 tries), then skipped and listed in the report.
