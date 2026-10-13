# Owner Featured: Field Notes v1, fill-in prompt (paste to Nano)

Make an Owner Featured: Field Notes v1 reel for <business slug, e.g. truenorth>.
Title: <short title>
1. Customer reaction (about 4 s): <who, where, what they see, the visible reaction>. Owner voiceover, exactly: "<one line>"
2. Owner intro, exactly: "<one or two short lines>"
3. Field Notes explainer: <reuse project <name> | make a new one from this brief: <plain-English brief>>
4. Close: the business's saved close (<close id, or 'standard'>)
Quote everything first; show me the customer keyframe before animating. Draft only, no publishing.

Nano runs `python -m studio.owner_featured draft <slug> <project>` with the filled prompt as the brief, then quotes only the
missing paid items. Everything else comes from format.json and tenants/<slug>.json.
