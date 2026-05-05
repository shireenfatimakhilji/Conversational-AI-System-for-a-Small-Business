# evals/eval_faithfulness.py
"""
Checks if LLM answers are grounded in retrieved documents.
Faithfulness = answer only contains info from retrieved chunks.

Run from project root: python evals/eval_faithfulness.py
"""

import sys, os, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retrieval.retriever import retrieve
from evals.ground_truth import GROUND_TRUTH
import ollama
from config import MODEL_NAME

def generate_answer(query: str, chunks) -> str:
    context = "\n\n".join([f"[{c.source}]:\n{c.text}" for c in chunks])
    prompt = f"""You are a helpful assistant for Crochetzies, a custom crochet business.
Use ONLY the following information to answer. Do not add anything not in the documents.

{context}

Question: {query}
Answer:"""
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"].strip()


def judge_faithfulness(query: str, answer: str, context: str) -> dict:
    """Use LLM as judge to score faithfulness 1-5."""
    judge_prompt = f"""You are evaluating whether an AI answer is faithful to the provided context.

Context:
{context}

Question: {query}

Answer: {answer}

Score the answer on faithfulness (1-5):
1 = Completely hallucinated, nothing from context
2 = Mostly hallucinated, little from context  
3 = Partially faithful, some hallucination
4 = Mostly faithful, minor additions
5 = Completely faithful, only uses context

Respond with ONLY a JSON object like:
{{"score": 4, "reason": "The answer correctly states..."}}"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": judge_prompt}]
    )

    text = response["message"]["content"].strip()
    try:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {"score": 3, "reason": "Could not parse judge response"}


def run_faithfulness_eval():
    print("=" * 60)
    print("FAITHFULNESS EVALUATION")
    print("=" * 60)

    results = []

    # Use first 10 queries for faithfulness (LLM calls are slow)
    queries = GROUND_TRUTH[:10]

    for item in queries:
        query = item["query"]
        print(f"Evaluating: {query[:50]}...")

        chunks  = retrieve(query, top_k=3)
        context = "\n\n".join([f"[{c.source}]: {c.text}" for c in chunks])
        answer  = generate_answer(query, chunks)
        verdict = judge_faithfulness(query, answer, context)

        results.append({
            "query":   query,
            "answer":  answer,
            "score":   verdict.get("score", 0),
            "reason":  verdict.get("reason", ""),
            "sources": [c.source for c in chunks]
        })

        print(f"  Score: {verdict.get('score')}/5 — {verdict.get('reason', '')[:80]}")
        print()

    avg_score = sum(r["score"] for r in results) / len(results)

    print("=" * 60)
    print("FAITHFULNESS SUMMARY")
    print("=" * 60)
    print(f"Queries evaluated: {len(results)}")
    print(f"Avg faithfulness:  {avg_score:.2f}/5")
    print("=" * 60)

    os.makedirs("evals/results", exist_ok=True)
    with open("evals/results/faithfulness_metrics.json", "w") as f:
        json.dump({
            "avg_faithfulness_score": avg_score,
            "max_score": 5,
            "queries_evaluated": len(results),
            "per_query": results
        }, f, indent=2)
    print("Results saved to evals/results/faithfulness_metrics.json")

if __name__ == "__main__":
    run_faithfulness_eval()