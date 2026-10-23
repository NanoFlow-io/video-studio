# Owner Featured: Field Notes v1, rollout and rollback (for review; not run)

Live checkout: `/home/adam/video-studio` on `main`. Branch: `work/owner-featured-20261012`. No service restart is
needed: the draft command and the skill are read on each use. Nothing here generates, buys or publishes anything.

## Before

1. Record the live state: `git -C /home/adam/video-studio status --short > ~/backups/owner-featured-rollout-<date>/status-before.txt`
   and `git rev-parse HEAD`. The uncommitted brand edits (`projects/nanoflow/brand/logo-full.webp`, `mark.png`,
   `projects/nanoflow/project.json`) must appear unchanged before and after. Also save their sha256 sums.
2. Tag the current main: `git tag pre-owner-featured-rollout-<date>`.
3. Confirm `~/.claude/skills/owner-featured-reel` does not exist yet.

## Rollout

1. `git merge --no-ff work/owner-featured-20261012 -m "Owner Featured: Field Notes v1"` in the live checkout. The
   merge touches only branch files (studio/owner_featured.py, owner_profile.py, owner_steps.py, owner_card.py, tests,
   templates-experimental/owner-featured-field-notes-v1 incl. card fonts under the SIL Open Font License);
   none of them are the uncommitted brand files, so git leaves those alone. If git refuses, stop; do not stash or reset.
2. Install the skill by copying it: `cp -r templates-experimental/owner-featured-field-notes-v1/nano-skill ~/.claude/skills/owner-featured-reel`.

## Verify

1. `.venv/bin/python -m unittest discover -s tests` passes.
2. The brand-file sha256 sums and `status-before.txt` match (except the merged files are no longer listed).
3. A free draft from the live checkout: `studio.owner_featured draft truenorth <test-project>` with a filled prompt
   returns no problems and a quote. No paid step.
4. A fresh Nano chat with the invocation prompt stops at Gate 1 with the quote.

## Rollback (targeted, recoverable)

1. `git revert -m 1 <merge-commit>` in the live checkout. This adds a new commit that undoes only the merge; history,
   other commits and the uncommitted brand edits stay. No `reset --hard`, no `checkout .`, no `clean`.
2. Archive the skill instead of deleting it: `mv ~/.claude/skills/owner-featured-reel ~/backups/owner-featured-rollout-<date>/skill`.
3. Generated media in `owner-featured/` and Studio review copies are left in place. They are not tracked by git, so
   neither the merge nor the revert touches them.
4. Check the brand-file sums again, and run the test suite.

## Still manual after rollout

- Each paid step is one command (studio.owner_steps) behind its approval gate; Nano still writes the prompts and
  relays each result for review.
- A new business needs a ready profile first (owner_profile init fills logo, colours and number; a person picks the
  presenter and voice and approves the saved close). Music defaults to the shared NanoFlow bed.
- Account prices still unverified: the Higgsfield Pro plan, the Argil plan and the Claude plan.
