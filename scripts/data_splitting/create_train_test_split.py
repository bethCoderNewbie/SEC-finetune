"""
Data Splitting: Create Train/Validation/Test Splits

Purpose: Split processed data into train/validation/test sets
Stage: 5 - Data Splitting
Input: data/processed/ - Processed features and labels
Output: data/processed/splits/ - Train/val/test datasets

Usage:
    python scripts/05_data_splitting/create_train_test_split.py
    python scripts/05_data_splitting/create_train_test_split.py --test-size 0.2 --val-size 0.1
"""

import argparse
from pathlib import Path
import sys
import json
from typing import Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import PROCESSED_DATA_DIR


def load_processed_data(data_dir: Path):
    """
    Load processed data for splitting

    Args:
        data_dir: Directory containing processed data

    Returns:
        Combined dataset
    """
    # TODO: Implement data loading
    # - Load features and labels
    # - Combine into single dataset
    # - Handle different data formats

    print(f"[TODO] Load processed data from {data_dir}")
    return None


def stratified_split(
    dataset,
    test_size: float = 0.2,
    val_size: float = 0.1,
    random_state: int = 42
) -> Tuple:
    """
    Create stratified train/val/test splits

    Args:
        dataset: Full dataset
        test_size: Proportion for test set
        val_size: Proportion for validation set
        random_state: Random seed for reproducibility

    Returns:
        Tuple of (train, val, test) datasets
    """
    # TODO: Implement stratified splitting
    # - Use sklearn.model_selection.train_test_split
    # - Ensure stratification by important variables:
    #   * Company ticker (for diversity)
    #   * Year (temporal distribution)
    #   * Risk categories (label distribution)
    # - Maintain temporal ordering if needed
    #
    # Example:
    # from sklearn.model_selection import train_test_split
    #
    # # First split: train+val vs test
    # train_val, test = train_test_split(
    #     dataset,
    #     test_size=test_size,
    #     stratify=dataset['labels'],
    #     random_state=random_state
    # )
    #
    # # Second split: train vs val
    # val_ratio = val_size / (1 - test_size)
    # train, val = train_test_split(
    #     train_val,
    #     test_size=val_ratio,
    #     stratify=train_val['labels'],
    #     random_state=random_state
    # )

    print(f"[TODO] Create splits: test={test_size}, val={val_size}")
    return None, None, None


def temporal_split(dataset, test_cutoff_year: int, val_cutoff_year: int) -> Tuple:
    """
    Create temporal train/val/test splits

    Args:
        dataset: Full dataset with temporal information
        test_cutoff_year: Year to start test set
        val_cutoff_year: Year to start validation set

    Returns:
        Tuple of (train, val, test) datasets
    """
    # TODO: Implement temporal splitting
    # Important for time-series data:
    # - Train on older data (e.g., 2015-2019)
    # - Validate on middle period (e.g., 2020-2021)
    # - Test on recent data (e.g., 2022-2024)
    # This prevents data leakage from future to past

    print(f"[TODO] Create temporal splits: val>={val_cutoff_year}, test>={test_cutoff_year}")
    return None, None, None


def save_splits(train, val, test, output_dir: Path):
    """
    Save train/val/test splits

    Args:
        train: Training dataset
        val: Validation dataset
        test: Test dataset
        output_dir: Directory to save splits
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # TODO: Save splits in appropriate format
    # - Save as separate files: train.json, val.json, test.json
    # - Include metadata: split sizes, date ranges, statistics
    # - Consider compression for large datasets
    # - Version with DVC

    print(f"[TODO] Save splits to {output_dir}")


def analyze_splits(train, val, test):
    """
    Analyze split distributions

    Args:
        train: Training dataset
        val: Validation dataset
        test: Test dataset
    """
    # TODO: Analyze split statistics
    # - Dataset sizes
    # - Label distributions
    # - Company distributions
    # - Temporal coverage
    # - Statistical tests for distribution similarity

    print("[TODO] Analyze split distributions")


def main():
    parser = argparse.ArgumentParser(
        description="Create train/validation/test splits"
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default=str(PROCESSED_DATA_DIR),
        help='Directory containing processed data'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=str(PROCESSED_DATA_DIR / "splits"),
        help='Output directory for splits'
    )
    parser.add_argument(
        '--test-size',
        type=float,
        default=0.2,
        help='Proportion for test set (default: 0.2)'
    )
    parser.add_argument(
        '--val-size',
        type=float,
        default=0.1,
        help='Proportion for validation set (default: 0.1)'
    )
    parser.add_argument(
        '--split-type',
        type=str,
        default='stratified',
        choices=['stratified', 'temporal'],
        help='Type of split to create'
    )
    parser.add_argument(
        '--temporal-test-year',
        type=int,
        help='Year to start test set (for temporal split)'
    )
    parser.add_argument(
        '--temporal-val-year',
        type=int,
        help='Year to start validation set (for temporal split)'
    )
    parser.add_argument(
        '--random-seed',
        type=int,
        default=42,
        help='Random seed for reproducibility'
    )

    args = parser.parse_args()

    print("Data Splitting Pipeline")
    print("=" * 80)
    print(f"Split type: {args.split_type}")
    print(f"Test size: {args.test_size}")
    print(f"Validation size: {args.val_size}")
    print("=" * 80)

    # Load data
    print("\n1. Loading processed data...")
    dataset = load_processed_data(Path(args.data_dir))

    # Create splits
    print("\n2. Creating splits...")
    if args.split_type == 'stratified':
        train, val, test = stratified_split(
            dataset,
            test_size=args.test_size,
            val_size=args.val_size,
            random_state=args.random_seed
        )
    else:  # temporal
        if not args.temporal_test_year or not args.temporal_val_year:
            parser.error("--temporal-test-year and --temporal-val-year required for temporal split")
        train, val, test = temporal_split(
            dataset,
            test_cutoff_year=args.temporal_test_year,
            val_cutoff_year=args.temporal_val_year
        )

    # Analyze splits
    print("\n3. Analyzing splits...")
    analyze_splits(train, val, test)

    # Save splits
    print("\n4. Saving splits...")
    save_splits(train, val, test, Path(args.output_dir))

    print("\n" + "=" * 80)
    print("Data splitting complete!")
    print(f"Splits saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
