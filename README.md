# BetterPF

BetterPF mirrors xivpf.com Party Finder listings by scraping the public HTML and
serving a cached API + frontend dashboard. It never scrapes on user requests;
only the background scheduler refreshes the cache every 5 minutes.

## Features
- Scheduled scraper (5-minute interval) with cached results and last-updated timestamp
- API filtering, sorting, and search
- Frontend QoL: saved filters, keyword highlights, hide/mute rules, new since last visit, compact mode, dark mode

## Run locally

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000` in a browser.

## Docker

```bash
docker compose up --build
```

## API

`GET /api/listings`

Query parameters:
- `q`: substring search across duty, creator, description
- `data_centre`: comma-separated list
- `pf_category`: comma-separated list
- `min_parties`, `max_parties`: numeric bounds
- `joinable_role`: exact role match
- `since`: ISO timestamp (filters listings fetched after this time)
- `sort`: `duty`, `creator`, `num_parties`, `data_centre`, `pf_category`, `fetched_at`
- `order`: `asc` or `desc`
- `limit`, `offset`: pagination

Response:

```json
{
  "last_updated": "2025-01-01T12:34:56Z",
  "total": 42,
  "returned": 20,
  "items": [
    {
      "data_centre": "Aether",
      "pf_category": "Raids",
      "num_parties": 3,
      "joinable_roles": ["Tank", "Healer"],
      "duty": "Example Duty",
      "creator": "ExampleCreator",
      "description": "Bring food",
      "fetched_at": "2025-01-01T12:34:56Z"
    }
  ]
}
```

## Notes
- If the scrape fails, the API serves the last cached results and keeps the
  previous `last_updated` value.
- The scheduler runs immediately at startup, then every 5 minutes.
