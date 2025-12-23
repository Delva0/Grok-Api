from grok_api.core import Log, Grok

# No proxy for this POC unless needed, in which case uncomment and set below
# proxy = "http://user:pass@ip:port"
proxy = None

def main():
    try:
        print("Starting POC...")

        # 1. Simple greeting
        message1 = "Hello, this is a test. Are you working?"
        Log.Info("USER: " + message1)
        data1 = Grok(proxy=proxy).chat(message1, extra_data=None)

        if data1 and "response" in data1:
            Log.Info("GROK: " + data1["response"])
        else:
            Log.Error("Failed to get response for message 1")
            return

        # 2. Follow up to test context/continuation
        message2 = "Great! Tell me a short joke."
        Log.Info("USER: " + message2)
        # Pass extra_data to maintain conversation context
        data2 = Grok(proxy=proxy).chat(message2, extra_data=data1.get("extra_data"))

        if data2 and "response" in data2:
            Log.Info("GROK: " + data2["response"])
        else:
            Log.Error("Failed to get response for message 2")

    except Exception as e:
        Log.Error(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
