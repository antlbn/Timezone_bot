"""
upload_dataset.py — Upload cases.yaml test cases to a LangSmith Dataset.

Usage:
    uv run python tests/langsmith/upload_dataset.py

What it does:
  - Reads tests/promptfoo/cases.yaml
  - Creates (or updates) a LangSmith dataset named DATASET_NAME
  - Each case becomes one Example: inputs = vars, outputs = expected assertions

Run once; re-running updates the dataset (deduplicates by description).
"""

import os
import sys
import yaml
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────
DATASET_NAME = "timezone-bot-event-detection"
CASES_FILE   = Path(__file__).parent.parent / "promptfoo" / "cases.yaml"


def main():
    client = Client()

    # Load cases
    with open(CASES_FILE) as f:
        cases = [c for c in yaml.safe_load(f) if c and isinstance(c, dict)]

    print(f"Loaded {len(cases)} cases from {CASES_FILE.name}")

    # Create or reuse dataset
    datasets = {d.name: d for d in client.list_datasets()}
    if DATASET_NAME in datasets:
        dataset = datasets[DATASET_NAME]
        print(f"Using existing dataset: {DATASET_NAME} (id={dataset.id})")
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Event detection test cases from promptfoo/cases.yaml",
        )
        print(f"Created dataset: {DATASET_NAME} (id={dataset.id})")

    # Upload each case as an Example
    existing = {e.metadata.get("description"): e for e in client.list_examples(dataset_id=dataset.id)}
    added = skipped = 0

    for case in cases:
        desc = case.get("description", "")
        v    = case.get("vars", {})

        # Parse expected result from JS assert (best-effort)
        # We extract event=true/false if present in the assert string
        asserts = case.get("assert", [])
        expected_event = None
        for a in asserts:
            val = a.get("value", "")
            if "data.event === true" in val:
                expected_event = True
            elif "data.event === false" in val:
                expected_event = False

        inputs = {
            "text":        v.get("text", ""),
            "history":     v.get("history", ""),
            "timestamp":   v.get("timestamp", ""),
            "sender_id":   v.get("sender_id", ""),
            "sender_name": v.get("sender_name", ""),
            "author":      v.get("author", v.get("sender_name", "")),
        }
        outputs = {"event": expected_event}  # ground truth

        if desc in existing:
            skipped += 1
            continue

        client.create_example(
            dataset_id=dataset.id,
            inputs=inputs,
            outputs=outputs,
            metadata={"description": desc},
        )
        added += 1

    print(f"Done — added {added} examples, skipped {skipped} existing")
    print(f"\nView at: https://eu.smith.langchain.com/datasets/{dataset.id}")


if __name__ == "__main__":
    main()
