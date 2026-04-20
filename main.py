from convo_manager import ConversationManager

def main():
    print("=" * 50)
    print("Welcome to Crochetzies Chatbot!")
    print("Type 'quit' to exit at any time")
    print("=" * 50)

    manager = ConversationManager()

    # Greeting — streamed
    print("\nBot: ", end="", flush=True)
    manager.get_response("hello", stream=True)
    print()

    while True:
        # End loop if order was confirmed in the previous turn
        if manager.session_ended:
            print("\n[Order confirmed. Session closed.]")
            break

        user_input = input("You: ").strip()

        if user_input.lower() == "quit":
            print("Goodbye!")
            break

        if not user_input:
            continue

        print("\nBot: ", end="", flush=True)
        manager.get_response(user_input, stream=True)
        print()

if __name__ == "__main__":
    main()