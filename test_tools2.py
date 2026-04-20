from orchestrator import execute_tool_sync

def test_tool(name, args):
    print("\n==============================")
    print("TOOL:", name)
    print("ARGS:", args)
    print("==============================\n")

    result = execute_tool_sync(name, args)

    print("RESULT:\n", result)
    print("\n------------------------------\n")


if __name__ == "__main__":

    # Calculator test
    test_tool("calculator", {
        "expression": "12 * 5 + 3"
    })

    # Weather test
    test_tool("weather", {
        "action": "assess_delivery",
        "location": "Islamabad"
    })

    # CRM test (example - adjust fields if needed)
    test_tool("crm", {
        "action": "store",
        "user_id": "test123",
        "data": {
            "name": "Shireen",
            "preference": "crochet bags"
        }
    })

    # Calendar test (YOUR NEW TOOL)
    test_tool("calendar", {
        "order_date": "2026-04-20",
        "processing_days": 5
    })