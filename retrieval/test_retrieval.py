# retrieval/test_retrieval.py
"""
Test harness — run this to verify retrieval works without the chatbot.
Usage: python retrieval/test_retrieval.py
"""

from retriever import retrieve

TEST_QUERIES = [
    "what is your return policy?",
    "how much does a large cat cost?",
    "how long does delivery take?",
    "what colors can I choose?",
    "do you gift wrap orders?",
    "how do I wash my crochet item?",
    "what animals do you make?",
    "can I order in bulk?",
    "what payment methods do you accept?",
    "how do I place an order?",
]

def run_tests():
    print("=" * 60)
    print("RETRIEVAL TEST HARNESS")
    print("=" * 60)

    for query in TEST_QUERIES:
        print(f"\nQuery: '{query}'")
        print("-" * 40)
        chunks = retrieve(query, top_k=3)
        for i, chunk in enumerate(chunks):
            print(f"[{i+1}] Source: {chunk.source} | Score: {chunk.score}")
            print(f"     {chunk.text[:150]}...")
        print()

if __name__ == "__main__":
    run_tests()