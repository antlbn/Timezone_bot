import json
with open('out_gemini_full.json', 'r') as f:
    data = json.load(f)

count = 0
for row in data['results']['results']:
    if not row.get('success'):
        print(f"\nFAIL: {row['testCase']['description']}")
        print(f"Output: {row['response'].get('output')}")
        count += 1
print(f"Total failures: {count}")
