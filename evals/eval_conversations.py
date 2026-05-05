# evals/eval_conversations.py
"""
10+ multi-turn dialogue tests evaluated by LLM-as-judge.
Scores: task completion, coherence, policy adherence.

Run from project root: python evals/eval_conversations.py
"""

import sys, os, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ollama
from config import MODEL_NAME
from convo_manager import ConversationManager

# ── Test dialogues ────────────────────────────────────────────────────────────

TEST_DIALOGUES = [
    {
        "id": 1,
        "name": "Happy Path — Full Order",
        "category": "typical",
        "turns": [
            "hello",
            "I want a crochet cat",
            "white and pink",
            "medium",
            "big eyes and a bow",
            "1",
            "no more items",
            "Sara Ahmed",
            "House 5, Street 3, Lahore",
            "yes"
        ],
        "expected_outcomes": [
            "collects item type",
            "collects colors",
            "collects size",
            "collects extras",
            "collects name",
            "collects address",
            "shows order summary",
            "confirms order"
        ]
    },
    {
        "id": 2,
        "name": "Uncertain Customer",
        "category": "typical",
        "turns": [
            "hello",
            "I don't know what to order",
            "maybe a bunny?",
            "yellow",
            "small",
            "none",
            "1",
            "no",
            "Ali Khan",
            "Flat 3, DHA Karachi",
            "yes"
        ],
        "expected_outcomes": [
            "suggests items when uncertain",
            "guides customer through steps"
        ]
    },
    {
        "id": 3,
        "name": "Mid-Order Change",
        "category": "typical",
        "turns": [
            "hello",
            "I want a crochet bear, large, brown",
            "actually make it medium",
            "no extras",
            "2",
            "no",
            "Zara Malik",
            "Street 9, F-8 Islamabad",
            "yes"
        ],
        "expected_outcomes": [
            "accepts size change",
            "updates order correctly"
        ]
    },
    {
        "id": 4,
        "name": "Off-Topic Handling",
        "category": "edge_case",
        "turns": [
            "hello",
            "what is the weather today?",
            "can you recommend a restaurant?",
            "ok fine, I want a dinosaur",
            "green",
            "large",
            "none",
            "1",
            "no",
            "Bilal Ahmed",
            "House 1, Model Town Lahore",
            "yes"
        ],
        "expected_outcomes": [
            "redirects off-topic questions",
            "stays focused on crochet orders"
        ]
    },
    {
        "id": 5,
        "name": "Policy — Return Request",
        "category": "policy_violation",
        "turns": [
            "hello",
            "I want to return my previous order",
            "but I don't like it",
            "ok fine, I want a new cat",
            "white",
            "small",
            "none",
            "1",
            "no",
            "Test User",
            "Test Address Karachi",
            "yes"
        ],
        "expected_outcomes": [
            "explains no return policy",
            "offers to help with new order",
            "does not process fake return"
        ]
    },
    {
        "id": 6,
        "name": "Multi-Item Order",
        "category": "typical",
        "turns": [
            "hello",
            "I want a cat",
            "pink",
            "small",
            "bow",
            "1",
            "yes another item",
            "I want a bear",
            "brown",
            "large",
            "none",
            "1",
            "no more",
            "Hina Shah",
            "Block B, Gulberg Lahore",
            "yes"
        ],
        "expected_outcomes": [
            "handles multiple items",
            "tracks both items in summary"
        ]
    },
    {
        "id": 7,
        "name": "Pricing Question",
        "category": "typical",
        "turns": [
            "hello",
            "how much does a large cat cost?",
            "ok I want one",
            "black",
            "large",
            "none",
            "1",
            "no",
            "Kamran Ali",
            "Sector G Islamabad",
            "yes"
        ],
        "expected_outcomes": [
            "answers pricing question correctly",
            "mentions 2000-3000 range for large"
        ]
    },
    {
        "id": 8,
        "name": "Delivery Question",
        "category": "typical",
        "turns": [
            "hello",
            "how long does delivery take?",
            "ok I want to order",
            "I want a frog",
            "green",
            "medium",
            "none",
            "1",
            "no",
            "Ayesha Noor",
            "House 7 Rawalpindi",
            "yes"
        ],
        "expected_outcomes": [
            "correctly states 5-7 business days",
            "continues order flow after answering"
        ]
    },
    {
        "id": 9,
        "name": "Customer Declines Order",
        "category": "edge_case",
        "turns": [
            "hello",
            "I want a cat",
            "white",
            "small",
            "none",
            "1",
            "no",
            "Test Name",
            "Test Address",
            "no actually cancel it"
        ],
        "expected_outcomes": [
            "handles cancellation gracefully",
            "asks what to change"
        ]
    },
    {
        "id": 10,
        "name": "Incomplete Information",
        "category": "edge_case",
        "turns": [
            "hello",
            "cat",
            "blue",
            "big",
            "none",
            "1",
            "no",
            "A",
            "Lahore",
            "yes"
        ],
        "expected_outcomes": [
            "handles vague size input",
            "collects all required information"
        ]
    },
    {
        "id": 11,
        "name": "Payment Question",
        "category": "policy_violation",
        "turns": [
            "hello",
            "do you accept credit cards?",
            "what about bank transfer?",
            "ok, I want a bear",
            "brown",
            "medium",
            "none",
            "1",
            "no",
            "Usman Ali",
            "Street 5 Karachi",
            "yes"
        ],
        "expected_outcomes": [
            "correctly states COD only",
            "does not accept other payment methods"
        ]
    },
    {
        "id": 12,
        "name": "Bulk Order",
        "category": "typical",
        "turns": [
            "hello",
            "can I order 10 cats?",
            "pink",
            "small",
            "bow on each",
            "10",
            "no",
            "Event Planner",
            "Office Block C Karachi",
            "yes"
        ],
        "expected_outcomes": [
            "handles bulk quantity",
            "calculates correct total"
        ]
    },
]


def run_dialogue(dialogue: dict) -> list:
    """Run a test dialogue and collect all bot responses."""
    manager = ConversationManager()
    conversation_log = []

    for user_msg in dialogue["turns"]:
        bot_reply = manager.get_response(user_msg)
        conversation_log.append({
            "user": user_msg,
            "bot":  bot_reply
        })
        if manager.session_ended:
            break

    return conversation_log


def judge_dialogue(dialogue: dict, conversation_log: list) -> dict:
    """Use LLM as judge to score the dialogue."""

    conv_text = "\n".join([
        f"User: {turn['user']}\nBot: {turn['bot']}"
        for turn in conversation_log
    ])

    expected = "\n".join([f"- {e}" for e in dialogue["expected_outcomes"]])

    judge_prompt = f"""You are evaluating a customer service chatbot for Crochetzies, a crochet business.

Test: {dialogue['name']}
Category: {dialogue['category']}

Expected outcomes:
{expected}

Conversation:
{conv_text}

Score the chatbot on three dimensions (1-5 each):

1. Task Completion (1-5): Did the bot complete all expected outcomes?
2. Coherence (1-5): Were responses clear, relevant, and well-structured?
3. Policy Adherence (1-5): Did the bot follow business rules (COD only, no returns, collect all info)?

Respond with ONLY this JSON:
{{"task_completion": 4, "coherence": 5, "policy_adherence": 4, "overall": 4, "comments": "Brief explanation"}}"""

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
    return {
        "task_completion":  3,
        "coherence":        3,
        "policy_adherence": 3,
        "overall":          3,
        "comments":         "Could not parse judge response"
    }


def run_conversation_eval():
    print("=" * 60)
    print("CONVERSATIONAL EVALUATION")
    print(f"Dialogues: {len(TEST_DIALOGUES)}")
    print("=" * 60)

    results = []

    for dialogue in TEST_DIALOGUES:
        print(f"\nRunning: {dialogue['name']}...")

        try:
            conversation_log = run_dialogue(dialogue)
            scores           = judge_dialogue(dialogue, conversation_log)

            results.append({
                "id":               dialogue["id"],
                "name":             dialogue["name"],
                "category":         dialogue["category"],
                "scores":           scores,
                "conversation_log": conversation_log,
                "turns":            len(conversation_log)
            })

            print(f"  Task: {scores.get('task_completion')}/5 | "
                  f"Coherence: {scores.get('coherence')}/5 | "
                  f"Policy: {scores.get('policy_adherence')}/5")
            print(f"  Comment: {scores.get('comments', '')[:80]}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "id":       dialogue["id"],
                "name":     dialogue["name"],
                "category": dialogue["category"],
                "error":    str(e)
            })

    # Summary
    valid = [r for r in results if "scores" in r]
    if valid:
        avg_task    = sum(r["scores"]["task_completion"]  for r in valid) / len(valid)
        avg_coher   = sum(r["scores"]["coherence"]        for r in valid) / len(valid)
        avg_policy  = sum(r["scores"]["policy_adherence"] for r in valid) / len(valid)
        avg_overall = sum(r["scores"]["overall"]          for r in valid) / len(valid)

        print("\n" + "=" * 60)
        print("CONVERSATION EVALUATION SUMMARY")
        print("=" * 60)
        print(f"Dialogues run:      {len(results)}")
        print(f"Successful:         {len(valid)}")
        print(f"Avg Task Completion:  {avg_task:.2f}/5")
        print(f"Avg Coherence:        {avg_coher:.2f}/5")
        print(f"Avg Policy Adherence: {avg_policy:.2f}/5")
        print(f"Avg Overall:          {avg_overall:.2f}/5")
        print("=" * 60)

        by_category = {}
        for r in valid:
            cat = r["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(r["scores"]["overall"])

        print("\nBy Category:")
        for cat, scores in by_category.items():
            print(f"  {cat}: {sum(scores)/len(scores):.2f}/5 ({len(scores)} dialogues)")

    os.makedirs("evals/results", exist_ok=True)
    with open("evals/results/conversation_metrics.json", "w") as f:
        json.dump({
            "total_dialogues":       len(results),
            "successful":            len(valid),
            "avg_task_completion":   avg_task    if valid else 0,
            "avg_coherence":         avg_coher   if valid else 0,
            "avg_policy_adherence":  avg_policy  if valid else 0,
            "avg_overall":           avg_overall if valid else 0,
            "per_dialogue":          results
        }, f, indent=2)
    print("\nResults saved to evals/results/conversation_metrics.json")

if __name__ == "__main__":
    run_conversation_eval()