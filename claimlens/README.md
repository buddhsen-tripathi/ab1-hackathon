# ClaimLens AI

Evidence-backed Medicare Part B wound-care billing triage. ClaimLens ingests synthetic PCC records, extracts wound documentation, scores claim readiness, and gives billers a source-linked action queue.

## Run everything

From the `claimlens` directory:

```bash
./start.sh
```

The first run creates a local Python virtual environment and installs both backend and frontend dependencies. Keep that terminal open, then visit [http://localhost:5173](http://localhost:5173). Press `Ctrl+C` once to stop both services.

## Enable Claude assist

Claude is optional. The deterministic assessment, regex, and ICD-10 extraction pipeline works without an API key.

To enable LLM extraction and on-demand patient summaries:

```bash
cd claimlens/backend
cp .env.example .env
```

Open `claimlens/backend/.env` and replace the placeholder:

```dotenv
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
```

Restart `./start.sh`. The real `.env` is ignored by Git. Do not paste or commit the key.

## Sync behavior

- The first run is a full sync across facilities 101, 102, and 103.
- Later runs pass the last successful cursor to the PCC patients endpoint using `since` and reprocess only changed patients.
- Set `incremental=false` on `POST /api/sync` when a deliberate full refresh is needed.
- Every API call handles HTTP 429 using the server-provided `Retry-After` delay, with bounded retries.

## Product surfaces

- Claim readiness score and required routing labels
- Evidence trace with source-level excerpts
- Claim packet and missing-documentation request
- Multi-wound primary wound comparison
- API reliability and retry monitor
- On-demand, cached Claude packet narrative
- Full and incremental sync status
