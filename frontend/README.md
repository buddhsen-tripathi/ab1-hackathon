# ABI Pipeline — Frontend

Next.js (App Router, React 19, Tailwind v4) dashboard that visualizes the
wound-care billing pipeline stage by stage. It reads from the FastAPI backend in
`../backend`.

## Pages

| Route | Stage | What it shows |
|---|---|---|
| `/` | Overview | Pipeline stepper (ingest → store → characterize → extract → route → present) + headline KPIs |
| `/ingestion` | 1–2 | Request stats, the 429 retry math, Retry-After distribution, stored row counts, and a "Run ingestion" trigger |
| `/characterization` | 3 | Payer mix, coverage signal, note formats, measurement completeness, dirty-data traps, and raw note samples |
| `/patients` | Roster | Searchable, facility-filterable patient table with Medicare Part B eligibility |

## Run it

From the repo root, one command runs both servers together:

```bash
npm run setup        # first time only: pip install + npm install
npm run dev          # backend :8000 + frontend :3000, side by side
```

`npm run dev` uses `concurrently` to start the FastAPI backend (`dev:be`) and the
Next.js dev server (`dev:fe`); Ctrl+C stops both. The API base URL is read from
`NEXT_PUBLIC_API_URL` (`.env.local`), defaulting to `http://localhost:8000`.

To run just one side: `npm run dev:be` or `npm run dev:fe`.

## Design system

Follows the project design system: semantic color tokens only (no hardcoded
colors except `StatusPill`), Lora / Plus Jakarta Sans / IBM Plex Mono type roles,
the `--text-*` scale, and the canonical components in `components/ui`.
