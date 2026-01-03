import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.scraper import fetch_listings
from app.storage import init_db, load_cache, save_cache

logger = logging.getLogger("betterpf")
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="BetterPF")
scheduler = BackgroundScheduler()


def _parse_list_param(value: Optional[str]) -> Optional[Set[str]]:
    if not value:
        return None
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def _matches_search(item: dict, query: str) -> bool:
    text = " ".join(
        [
            item.get("duty", ""),
            item.get("creator", ""),
            item.get("description", ""),
        ]
    ).lower()
    return query in text


def _apply_filters(
    items: List[dict],
    search: Optional[str],
    data_centres: Optional[Set[str]],
    categories: Optional[Set[str]],
    min_parties: Optional[int],
    max_parties: Optional[int],
    joinable_roles: Optional[Set[str]],
    since: Optional[str],
) -> List[dict]:
    filtered: List[dict] = []
    search_lc = search.lower() if search else None
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            since_dt = None

    for item in items:
        data_centre = (item.get("data_centre") or "").lower()
        category = (item.get("pf_category") or "").lower()
        num_parties = item.get("num_parties")

        if data_centres and data_centre not in data_centres:
            continue
        if categories and category not in categories:
            continue
        if min_parties is not None and num_parties is not None and num_parties < min_parties:
            continue
        if max_parties is not None and num_parties is not None and num_parties > max_parties:
            continue
        if joinable_roles:
            roles = {role.lower() for role in item.get("joinable_roles", [])}
            if not roles.intersection(joinable_roles):
                continue
        if search_lc and not _matches_search(item, search_lc):
            continue
        if since_dt and item.get("fetched_at"):
            try:
                item_dt = datetime.fromisoformat(item["fetched_at"].replace("Z", "+00:00"))
                if item_dt <= since_dt:
                    continue
            except ValueError:
                pass

        filtered.append(item)

    return filtered


def _apply_sort(items: List[dict], sort: Optional[str], order: str) -> List[dict]:
    if not sort:
        return items

    sort_key = sort.lower()
    key_map = {
        "duty": lambda item: (item.get("duty") or "").lower(),
        "creator": lambda item: (item.get("creator") or "").lower(),
        "num_parties": lambda item: item.get("num_parties") or 0,
        "data_centre": lambda item: (item.get("data_centre") or "").lower(),
        "pf_category": lambda item: (item.get("pf_category") or "").lower(),
        "fetched_at": lambda item: item.get("fetched_at") or "",
    }
    key_fn = key_map.get(sort_key)
    if not key_fn:
        return items

    reverse = order.lower() == "desc"
    return sorted(items, key=key_fn, reverse=reverse)


def scrape_job() -> None:
    try:
        listings = fetch_listings()
    except Exception:
        logger.exception("Scrape failed; keeping last cached results.")
        return

    updated_at = datetime.now(timezone.utc).isoformat()
    for item in listings:
        item["fetched_at"] = updated_at
    save_cache(listings, updated_at)
    logger.info("Cache updated with %d listings.", len(listings))


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    scheduler.add_job(scrape_job, "interval", minutes=5, id="scrape_job", replace_existing=True)
    scheduler.start()
    scrape_job()


@app.on_event("shutdown")
def shutdown_event() -> None:
    scheduler.shutdown(wait=False)


@app.get("/api/listings")
def get_listings(
    q: Optional[str] = Query(default=None),
    data_centre: Optional[str] = Query(default=None),
    pf_category: Optional[str] = Query(default=None),
    min_parties: Optional[int] = Query(default=None, ge=0),
    max_parties: Optional[int] = Query(default=None, ge=0),
    joinable_role: Optional[str] = Query(default=None),
    since: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default="duty"),
    order: Optional[str] = Query(default="asc"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    cache = load_cache()
    if not cache:
        return {"last_updated": None, "total": 0, "returned": 0, "items": []}

    items = cache["payload"]
    filtered = _apply_filters(
        items=items,
        search=q,
        data_centres=_parse_list_param(data_centre),
        categories=_parse_list_param(pf_category),
        min_parties=min_parties,
        max_parties=max_parties,
        joinable_roles=_parse_list_param(joinable_role),
        since=since,
    )
    sorted_items = _apply_sort(filtered, sort=sort, order=order or "asc")
    page = sorted_items[offset : offset + limit]

    return {
        "last_updated": cache["updated_at"],
        "total": len(filtered),
        "returned": len(page),
        "items": page,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
