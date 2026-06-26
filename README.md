# MedArchive — Clinic Price-List Processing

Automatic processing of an archive of clinic price lists (PDF / scanned PDF /
DOCX / XLSX / XLS) into a **normalized, versioned database** of partners,
services and prices, with a **REST/OpenAPI** search layer.

Built for Case 2 "MedArchive". See `ТЗ_Кейс2_MedArchive (1).docx` for the spec.

## What it does

```
ZIP/file → store raw → detect format → extract (text-first, OCR fallback)
        → map price tiers (resident / near-abroad / far-abroad / no-VAT)
        → normalize service name to the dictionary (RapidFuzz + embeddings)
        → validate (price>0, nonres≥res, dedup, >50% anomaly, currency→KZT)
        → version (archive-on-change) → searchable via REST API
```

Highlights, grounded in the real sample data:
- **Adaptive PDF pipeline** — tries the embedded text layer first; falls back to
  Tesseract OCR (rus+kaz+eng) only on genuine scan pages, with a per-document OCR
  budget. Header-less price lists are handled by a line-item parser.
- **Buried-header detection** — Excel headers sit under 8–17 rows of letterhead;
  detected by keyword scoring, with multi-row merged headers and inline category
  rows ("1. СТАЦИОНАР") handled.
- **Flexible price tiers** — real files have up to 4 price columns; modeled as
  N `PriceTier` rows per item, not a fixed resident/non-resident pair.
- **Pluggable extractors** — one `BaseExtractor` interface + registry; add a
  format with one new file, the core never changes.
- **Versioning** — a new document supersedes prior items (archive-on-change);
  history is kept indefinitely.

## Quick start (Docker)

```bash
cd backend
cp .env.example .env
docker compose up --build        # api + worker + postgres + redis, runs migrations
# API docs:  http://localhost:8000/docs
```

Ingest the provided archive and build the dictionary:

```bash
# copy the sample data into the container's storage, or upload via the API:
curl -F "file=@/path/to/archive.zip" "http://localhost:8000/upload?asynchronous=true"

# load the organizer dictionary (or seed-dictionary to bootstrap from data), then re-normalize:
docker compose exec api python -m app.cli load-dictionary "Справочник услуг.xlsx"
docker compose exec api python -m app.cli renormalize
docker compose exec api python -m app.cli report
```

## Quick start (local, no Docker)

Requires Python 3.11, Postgres, Redis, and Tesseract (`brew install tesseract
tesseract-lang`).

```bash
cd backend
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,embeddings]"     # omit 'embeddings' to skip torch (RapidFuzz only)
export DATABASE_URL=postgresql+psycopg2://medarchive:medarchive@localhost:5432/medarchive
alembic upgrade head

# end-to-end over the sample data directory (synchronous, no Celery):
python -m app.cli ingest ../data
python -m app.cli load-dictionary "../Справочник услуг.xlsx"   # or: seed-dictionary
python -m app.cli renormalize
python -m app.cli report

uvicorn app.main:app --reload          # http://localhost:8000/docs
```

## CLI

| command | purpose |
|---|---|
| `python -m app.cli extract <file-or-dir>` | dry-run extraction, prints a summary (no DB) |
| `python -m app.cli ingest <dir-or-zip>` | register + process documents into the DB |
| `python -m app.cli load-dictionary <xlsx-or-json>` | load an organizer-provided target dictionary |
| `python -m app.cli seed-dictionary` | bootstrap the Service dictionary from extracted items (fallback) |
| `python -m app.cli renormalize` | re-match all items against the current dictionary |
| `python -m app.cli report` | quality report (docs, % auto-normalized, queue sizes) |

## API (OpenAPI at `/docs`)

| method | endpoint | description |
|---|---|---|
| GET | `/services` | dictionary services, filter by category / substring |
| GET | `/services/{id}/partners` | who offers a service + prices (cheapest first) |
| GET | `/partners` | partners, filter by city / status |
| GET | `/partners/{id}/services` | a partner's full price list |
| GET | `/search?q=` | FTS over services + partners (trigram typo fallback) |
| GET | `/unmatched` | review queue with ranked dictionary suggestions |
| POST | `/match` | operator confirms / creates a match (learns a synonym) |
| POST | `/upload` | upload a ZIP or single file, optionally enqueue processing |
| GET | `/documents`, `/documents/{id}` | processing status + parse warnings |
| GET | `/dashboard/stats` | aggregate metrics |

## Configuration

All via env / `.env` (see `.env.example`): DB/Redis URLs, storage dir, match
thresholds (`MATCH_AUTO_THRESHOLD`, `MATCH_REVIEW_FLOOR`), `USE_EMBEDDINGS`,
OCR language/DPI, and the price-anomaly percent.

## Data model

`Partner` · `PriceDocument` · `PriceItem` (+ `PriceTier`) · `Service`
(+ `ServiceSynonym`) · `MatchDecision`. See `app/models/`.

## Tests

```bash
pytest tests/ -q     # pure-logic unit tests (parsing, columns, validation)
```

## Notes / assumptions

- The organizer dictionary `Справочник услуг.xlsx` (~1230 services) is loaded via
  `load-dictionary` (XLSX/JSON supported). If no dictionary is supplied,
  `seed-dictionary` bootstraps one from the extracted item names instead.
- Normalization is **precision-first**: ~37% auto-match at score ≥ 0.85, ~55% routed
  to the review queue with ranked suggestions, ~7% unmatched. See `REPORT.md` for why
  this beats lowering the threshold to hit the 70% goal with wrong matches.
- The 6 sample PDFs are **scans** (JBIG2/JPEG2000) with a variable-quality
  embedded text layer; the pipeline uses text where good and OCR where not.
- Currency→KZT uses a small static rate table (`app/currency.py`); swap for a
  dated National-Bank lookup in production.
