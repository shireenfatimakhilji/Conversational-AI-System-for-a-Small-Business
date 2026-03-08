"""
test_dialogues.py — Multi-Turn Dialogue Tests
Phase III Deliverable: Conversation Orchestration Tests

Tests 5 scenarios:
  1. Happy Path          — clean order from start to finish
  2. Uncertain Customer  — customer doesn't know what to order
  3. Mid-Order Change    — customer changes a detail before confirming
  4. Multi-Detail Input  — customer provides several details at once
  5. Off-Topic Handling  — customer asks something unrelated

Usage:
    python test_dialogues.py              # run all tests
    python test_dialogues.py --test 1     # run a specific test by number
    python test_dialogues.py --verbose    # show full bot responses

Each test prints PASS / FAIL based on simple keyword checks.
All tests also print a readable conversation log.
"""

import argparse
import time
from convo_manager import ConversationManager


# ── ANSI colours for terminal output ─────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


# ── Test case definitions ─────────────────────────────────────────────────────

TEST_CASES = [
    {
        "id": 1,
        "name": "Happy Path — Full Order",
        "description": "Customer places a complete order with no issues.",
        "turns": [
            "hello",
            "I want a crochet dinosaur",
            "Green and yellow",
            "Medium",
            "Big eyes and a little bow",
            "Ayesha",
            "House 12, Street 4, Rawalpindi",
            "Yes",
        ],
        # Keywords that must appear somewhere in the final bot reply
        "expect_in_last": ["confirm", "thank"],
        # Keywords that must appear somewhere in the full conversation
        "expect_in_any": ["summary", "dinosaur", "medium", "ayesha"],
    },
    {
        "id": 2,
        "name": "Uncertain Customer",
        "description": "Customer doesn't know what they want and asks for suggestions.",
        "turns": [
            "hello",
            "I'm not sure, what can you make?",
            "Maybe a cat",
            "Pink and white",
            "Small please",
            "No that's fine",
            "Sara",
            "Flat 5, Block B, Lahore",
            "Yes please",
        ],
        "expect_in_last": ["confirm", "thank"],
        "expect_in_any": ["cat", "small", "sara"],
    },
    {
        "id": 3,
        "name": "Mid-Order Change",
        "description": "Customer changes the size after providing it.",
        "turns": [
            "hello",
            "I want a crochet bear, large, brown and black",
            "Actually can I change the size to medium?",
            "No just keep it simple",
            "Ali",
            "House 3, Model Town, Lahore",
            "Yes",
        ],
        "expect_in_last": ["confirm", "thank"],
        "expect_in_any": ["medium", "bear", "ali"],
    },
    {
        "id": 4,
        "name": "Multi-Detail Input",
        "description": "Customer provides multiple order details in a single message.",
        "turns": [
            "hello",
            "I want a medium blue bunny with floppy ears",
            "No extra customization",
            "Zara",
            "Apartment 7, DHA Phase 2, Karachi",
            "Yes confirm it",
        ],
        "expect_in_last": ["confirm", "thank"],
        "expect_in_any": ["bunny", "blue", "zara"],
    },
    {
        "id": 5,
        "name": "Off-Topic Handling",
        "description": "Customer asks something unrelated; bot should stay on topic.",
        "turns": [
            "hello",
            "What's the weather like today?",
            "Can you recommend a good restaurant?",
            "Ok fine, I want a crochet frog",
            "Green",
            "Small",
            "None",
            "Bilal",
            "Street 9, F-8, Islamabad",
            "Yes",
        ],
        "expect_in_last": ["confirm", "thank"],
        # Bot must have redirected back to crochet topic
        "expect_in_any": ["frog", "bilal", "crochet"],
    },
]


# ── Test runner ───────────────────────────────────────────────────────────────

def run_test(test: dict, verbose: bool = False) -> bool:
    """
    Runs a single test case.
    Returns True if PASS, False if FAIL.
    """
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}Test {test['id']}: {test['name']}{RESET}")
    print(f"{YELLOW}{test['description']}{RESET}")
    print(f"{'─' * 60}")

    manager = ConversationManager()
    all_bot_text = []
    last_bot_reply = ""

    for i, user_msg in enumerate(test["turns"]):
        turn_start = time.time()
        bot_reply = manager.get_response(user_msg)
        elapsed = time.time() - turn_start

        all_bot_text.append(bot_reply.lower())
        last_bot_reply = bot_reply.lower()

        print(f"  {BOLD}You:{RESET}  {user_msg}")
        if verbose:
            print(f"  {BOLD}Bot:{RESET}  {bot_reply}  {YELLOW}[{elapsed:.1f}s]{RESET}")
        else:
            # Truncate long replies for readability
            preview = bot_reply[:120].replace("\n", " ")
            if len(bot_reply) > 120:
                preview += "..."
            print(f"  {BOLD}Bot:{RESET}  {preview}  {YELLOW}[{elapsed:.1f}s]{RESET}")
        print()

    # ── Assertions ────────────────────────────────────────────────────────────
    failures = []

    for keyword in test.get("expect_in_last", []):
        if keyword.lower() not in last_bot_reply:
            failures.append(f"Last reply missing keyword: '{keyword}'")

    combined_text = " ".join(all_bot_text)
    for keyword in test.get("expect_in_any", []):
        if keyword.lower() not in combined_text:
            failures.append(f"Full conversation missing keyword: '{keyword}'")

    stats = manager.get_stats()
    print(f"  Session stats: {stats}")

    if failures:
        print(f"\n  {RED}{BOLD}FAIL{RESET}")
        for f in failures:
            print(f"    {RED}✗ {f}{RESET}")
        return False
    else:
        print(f"\n  {GREEN}{BOLD}PASS{RESET}")
        return True


def run_all_tests(test_ids: list = None, verbose: bool = False):
    """Runs all (or selected) tests and prints a summary."""
    tests_to_run = TEST_CASES
    if test_ids:
        tests_to_run = [t for t in TEST_CASES if t["id"] in test_ids]

    results = []
    total_start = time.time()

    for test in tests_to_run:
        passed = run_test(test, verbose=verbose)
        results.append((test["name"], passed))

    total_elapsed = time.time() - total_start

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}TEST SUMMARY  ({total_elapsed:.1f}s total){RESET}")
    print(f"{'═' * 60}")
    passed_count = sum(1 for _, p in results if p)
    for name, passed in results:
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {status}  {name}")
    print(f"\n  {passed_count}/{len(results)} tests passed")
    print(f"{'═' * 60}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Crochetzies multi-turn dialogue tests")
    parser.add_argument("--test",    type=int, nargs="+", help="Run specific test IDs (e.g. --test 1 3)")
    parser.add_argument("--verbose", action="store_true",  help="Show full bot responses")
    args = parser.parse_args()

    run_all_tests(test_ids=args.test, verbose=args.verbose)