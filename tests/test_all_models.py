from grok_api.core import Log, Grok
import sys

MODELS_TO_TEST = [
    "grok-3-auto",
    "grok-3-fast",
    "grok-4",
    "grok-4-mini-thinking-tahoe",
]

def test_model(model_name):
    print(f"\n--- Testing model: {model_name} ---")
    try:
        grok = Grok(model=model_name)
        response = grok.chat("Say hello and tell me your model name.")

        if "error" in response:
            print(f"Failed: {response['error']}", file=sys.stderr)
            return False

        print(f"Response: {response['response'][:100]}...") # Print first 100 chars
        return True
    except Exception as e:
        print(f"Exception: {e}", file=sys.stderr)
        return False

def main():
    print("Starting Model Support Test...")
    results = {}

    for model in MODELS_TO_TEST:
        success = test_model(model)
        results[model] = "PASS" if success else "FAIL"

    print("\n\n=== TEST SUMMARY ===")
    for model, result in results.items():
        print(f"{model}: {result}")

if __name__ == "__main__":
    main()
