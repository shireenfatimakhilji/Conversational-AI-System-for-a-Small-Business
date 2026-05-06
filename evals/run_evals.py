# eval/run_evals.py
"""
Master evaluation runner — runs all evaluations in sequence.
Usage: python eval/run_evals.py

Runs:
  1.  Retrieval evaluation        (Precision@k & Recall@k)
  2.  Faithfulness evaluation     (LLM-as-Judge)
  3.  Conversation evaluation     (Multi-turn dialogues)
  4.  Performance evaluation      (Latency + Throughput)
  5.  CRM unit tests              (direct CRUD + validation)
  6.  Calculator unit tests       (arithmetic + precision)
  7.  Calendar unit tests         (date calculation + edge cases)
  8.  Weather unit tests          (demo mode + risk assessment)
  9.  Failure mode tests          (timeouts, empty DB, malformed calls)
  10. LLM tool-invocation accuracy (requires Ollama)
"""

import sys
import os
import json
import time
import asyncio
import platform
import importlib.metadata
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EVALS_DIR   = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(EVALS_DIR, "results")


# ============================================================================
# Helpers
# ============================================================================

def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_section(title: str):
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print('-' * 60)


# ============================================================================
# Step 1: Retrieval
# ============================================================================

def run_retrieval_eval():
    print_section("STEP 1 -- RETRIEVAL EVALUATION (Precision@k & Recall@k)")
    start = time.time()
    try:
        from evals.eval_retrieval import run_retrieval_eval as _run
        _run()
        print(f"\n  [PASSED] Retrieval eval completed in {time.time() - start:.1f}s")
        return True
    except Exception as e:
        print(f"\n  [FAILED] Retrieval eval: {e}")
        return False


# ============================================================================
# Step 2: Faithfulness
# ============================================================================

def run_faithfulness_eval():
    print_section("STEP 2 -- FAITHFULNESS EVALUATION (LLM-as-Judge)")
    start = time.time()
    try:
        from evals.eval_faithfulness import run_faithfulness_eval as _run
        _run()
        print(f"\n  [PASSED] Faithfulness eval completed in {time.time() - start:.1f}s")
        return True
    except Exception as e:
        print(f"\n  [FAILED] Faithfulness eval: {e}")
        return False


# ============================================================================
# Step 3: Conversations
# ============================================================================

def run_conversation_eval():
    print_section("STEP 3 -- CONVERSATION EVALUATION (Multi-turn Dialogues)")
    start = time.time()
    try:
        from evals.eval_conversations import run_conversation_eval as _run
        _run()
        print(f"\n  [PASSED] Conversation eval completed in {time.time() - start:.1f}s")
        return True
    except Exception as e:
        print(f"\n  [FAILED] Conversation eval: {e}")
        return False


# ============================================================================
# Step 4: Performance (Latency + Throughput)
# ============================================================================

def run_performance_eval():
    print_section("STEP 4 -- PERFORMANCE EVALUATION (Latency + Throughput)")
    start = time.time()
    try:
        if EVALS_DIR not in sys.path:
            sys.path.insert(0, EVALS_DIR)

        from latency    import run_all_latency_scenarios
        from throughput import run_throughput_test
        from utils      import check_thresholds

        print("\n  Running latency scenarios (10 trials each)...")
        latency_results = asyncio.run(run_all_latency_scenarios(trials=10))

        print("\n  Running throughput ramp-up (up to 8 concurrent users)...")
        throughput_result = asyncio.run(run_throughput_test(levels=[1, 2, 4, 6, 8]))

        violations = []
        for result in latency_results.values():
            violations.extend(check_thresholds(result))

        os.makedirs(RESULTS_DIR, exist_ok=True)
        perf_data = {
            "latency":              {k: v.to_dict() for k, v in latency_results.items()},
            "throughput":           throughput_result.to_dict(),
            "threshold_violations": violations,
        }
        with open(os.path.join(RESULTS_DIR, "performance_metrics.json"), "w") as f:
            json.dump(perf_data, f, indent=2)
        print("  Results saved to eval/results/performance_metrics.json")
        print(f"\n  [PASSED] Performance eval completed in {time.time() - start:.1f}s")
        return True, perf_data

    except Exception as e:
        import traceback
        print(f"\n  [FAILED] Performance eval: {e}")
        traceback.print_exc()
        return False, None


# ============================================================================
# Step 5: CRM unit tests
# ============================================================================

def run_crm_tests() -> dict:
    print_section("STEP 5 -- CRM UNIT TESTS")
    t0 = time.time()
    try:
        from evals.test_crm_unit import run_crm_unit_tests
        result = run_crm_unit_tests()
        result["elapsed_s"] = round(time.time() - t0, 2)
        status = "[PASSED]" if result["passed"] else "[FAILED]"
        print(f"\n  {status} -- {result['total']} tests in {result['elapsed_s']:.1f}s")
        return result
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"passed": False, "error": str(exc), "total": 0,
                "elapsed_s": round(time.time() - t0, 2)}


# ============================================================================
# Step 6: Calculator unit tests
# ============================================================================

def run_calculator_tests() -> dict:
    print_section("STEP 6 -- CALCULATOR UNIT TESTS")
    t0 = time.time()
    try:
        from evals.test_calculator_unit import run_calculator_unit_tests
        result = run_calculator_unit_tests()
        result["elapsed_s"] = round(time.time() - t0, 2)
        status = "[PASSED]" if result["passed"] else "[FAILED]"
        print(f"\n  {status} -- {result['total']} tests in {result['elapsed_s']:.1f}s")
        return result
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"passed": False, "error": str(exc), "total": 0,
                "elapsed_s": round(time.time() - t0, 2)}


# ============================================================================
# Step 7: Calendar unit tests
# ============================================================================

def run_calendar_tests() -> dict:
    print_section("STEP 7 -- CALENDAR UNIT TESTS")
    t0 = time.time()
    try:
        from evals.test_calendar_unit import run_calendar_unit_tests
        result = run_calendar_unit_tests()
        result["elapsed_s"] = round(time.time() - t0, 2)
        status = "[PASSED]" if result["passed"] else "[FAILED]"
        print(f"\n  {status} -- {result['total']} tests in {result['elapsed_s']:.1f}s")
        return result
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"passed": False, "error": str(exc), "total": 0,
                "elapsed_s": round(time.time() - t0, 2)}


# ============================================================================
# Step 8: Weather unit tests
# ============================================================================

def run_weather_tests() -> dict:
    print_section("STEP 8 -- WEATHER UNIT TESTS")
    t0 = time.time()
    try:
        from evals.test_weather_unit import run_weather_unit_tests
        result = run_weather_unit_tests()
        result["elapsed_s"] = round(time.time() - t0, 2)
        status = "[PASSED]" if result["passed"] else "[FAILED]"
        print(f"\n  {status} -- {result['total']} tests in {result['elapsed_s']:.1f}s")
        return result
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"passed": False, "error": str(exc), "total": 0,
                "elapsed_s": round(time.time() - t0, 2)}


# ============================================================================
# Step 9: Failure mode tests
# ============================================================================

def run_failure_tests() -> dict:
    print_section("STEP 9 -- FAILURE MODE TESTS")
    t0 = time.time()
    try:
        from evals.test_failure_modes import run_failure_mode_tests
        result = run_failure_mode_tests()
        result["elapsed_s"] = round(time.time() - t0, 2)
        status = "[PASSED]" if result["passed"] else "[FAILED]"
        print(f"\n  {status} -- {result['total']} tests in {result['elapsed_s']:.1f}s")
        return result
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"passed": False, "error": str(exc), "total": 0,
                "elapsed_s": round(time.time() - t0, 2)}


# ============================================================================
# Step 10: LLM tool-invocation accuracy
# ============================================================================

def run_llm_tool_tests() -> dict:
    print_section("STEP 10 -- LLM TOOL-INVOCATION ACCURACY")
    print("  [NOTE] Requires Ollama running locally. Skipped if unavailable.")
    t0 = time.time()
    try:
        import ollama
        from evals.test_llm_tool_invocation import run_llm_invocation_eval
        result = run_llm_invocation_eval()
        result["elapsed_s"] = round(time.time() - t0, 2)
        result["passed"] = result.get("overall_accuracy", 0) >= 0.50
        status = "[PASSED]" if result["passed"] else "[LOW ACCURACY]"
        acc = result.get("overall_accuracy", 0)
        print(f"\n  {status} -- Overall accuracy: {acc:.0%} in {result['elapsed_s']:.1f}s")
        return result
    except ImportError:
        print("  [SKIP] Ollama not installed.")
        return {"passed": None, "skipped": True, "reason": "ollama not installed",
                "elapsed_s": round(time.time() - t0, 2)}
    except Exception as exc:
        print(f"  [SKIP] {exc}")
        return {"passed": None, "skipped": True, "reason": str(exc),
                "elapsed_s": round(time.time() - t0, 2)}


# ============================================================================
# Hardware + dependency snapshot (for report)
# ============================================================================

def _collect_environment() -> dict:
    """Collect Python version, OS, and key dependency versions for the report."""
    packages = [
        "fastapi", "uvicorn", "ollama", "chromadb",
        "sentence-transformers", "transformers", "torch",
        "numpy", "aiohttp", "openai-whisper",
    ]
    deps = {}
    for pkg in packages:
        try:
            deps[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            deps[pkg] = "not installed"

    return {
        "python":       sys.version,
        "platform":     platform.platform(),
        "processor":    platform.processor() or "unknown",
        "dependencies": deps,
    }


# ============================================================================
# Final report
# ============================================================================

def generate_final_report(
    results:      dict,
    tool_results: dict,
    perf_data:    dict | None,
    env:          dict,
    total_elapsed_s: float,
):
    print_header("FINAL EVALUATION REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    report = {
        "generated_at":    datetime.now().isoformat(),
        "total_time_s":    round(total_elapsed_s, 1),
        "environment":     env,
        "modules_run":     results,
        "tool_evals":      tool_results,
        "summary":         {},
        "failures_log":    [],
        "scenario_comparison": {},
    }

    # ── Retrieval ──────────────────────────────────────────────────────────
    retrieval_path = os.path.join(RESULTS_DIR, "retrieval_metrics.json")
    if os.path.exists(retrieval_path):
        with open(retrieval_path) as f:
            r = json.load(f)
        report["summary"]["retrieval"] = {
            "avg_precision_at_k": r.get("avg_precision_at_k"),
            "avg_recall_at_k":    r.get("avg_recall_at_k"),
            "total_queries":      r.get("total_queries"),
            "hits":               r.get("hits"),
            "top_k":              r.get("top_k"),
        }
        print(f"  RETRIEVAL METRICS")
        print(f"    Avg Precision@{r.get('top_k')}: {r.get('avg_precision_at_k', 0):.3f}")
        print(f"    Avg Recall@{r.get('top_k')}:    {r.get('avg_recall_at_k', 0):.3f}")
        print(f"    Queries with hits: {r.get('hits')}/{r.get('total_queries')}")
    else:
        print("  RETRIEVAL METRICS: not found (eval may have failed)")
        report["failures_log"].append("retrieval_metrics.json not generated")

    # ── Faithfulness ───────────────────────────────────────────────────────
    faithful_path = os.path.join(RESULTS_DIR, "faithfulness_metrics.json")
    if os.path.exists(faithful_path):
        with open(faithful_path) as f:
            fd = json.load(f)
        report["summary"]["faithfulness"] = {
            "avg_faithfulness_score": fd.get("avg_faithfulness_score"),
            "queries_evaluated":      fd.get("queries_evaluated"),
        }
        print(f"\n  FAITHFULNESS METRICS")
        print(f"    Avg Faithfulness: {fd.get('avg_faithfulness_score', 0):.2f}/5")
        print(f"    Queries evaluated: {fd.get('queries_evaluated')}")
    else:
        print("\n  FAITHFULNESS METRICS: not found (eval may have failed)")
        report["failures_log"].append("faithfulness_metrics.json not generated")

    # ── Conversations ──────────────────────────────────────────────────────
    convo_path = os.path.join(RESULTS_DIR, "conversation_metrics.json")
    if os.path.exists(convo_path):
        with open(convo_path) as f:
            c = json.load(f)
        report["summary"]["conversations"] = {
            "avg_task_completion":  c.get("avg_task_completion"),
            "avg_coherence":        c.get("avg_coherence"),
            "avg_policy_adherence": c.get("avg_policy_adherence"),
            "avg_overall":          c.get("avg_overall"),
            "total_dialogues":      c.get("total_dialogues"),
            "successful":           c.get("successful"),
        }
        print(f"\n  CONVERSATION METRICS")
        print(f"    Avg Task Completion:  {c.get('avg_task_completion', 0):.2f}/5")
        print(f"    Avg Coherence:        {c.get('avg_coherence', 0):.2f}/5")
        print(f"    Avg Policy Adherence: {c.get('avg_policy_adherence', 0):.2f}/5")
        print(f"    Avg Overall:          {c.get('avg_overall', 0):.2f}/5")
        print(f"    Dialogues: {c.get('successful')}/{c.get('total_dialogues')} successful")
    else:
        print("\n  CONVERSATION METRICS: not found (eval may have failed)")
        report["failures_log"].append("conversation_metrics.json not generated")

    # ── Performance ────────────────────────────────────────────────────────
    perf_path = os.path.join(RESULTS_DIR, "performance_metrics.json")
    if os.path.exists(perf_path):
        with open(perf_path) as f:
            p = json.load(f)
        tput = p.get("throughput", {})
        lat  = p.get("latency", {})
        report["summary"]["performance"] = {
            "max_concurrency":      tput.get("max_concurrency"),
            "breakpoint":           tput.get("breakpoint"),
            "peak_turns_per_sec":   tput.get("peak_turns_per_sec"),
            "threshold_violations": p.get("threshold_violations", []),
            "latency_by_scenario":  {
                k: {
                    "ttft_median": v.get("ttft", {}).get("median"),
                    "e2e_median":  v.get("end_to_end", {}).get("median"),
                }
                for k, v in lat.items()
            },
        }
        print(f"\n  PERFORMANCE METRICS")
        print(f"    Max sustainable concurrency: {tput.get('max_concurrency')}")
        bp = tput.get("breakpoint")
        print(f"    Breakpoint: {bp if bp else 'not reached'}")
        print(f"    Peak throughput: {tput.get('peak_turns_per_sec', 0):.2f} turns/s")

        # Scenario comparison table (RAG vs no-RAG, tool vs no-tool)
        if lat:
            print(f"\n  SCENARIO COMPARISON (median latency)")
            print(f"    {'Scenario':<10}  {'TTFT (s)':>10}  {'E2E (s)':>10}")
            print(f"    {'-'*36}")
            for scenario, metrics in lat.items():
                ttft = metrics.get("ttft", {}).get("median", 0)
                e2e  = metrics.get("end_to_end", {}).get("median", 0)
                print(f"    {scenario:<10}  {ttft:>10.3f}  {e2e:>10.3f}")
            report["scenario_comparison"] = {
                "description": (
                    "simple=no RAG no tool, rag=RAG only, "
                    "tool=tool only, mixed=RAG+tool"
                ),
                "latency": {
                    k: {
                        "ttft_median": v.get("ttft", {}).get("median"),
                        "e2e_median":  v.get("end_to_end", {}).get("median"),
                    }
                    for k, v in lat.items()
                },
            }

        violations = p.get("threshold_violations", [])
        if violations:
            print(f"\n    {len(violations)} threshold violation(s):")
            for v in violations:
                print(f"      - {v}")
            report["failures_log"].extend(violations)
        else:
            print("    All latency thresholds passed")
    else:
        print("\n  PERFORMANCE METRICS: not found (eval may have failed)")
        report["failures_log"].append("performance_metrics.json not generated")

    # ── Tool unit test summary ─────────────────────────────────────────────
    print(f"\n  TOOL UNIT TEST RESULTS")
    tool_step_names = {
        "crm":        "CRM Unit Tests",
        "calculator": "Calculator Unit Tests",
        "calendar":   "Calendar Unit Tests",
        "weather":    "Weather Unit Tests",
        "failures":   "Failure Mode Tests",
        "llm":        "LLM Tool-Invocation Accuracy",
    }
    tool_summary = {}
    for key, name in tool_step_names.items():
        r = tool_results.get(key, {})
        if r.get("skipped"):
            print(f"    [SKIP]   {name} ({r.get('reason', '')})")
            tool_summary[key] = {"status": "skipped", "reason": r.get("reason")}
            continue
        passed = r.get("passed")
        if passed is None:
            print(f"    [SKIP]   {name}")
            tool_summary[key] = {"status": "skipped"}
            continue
        total    = r.get("total", "?")
        elapsed  = r.get("elapsed_s", 0)
        failures = r.get("failures", 0) + r.get("errors", 0)
        if passed:
            print(f"    [PASSED] {name} ({total} tests, {elapsed:.1f}s)")
            tool_summary[key] = {"status": "passed", "total": total, "elapsed_s": elapsed}
        else:
            print(f"    [FAILED] {name} ({failures}/{total} failed, {elapsed:.1f}s)")
            tool_summary[key] = {"status": "failed", "total": total,
                                 "failures": failures, "elapsed_s": elapsed}
            report["failures_log"].append(
                f"{name}: {failures}/{total} tests failed"
            )

    report["summary"]["tool_unit_tests"] = tool_summary

    # LLM accuracy breakdown
    llm = tool_results.get("llm", {})
    if not llm.get("skipped") and llm.get("overall_accuracy") is not None:
        print(f"\n    LLM Accuracy: {llm['overall_accuracy']:.0%} overall")
        for cat, stats in llm.get("by_category", {}).items():
            print(f"      {cat:12s}: {stats['correct']}/{stats['total']} "
                  f"({stats['accuracy']:.0%})")

    # ── Module pass/fail summary ───────────────────────────────────────────
    print(f"\n  MODULE STATUS")
    for module, passed in results.items():
        status = "[PASSED]" if passed else "[FAILED]"
        print(f"    {status} {module}")
        if not passed:
            report["failures_log"].append(f"Module {module} failed")

    # ── Environment info ───────────────────────────────────────────────────
    print(f"\n  ENVIRONMENT")
    print(f"    Python  : {env['python'].split()[0]}")
    print(f"    OS      : {env['platform']}")
    print(f"    CPU     : {env['processor']}")
    print(f"    Key deps:")
    for pkg in ["chromadb", "sentence-transformers", "torch", "ollama"]:
        print(f"      {pkg}: {env['dependencies'].get(pkg, 'unknown')}")

    # ── Total time ─────────────────────────────────────────────────────────
    print(f"\n  Total evaluation time: {total_elapsed_s/60:.1f} minutes")

    # ── Save combined report ───────────────────────────────────────────────
    os.makedirs(RESULTS_DIR, exist_ok=True)
    report_path = os.path.join(RESULTS_DIR, "full_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  [SAVED] Full report -> {report_path}")
    print("=" * 60)


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    total_start = time.time()

    print_header("CROCHETZIES -- AUTOMATED EVALUATION SUITE")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n  This will run 10 evaluations in sequence:")
    print("    1.  Retrieval             (~30 seconds)")
    print("    2.  Faithfulness          (~5 minutes)")
    print("    3.  Conversations         (~60 minutes)")
    print("    4.  Performance           (~30 minutes)")
    print("    5.  CRM unit tests        (~2 seconds)")
    print("    6.  Calculator unit tests (~1 second)")
    print("    7.  Calendar unit tests   (~1 second)")
    print("    8.  Weather unit tests    (~1 second)")
    print("    9.  Failure mode tests    (~2 seconds)")
    print("    10. LLM tool-invocation   (~3 minutes, needs Ollama)")
    print("\n  Make sure the chatbot server is running:")
    print("    python -m uvicorn api:app")
    print("\n  Do not close this window.\n")

    # Collect environment info once at start
    env = _collect_environment()

    # Performance runs first (needs the server)
    perf_ok, perf_data = run_performance_eval()

    # RAG + LLM quality evals
    results = {
        "eval_retrieval":     run_retrieval_eval(),
        "eval_faithfulness":  run_faithfulness_eval(),
        "eval_conversations": run_conversation_eval(),
        "eval_performance":   perf_ok,
    }

    # Tool unit tests (fast, no server needed)
    tool_results = {
        "crm":        run_crm_tests(),
        "calculator": run_calculator_tests(),
        "calendar":   run_calendar_tests(),
        "weather":    run_weather_tests(),
        "failures":   run_failure_tests(),
        "llm":        run_llm_tool_tests(),
    }

    total_elapsed = time.time() - total_start
    print(f"\n  Total time: {total_elapsed / 60:.1f} minutes")

    generate_final_report(results, tool_results, perf_data, env, total_elapsed)