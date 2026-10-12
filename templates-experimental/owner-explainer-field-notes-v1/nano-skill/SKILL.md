---
name: fieldnotes-explainer
description: Draft an "Owner Explainer: Field Notes v1" animated explainer (the paper field-notes layout, section 3 of the owner explainer) from a plain-English brief, revise it in plain words, migrate an old saved plan, and hand back a silent preview with a checked Studio review link. Draft only. Use when an admin asks Nano for a Field Notes explainer, a Field Notes revision or a Field Notes preview link.
---

# Field Notes explainer (draft only)

You turn a person's plain-English brief into a silent Field Notes preview and a review link. The person never edits
JSON or scene data, and neither do you: every story change goes through `revise`, and the planner, validator and
compiler do the rest. Run every command from the Studio checkout:

```bash
cd "${FIELDNOTES_STUDIO:-/home/adam/video-studio}" && .venv/bin/python -m studio.fieldnotes_agent <action> ...
```

Each command prints one JSON object. Relay it in plain words; do not paste the JSON.

## Steps

1. **Collect the brief.** Ask for anything missing: business (name and type), audience, problem, verified cause,
   solution, realistic outcome, optional narration in quotes, and the length ("about 15 seconds"). Use only what the
   person says; do not add facts.
2. **Quote first.** `quote new <project>` (or `revise`, `migrate`). Show the person the model calls and the
   API-equivalent range, and that nothing else is spent. Run only after they agree; pass the `quote_id`.
3. **Run.**
   - New: `new <project> --quote <id> --title "<title>"` with the brief on stdin (a quoted heredoc).
     The project name is 2 to 40 lower-case letters, digits or dashes.
   - Change: `revise <project> --quote <id> --change "<the person's words>"`.
   - Old plan: `migrate <project> --quote <id> --version <N>` (same approved brief, planned again under the
     current rules; the old version stays as it was).
   - Renderer-only fix: `rebuild <project>`. No model call; refuses a plan that needs migration.
   - Link again: `deliver <project> --version <N>`. Status of all versions: `status <project>`.
4. **Report.** On `ok: true`, give:
   - the `storyboard` (it is markdown);
   - `changes`, if any;
   - stand-ins from `missing_illustrations`;
   - the model usage;
   - the review link `review.url`, only if `review.verified` is true, otherwise the local `preview.path` and the reason.

   Say it is a silent draft for approval. Otherwise, relay `questions` or the problems and stop.

## Never

- Edit `project.json`, `plan-v*.json` or anything under `fieldnotes/`. Never hand-edit scene data.
- Narrate (paid voice), `render-remote`, publish, approve on the person's behalf, merge, deploy or restart.
- Delete or overwrite review copies. `deliver` refuses folders it did not create.
- Make an old plan pass by weakening the brief or a check. Migrate it instead and show what changed.
