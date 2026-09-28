#!/usr/bin/env python3
"""
Simple terminal chat client for local_rag_api.py

Run:
    python chat.py

It sends your input to:
    POST http://127.0.0.1:8000/chat

Type:
    exit
or
    quit

to stop.
"""

import requests

API_URL = "http://127.0.0.1:8000/chat"


def main():
    print("===================================")
    print(" Local Qwen3 Chat")
    print(" Type 'exit' or 'quit' to stop")
    print("===================================")

    while True:
        try:
            message = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not message:
            continue

        if message.lower() in {"exit", "quit"}:
            print("Bye!")
            break

        try:
            response = requests.post(
                API_URL,
                json={"message": message},
                timeout=300,
            )
            response.raise_for_status()

            data = response.json()
            print(f"\nAI: {data.get('answer', '')}")

        except requests.exceptions.ConnectionError:
            print(
                "\n[ERROR] Không kết nối được API."
                "\nHãy chạy: python local_rag_api.py"
            )

        except requests.exceptions.Timeout:
            print("\n[ERROR] Model phản hồi quá lâu.")

        except requests.exceptions.RequestException as exc:
            print(f"\n[ERROR] HTTP: {exc}")

        except ValueError:
            print("\n[ERROR] API trả về JSON không hợp lệ.")


if __name__ == "__main__":
    main()

