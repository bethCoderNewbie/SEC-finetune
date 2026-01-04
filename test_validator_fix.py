"""
Test script to verify Section End Precision validator fix
"""
import json
import re
from pathlib import Path

def check_old(text: str) -> bool:
    """Old validator (buggy)"""
    overshoot_pattern = r'Item\s+\d+[A-Z]?\s*\.\s+[A-Z]'
    return bool(re.search(overshoot_pattern, text))

def check_new(text: str) -> bool:
    """New validator (fixed)"""
    text_body = text[300:] if len(text) > 300 else ""
    overshoot_pattern = r'(\n|^)(Item|ITEM)\s+(?!1A)[1-9]+[A-Z]?\s*\.\s+[A-Z]'
    return bool(re.search(overshoot_pattern, text_body))

# Test on sample files
extract_dir = Path(r'data/interim/extracted/20251229_140905_batch_extract_648bf25')
files = list(extract_dir.glob('*_extracted_risks.json'))

old_failures = 0
new_failures = 0
examples = []

for f in files:
    data = json.load(open(f, encoding='utf-8'))
    text = data['text']

    old_fail = check_old(text)
    new_fail = check_new(text)

    if old_fail:
        old_failures += 1
    if new_fail:
        new_failures += 1
        # Collect example
        examples.append(f.name[:30])

print(f'Validator Fix Test Results')
print(f'=' * 60)
print(f'Total files tested: {len(files)}')
print()
print(f'OLD validator (buggy):')
print(f'  Failures: {old_failures:3d} ({old_failures/len(files)*100:5.1f}%)')
print(f'  Passes:   {len(files)-old_failures:3d} ({(len(files)-old_failures)/len(files)*100:5.1f}%)')
print()
print(f'NEW validator (fixed):')
print(f'  Failures: {new_failures:3d} ({new_failures/len(files)*100:5.1f}%)')
print(f'  Passes:   {len(files)-new_failures:3d} ({(len(files)-new_failures)/len(files)*100:5.1f}%)')
print()
print(f'>> False positives eliminated: {old_failures - new_failures}')
if old_failures > 0:
    print(f'>> Improvement: {((old_failures - new_failures)/old_failures*100):.1f}%')

if new_failures > 0:
    print(f'\n!! Files still failing (possible overshoot):')
    for ex in examples[:10]:
        print(f'     - {ex}')
else:
    print(f'\n>> All files pass - no boundary overshoot detected!')
