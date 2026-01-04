"""
Utility script to inspect parsed SEC filings saved as JSON files
Helps verify parsing results and explore the structure of ParsedFiling objects

Usage:
    python scripts/inspect_parsed.py list
    python scripts/inspect_parsed.py inspect <json_file>
    python scripts/inspect_parsed.py inspect <json_file> --samples --max-samples 10
"""

from pathlib import Path
from typing import Union, Optional
import argparse

from src.preprocessing.parser import ParsedFiling


def inspect_parsed_filing(
    pickle_path: Union[str, Path],
    show_sections: bool = True,
    show_elements: bool = True,
    show_samples: bool = False,
    max_samples: int = 5
) -> None:
    """
    Load and inspect a parsed SEC filing from JSON file

    Args:
        pickle_path: Path to the JSON file (.json or .pkl)
        show_sections: Whether to display section names
        show_elements: Whether to display element type counts
        show_samples: Whether to display sample content from elements
        max_samples: Maximum number of sample elements to show
    """
    pickle_path = Path(pickle_path)

    print(f"Loading parsed filing from: {pickle_path}")
    print("=" * 80)

    # Load the filing data
    try:
        data = ParsedFiling.load_from_pickle(pickle_path)
    except Exception as e:
        print(f"ERROR: Failed to load pickle file: {e}")
        return

    # Display basic information
    print(f"\nForm Type: {data['form_type']}")
    print(f"Total Elements: {len(data['elements'])}")
    print(f"File Size: {pickle_path.stat().st_size / 1024:.2f} KB")
    print(f"Format Version: {data.get('version', 'unknown')}")

    # Display metadata
    if data.get('metadata'):
        print("\n--- Metadata ---")
        for key, value in data['metadata'].items():
            if key == 'element_types':
                continue  # Show this separately
            print(f"  {key}: {value}")

    # Display section names
    if show_sections:
        print("\n--- Section Names ---")
        sections = data.get('section_names', [])
        if sections:
            for idx, section in enumerate(sections, 1):
                print(f"  {idx}. {section}")
        else:
            print("  No top-level sections found")

    # Display element type counts
    if show_elements and data.get('metadata') and 'element_types' in data['metadata']:
        print("\n--- Element Type Counts ---")
        element_types = data['metadata']['element_types']
        # Sort by count (descending)
        sorted_types = sorted(
            element_types.items(),
            key=lambda x: x[1],
            reverse=True
        )
        for element_type, count in sorted_types:
            print(f"  {element_type}: {count}")

    # Display sample elements
    if show_samples and data.get('elements'):
        print(f"\n--- Sample Elements (first {max_samples}) ---")
        for idx, element_data in enumerate(data['elements'][:max_samples], 1):
            element_type = element_data.get('type', 'Unknown')
            text = element_data.get('text', '').strip()
            text_preview = text[:100] + "..." if len(text) > 100 else text
            print(f"\n  {idx}. {element_type}")
            if text_preview:
                # Handle Unicode characters safely for Windows console
                try:
                    print(f"     Text: {text_preview}")
                except UnicodeEncodeError:
                    # Fallback to ASCII-safe representation
                    safe_text = text_preview.encode('ascii', errors='replace').decode('ascii')
                    print(f"     Text: {safe_text}")

    print("\n" + "=" * 80)
    print("Inspection complete!")


def list_parsed_filings(directory: Union[str, Path]) -> None:
    """
    List all parsed filing JSON files in a directory

    Args:
        directory: Directory to search for JSON files (.json or .pkl)
    """
    directory = Path(directory)

    if not directory.exists():
        print(f"Directory not found: {directory}")
        return

    # Look for both .pkl and .json files
    pickle_files = list(directory.glob("*.pkl")) + list(directory.glob("*.json"))

    if not pickle_files:
        print(f"No parsed files (.json or .pkl) found in: {directory}")
        return

    print(f"Found {len(pickle_files)} parsed filing(s) in: {directory}")
    print("=" * 80)

    for idx, pickle_file in enumerate(sorted(pickle_files), 1):
        size_kb = pickle_file.stat().st_size / 1024
        modified = pickle_file.stat().st_mtime

        print(f"{idx}. {pickle_file.name}")
        print(f"   Size: {size_kb:.2f} KB")
        print(f"   Modified: {Path(pickle_file).stat().st_mtime}")

        # Try to load and show basic info
        try:
            data = ParsedFiling.load_from_pickle(pickle_file)
            print(f"   Form: {data['form_type']}")
            print(f"   Elements: {len(data['elements'])}")
        except Exception as e:
            print(f"   ERROR: Could not load file - {e}")
        print()


def main():
    """Command-line interface for inspecting parsed filings"""
    parser = argparse.ArgumentParser(
        description="Inspect parsed SEC filings saved as JSON files"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Inspect command
    inspect_parser = subparsers.add_parser('inspect', help='Inspect a single JSON file')
    inspect_parser.add_argument(
        'pickle_file',
        type=str,
        help='Path to JSON file (.json or .pkl)'
    )
    inspect_parser.add_argument(
        '--no-sections',
        action='store_true',
        help='Hide section names'
    )
    inspect_parser.add_argument(
        '--no-elements',
        action='store_true',
        help='Hide element type counts'
    )
    inspect_parser.add_argument(
        '--samples',
        action='store_true',
        help='Show sample content from elements'
    )
    inspect_parser.add_argument(
        '--max-samples',
        type=int,
        default=5,
        help='Maximum number of samples to show (default: 5)'
    )

    # List command
    list_parser = subparsers.add_parser('list', help='List all JSON files in a directory')
    list_parser.add_argument(
        'directory',
        type=str,
        nargs='?',
        help='Directory to search for JSON files (default: data/interim/parsed)'
    )

    args = parser.parse_args()

    if args.command == 'inspect':
        inspect_parsed_filing(
            args.pickle_file,
            show_sections=not args.no_sections,
            show_elements=not args.no_elements,
            show_samples=args.samples,
            max_samples=args.max_samples
        )
    elif args.command == 'list':
        # Default to PARSED_DATA_DIR if no directory specified
        if args.directory:
            directory = args.directory
        else:
            from src.config import settings
            directory = settings.paths.parsed_data_dir

        list_parsed_filings(directory)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
