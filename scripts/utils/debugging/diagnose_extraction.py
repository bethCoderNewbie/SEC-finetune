"""
Diagnostic Script: Investigate why Risk Factors section is not found

This script performs a 5 Whys analysis by examining:
1. What sections are actually in the filing
2. What identifiers sec-parser assigned
3. What text content exists
4. How normalization affects matching
5. What the tree structure looks like
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import SECSectionExtractor
from src.config import RAW_DATA_DIR

try:
    import sec_parser as sp
except ImportError:
    print("ERROR: sec-parser not installed")
    sys.exit(1)


def diagnose_extraction_failure(input_file: Path):
    """
    Comprehensive diagnostic of extraction failure

    Performs 5 Whys analysis:
    - Why 1: Section not found - check if parsing succeeded
    - Why 2: Tree navigation failed - check tree structure
    - Why 3: Identifier mismatch - check identifiers
    - Why 4: Text matching failed - check text normalization
    - Why 5: Wrong form type - check form type detection
    """

    print("=" * 80)
    print("DIAGNOSTIC REPORT: Risk Factors Extraction Failure")
    print("=" * 80)
    print(f"\nInput file: {input_file.name}")

    # Step 1: Parse the filing
    print("\n" + "=" * 80)
    print("STEP 1: Parsing Filing")
    print("=" * 80)

    parser = SECFilingParser()
    try:
        filing = parser.parse_filing(input_file, form_type="10-K")
        print("[OK] Parsing succeeded")
        print(f"  - Total elements: {len(filing)}")
        print(f"  - Form type: {filing.form_type.value}")
        # Convert generator to list to get length
        tree_nodes = list(filing.tree.nodes)
        print(f"  - Tree nodes: {len(tree_nodes)}")
    except Exception as e:
        print(f"[FAIL] Parsing FAILED: {e}")
        return

    # Step 2: Examine tree structure
    print("\n" + "=" * 80)
    print("STEP 2: Tree Structure Analysis")
    print("=" * 80)

    top_sections = []
    for i, node in enumerate(filing.tree.nodes):
        if isinstance(node.semantic_element, sp.TopSectionTitle):
            top_sections.append(node)

    print(f"Found {len(top_sections)} top-level sections:")
    print()

    for i, node in enumerate(top_sections[:20]):  # Show first 20
        print(f"{i+1}. Type: {node.semantic_element.__class__.__name__}")

        # Check for identifier attribute
        identifier = getattr(node.semantic_element, 'identifier', None)
        print(f"   Identifier: {identifier if identifier else 'NOT SET'}")

        # Show text (truncated)
        text = node.text.strip()[:100]
        print(f"   Text: {text}...")
        print()

    # Step 3: Search for Risk Factors by various methods
    print("\n" + "=" * 80)
    print("STEP 3: Searching for 'Risk Factors' Section")
    print("=" * 80)

    # Method 1: By identifier "part1item1a"
    print("\n[Method 1] Searching by identifier 'part1item1a':")
    found_by_id = False
    for node in filing.tree.nodes:
        if isinstance(node.semantic_element, sp.TopSectionTitle):
            identifier = getattr(node.semantic_element, 'identifier', None)
            if identifier == "part1item1a":
                print("[OK] FOUND by identifier!")
                print(f"  Text: {node.text[:200]}")
                found_by_id = True
                break

    if not found_by_id:
        print("[FAIL] NOT FOUND by identifier 'part1item1a'")

    # Method 2: By text content search
    print("\n[Method 2] Searching by text content 'risk factors':")
    risk_keywords = ['risk factors', 'item 1a', 'item1a']

    for node in filing.tree.nodes:
        if isinstance(node.semantic_element, sp.TopSectionTitle):
            text_lower = node.text.lower()

            for keyword in risk_keywords:
                if keyword in text_lower:
                    identifier = getattr(node.semantic_element, 'identifier', None)
                    print(f"[OK] FOUND section containing '{keyword}':")
                    print(f"  Identifier: {identifier}")
                    print(f"  Full text: {node.text[:200]}")
                    print()

    # Method 3: Search ALL elements (not just TopSectionTitle)
    print("\n[Method 3] Searching ALL semantic elements for 'risk':")
    risk_elements = []

    for element in filing.elements[:100]:  # Check first 100 elements
        text = str(element.text).lower()
        if 'risk' in text and 'factor' in text:
            risk_elements.append(element)

    print(f"Found {len(risk_elements)} elements mentioning 'risk factors'")

    for elem in risk_elements[:5]:  # Show first 5
        print(f"  - Type: {elem.__class__.__name__}")
        print(f"    Text: {elem.text[:100]}...")
        print()

    # Step 4: Test the extractor
    print("\n" + "=" * 80)
    print("STEP 4: Testing SECSectionExtractor")
    print("=" * 80)

    extractor = SECSectionExtractor()

    # Try to extract
    print("\nAttempting to extract Risk Factors...")
    risk_section = extractor.extract_risk_factors(filing)

    if risk_section:
        print("[OK] SUCCESS! Risk Factors extracted")
        print(f"  Title: {risk_section.title}")
        print(f"  Length: {len(risk_section):,} characters")
        print(f"  Subsections: {len(risk_section.subsections)}")
    else:
        print("[FAIL] FAILED - Risk Factors section not found")

        # Debug the _find_section_node method
        print("\nDebugging _find_section_node()...")

        section_id = "part1item1a"
        form_type = "10-K"

        print(f"  Looking for section_id: {section_id}")
        print(f"  Form type: {form_type}")

        expected_title = extractor._get_section_title(section_id, form_type)
        print(f"  Expected title: {expected_title}")

        normalized_expected = extractor._normalize_title(expected_title)
        print(f"  Normalized expected: '{normalized_expected}'")

        print("\n  Checking each TopSectionTitle node:")
        for i, node in enumerate(filing.tree.nodes):
            if not isinstance(node.semantic_element, sp.TopSectionTitle):
                continue

            identifier = getattr(node.semantic_element, 'identifier', None)
            node_text_normalized = extractor._normalize_title(node.text)

            print(f"\n  Node {i+1}:")
            print(f"    Identifier: {identifier}")
            print(f"    Raw text: {node.text[:80]}")
            print(f"    Normalized: '{node_text_normalized[:80]}'")
            print(f"    Match by ID: {identifier == section_id if identifier else 'N/A'}")
            print(f"    Match by text: {normalized_expected in node_text_normalized}")

            if i >= 10:  # Limit output
                print("\n  ... (showing first 10 nodes only)")
                break

    # Step 5: Root Cause Analysis
    print("\n" + "=" * 80)
    print("STEP 5: ROOT CAUSE ANALYSIS (5 Whys)")
    print("=" * 80)

    print("""
WHY 1: Why is the Risk Factors section not found?
=> The _find_section_node() method returns None

WHY 2: Why does _find_section_node() return None?
=> Either:
  a) No TopSectionTitle nodes exist in tree.nodes, OR
  b) None of the TopSectionTitle nodes match the section_id

WHY 3: Why don't the TopSectionTitle nodes match?
=> Either:
  a) node.semantic_element.identifier is not set to 'part1item1a', OR
  b) The text normalization doesn't match

WHY 4: Why isn't the identifier set correctly?
=> Possible reasons:
  a) sec-parser version doesn't support identifier attribute
  b) The HTML structure doesn't allow sec-parser to detect sections
  c) The filing is not a standard 10-K format

WHY 5: What is the actual root cause?
=> Check the diagnostic output above to determine:
  1. If TopSectionTitle nodes exist
  2. If identifier attributes are set
  3. If text matching logic works
  4. If the filing is properly formatted
    """)

    # Step 6: Recommendations
    print("\n" + "=" * 80)
    print("STEP 6: RECOMMENDATIONS")
    print("=" * 80)

    if not top_sections:
        print("""
[CRITICAL] No TopSectionTitle nodes found!

ROOT CAUSE: The sec-parser library did not detect any top-level sections.

POSSIBLE SOLUTIONS:
1. Verify HTML file is a valid SEC filing (10-K format)
2. Check if file is HTML (not TXT)
3. Update sec-parser to latest version
4. Try with a different SEC filing as a test
        """)

    elif found_by_id:
        print("""
[OK] Section exists with correct identifier!

This means the extraction SHOULD work. If it didn't, check:
1. Form type detection (is it detecting as 10-K?)
2. Tree structure (is the node in tree.nodes?)
        """)

    else:
        print("""
[WARNING] TopSectionTitle nodes exist, but identifiers may not be set correctly

RECOMMENDED SOLUTIONS (in order):

1. IMMEDIATE FIX: Use relaxed text matching
   - Modify _find_section_node to be more flexible
   - Check for partial matches
   - Case-insensitive matching

2. HTML FORMAT: Check if the input file format is correct
   - Must be HTML (not TXT)
   - Should be from EDGAR system
   - Download fresh copy if needed

3. SEC-PARSER VERSION: Update to latest version
   - Current implementation may have bugs
   - Newer versions may have better section detection

4. FALLBACK STRATEGY: Implement regex-based extraction
   - If semantic parsing fails, use text patterns
   - More robust for edge cases
        """)

    print("\n" + "=" * 80)
    print("END OF DIAGNOSTIC REPORT")
    print("=" * 80)


if __name__ == "__main__":
    # Use the first HTML file in raw data directory
    html_files = list(RAW_DATA_DIR.glob("*.html"))

    if not html_files:
        print(f"No HTML files found in {RAW_DATA_DIR}")
        print("Please add a 10-K HTML file to the data/raw/ directory")
        sys.exit(1)

    input_file = html_files[0]
    print(f"Analyzing: {input_file.name}\n")

    diagnose_extraction_failure(input_file)
