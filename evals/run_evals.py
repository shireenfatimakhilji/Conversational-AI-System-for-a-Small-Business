# eval/run_evals.py
"""
Master evaluation runner — runs all evaluations in sequence.
Usage: python eval/run_evals.py

Runs:
  1. Retrieval evaluation     (Precision@k & Recall@k)
  2. Faithfulness evaluation  (LLM-as-Judge)
  3. Conversation evaluation  (Multi-turn dialogues)
  4. Performance evaluation   (Latency + Throughput)
"""

import sys
import os
import json
import time
import asyncio
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Helpers ───────────────────────────────────────────────────────────────────

def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


# ── Step 1: Retrieval ─────────────────────────────────────────────────────────

def run_retrieval_eval():
    print_section("STEP 1 — RETRIEVAL EVALUATION (Precision@k & Recall@k)")
    start = time.time()
    try:
        from eval.eval_retrieval import run_retrieval_eval as _run
        _run()
        print(f"\n✅ Retrieval eval completed in {time.time() - start:.1f}s")
        return True
    except Exception as e:
        print(f"\n❌ Retrieval eval FAILED: {e}")
        return False


# ── Step 2: Faithfulness ──────────────────────────────────────────────────────

def run_faithfulness_eval():
    print_section("STEP 2 — FAITHFULNESS EVALUATION (LLM-as-Judge)")
    start = time.time()
    try:
        from eval.eval_faithfulness import run_faithfulness_eval as _run
        _run()
        print(f"\n✅ Faithfulness eval completed in {time.time() - start:.1f}s")
        return True
    except Exception as e:
        print(f"\n❌ Faithfulness eval FAILED: {e}")
        return False


# ── Step 3: Conversations ─────────────────────────────────────────────────────

def run_conversation_eval():
    print_section("STEP 3 — CONVERSATION EVALUATION (Multi-turn Dialogues)")
    start = time.time()
    try:
        from eval.eval_conversations import run_conversation_eval as _run
        _run()
        print(f"\n✅ Conversation eval completed in {time.time() - start:.1f}s")
        return True
    except Exception as e:
        print(f"\n❌ Conversation eval FAILED: {e}")
        return False


# ── Step 4: Performance (Latency + Throughput) ────────────────────────────────

def run_performance_eval():
    print_section("STEP 4 — PERFORMANCE EVALUATION (Latency + Throughput)")
    start = time.time()
    try:
        # Add evals folder to path so latency/throughput/utils are importable
        evals_dir = os.path.dirname(os.path.abspath(__file__))
        if evals_dir not in sys.path:
            sys.path.insert(0, evals_dir)

        from latency    import run_all_latency_scenarios
        from throughput import run_throughput_test
        from utils      import check_thresholds

        # Run latency scenarios (reduced trials for speed inside full suite)
        print("\n  Running latency scenarios (10 trials each)...")
        latency_results = asyncio.run(
            run_all_latency_scenarios(trials=10)
        )

        # Run throughput ramp-up (capped at 8 concurrent users)
        print("\n  Running throughput ramp-up (up to 8 concurrent users)...")
        throughput_result = asyncio.run(
            run_throughput_test(levels=[1, 2, 4, 6, 8])
        )

        # Collect threshold violations
        violations = []
        for result in latency_results.values():
            violations.extend(check_thresholds(result))

        # Save performance results
        os.makedirs("eval/results", exist_ok=True)
        perf_data = {
            "latency":    {k: v.to_dict() for k, v in latency_results.items()},
            "throughput": throughput_result.to_dict(),
            "threshold_violations": violations,
        }
        with open("eval/results/performance_metrics.json", "w") as f:
            json.dump(perf_data, f, indent=2)
        print("  Results saved to eval/results/performance_metrics.json")

        print(f"\n✅ Performance eval completed in {time.time() - start:.1f}s")
        return True, perf_data

    except Exception as e:
        import traceback
        print(f"\n❌ Performance eval FAILED: {e}")
        traceback.print_exc()
        return False, None


# ── Final report ──────────────────────────────────────────────────────────────

def generate_final_report(results: dict, perf_data: dict | None):
    print_header("FINAL EVALUATION REPORT")

    report = {
        "generated_at": datetime.now().isoformat(),
        "modules_run":  results,
        "summary":      {}
    }

    # ── Retrieval ──────────────────────────────────────────────────────────
    retrieval_path = "eval/results/retrieval_metrics.json"
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
        print(f"\n📊 RETRIEVAL METRICS")
        print(f"   Avg Precision@{r.get('top_k')}: {r.get('avg_precision_at_k', 0):.3f}")
        print(f"   Avg Recall@{r.get('top_k')}:    {r.get('avg_recall_at_k', 0):.3f}")
        print(f"   Queries with hits: {r.get('hits')}/{r.get('total_queries')}")
    else:
        print("\n📊 RETRIEVAL METRICS: not found (eval may have failed)")

    # ── Faithfulness ───────────────────────────────────────────────────────
    faithful_path = "eval/results/faithfulness_metrics.json"
    if os.path.exists(faithful_path):
        with open(faithful_path) as f:
            fd = json.load(f)
        report["summary"]["faithfulness"] = {
            "avg_faithfulness_score": fd.get("avg_faithfulness_score"),
            "max_score":              fd.get("max_score"),
            "queries_evaluated":      fd.get("queries_evaluated"),
        }
        print(f"\n📊 FAITHFULNESS METRICS")
        print(f"   Avg Faithfulness: {fd.get('avg_faithfulness_score', 0):.2f}/5")
        print(f"   Queries evaluated: {fd.get('queries_evaluated')}")
    else:
        print("\n📊 FAITHFULNESS METRICS: not found (eval may have failed)")

    # ── Conversations ──────────────────────────────────────────────────────
    convo_path = "eval/results/conversation_metrics.json"
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
        print(f"\n📊 CONVERSATION METRICS")
        print(f"   Avg Task Completion:   {c.get('avg_task_completion', 0):.2f}/5")
        print(f"   Avg Coherence:         {c.get('avg_coherence', 0):.2f}/5")
        print(f"   Avg Policy Adherence:  {c.get('avg_policy_adherence', 0):.2f}/5")
        print(f"   Avg Overall:           {c.get('avg_overall', 0):.2f}/5")
        print(f"   Dialogues: {c.get('successful')}/{c.get('total_dialogues')} successful")
    else:
        print("\n📊 CONVERSATION METRICS: not found (eval may have failed)")

    # ── Performance ────────────────────────────────────────────────────────
    perf_path = "eval/results/performance_metrics.json"
    if os.path.exists(perf_path):
        with open(perf_path) as f:
            p = json.load(f)
        tput = p.get("throughput", {})
        lat  = p.get("latency", {})
        report["summary"]["performance"] = {
            "max_concurrency":    tput.get("max_concurrency"),
            "breakpoint":         tput.get("breakpoint"),
            "peak_turns_per_sec": tput.get("peak_turns_per_sec"),
            "threshold_violations": p.get("threshold_violations", []),
        }
        print(f"\n📊 PERFORMANCE METRICS")
        print(f"   Max sustainable concurrency: {tput.get('max_concurrency')}")
        bp = tput.get('breakpoint')
        print(f"   Breakpoint: {bp if bp else 'not reached'}")
        print(f"   Peak throughput: {tput.get('peak_turns_per_sec'):.2f} turns/s")
        print(f"   Latency scenarios measured: {list(lat.keys())}")
        violations = p.get("threshold_violations", [])
        if violations:
            print(f"   ⚠  {len(violations)} threshold violation(s):")
            for v in violations:
                print(f"      • {v}")
        else:
            print("   ✓  All latency thresholds passed")
    else:
        print("\n📊 PERFORMANCE METRICS: not found (eval may have failed)")

    # ── Module status ──────────────────────────────────────────────────────
    print(f"\n📋 MODULE STATUS")
    for module, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {status} — {module}")

    # ── Save combined report ───────────────────────────────────────────────
    os.makedirs("eval/results", exist_ok=True)
    report_path = "eval/results/full_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n💾 Full report saved to {report_path}")
    print("=" * 60)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    total_start = time.time()

    print_header("CROCHETZIES — AUTOMATED EVALUATION SUITE")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nThis will run 4 evaluations in sequence:")
    print("  1. Retrieval      (~30 seconds)")
    print("  2. Faithfulness   (~5 minutes)")
    print("  3. Conversations  (~20 minutes)")
    print("  4. Performance    (~15 minutes)")
    print("\nMake sure the chatbot server is running:")
    print("  python -m uvicorn api:app")
    print("\nDo not close this window.")

    perf_data = None

    perf_ok, perf_data = run_performance_eval()

    results = {
        "eval_retrieval":    run_retrieval_eval(),
        "eval_faithfulness": run_faithfulness_eval(),
        "eval_conversations": run_conversation_eval(),
        "eval_performance":  perf_ok,
    }

    total_elapsed = time.time() - total_start
    print(f"\n⏱  Total time: {total_elapsed/60:.1f} minutes")

    generate_final_report(results, perf_data)