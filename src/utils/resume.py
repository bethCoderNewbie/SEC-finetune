"""Output-existence-based resume filter for batch processing.

Checks whether output files already exist to skip reprocessing, enabling
efficient resume of interrupted batch runs without recomputing hashes.

This is complementary to StateManifest (which uses content hashes for
change detection). Use ResumeFilter when you just want to skip files that
already have output — the common pattern for long batch preprocessing runs.

Usage:
    from src.utils.resume import ResumeFilter

    resume_filter = ResumeFilter(
        output_dir=Path("data/processed"),
        output_suffix="_segmented.json"
    )

    # Filter a list down to only unprocessed files
    pending = resume_filter.filter_unprocessed(all_html_files)

    # Single-file check
    if resume_filter.is_processed(Path("data/raw/AAPL_10K.html")):
        print("Already done, skipping")
"""

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class ResumeFilter:
    """
    Output-existence-based resume filter for batch processing.

    Checks whether an output file exists in ``output_dir`` for each input
    file. Uses a bulk O(1) lookup (glob + set) rather than per-file stat
    calls, so filtering thousands of files is fast.

    Args:
        output_dir: Directory where processed output files are written.
        output_suffix: Suffix appended to the input file stem to form the
            output filename. Examples: ``"_segmented.json"``,
            ``"_segmented_risks.json"``, ``"_extracted_risks.json"``.

    Example:
        >>> f = ResumeFilter(Path("data/processed"), "_segmented.json")
        >>> pending = f.filter_unprocessed(html_files)
        Resume mode: Skipping 42 already processed files
    """

    def __init__(self, output_dir: Path, output_suffix: str = "_segmented.json"):
        self.output_dir = Path(output_dir)
        self.output_suffix = output_suffix

        # Derive the stem portion of the suffix (strips extension).
        # e.g. "_segmented.json" -> "_segmented"
        #      "_segmented_risks.json" -> "_segmented_risks"
        self._stem_suffix = Path(output_suffix).stem

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_processed(self, input_file: Path) -> bool:
        """
        Check whether an output file already exists for *input_file*.

        Args:
            input_file: Path to the raw input file (e.g. HTML filing).

        Returns:
            True if the expected output file exists, False otherwise.
        """
        output_path = self.output_dir / f"{input_file.stem}{self.output_suffix}"
        return output_path.exists()

    def get_processed_stems(self) -> set:
        """
        Return the set of input-file stems that already have output.

        Performs a single glob over ``output_dir`` and strips the output
        suffix, giving an O(1)-lookup set for batch filtering.

        Returns:
            Set of stems (str) corresponding to already-processed inputs.
            Empty set if ``output_dir`` does not exist yet.
        """
        if not self.output_dir.exists():
            return set()

        processed = set()
        for f in self.output_dir.glob(f"*{self.output_suffix}"):
            stem = self._strip_stem_suffix(f.stem)
            processed.add(stem)

        return processed

    def filter_unprocessed(
        self,
        input_files: List[Path],
        quiet: bool = False,
    ) -> List[Path]:
        """
        Return only the files from *input_files* that have not yet been
        processed (i.e. whose output file does not exist in *output_dir*).

        Uses a single bulk lookup via :meth:`get_processed_stems` rather
        than stat-ing each file individually.

        Args:
            input_files: Full list of candidate input files.
            quiet: If True, suppress the skip-count message.

        Returns:
            Subset of *input_files* that still need processing.
        """
        processed_stems = self.get_processed_stems()
        unprocessed = [f for f in input_files if f.stem not in processed_stems]

        skipped = len(input_files) - len(unprocessed)
        if skipped > 0 and not quiet:
            print(f"Resume mode: Skipping {skipped} already processed files")

        logger.info(
            "Resume filter: %d/%d files pending (%d skipped)",
            len(unprocessed), len(input_files), skipped,
        )
        return unprocessed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _strip_stem_suffix(self, stem: str) -> str:
        """Strip the stem-suffix from the *right* end of *stem*.

        Strips from the right end only, so input filenames that happen to
        contain the suffix string in the middle are handled correctly.

        Example:
            stem="_segmented_risks"  ->  ""   (edge case, handled)
            stem="AAPL_10K_segmented"  ->  "AAPL_10K"
        """
        if stem.endswith(self._stem_suffix):
            return stem[: -len(self._stem_suffix)]
        return stem
