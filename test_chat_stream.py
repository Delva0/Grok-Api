from core import Log, Grok
import sys
import time

proxy = None

def main():
    try:
        print("Starting Streaming POC...")
        grok = Grok(proxy=proxy)

        # 1. Simple greeting
        message1 = "Write a short poem about coding."
        Log.Info("USER: " + message1)
        print("GROK (Streaming): ", end="", flush=True)

        extra_data = None

        # Using the new chat_stream method
        for chunk in grok.chat_stream(message1, extra_data=None):
            if "error" in chunk:
                print(f"\nError: {chunk['error']}")
                return

            if chunk.get("token"):
                print(chunk["token"], end="", flush=True)

            if chunk.get("meta"):
                extra_data = chunk["meta"]["extra_data"]

        print("\n\n[Message Complete]\n")

        if not extra_data:
            Log.Error("Failed to get context for next message")
            return

        # 2. Follow up
        message2 = "Now rewrite it in the style of a pirate."
        Log.Info("USER: " + message2)
        print("GROK (Streaming): ", end="", flush=True)

        for chunk in grok.chat_stream(message2, extra_data=extra_data):
            if "error" in chunk:
                print(f"\nError: {chunk['error']}")
                return

            if chunk.get("token"):
                print(chunk["token"], end="", flush=True)

        print("\n\n[Conversation Complete]")

    except Exception as e:
        Log.Error(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
