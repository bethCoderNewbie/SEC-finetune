"""
Exploratory Data Analysis: Analyze SEC Filing Data

Purpose: Perform EDA on parsed SEC filings and extracted risk factors
Stage: 3 - Exploratory Data Analysis
Input: data/interim/ - Parsed filings, extracted sections
Output: reports/figures/ - Visualizations and statistical summaries

Usage:
    python scripts/03_eda/exploratory_analysis.py
    python scripts/03_eda/exploratory_analysis.py --output-dir reports/eda_2024
"""

import argparse
from pathlib import Path
import sys
from typing import Dict, List
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import PARSED_DATA_DIR, EXTRACTED_DATA_DIR


def analyze_filing_statistics(data_dir: Path) -> Dict:
    """
    Compute basic statistics about filings

    Args:
        data_dir: Directory containing parsed filing data

    Returns:
        Dictionary with statistical summaries
    """
    stats = {
        'num_filings': 0,
        'avg_length': 0,
        'avg_sections': 0,
        'risk_factors_found': 0
    }

    # TODO: Implement statistical analysis
    # - Count total filings
    # - Analyze text length distribution
    # - Count sections per filing
    # - Identify missing sections
    # - Analyze filing dates over time

    print("[TODO] Implement filing statistics analysis")
    return stats


def analyze_risk_factors(data_dir: Path) -> Dict:
    """
    Analyze extracted risk factors

    Args:
        data_dir: Directory containing extracted risk data

    Returns:
        Dictionary with risk factor analysis
    """
    analysis = {
        'num_risks': 0,
        'avg_risk_length': 0,
        'common_themes': []
    }

    # TODO: Implement risk factor analysis
    # - Count total risk factors
    # - Analyze length distribution
    # - Extract common keywords/themes
    # - Identify risk categories
    # - Analyze year-over-year changes

    print("[TODO] Implement risk factor analysis")
    return analysis


def generate_visualizations(stats: Dict, output_dir: Path):
    """
    Generate EDA visualizations

    Args:
        stats: Statistical summaries
        output_dir: Directory to save visualizations
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # TODO: Create visualizations using matplotlib/seaborn
    # - Text length distributions
    # - Section coverage heatmap
    # - Risk factor word clouds
    # - Temporal trends
    # - Company comparisons

    print(f"[TODO] Generate visualizations to {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Perform exploratory data analysis on SEC filings"
    )
    parser.add_argument(
        '--parsed-dir',
        type=str,
        default=str(PARSED_DATA_DIR),
        help='Directory containing parsed filings'
    )
    parser.add_argument(
        '--extracted-dir',
        type=str,
        default=str(EXTRACTED_DATA_DIR),
        help='Directory containing extracted sections'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='reports/figures',
        help='Output directory for visualizations'
    )

    args = parser.parse_args()

    print("SEC Filing Exploratory Data Analysis")
    print("=" * 80)

    # Analyze filings
    print("\n1. Analyzing filing statistics...")
    filing_stats = analyze_filing_statistics(Path(args.parsed_dir))

    # Analyze risk factors
    print("\n2. Analyzing risk factors...")
    risk_stats = analyze_risk_factors(Path(args.extracted_dir))

    # Generate visualizations
    print("\n3. Generating visualizations...")
    generate_visualizations(
        {**filing_stats, **risk_stats},
        Path(args.output_dir)
    )

    print("\n" + "=" * 80)
    print("EDA Complete!")
    print(f"Results saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
