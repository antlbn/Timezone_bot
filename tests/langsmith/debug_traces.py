from langsmith import Client

def main():
    client = Client()
    runs = client.list_runs(
        project_name="timezone-bot-tests",
        run_type="chain",
        limit=20
    )
    
    for r in runs:
        if "ок, тогда в полвторого" in r.inputs.get("text", ""):
            print("="*40)
            print("Negotiation Test Trace")
            print("Inputs:", r.inputs.get("history"))
            print("Outputs:", r.outputs)
            
        elif "sync tomorrow" in r.inputs.get("text", ""):
            print("="*40)
            print("London Sync Test Trace")
            print("Outputs:", r.outputs)

if __name__ == "__main__":
    main()
