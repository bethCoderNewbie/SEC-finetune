"""
Data Collection: Download SEC Filings from EDGAR

Purpose: Fetch 10-K/10-Q filings from SEC EDGAR for specified companies
Stage: 1 - Data Collection
Output: data/raw/ - Raw HTML filings

Usage:
    python scripts/01_data_collection/download_sec_filings.py --ticker AAPL
    python scripts/01_data_collection/download_sec_filings.py --ticker-file tickers.txt
"""

import argparse
from pathlib import Path
from typing import List
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings


def download_filings(
    tickers: List[str],
    form_type: str = "10-K",
    num_filings: int = 1,
    after_date: str = None,
    before_date: str = None
):
    """
    Download SEC filings for specified tickers

    Args:
        tickers: List of company ticker symbols
        form_type: Type of SEC form (10-K, 10-Q)
        num_filings: Number of filings to download per ticker
        after_date: Download filings after this date (YYYY-MM-DD)
        before_date: Download filings before this date (YYYY-MM-DD)

    Returns:
        List of downloaded file paths
    """
    settings.paths.ensure_directories()

    print(f"Downloading {form_type} filings for {len(tickers)} ticker(s)")
    print(f"Output directory: {settings.paths.raw_data_dir}")
    print("=" * 80)

    # TODO: Implement using src/acquisition/edgar_client.py
    # Example implementation:
    # from src.acquisition.edgar_client import EdgarClient
    #
    # client = EdgarClient()
    # downloaded_files = []
    #
    # for ticker in tickers:
    #     filings = client.get_filings(
    #         ticker=ticker,
    #         form_type=form_type,
    #         num_filings=num_filings,
    #         after_date=after_date,
    #         before_date=before_date
    #     )
    #
    #     for filing in filings:
    #         file_path = client.download_filing(
    #             filing,
    #             output_dir=RAW_DATA_DIR
    #         )
    #         downloaded_files.append(file_path)
    #         print(f"Downloaded: {file_path.name}")
    #
    # return downloaded_files

    print("[TODO] Implement filing download logic")
    print("See: src/acquisition/edgar_client.py")
    return []


def main():
    parser = argparse.ArgumentParser(
        description="Download SEC filings from EDGAR"
    )
    parser.add_argument(
        '--ticker',
        type=str,
        help='Single ticker symbol (e.g., AAPL)'
    )
    parser.add_argument(
        '--ticker-file',
        type=str,
        help='Path to file containing ticker symbols (one per line)'
    )
    parser.add_argument(
        '--form-type',
        type=str,
        default='10-K',
        choices=['10-K', '10-Q'],
        help='Type of SEC form (default: 10-K)'
    )
    parser.add_argument(
        '--num-filings',
        type=int,
        default=1,
        help='Number of filings to download per ticker (default: 1)'
    )
    parser.add_argument(
        '--after-date',
        type=str,
        help='Download filings after this date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--before-date',
        type=str,
        help='Download filings before this date (YYYY-MM-DD)'
    )

    args = parser.parse_args()

    # Get ticker list
    tickers = []
    if args.ticker:
        tickers = [args.ticker.upper()]
    elif args.ticker_file:
        with open(args.ticker_file, 'r') as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    else:
        parser.error("Either --ticker or --ticker-file must be provided")

    # Download filings
    download_filings(
        tickers=tickers,
        form_type=args.form_type,
        num_filings=args.num_filings,
        after_date=args.after_date,
        before_date=args.before_date
    )


if __name__ == "__main__":
    main()
