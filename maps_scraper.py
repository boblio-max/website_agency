"""
maps_scraper.py — Find businesses nearby via Google Maps, save to JSON.

Location is based around the *current machine location* (IP geolocation)
unless overridden with --lat/--lng or --location.

Each record in the output JSON looks like:
    {
      "name": "Example Auto Repair",
      "category": "Auto repair shop",
      "address": "123 Main St, Bothell, WA",
      "phone": "(425) 555-1234",
      "website": "https://example.com",
      "rating": 4.7,
      "review_count": 183,
      "maps_url": "https://www.google.com/maps/place/...",
      "source": "google_maps",
      "discovered_at": "2026-09-07T..."
    }

Usage:
    pip install playwright requests
    playwright install chromium
    python maps_scraper.py --query "auto repair" --max 20 --output businesses.json
    python maps_scraper.py --query "coffee shop" --query "plumber" --max 50
    python maps_scraper.py --query "restaurants" --lat 47.6062 --lng -122.3321
    python maps_scraper.py --query "dentist" --location "Bothell, WA" --no-headless

Notes:
- Google Maps HTML changes often; selectors below use several fallbacks.
- Keep --max modest (20-50) to avoid bot detection / long runs.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import time
import urllib.parse

import requests

DEFAULT_QUERIES = ["auto repair", "coffee shop", "restaurant"]


# ---------------------------------------------------------------------------
# Geolocation (current machine location)
# ---------------------------------------------------------------------------

def get_current_location(timeout: int = 10) -> dict:
    """Return {'lat', 'lng', 'city', 'region', 'country'} via IP geolocation.

    Tries ipapi.co first (lat/long + city), falls back to ip-api.com.
    Raises RuntimeError if both fail.
    """
    errors = []

    # Provider 1: ipapi.co (no key needed for basic usage)
    try:
        r = requests.get("https://ipapi.co/json/", timeout=timeout)
        r.raise_for_status()
        d = r.json()
        lat, lng = d.get("latitude"), d.get("longitude")
        if lat is not None and lng is not None:
            return {
                "lat": float(lat),
                "lng": float(lng),
                "city": d.get("city") or "",
                "region": d.get("region") or "",
                "country": d.get("country_name") or d.get("country") or "",
            }
        errors.append(f"ipapi.co missing coords: {d}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"ipapi.co failed: {e}")

    # Provider 2: ip-api.com (plain http, generous free tier)
    try:
        r = requests.get("http://ip-api.com/json/", timeout=timeout)
        r.raise_for_status()
        d = r.json()
        if d.get("status") == "success":
            return {
                "lat": float(d["lat"]),
                "lng": float(d["lon"]),
                "city": d.get("city") or "",
                "region": d.get("regionName") or "",
                "country": d.get("country") or "",
            }
        errors.append(f"ip-api.com error: {d}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"ip-api.com failed: {e}")

    raise RuntimeError("Could not determine machine location: " + " | ".join(errors))


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_rating(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(",", "."))
    if not m:
        return None
    try:
        v = float(m.group(1))
        return v if 0 <= v <= 5 else None
    except ValueError:
        return None


def parse_review_count(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def dedupe(records: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for r in records:
        key = (r.get("maps_url") or "").split("?")[0].lower() or (r.get("name") or "").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Google Maps scraping (Playwright)
# ---------------------------------------------------------------------------

def build_search_url(query: str, lat: float, lng: float, zoom: int = 14, city: str = "") -> str:
    """Build a Google Maps search URL biased to the machine location."""
    if city:
        q = f"{query} near {city}"
    else:
        q = query
    encoded = urllib.parse.quote_plus(q)
    # /@lat,lng,zoom biases results without requiring geolocation permission.
    return f"https://www.google.com/maps/search/{encoded}/@{lat},{lng},{zoom}z"


def _safe_text(locator, timeout: int = 3000) -> str | None:
    try:
        el = locator.first
        if el.count() == 0:
            return None
        t = el.inner_text(timeout=timeout).strip()
        return t or None
    except Exception:  # noqa: BLE001
        return None


def _safe_attr(locator, attr: str, timeout: int = 3000) -> str | None:
    try:
        el = locator.first
        if el.count() == 0:
            return None
        v = el.get_attribute(attr, timeout=timeout)
        return v.strip() if v else None
    except Exception:  # noqa: BLE001
        return None


def collect_listing_urls(page, max_results: int, scroll_delay: float = 1.2) -> list[str]:
    """Scroll the results feed and collect unique business URLs."""
    urls: list[str] = []
    seen: set[str] = set()

    try:
        page.wait_for_selector('div[role="feed"], a.hfpxzc', timeout=15000)
    except Exception:  # noqa: BLE001
        pass  # single-result pages may have no feed

    feed = None
    try:
        if page.locator('div[role="feed"]').count() > 0:
            feed = page.locator('div[role="feed"]').first
    except Exception:  # noqa: BLE001
        feed = None

    last_count = -1
    stall_rounds = 0
    # Scroll until we have enough or the feed stops growing.
    for _ in range(40):
        cards = page.locator("a.hfpxzc")
        try:
            n = cards.count()
        except Exception:  # noqa: BLE001
            n = 0
        for i in range(n):
            try:
                href = cards.nth(i).get_attribute("href")
            except Exception:  # noqa: BLE001
                continue
            if href and href.startswith("http") and href not in seen:
                seen.add(href)
                urls.append(href)
                if len(urls) >= max_results:
                    return urls
        if len(urls) == last_count:
            stall_rounds += 1
            if stall_rounds >= 4:
                break
        else:
            stall_rounds = 0
            last_count = len(urls)
        try:
            if feed is not None:
                feed.evaluate("(el) => el.scrollBy(0, el.clientHeight * 0.9)")
            else:
                page.mouse.wheel(0, 2000)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(scroll_delay)
        # Click "next page" style; Google mostly infinite-scrolls the feed.
    return urls


def scrape_detail(context, url: str, timeout_ms: int = 15000) -> dict:
    """Visit one business page and extract the target record fields."""
    page = context.new_page()
    rec: dict = {
        "name": None,
        "category": None,
        "address": None,
        "phone": None,
        "website": None,
        "rating": None,
        "review_count": None,
        "maps_url": url.split("?")[0] if "?" in url else url,
        "source": "google_maps",
        "discovered_at": utc_now_iso(),
    }
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(1500)

        # Canonical URL (contains place id / coords)
        try:
            rec["maps_url"] = page.url
        except Exception:  # noqa: BLE001
            pass

        # Name
        name = _safe_text(page.locator("h1.DUwDvf"))
        if name:
            rec["name"] = name

        # Category (e.g. "Auto repair shop")
        cat = _safe_text(page.locator("button.DkEaL"))
        if not cat:
            # fallback: first span in the header area listing categories
            cat = _safe_text(page.locator("button.DkEaL span, div.PYvSYb span"))
        if cat:
            rec["category"] = cat.split("·")[0].strip()

        # Rating, e.g. <span aria-hidden="true">4.7</span>
        rating_txt = _safe_text(page.locator("div.F7nice span[aria-hidden='true']").first)
        if not rating_txt:
            rating_txt = _safe_text(page.locator("div.F7nice"))
        rec["rating"] = parse_rating(rating_txt)

        # Review count, e.g. <span>(183)</span> near the rating
        rc_txt = _safe_text(page.locator("div.F7nice span[aria-label*='review']").first)
        if not rc_txt:
            # common pattern: button containing "(183)"
            for sel in ["button span", "div.F7nice span", "span.UY7F9"]:
                try:
                    for i in range(min(page.locator(sel).count(), 12)):
                        t = page.locator(sel).nth(i).inner_text(timeout=1000).strip()
                        if re.fullmatch(r"\(\s*[\d.,\s]+\s*\)", t):
                            rc_txt = t
                            break
                    if rc_txt:
                        break
                except Exception:  # noqa: BLE001
                    continue
        rec["review_count"] = parse_review_count(rc_txt)

        # Address
        addr = _safe_text(page.locator("button[data-item-id='address'] div.Io6YTe"))
        if not addr:
            addr = _safe_text(page.locator("button[data-item-id*='address']"))
        if addr:
            rec["address"] = addr

        # Phone
        phone = _safe_text(page.locator("button[data-item-id*='phone'] div.Io6YTe"))
        if not phone:
            phone = _safe_text(page.locator("button[data-item-id*='tel:']"))
        if phone:
            rec["phone"] = phone

        # Website
        site = _safe_attr(page.locator("a[data-item-id='authority']").first, "href")
        if not site:
            # fallback: any outbound link labelled with the domain
            try:
                for i in range(min(page.locator("a[data-item-id='authority']").count(), 3)):
                    href = page.locator("a[data-item-id='authority']").nth(i).get_attribute("href")
                    if href and href.startswith("http"):
                        site = href
                        break
            except Exception:  # noqa: BLE001
                pass
        if site:
            rec["website"] = site
    finally:
        try:
            page.close()
        except Exception:  # noqa: BLE001
            pass
    return rec


def scrape_query(query: str, lat: float, lng: float, city: str,
                 max_results: int, headless: bool, zoom: int,
                 scroll_delay: float, timeout_ms: int) -> list[dict]:
    from playwright.sync_api import sync_playwright

    url = build_search_url(query, lat, lng, zoom=zoom, city=city)
    print(f"[maps_scraper] query={query!r} url={url}", flush=True)
    records: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            locale="en-US",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(2500)

            # If search resolves directly to a single place (no feed), scrape it.
            is_place = "/place/" in (page.url or "")
            n_cards = 0
            try:
                n_cards = page.locator("a.hfpxzc").count()
            except Exception:  # noqa: BLE001
                n_cards = 0

            if is_place and n_cards == 0:
                print("[maps_scraper] single-place result, scraping directly", flush=True)
                records.append(scrape_detail(context, page.url, timeout_ms))
            else:
                urls = collect_listing_urls(page, max_results, scroll_delay)
                print(f"[maps_scraper] found {len(urls)} listing(s) for {query!r}", flush=True)
                for u in urls[:max_results]:
                    try:
                        records.append(scrape_detail(context, u, timeout_ms))
                        time.sleep(0.5)  # be polite
                    except Exception as e:  # noqa: BLE001
                        print(f"[maps_scraper] WARN detail failed: {e}", flush=True)
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass
            context.close()
            browser.close()
    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape nearby businesses from Google Maps into JSON.")
    p.add_argument("--query", action="append", default=[],
                   help="Business type to search (repeatable). e.g. --query 'auto repair' --query 'coffee shop'")
    p.add_argument("--lat", type=float, default=None, help="Override latitude (default: IP geolocation)")
    p.add_argument("--lng", type=float, default=None, help="Override longitude (default: IP geolocation)")
    p.add_argument("--location", default="", help="City/region hint, e.g. 'Bothell, WA' (used in search text)")
    p.add_argument("--max", type=int, default=20, help="Max businesses PER query (default: 20)")
    p.add_argument("--zoom", type=int, default=14, help="Map zoom bias 1-21 (default: 14)")
    p.add_argument("--output", "-o", default="", help="Output JSON path (default: businesses_<timestamp>.json)")
    p.add_argument("--headless", dest="headless", action="store_true", default=True, help="Run browser headless (default)")
    p.add_argument("--no-headless", dest="headless", action="store_false", help="Show browser window (debug)")
    p.add_argument("--scroll-delay", type=float, default=1.2, help="Seconds between result scrolls (default: 1.2)")
    p.add_argument("--timeout", type=int, default=30000, help="Page timeout ms (default: 30000)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None, **kwargs) -> str | int:
    """Run the scraper. Returns the output JSON path (str), or an int exit code on error.

    Orchestrator-friendly: ``main(output="businesses.json", query=["plumber"], max=20)``.
    Any keyword matching an argparse option overrides the CLI default. A bare
    main() call uses defaults (sys.argv is only used via the CLI).
    """
    if argv is None:
        # Plain main() uses defaults (never sys.argv); the CLI passes
        # sys.argv[1:] explicitly via the __main__ block below.
        argv = []
    args = parse_args(argv)
    for _k, _v in kwargs.items():
        if not hasattr(args, _k):
            raise TypeError(f"maps_scraper.main() got an unexpected option {_k!r}")
        setattr(args, _k, _v)
    if isinstance(args.query, str):
        args.query = [args.query]
    queries = args.query or DEFAULT_QUERIES

    # Resolve location: explicit flags win, else IP geolocation of this machine.
    city = args.location.strip()
    if args.lat is not None and args.lng is not None:
        lat, lng = args.lat, args.lng
        print(f"[maps_scraper] using override location: {lat},{lng} ({city or 'no city hint'})", flush=True)
    else:
        print("[maps_scraper] detecting machine location via IP geolocation…", flush=True)
        try:
            loc = get_current_location()
        except RuntimeError as e:
            print(f"[maps_scraper] ERROR {e}", file=sys.stderr)
            print("[maps_scraper] Hint: pass --lat/--lng manually.", file=sys.stderr)
            return 2
        lat, lng = loc["lat"], loc["lng"]
        if not city and loc.get("city"):
            region = loc.get("region") or ""
            city = f"{loc['city']}, {region}".strip(", ") if region else loc["city"]
        print(f"[maps_scraper] machine location ≈ {lat},{lng} ({city}, {loc.get('country','')})", flush=True)

    all_records: list[dict] = []
    for q in queries:
        # allow comma-separated: --query "plumber, electrician"
        for sub_q in [s.strip() for s in q.split(",") if s.strip()]:
            try:
                recs = scrape_query(sub_q, lat, lng, city, args.max,
                                    args.headless, args.zoom, args.scroll_delay, args.timeout)
                all_records.extend(recs)
            except Exception as e:  # noqa: BLE001
                print(f"[maps_scraper] ERROR query {sub_q!r}: {e}", file=sys.stderr)

    all_records = dedupe(all_records)
    # Drop entries with no name (failed parses)
    all_records = [r for r in all_records if r.get("name")]

    out = args.output.strip() or f"businesses_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    print(f"[maps_scraper] wrote {len(all_records)} business(es) → {out}", flush=True)
    return out


if __name__ == "__main__":
    _rc = main(sys.argv[1:])
    raise SystemExit(_rc if isinstance(_rc, int) else 0)
