# eval/eval_retrieval.py
"""
Measures how well the RAG system retrieves the right documents.
Metrics: Precision@k and Recall@k

Run from project root: python eval/eval_retrieval.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retrieval.retriever import retrieve
from evals.ground_truth import GROUND_TRUTH

TOP_K = 3

def precision_at_k(retrieved_sources, relevant_sources, k):
    """Of the top-k retrieved, how many are relevant?"""
    retrieved_k = retrieved_sources[:k]
    hits = sum(1 for s in retrieved_k if s in relevant_sources)
    return hits / k

def recall_at_k(retrieved_sources, relevant_sources, k):
    """Of all relevant docs, how many did we retrieve in top-k?"""
    retrieved_k = retrieved_sources[:k]
    hits = sum(1 for s in relevant_sources if s in retrieved_k)
    return hits / len(relevant_sources) if relevant_sources else 0

def run_retrieval_eval():
    print("=" * 60)
    print("RAG RETRIEVAL EVALUATION")
    print(f"Queries: {len(GROUND_TRUTH)} | Top-K: {TOP_K}")
    print("=" * 60)

    results = []

    for item in GROUND_TRUTH:
        query    = item["query"]
        relevant = item["relevant_sources"]

        # Run retrieval
        chunks = retrieve(query, top_k=TOP_K)
        retrieved_sources = [c.source for c in chunks]
        scores            = [c.score for c in chunks]

        p_at_k = precision_at_k(retrieved_sources, relevant, TOP_K)
        r_at_k = recall_at_k(retrieved_sources, relevant, TOP_K)

        results.append({
            "query":     query,
            "p@k":       p_at_k,
            "r@k":       r_at_k,
            "retrieved": retrieved_sources,
            "relevant":  relevant,
            "scores":    scores,
        })

        status = "✅" if p_at_k > 0 else "❌"
        print(f"{status} Query: {query[:50]}")
        print(f"   Retrieved: {retrieved_sources}")
        print(f"   Relevant:  {relevant}")
        print(f"   P@{TOP_K}: {p_at_k:.2f} | R@{TOP_K}: {r_at_k:.2f}")
        print()

    # Summary
    avg_precision = sum(r["p@k"] for r in results) / len(results)
    avg_recall    = sum(r["r@k"] for r in results) / len(results)
    hits          = sum(1 for r in results if r["p@k"] > 0)

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total queries:     {len(results)}")
    print(f"Queries with hits: {hits}/{len(results)}")
    print(f"Avg Precision@{TOP_K}: {avg_precision:.3f}")
    print(f"Avg Recall@{TOP_K}:    {avg_recall:.3f}")
    print("=" * 60)

    # Save results to file
    import json
    os.makedirs("results", exist_ok=True)
    with open("results/retrieval_metrics.json", "w") as f:
        json.dump({
            "avg_precision_at_k": avg_precision,
            "avg_recall_at_k":    avg_recall,
            "top_k":              TOP_K,
            "total_queries":      len(results),
            "hits":               hits,
            "per_query":          results
        }, f, indent=2)
    print("Results saved to results/retrieval_metrics.json")

if __name__ == "__main__":
    run_retrieval_eval()