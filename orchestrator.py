"""orchestrator.py — Chain the bots via their orchestrator-friendly main() calls.

Convention every bot follows:
    result = bot.main(argv=None, **kwargs)   # kwargs override argparse options
    # success -> output path (str), tuple, or dict artifact
    # failure -> int exit code

Each ``main`` can still be run from the CLI (``python <bot>.py --help``);
the ``**kwargs`` form is what the orchestrator uses below.

Run:
    python orchestrator.py
"""

from __future__ import annotations

import sys

import maps_scraper as ms
import website_classifier as wc
import website_qualifier as wq
import lead_prioritizer as lp
import data_merger as dm

def _require(result, stage: str):
    """Unwrap a bot return: artifact passes through, int exit code raises."""
    if isinstance(result, int):
        raise RuntimeError(f"{stage} failed with exit code {result}")
    return result


def run(queries: list[str] | None = None, max_per_query: int = 20,
        threshold: int = 60) -> str:
    """Run scrape -> classify -> qualify -> merge -> prioritize. Returns target_leads path."""
    # Bot 1: scrape nearby businesses -> businesses.json
    scrape_kwargs: dict = {"max": max_per_query, "output": "businesses.json"}
    if queries:
        scrape_kwargs["query"] = queries
    businesses_file = _require(ms.main(**scrape_kwargs), "maps_scraper")

    # Bot 2: split by website presence -> with/without files
    classified = _require(
        wc.main(input=businesses_file,
                with_path="with_websites.json",
                without_path="without_websites.json"),
        "website_classifier",
    )
    with_path, without_path = classified

    # Bot 3: keep the BAD websites -> bad_websites.json
    bad_path = _require(
        wq.main(input=with_path, output="bad_websites.json", threshold=threshold),
        "website_qualifier",
    )

    # Merge the two lead pools (bad sites + no sites) -> merged_leads.json
    _require(
        dm.main(input1=bad_path, input2=without_path, output="merged_leads.json"),
        "data_merger",
    )

    # Bot 4: merge + rank -> target_leads.json
    leads_path = _require(
        lp.main(without=without_path, bad=bad_path, output="target_leads.json"),
        "lead_prioritizer",
    )
    return leads_path


if __name__ == "__main__":
    try:
        final = run()
    except RuntimeError as e:
        print(f"[orchestrator] ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"[orchestrator] done -> {final}", flush=True)
