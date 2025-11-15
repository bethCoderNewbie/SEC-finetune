"""
Debug script to understand the node structure
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import SECSectionExtractor
from src.config import RAW_DATA_DIR
import sec_parser as sp

def debug_node_structure():
    # Find HTML file
    html_files = list(RAW_DATA_DIR.glob("*.html"))
    input_file = html_files[0]

    print(f"Analyzing: {input_file.name}\n")

    # Parse filing
    parser = SECFilingParser()
    filing = parser.parse_filing(input_file, form_type="10-K")

    # Find the Risk Factors node
    extractor = SECSectionExtractor()

    print("Searching for ITEM 1A node...")
    for i, node in enumerate(filing.tree.nodes):
        if isinstance(node.semantic_element, sp.TitleElement):
            if "1a" in node.text.lower() or "1 a" in node.text.lower():
                print(f"\nFound potential ITEM 1A node at index {i}:")
                print(f"  Type: {node.semantic_element.__class__.__name__}")
                print(f"  Text: {repr(node.text)}")
                print(f"  Text length: {len(node.text)}")

                # Check descendants
                print(f"\n  Checking descendants:")
                try:
                    descendants = list(node.get_descendants())
                    print(f"    Total descendants: {len(descendants)}")

                    if descendants:
                        print(f"\n    First 10 descendants:")
                        for j, desc in enumerate(descendants[:10], 1):
                            desc_type = desc.semantic_element.__class__.__name__
                            desc_text = desc.text[:100] if hasattr(desc, 'text') else 'N/A'
                            print(f"      {j}. {desc_type}: {repr(desc_text)}...")
                    else:
                        print("    NO DESCENDANTS FOUND!")
                        print("\n    This might mean:")
                        print("    - The node is a leaf node (title only)")
                        print("    - Content is at the same level, not nested")

                    # Check siblings
                    print(f"\n  Checking next siblings:")
                    start_idx = i + 1
                    for j, sibling in enumerate(list(filing.tree.nodes)[start_idx:start_idx+5], 1):
                        sib_type = sibling.semantic_element.__class__.__name__
                        sib_text = sibling.text[:80] if hasattr(sibling, 'text') else 'N/A'
                        print(f"    {j}. {sib_type}: {repr(sib_text)}...")

                except Exception as e:
                    print(f"    ERROR getting descendants: {e}")

                break

if __name__ == "__main__":
    debug_node_structure()
