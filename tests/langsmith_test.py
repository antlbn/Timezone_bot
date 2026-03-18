import os
from langsmith import traceable
from groq import Groq


# Load .env manually to be safe before other logic
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value


load_env()

print(f"DEBUG: LANGCHAIN_ENDPOINT={os.environ.get('LANGCHAIN_ENDPOINT')}")
print(f"DEBUG: LANGSMITH_ENDPOINT={os.environ.get('LANGSMITH_ENDPOINT')}")

# 1. Setup Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


# 2. Add LangSmith tracing
# This decorator automatically sends traces to LangSmith if environment variables are set
@traceable(name="Timezone Bot: Tool Extraction")
def run_extraction(user_input: str):
    prompt_path = os.path.join(
        os.path.dirname(__file__), "promptfoo", "prompt_smart.txt"
    )
    with open(prompt_path, "r") as f:
        prompt = f.read()

    context_prefix = "SENDER: id=123 name=John\nANCHOR: 2026-03-13T10:00:00Z\nHISTORY:\n(no prior context)\n\nCURRENT MESSAGE:\n"
    full_query = f"{prompt}\n\n{context_prefix}{user_input}"

    tools = [
        {
            "type": "function",
            "function": {
                "name": "convert_time",
                "description": "Convert event time(s) to local time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reflections": {"type": "object"},
                        "event": {"type": "boolean"},
                        "sender_id": {"type": "string"},
                        "sender_name": {"type": "string"},
                        "time": {"type": "array", "items": {"type": "string"}},
                        "city": {
                            "type": "array",
                            "items": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        },
                    },
                    "required": [
                        "reflections",
                        "event",
                        "sender_id",
                        "sender_name",
                        "time",
                        "city",
                    ],
                },
            },
        }
    ]

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": full_query}],
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
        )
        return response
    except Exception as e:
        print(f"Tool call failed with error: {e}. Retrying without tools...")
        # Fallback to raw JSON if tools fail
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": full_query}],
            temperature=0.1,
        )
        return response


if __name__ == "__main__":
    # Ensure LangSmith variables are mentioned for the user
    # os.environ["LANGCHAIN_TRACING_V2"] = "true"
    # os.environ["LANGCHAIN_API_KEY"] = "your-key-here"
    # os.environ["LANGCHAIN_PROJECT"] = "timezone-bot-tests"

    print("Running extraction with LangSmith tracing...")
    result = run_extraction("[John]: Давай завтра в 10 утра созвонимся")

    message = result.choices[0].message
    if message.tool_calls:
        print("Tool Call Detected:")
        print(message.tool_calls[0].function.arguments)
    else:
        print("Raw Content:")
        print(message.content)
