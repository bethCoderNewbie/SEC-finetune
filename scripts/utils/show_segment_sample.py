"""Quick script to show segment structure"""
import json
import sys
from pathlib import Path

filepath = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/processed/goog-20241231_segmented_risks.json")

with open(filepath) as f:
    data = json.load(f)

# Show metadata
print("="*80)
print("FILE METADATA")
print("="*80)
metadata = {k: v for k, v in data.items() if k != 'segments'}
print(json.dumps(metadata, indent=2))

# Show first segment as example
print("\n" + "="*80)
print("FIRST SEGMENT SAMPLE")
print("="*80)
segment = data['segments'][0]
print(json.dumps(segment, indent=2)[:2000])
print("\n[Truncated for display...]")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Total segments: {len(data['segments'])}")
print(f"Sentiment enabled: {data.get('sentiment_analysis_enabled', False)}")
if 'aggregate_sentiment' in data:
    print("\nAggregate Sentiment:")
    for k, v in data['aggregate_sentiment'].items():
        print(f"  {k}: {v:.4f}")
