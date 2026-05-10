"""
Benchmark runner — 1,000 referrals through the real intake agent.
Uses real Claude Sonnet API. Skips email sending and outbound calls.

Run: python benchmark_1000.py [--workers 20] [--limit 1000]
"""
import os
import sys
import json
import time
import datetime
import threading
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Import agent modules
from intake_agent import load_pdfs, extract_fields, check_completeness, draft_outreach_email, save_episode

REFERRALS_DIR = Path(__file__).parent / "referrals" / "benchmark_1000"
RESULTS_FILE  = Path(__file__).parent / "output" / "benchmark_results.json"
REPORT_FILE   = Path(__file__).parent / "output" / "benchmark_report.md"

# Thread-safe counters
_lock = threading.Lock()
_stats = {
    "done": 0, "errors": 0, "gaps": 0, "outreach_drafted": 0,
    "icd_conflicts": 0, "escalations": 0,
    "timings": [],   # list of per-referral seconds
    "start_time": None,
}


def process_one(folder: Path) -> dict:
    t0 = time.time()
    result = {
        "claim": folder.name,
        "status": "error",
        "elapsed_sec": 0,
        "gaps": [],
        "icd_conflict": False,
        "escalate": False,
        "error": None,
    }
    try:
        # Module 1: Load PDFs
        docs = load_pdfs(str(folder))
        if not docs:
            raise ValueError("No PDFs found")

        # Module 2: Extract + intelligence (real Claude Sonnet call)
        fields = extract_fields(docs, claim_number=folder.name)

        # Module 3: Completeness check
        completeness = check_completeness(fields)

        # Module 4: Draft outreach email (real Claude call) — only if gaps
        email_body = ""
        if not completeness["is_complete"]:
            email_body = draft_outreach_email(fields, completeness)

        # Module 5: Save episode (no email send, no outbound call)
        save_episode(fields, completeness, email_body, email_sent=False, folder=str(folder))

        elapsed = time.time() - t0
        result.update({
            "status": "ok",
            "elapsed_sec": round(elapsed, 2),
            "gaps": list(completeness["gaps"].keys()),
            "icd_conflict": bool(fields.get("icd_conflict")),
            "escalate": bool(fields.get("escalate")),
        })

    except Exception as e:
        result["elapsed_sec"] = round(time.time() - t0, 2)
        result["error"] = str(e)

    return result


def update_stats(result: dict):
    with _lock:
        _stats["done"] += 1
        if result["status"] == "ok":
            _stats["timings"].append(result["elapsed_sec"])
            if result["gaps"]:
                _stats["gaps"] += len(result["gaps"])
                _stats["outreach_drafted"] += 1
            if result["icd_conflict"]:
                _stats["icd_conflicts"] += 1
            if result["escalate"]:
                _stats["escalations"] += 1
        else:
            _stats["errors"] += 1


def print_progress(total: int):
    elapsed = time.time() - _stats["start_time"]
    done = _stats["done"]
    pct  = 100 * done // total
    rate = done / elapsed if elapsed > 0 else 0
    eta  = (total - done) / rate if rate > 0 else 0
    avg  = sum(_stats["timings"]) / len(_stats["timings"]) if _stats["timings"] else 0
    bar  = "#" * (pct // 4) + "-" * (25 - pct // 4)
    try:
        print(
            f"\r  [{bar}] {pct:3d}%  {done}/{total}  "
            f"rate={rate:.1f}/s  avg={avg:.1f}s/ref  ETA={eta:.0f}s  "
            f"gaps={_stats['gaps']}  errors={_stats['errors']}",
            end="", flush=True
        )
    except UnicodeEncodeError:
        pass


def save_results(results: list, total: int, wall_time: float):
    timings = [r["elapsed_sec"] for r in results if r["status"] == "ok"]
    timings_sorted = sorted(timings)
    p50 = timings_sorted[len(timings_sorted)//2] if timings_sorted else 0
    p95 = timings_sorted[int(len(timings_sorted)*0.95)] if timings_sorted else 0
    avg = sum(timings)/len(timings) if timings else 0

    projection_10k = (wall_time / total) * 10000 if total > 0 else 0

    summary = {
        "run_date": datetime.datetime.now().isoformat(),
        "model": "claude-sonnet-4-6",
        "total_referrals": total,
        "workers": args.workers,
        "wall_time_sec": round(wall_time, 1),
        "wall_time_min": round(wall_time/60, 2),
        "avg_per_referral_sec": round(avg, 2),
        "p50_sec": round(p50, 2),
        "p95_sec": round(p95, 2),
        "success": len(timings),
        "errors": _stats["errors"],
        "total_gaps": _stats["gaps"],
        "outreach_drafted": _stats["outreach_drafted"],
        "icd_conflicts": _stats["icd_conflicts"],
        "escalations": _stats["escalations"],
        "projection_10k_min": round(projection_10k/60, 1),
        "results": results,
    }

    RESULTS_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Markdown report
    lines = [
        "# Benchmark Report — 1,000 Referrals · Real Agent · Claude Sonnet",
        f"**Run:** {summary['run_date']}",
        f"**Model:** {summary['model']}",
        "",
        "## Results",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total referrals processed | {summary['total_referrals']} |",
        f"| Parallel workers | {summary['workers']} |",
        f"| **Total wall-clock time** | **{summary['wall_time_min']} min ({summary['wall_time_sec']} sec)** |",
        f"| Avg per referral | {summary['avg_per_referral_sec']} sec |",
        f"| P50 latency | {summary['p50_sec']} sec |",
        f"| P95 latency | {summary['p95_sec']} sec |",
        f"| Successful | {summary['success']} |",
        f"| Errors | {summary['errors']} |",
        "",
        "## What the Agent Found",
        "",
        f"| | Count |",
        f"|---|---|",
        f"| Total gaps detected | {summary['total_gaps']} |",
        f"| Referrals with outreach drafted | {summary['outreach_drafted']} |",
        f"| ICD-10 conflicts caught | {summary['icd_conflicts']} |",
        f"| Escalated to human review | {summary['escalations']} |",
        "",
        "## Scale Projection",
        "",
        f"At this measured throughput:",
        f"- **10,000 referrals → ~{summary['projection_10k_min']} minutes**",
        f"- Rate: {round(total/wall_time*60, 0):.0f} referrals/minute",
        f"- 0 staff hours · fully automated",
        "",
        f"*Based on {summary['workers']} parallel workers · real Claude Sonnet API · real PDF extraction*",
    ]

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    return summary


def main():
    folders = sorted(REFERRALS_DIR.iterdir())
    folders = [f for f in folders if f.is_dir()]

    if not folders:
        print(f"ERROR: No referral folders found in {REFERRALS_DIR}")
        print("Run: python generate_1000_referrals.py first")
        sys.exit(1)

    if args.limit:
        folders = folders[:args.limit]

    total = len(folders)
    print(f"\nBenchmark — {total} referrals · {args.workers} workers · claude-sonnet-4-6")
    print(f"Output -> {RESULTS_FILE}\n")

    results = []
    _stats["start_time"] = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one, f): f for f in folders}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            update_stats(result)
            print_progress(total)

    wall_time = time.time() - _stats["start_time"]
    print()  # newline after progress bar

    summary = save_results(results, total, wall_time)

    # Print final summary
    print(f"\n{'='*60}")
    print(f"BENCHMARK COMPLETE")
    print(f"{'='*60}")
    print(f"  Referrals processed : {summary['success']}/{total}")
    print(f"  Wall-clock time     : {summary['wall_time_min']} min  ({summary['wall_time_sec']} sec)")
    print(f"  Avg per referral    : {summary['avg_per_referral_sec']} sec")
    print(f"  P50 / P95           : {summary['p50_sec']}s / {summary['p95_sec']}s")
    print(f"  Gaps detected       : {summary['total_gaps']}")
    print(f"  Outreach drafted    : {summary['outreach_drafted']}")
    print(f"  ICD conflicts       : {summary['icd_conflicts']}")
    print(f"  Escalations         : {summary['escalations']}")
    print(f"  Errors              : {summary['errors']}")
    print(f"\n  10,000 projection   : ~{summary['projection_10k_min']} min")
    print(f"\n  Full results -> {RESULTS_FILE}")
    print(f"  Report       -> {REPORT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=20, help="Parallel workers (default: 20)")
    parser.add_argument("--limit", type=int, default=0, help="Process only N referrals (default: all)")
    args = parser.parse_args()
    main()
