# Owner Featured: any business (general template)

Ask Nano: **"Use the Owner Featured template for <business> and make it about <topic>."**

The format (`format.json`) is the same for every business: customer reaction hook, the owner's talking-head intro, a
new Field Notes explainer for the topic, the business's saved close, music. The close uses the Split card in the
business's own logo colours. Music is the shared NanoFlow bed unless the business has its own.

## First time for a business (once)

1. `owner_profile init <slug> --name "<Business>" --website <url>`: finds the logo, brand colours and phone number
   (from the website) where it can. A person confirms them.
2. A person chooses the presenter (Argil look) and the owner voice (ElevenLabs), and where the Argil call runs.
3. Saved close: Nano writes the close line ("call <Business> on <number, digit by digit>"), quotes it (about 60
   ElevenLabs credits and 1 Argil clip), makes it with the Split card, and it is saved once a person approves it.
4. `owner_profile check <slug>` says `ready: true`. From then on the one-line prompt works.

Until a business is ready, Nano says exactly what is missing and stops. It never uses another business's presenter,
voice, logo or number. True North is the first ready profile (see TRUE-NORTH.md).
