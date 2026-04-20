from retrieval.retriever import retrieve  # adjust path if your file name differs

def test_query(query: str):
    print("\n==============================")
    print("QUERY:", query)
    print("==============================\n")

    results = retrieve(query)

    if not results:
        print("No results found ❌")
        return

    print(f"Top {len(results)} retrieved chunks:\n")

    for i, chunk in enumerate(results):
        print(f"\n--- Chunk {i+1} ---")
        print(chunk)
        print("-------------------")


if __name__ == "__main__":
    test_queries = [
        "delivery time for crochet orders",
        "what is your refund policy",
        "custom crochet processing time",
        "shipping duration"
    ]

    for q in test_queries:
        test_query(q)