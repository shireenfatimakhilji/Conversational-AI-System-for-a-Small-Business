# evals/ground_truth.py
"""
20-30 test queries with manually annotated relevant document sources.
This is your ground truth dataset for RAG evaluation.
"""

GROUND_TRUTH = [
    {
        "query": "what is your return policy?",
        "relevant_sources": ["return_policy.txt", "faq_wrong_order.txt"],
        "expected_answer_contains": ["no returns", "custom", "contact us"]
    },
    {
        "query": "how much does a large item cost?",
        "relevant_sources": ["pricing_policy.txt", "pricing.txt"],
        "expected_answer_contains": ["2000", "3000", "large"]
    },
    {
        "query": "how long does delivery take?",
        "relevant_sources": ["faq_how_long_delivery.txt", "faq_production_vs_delivery.txt", "delivery.txt"],
        "expected_answer_contains": ["5", "7", "business days"]
    },
    {
        "query": "what payment methods do you accept?",
        "relevant_sources": ["faq_payment_methods.txt", "payment_and_delivery.txt"],
        "expected_answer_contains": ["cash on delivery", "COD"]
    },
    {
        "query": "do you gift wrap orders?",
        "relevant_sources": ["faq_gift_wrapping.txt", "packaging.txt"],
        "expected_answer_contains": ["free", "gift wrap"]
    },
    {
        "query": "how do I wash my crochet item?",
        "relevant_sources": ["care_instructions_general.txt"],
        "expected_answer_contains": ["hand wash", "cold water", "air dry"]
    },
    {
        "query": "what animals do you make?",
        "relevant_sources": ["faq_what_items_do_you_make.txt"],
        "expected_answer_contains": ["cat", "bear", "bunny"]
    },
    {
        "query": "can I order in bulk?",
        "relevant_sources": ["bulk_orders.txt", "customization_guide.txt"],
        "expected_answer_contains": ["bulk", "wholesale", "events"]
    },
    {
        "query": "how do I place an order?",
        "relevant_sources": ["faq_how_to_order.txt", "ordering_guide.txt"],
        "expected_answer_contains": ["chatbot", "step", "name", "address"]
    },
    {
        "query": "what colors can I choose?",
        "relevant_sources": ["faq_colors_available.txt", "faq_can_i_choose_colors.txt"],
        "expected_answer_contains": ["color", "custom", "any"]
    },
    {
        "query": "what sizes are available?",
        "relevant_sources": ["customization_guide.txt", "pricing_policy.txt"],
        "expected_answer_contains": ["small", "medium", "large"]
    },
    {
        "query": "how do I contact Crochetzies?",
        "relevant_sources": ["about_us.txt", "faq.txt"],
        "expected_answer_contains": ["crochetzies@gmail.com", "whatsapp"]
    },
    {
        "query": "is there free gift wrapping?",
        "relevant_sources": ["faq_gift_wrapping.txt", "packaging.txt"],
        "expected_answer_contains": ["free", "included"]
    },
    {
        "query": "what extras can I add to my order?",
        "relevant_sources": ["customization_guide.txt"],
        "expected_answer_contains": ["bow", "eyes", "name tag"]
    },
    {
        "query": "do you deliver outside Pakistan?",
        "relevant_sources": ["delivery.txt", "payment_and_delivery.txt"],
        "expected_answer_contains": ["pakistan"]
    },
    {
        "query": "how much does a small crochet cat cost?",
        "relevant_sources": ["pricing_policy.txt", "pricing.txt"],
        "expected_answer_contains": ["500", "800", "small"]
    },
    {
        "query": "can I customize the color of my order?",
        "relevant_sources": ["faq_can_i_choose_colors.txt", "customization_guide.txt"],
        "expected_answer_contains": ["yes", "custom", "color"]
    },
    {
        "query": "what happens if I receive the wrong item?",
        "relevant_sources": ["faq_wrong_order.txt", "return_policy.txt"],
        "expected_answer_contains": ["contact", "crochetzies@gmail.com"]
    },
    {
        "query": "how do I care for a baby crochet item?",
        "relevant_sources": ["care_instructions_babies.txt", "care_instructions_general.txt"],
        "expected_answer_contains": ["baby", "wash", "safe"]
    },
    {
        "query": "what is the difference between production and delivery time?",
        "relevant_sources": ["faq_production_vs_delivery.txt"],
        "expected_answer_contains": ["production", "delivery", "business days"]
    },
    {
        "query": "do you make crochet keychains?",
        "relevant_sources": ["faq_what_items_do_you_make.txt", "items_catalog.txt"],
        "expected_answer_contains": ["keychain"]
    },
    {
        "query": "what is the price of a medium bunny?",
        "relevant_sources": ["pricing_policy.txt", "pricing.txt"],
        "expected_answer_contains": ["1000", "1500", "medium"]
    },
    {
        "query": "can I get a crochet unicorn?",
        "relevant_sources": ["popular_items.txt", "faq_what_items_do_you_make.txt"],
        "expected_answer_contains": ["unicorn"]
    },
    {
        "query": "do you accept advance payment?",
        "relevant_sources": ["faq_payment_methods.txt", "payment_and_delivery.txt"],
        "expected_answer_contains": ["cash on delivery", "no advance", "COD"]
    },
    {
        "query": "what is the most popular item?",
        "relevant_sources": ["popular_items.txt"],
        "expected_answer_contains": ["cat", "bear", "popular"]
    },
]