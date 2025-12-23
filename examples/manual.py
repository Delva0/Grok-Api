from grok_api import Log, Grok, GrokError
from json import dumps
import sys

def main():
    proxy = "http://user:pass@ip:port"

    # Enable logging for the example
    Log.set_enabled(True)

    try:
        grok = Grok(proxy=proxy)

        message1: str = "Hey how are you??"
        Log.Info("USER: " + message1)
        data1 = grok.chat(message1, extra_data=None)
        Log.Info("GROK: " + data1["response"])

        message2: str = "cool stuff"
        Log.Info("USER: " + message2)
        data2 = grok.chat(message2, extra_data=data1["extra_data"])
        Log.Info("GROK: " + data2["response"])

        # ... and so on ...

    except GrokError as e:
        Log.Error(f"Grok API error occurred: {e}")
        sys.exit(1)
    except Exception as e:
        Log.Error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
