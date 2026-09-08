# Deep Answer

A rarity-based browser trivia game hosted on GitHub Pages.

## Game

- 7 prompts per dive
- 25 seconds per prompt
- rarity tiers: 10 / 20 / 40 / 60 / 80 / 100 points
- Daily Dive is deterministic by UTC date, so everyone gets the same seven prompts
- Practice Dive draws a fresh set
- answer normalization ignores case, accents, punctuation and a leading `the`, `a` or `an`, so `The Smiths` and `Smiths` both match

## Database

The production bank is generated from structured Wikidata relationships instead of AI-invented facts. `source/plan.json` requests 2,000 mixed questions across movies, music, geography, animals, science, sports, literature, games, technology and history.

The generated data is split for efficiency:

- `data/questions.json` — lightweight question index
- `data/answers/<question-id>.json` — accepted answers for one prompt
- `data/bank.json` — build metadata

The browser downloads only the answer file for the current prompt.

### What “complete” means

An answer list contains all matching answers returned by the structured source for that relation at build time. Wikidata can still have omissions, so the game records the source and keeps the database rebuildable instead of pretending any public knowledge graph is perfect.

## Rebuild

GitHub Actions rebuilds the question bank when the builder/config changes and once per month. It validates that there are exactly 2,000 questions and that every answer file is present before committing generated data.

Manual/Codespaces build:

```bash
pip install -r requirements.txt
python tools/build_database.py
python tools/validate_database.py
```

Successful Wikidata requests are cached in `.build_cache/` for efficient retries.

## GitHub Pages

Publish from `main` / root. The game itself is plain HTML, CSS and JavaScript.
