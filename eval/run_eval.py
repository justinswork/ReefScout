"""
run_eval.py — ReefScout's evaluation harness (rubric #13).

Definition of "good", made executable:
  1. AGENTIC CORRECTNESS — the model calls the *right tools* for each question type
     (and skips tools that aren't needed). Asserted on the tool-call trace.
  2. GROUNDED ANSWERS — concrete claims come from tool data: relative dates resolve to
     real calendar dates, verdicts lead the answer, both unit systems appear.
  3. HONESTY AT THE EDGES — out-of-range IDs get verified and hedged, not asserted;
     off-topic requests are declined without burning tool calls.

Each case sends one message through the real agent (live APIs + live model) and applies
declarative checks. Failures are recorded, not hidden — a failed case is a finding.

Run:  python -m eval.run_eval            (all cases)
      python -m eval.run_eval planning_basic id_out_of_range   (subset by id)

Writes eval/results/results_<date>.json (gitignored raw) and eval/RESULTS.md (committed).
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.agent import ReefScoutAgent  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_MD = Path(__file__).resolve().parent / "RESULTS.md"

TOMORROW = (date.today() + timedelta(days=1)).isoformat()

# ---------------------------------------------------------------------------------
# Check engine — small, declarative, readable in the results report.
# A check is (kind, *params). All checks must pass unless wrapped in any_of.
# ---------------------------------------------------------------------------------

def _tools_called(trace: list[dict]) -> list[str]:
    return [t["tool"] for t in trace]


def run_check(check: tuple, reply: str, trace: list[dict]) -> tuple[bool, str]:
    kind = check[0]
    tools = _tools_called(trace)

    if kind == "tools_include":
        missing = [t for t in check[1] if t not in tools]
        return (not missing, f"tools_include {check[1]}" + (f" — missing {missing}" if missing else ""))
    if kind == "tools_exclude":
        present = [t for t in check[1] if t in tools]
        return (not present, f"tools_exclude {check[1]}" + (f" — unexpectedly called {present}" if present else ""))
    if kind == "no_tools":
        return (len(tools) == 0, f"no_tools — called {tools}" if tools else "no_tools")
    if kind == "tool_arg_matches":
        _, tool, key, pattern = check
        for t in trace:
            if t["tool"] == tool and re.search(pattern, str(t["args"].get(key, ""))):
                return (True, f"tool_arg_matches {tool}.{key} ~ /{pattern}/")
        return (False, f"tool_arg_matches {tool}.{key} ~ /{pattern}/ — no matching call")
    if kind == "reply_matches":
        ok = re.search(check[1], reply, re.IGNORECASE | re.DOTALL) is not None
        return (ok, f"reply ~ /{check[1]}/" + ("" if ok else " — not found"))
    if kind == "reply_not_matches":
        ok = re.search(check[1], reply, re.IGNORECASE | re.DOTALL) is None
        return (ok, f"reply !~ /{check[1]}/" + ("" if ok else " — found"))
    if kind == "max_tool_calls":
        return (len(trace) <= check[1], f"max_tool_calls {check[1]} (got {len(trace)})")
    if kind == "any_of":
        results = [run_check(c, reply, trace) for c in check[1]]
        ok = any(r[0] for r in results)
        return (ok, "any_of(" + " | ".join(r[1] for r in results) + ")")
    raise ValueError(f"unknown check kind {kind}")


# ---------------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------------

CASES: list[dict] = [
    {
        "id": "planning_basic",
        "why": "Core planning flow: right tool chain, verdict-first format, both unit systems.",
        "message": "Is tomorrow morning good for snorkeling at La Jolla Cove?",
        "checks": [
            ("tools_include", ["geocode_place", "get_marine_conditions", "get_tides"]),
            ("reply_matches", r"^\s*\*\*"),                 # bolded verdict line first
            ("reply_matches", r"°C"), ("reply_matches", r"°F"),  # both unit systems
        ],
    },
    {
        "id": "planning_with_species",
        "why": "Asking what you'll see must trigger the species tool.",
        "message": "What marine life might I see snorkeling at La Jolla this weekend?",
        "checks": [
            ("tools_include", ["geocode_place", "get_species_nearby"]),
        ],
    },
    {
        "id": "tool_economy",
        "why": "A conditions-only question should NOT trigger the species tool (decision in the model).",
        "message": "How big are the waves at Waikiki tomorrow?",
        "checks": [
            ("tools_include", ["geocode_place", "get_marine_conditions"]),
            ("tools_exclude", ["get_species_nearby", "search_marine_taxa"]),
        ],
    },
    {
        "id": "date_grounding",
        "why": "Regression test for the Phase-3 bug: 'tomorrow' must resolve via the injected date.",
        "message": "Will the water be warm at Key Largo tomorrow?",
        "checks": [
            ("tool_arg_matches", "get_marine_conditions", "date", TOMORROW),
        ],
    },
    {
        "id": "id_plausible",
        "why": "ID flow: reason → taxonomy search → location verification for a species that IS local.",
        "message": "I saw a bright orange fish about 30cm long while snorkeling at La Jolla. What was it?",
        "checks": [
            ("any_of", [("tools_include", ["search_marine_taxa"]), ("tools_include", ["get_species_nearby"])]),
            ("reply_matches", r"garibaldi|hypsypops"),       # the obviously-right answer locally
        ],
    },
    {
        "id": "id_out_of_range",
        "why": "The distinctive behavior: a clownfish 'sighting' in California must be verified and challenged, not confirmed.",
        "message": "I'm pretty sure I saw a clownfish like Nemo while snorkeling at La Jolla yesterday. Cool right?",
        "checks": [
            ("any_of", [
                ("tools_include", ["get_species_nearby"]),
                ("tools_include", ["search_marine_taxa"]),
                ("tools_include", ["get_species_detail"]),
            ]),
            ("reply_matches", r"unlikely|not (?:typically|normally|known|found|native)|wouldn'?t expect|out(?:side)? (?:of )?(?:its |their )?(?:known |native )?range|no (?:recorded|local) (?:sightings|observations)|aren'?t (?:found|native)|garibaldi"),
        ],
    },
    {
        "id": "off_topic",
        "why": "Scope guard: non-marine request → decline in one sentence, zero tool spend.",
        "message": "Can you help me write a cover letter for a software job?",
        "checks": [
            ("no_tools",),
            ("reply_matches", r"marine|ocean|snorkel|scope|can'?t help|only help"),
        ],
    },
    {
        "id": "sparse_data_honesty",
        "why": "Remote, data-poor location: must be honest about tide-station distance / data gaps, not fake precision.",
        "message": "Is it a good day to snorkel near Toliara, Madagascar?",
        "checks": [
            ("tools_include", ["geocode_place", "get_marine_conditions"]),
            ("any_of", [
                ("reply_matches", r"tide (?:data|station|prediction)s? (?:is|are)? ?(?:unavailable|not available|too far|unreliable)|no (?:nearby|reliable) tide|tide.{0,80}(?:US|United States|NOAA)|(?:can'?t|cannot|unable to).{0,40}tide"),
                ("tools_exclude", ["get_tides"]),
            ]),
        ],
    },
]

# ---------------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------------

async def run(case_filter: set[str] | None) -> int:
    cases = [c for c in CASES if not case_filter or c["id"] in case_filter]
    agent = ReefScoutAgent()
    await agent.start()
    results = []
    try:
        for case in cases:
            print(f"\n=== {case['id']} ===")
            started = time.perf_counter()
            try:
                out = await agent.run(case["message"])
                reply, trace, usage = out["reply"], out["trace"], out.get("usage", {})
                error = None
            except Exception as exc:  # noqa: BLE001
                reply, trace, usage, error = "", [], {}, str(exc)
            latency_s = round(time.perf_counter() - started, 1)

            checks = []
            for check in case["checks"]:
                ok, desc = run_check(check, reply, trace) if not error else (False, f"{check[0]} — agent error")
                checks.append({"ok": ok, "desc": desc})
                print(f"  {'PASS' if ok else 'FAIL'}  {desc}")
            passed = all(c["ok"] for c in checks) and not error

            results.append({
                "id": case["id"], "why": case["why"], "message": case["message"],
                "passed": passed, "latency_s": latency_s, "error": error,
                "tools_called": _tools_called(trace), "checks": checks,
                "usage": usage, "reply": reply, "trace": trace,
            })
            print(f"  -> {'PASS' if passed else 'FAIL'} in {latency_s}s, tools: {_tools_called(trace)}")
    finally:
        await agent.stop()

    _write_reports(results, partial=bool(case_filter))
    n_pass = sum(r["passed"] for r in results)
    print(f"\n{'='*50}\n{n_pass}/{len(results)} cases passed")
    return 0 if n_pass == len(results) else 1


def _write_reports(results: list[dict], partial: bool) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = date.today().isoformat()
    raw_path = RESULTS_DIR / f"results_{stamp}.json"
    raw_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nraw results -> {raw_path}")

    if partial:  # don't overwrite the committed report from a subset run
        return
    lines = [
        "# Eval Results", "",
        f"Latest full run: **{stamp}** — {sum(r['passed'] for r in results)}/{len(results)} passed. ",
        "Raw transcripts (replies + full traces) in `eval/results/` (local, gitignored). ",
        "Case definitions and the check engine live in `eval/run_eval.py`.", "",
        "| Case | Why it matters | Result | Latency | Tools called |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        status = "✅ pass" if r["passed"] else "❌ **fail**"
        lines.append(f"| `{r['id']}` | {r['why']} | {status} | {r['latency_s']}s | {', '.join(r['tools_called']) or '—'} |")
    lines.append("")
    failed = [r for r in results if not r["passed"]]
    if failed:
        lines.append("## Failures (kept honest)")
        for r in failed:
            lines.append(f"\n### `{r['id']}`")
            if r["error"]:
                lines.append(f"- agent error: `{r['error']}`")
            for c in r["checks"]:
                if not c["ok"]:
                    lines.append(f"- failed check: `{c['desc']}`")
            lines.append(f"- reply excerpt: > {r['reply'][:300]}")
    RESULTS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report      -> {RESULTS_MD}")


if __name__ == "__main__":
    sys.exit(asyncio.run(run(set(sys.argv[1:]) or None)))
