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

import json
import sys
from pathlib import Path

import maps_scraper as ms
import website_classifier as wc
import website_qualifier as wq
import lead_prioritizer as lp
import website_generator as wg
import qa_bot as qb
import deployment_manager as dmgr
import current_lead_generator as clg
import email_generator as eg
import response_feedback_manager as rfm
def _require(result, stage: str):
    """Unwrap a bot return: artifact passes through, int exit code raises."""
    if isinstance(result, int):
        raise RuntimeError(f"{stage} failed with exit code {result}")
    return result


def _latest_preview(record_file: str | Path, lid: str) -> str:
    """Return the newest preview_url Bot 7 recorded for lid (or "")."""
    p = Path(record_file)
    if not p.exists():
        return ""
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    records = raw if isinstance(raw, list) else [raw]
    for r in reversed(records):
        if isinstance(r, dict) and r.get("preview_url") and \
                r.get("site", r.get("lead_id")) == lid:
            return str(r["preview_url"])
    return ""


def run(queries: list[str] | None = None, max_per_query: int = 20,
        threshold: int = 60, output_dir: str = "generated_sites",
        force: bool = False, no_opencode: bool = False,
        limit: int = 0, qa_threshold: int = 80,
        max_qa_attempts: int = 5, prod: bool = True,
        current_output: str = "current_leads.json",
        send_emails: bool = False) -> str:
    """Run scrape -> classify -> qualify -> merge -> prioritize -> per-lead loop.

    Per entry: Bot 5 generate -> Bot 6 QA loop ("good") -> Bot 7 deploy
    (GitHub + Vercel production). Bots 8/9 past deployment are commented
    out for now; Bot 10 (replies) is reactive; Bot 11 is a stub.
    Returns target_leads path.
    """
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

    # Bot 4: merge + rank -> target_leads.json
    leads_path = _require(
        lp.main(without=without_path, bad=bad_path, output="target_leads.json"),
        "lead_prioritizer",
    )
    
    # Bot 5: loop through target_leads.json -> generate one site per entry.
    # website_generator.main takes a single entry; looping lives here.
    leads = wg.load_leads(Path(leads_path))
    if limit and limit > 0:
        leads = leads[:limit]
    leads = leads[:1]  # TEMP: first entry only — remove to process all leads
    print(f"[orchestrator] Bot 5+6: generating {len(leads)} site(s)...", flush=True)
    for entry in leads:
        lid = entry.get("lead_id", "?")
        website_path = _require(
            wg.main(lead_data=entry, output_dir=output_dir,
                    force=force, no_opencode=no_opencode),
            "website_generator",
        )

        # Bot 6: loop until QA passes, then print good.
        # Retries force a regenerate so QA re-checks fresh output.
        for attempt in range(1, max_qa_attempts + 1):
            if attempt > 1:
                website_path = _require(
                    wg.main(lead_data=entry, output_dir=output_dir,
                            force=True, no_opencode=no_opencode),
                    "website_generator",
                )
            qa_res = qb.main(website_path, threshold=qa_threshold)
            if isinstance(qa_res, str):
                print(f"[orchestrator] good — {lid} passed QA", flush=True)
                break
            if qa_res == 1:
                print(f"[orchestrator] QA failed for {lid} "
                      f"(attempt {attempt}/{max_qa_attempts}), regenerating...",
                      flush=True)
                continue
            _require(qa_res, "qa_bot")
        else:
            raise RuntimeError(
                f"qa_bot: {lid} still failing QA after {max_qa_attempts} attempts")

        rc = dmgr.main(path_to_file=website_path, prod=prod)
        if rc != 0:
            raise RuntimeError(f"deployment_manager failed for {lid} (exit {rc})")

        # # Bot 8: outreach-ready lead (preview URL from Bot 7's record).
        # # (disabled — pipeline stops at deployment for now)
        # preview_url = _latest_preview("deployments/deployments.json", lid)
        # _require(
        #     clg.main(leads=leads_path, lead=lid, preview_url=preview_url or None,
        #              output=current_output),
        #     "current_lead_generator",
        # )

        # # Bot 9: outreach email (draft unless send_emails=True).
        # # (disabled — pipeline stops at deployment for now)
        # email_res = eg.main(lead=lid, current=current_output, send=send_emails,
        #                     preview_url=preview_url or None)
        # if isinstance(email_res, int):
        #     raise RuntimeError(f"email_generator failed for {lid} (exit {email_res})")
        # print(f"[orchestrator] email {'sent' if send_emails else 'drafted'} for {lid}",
        #       flush=True)
    return leads_path
     
 
# def handle_reply(incoming: str, lead: str | None = None,
#                  leads: str = "target_leads.json",
#                  output_dir: str = "generated_sites",
#                  no_opencode: bool = False,
#                  qa_threshold: int = 80,
#                  max_qa_attempts: int = 5,
#                  prod: bool = False,
#                  current_output: str = "current_leads.json",
#                  send_emails: bool = False) -> dict:
#     """Handle one inbound client reply (Bot 10) and route it.
# 
#     - revision request → Bot 5 rebuild with feedback → Bot 6 QA loop →
#       Bot 7 redeploy → Bot 8 refresh → Bot 9 revision-delivery email.
#     - anything else → classified feedback dict (sales/human handles it).
#     Returns the feedback dict.
#     (disabled — pipeline stops at deployment for now)
#     """
#     fb_path = f"feedback_{lead}.json" if lead else "feedback.json"
#     fb_res = rfm.main(incoming=incoming, lead=lead, output=fb_path, record=True)
#     feedback = _require(fb_res, "response_feedback_manager")
#     if not isinstance(feedback, dict):
#         feedback = json.loads(Path(fb_path).read_text(encoding="utf-8"))
#     print(f"[orchestrator] reply: {feedback['lead_id']}: "
#           f"{feedback['response_type']} -> {feedback['action']}", flush=True)
#     if feedback.get("action") != "website_revision":
#         return feedback  # sales / human review route — nothing to rebuild
# 
#     lid = feedback["lead_id"]
#     raw = json.loads(Path(leads).read_text(encoding="utf-8"))
#     items = raw if isinstance(raw, list) else raw.get("leads", [])
#     entry = next((e for e in items
#                   if isinstance(e, dict) and e.get("lead_id") == lid), None)
#     if entry is None:
#         raise RuntimeError(f"handle_reply: {lid} not in {leads}")
# 
#     site = _require(
#         wg.main(lead_data=entry, output_dir=output_dir, force=True,
#                 no_opencode=no_opencode, feedback=feedback),
#         "website_generator",
#     )
#     for attempt in range(1, max_qa_attempts + 1):
#         qa_res = qb.main(site, threshold=qa_threshold)
#         if isinstance(qa_res, str):
#             print(f"[orchestrator] good — {lid} revision passed QA", flush=True)
#             break
#         if qa_res == 1:
#             print(f"[orchestrator] revision QA failed for {lid} "
#                   f"(attempt {attempt}/{max_qa_attempts}), regenerating...", flush=True)
#             site = _require(
#                 wg.main(lead_data=entry, output_dir=output_dir, force=True,
#                         no_opencode=no_opencode, feedback=feedback),
#                 "website_generator",
#             )
#             continue
#         _require(qa_res, "qa_bot")
#     else:
#         raise RuntimeError(
#             f"qa_bot: {lid} revision still failing after {max_qa_attempts} attempts")
# 
#     rc = dmgr.main(path_to_file=site, prod=prod)
#     if rc != 0:
#         raise RuntimeError(f"deployment_manager failed for {lid} (exit {rc})")
#     preview_url = _latest_preview("deployments/deployments.json", lid)
#     _require(
#         clg.main(leads=leads, lead=lid, preview_url=preview_url or None,
#                  output=current_output),
#         "current_lead_generator",
#     )
#     email_res = eg.main(lead=lid, current=current_output, send=send_emails,
#                         preview_url=preview_url or None,
#                         purpose="revision_delivery")
#     if isinstance(email_res, int):
#         raise RuntimeError(f"email_generator failed for {lid} (exit {email_res})")
#     return feedback


if __name__ == "__main__":
    try:
        final = run()
    except RuntimeError as e:
        print(f"[orchestrator] ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"[orchestrator] done -> {final}", flush=True)
