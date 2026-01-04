"""Check COP file for overshoot pattern"""
import json
import re
from pathlib import Path

f = Path(r'data/interim/extracted/20251229_140905_batch_extract_648bf25/COP_10K_2022_20251229_140905_extracted_risks.json')
data = json.load(open(f, encoding='utf-8'))
text = data['text']

# Check what pattern matches
text_body = text[300:]
pattern = r'(\n|^)(Item|ITEM)\s+(?!1A)[1-9]+[A-Z]?\s*\.\s+[A-Z]'
match = re.search(pattern, text_body)

if match:
    print('MATCH FOUND:')
    print(f'Pattern matched: "{match.group()}"')
    print(f'Position: {match.start()} in body text (after skipping 300 char header)')
    print(f'\nContext (200 chars before and after):')
    start = max(0, match.start() - 200)
    end = min(len(text_body), match.end() + 200)
    context = text_body[start:end].replace('\n', ' ')
    print(context)
    print('\n' + '='*70)
    print('Last 500 chars of extraction:')
    print(text[-500:])
else:
    print('No match found')
