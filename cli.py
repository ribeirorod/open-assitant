#!/usr/bin/env python3
"""Interactive CLI to chat with Open Assistant agent."""

import asyncio
import sys

from src.agent.core import ask_agent, reset_agent

CHAT_ID = "cli-session"


async def main() -> None:
    # One-shot mode: python cli.py "what are my events today?"
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
        print(f"You: {message}\n")
        response = await ask_agent(message, CHAT_ID)
        print(f"Assistant: {response}")
        return

    # Interactive REPL mode
    print("Open Assistant CLI  (type 'exit' or Ctrl+C to quit, '/reset' to clear session)")
    print("-" * 60)
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Bye!")
            break
        if user_input == "/reset":
            await reset_agent(CHAT_ID)
            print("Session reset.")
            continue

        response = await ask_agent(user_input, CHAT_ID)
        print(f"\nAssistant: {response}")


if __name__ == "__main__":
    asyncio.run(main())
