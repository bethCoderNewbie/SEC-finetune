#!/usr/bin/env python3
"""
consolidate_sasb_taxonomy.py

Reconcile and enrich the SEC-finetune SASB taxonomy files using the
authoritative SASB Navigator scrape (77 industries, official names).

Source:
  scripts/data_collection/data/sasb_materiality_all.json

Targets:
  src/analysis/taxonomies/sasb_sics_mapping.json   (adds topics for ~52 new industries)
  src/analysis/taxonomies/archetype_to_sasb.yaml   (adds ~47 missing industries)

Modes:
  (default)   Print reconciliation report only; no files written.
  --write     Write *_updated.* files alongside originals in taxonomies dir.
  --in-place  Overwrite originals (creates .bak backups first).

Name Policy:
  Existing industry names in both taxonomy files are PRESERVED to maintain
  consistency with the sic_to_sasb lookup chain (sic → name → archetype).
  New industries (those in SASB but not in any existing file) are added using
  official SASB names; SIC codes for those would need to be added separately.
  Name mismatches are reported so you can decide whether to align them.
"""

import argparse
import json
import re
import shutil
import textwrap
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT  = Path(__file__).resolve().parents[2]
SCRAPE_PATH = REPO_ROOT / "scripts/data_collection/data/sasb_materiality_all.json"
SICS_PATH   = REPO_ROOT / "src/analysis/taxonomies/sasb_sics_mapping.json"
ARCH_PATH   = REPO_ROOT / "src/analysis/taxonomies/archetype_to_sasb.yaml"

# ---------------------------------------------------------------------------
# Dimension → archetype key mapping
# ---------------------------------------------------------------------------

DIM_TO_ARCH: dict[str, str] = {
    "Environment":                 "environment",
    "Social Capital":              "social_capital",
    "Human Capital":               "human_capital",
    "Business Model and Innovation": "business_model",
    "Leadership & Governance":     "governance",
}

# ---------------------------------------------------------------------------
# Known name aliases: old name used in existing files → official SASB name.
# These are one-way aliases for REPORTING only — the existing names are kept
# in the output files unless --rename is explicitly specified.
# ---------------------------------------------------------------------------

_NAME_ALIASES: dict[str, str] = {
    "Electric Utilities":
        "Electric Utilities & Power Generators",
    "Water Utilities":
        "Water Utilities & Services",
    "Pharmaceuticals":
        "Biotechnology & Pharmaceuticals",
    "Biotechnology":
        "Biotechnology & Pharmaceuticals",
    "Telecommunications":
        "Telecommunication Services",
    "Aerospace & Defense":
        "Aerospace & Defence",
    "Real Estate Owners, Developers & Investment Trusts":
        "Real Estate",
}

# Reverse alias: official name → list of old names it replaces
_OFFICIAL_TO_OLD: dict[str, list[str]] = {}
for _old, _new in _NAME_ALIASES.items():
    _OFFICIAL_TO_OLD.setdefault(_new, []).append(_old)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _gic_key(gic_name: str) -> str:
    """'Greenhouse Gas Emissions' → 'Greenhouse_Gas_Emissions'."""
    return "_".join(gic_name.split())


def _load_scrape() -> dict:
    with open(SCRAPE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_sics() -> dict:
    with open(SICS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_arch() -> dict:
    with open(ARCH_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_industries(scrape: dict) -> dict[str, dict]:
    """
    Extract industries from scrape, keyed by official name.

    Validates topic duplication: if the scraper captured N identical GraphQL
    responses (e.g., N=2 from React prefetch + mount), every topic code in an
    industry will appear exactly N times.  We detect N automatically, warn if
    the pattern is inconsistent, and strip duplicates so downstream counts
    reflect actual unique topics.

    The root cause of N>1 is in scrape_sasb_materiality.py — it now dedupes
    at source, so clean scrape runs will always give N=1 here.
    """
    industries: dict[str, dict] = {}
    for sector in scrape["sectors"]:
        for ind in sector["industries"]:
            industries[ind["name"]] = ind

    # Detect per-industry duplication factor and report anomalies
    factors: Counter = Counter()
    anomalies: list[str] = []

    for ind in industries.values():
        topics = ind.get("disclosure_topics", [])
        if not topics:
            factors[1] += 1
            continue

        code_counts: Counter = Counter(t.get("code", "") for t in topics)
        counts = set(code_counts.values())

        if len(counts) == 1:
            # All codes appear the same number of times — clean duplication factor
            n = counts.pop()
            factors[n] += 1
        else:
            # Mixed counts — unexpected; flag for review
            anomalies.append(
                f"{ind['name']}: uneven topic counts {dict(code_counts.most_common(3))}"
            )
            factors[max(counts)] += 1
            n = 1  # treat as unique; don't strip

        if n > 1:
            # Strip duplicates introduced by N-times GraphQL capture
            seen: set[str] = set()
            ind["disclosure_topics"] = [
                t for t in topics
                if t.get("code", "") not in seen and not seen.add(t.get("code", ""))  # type: ignore[func-returns-value]
            ]

    dominant = factors.most_common(1)[0][0] if factors else 1
    if dominant > 1:
        print(
            f"  NOTE: scrape contained {dominant}x duplicate topics per industry "
            f"({sum(factors.values())} industries affected). "
            f"Scraper dedup is now fixed; re-scrape for clean source data."
        )
    if anomalies:
        print(f"  WARNING: {len(anomalies)} industries with uneven topic counts:")
        for a in anomalies:
            print(f"    {a}")

    return industries


def _build_dim_gic_map(
    industries: dict[str, dict],
) -> dict[str, dict[str, Counter]]:
    """
    Returns:
        {official_industry_name: {dimension_name: Counter({gic_name: n_topics})}}
    """
    result: dict[str, dict[str, Counter]] = {}
    for ind in industries.values():
        name = ind["name"]
        result[name] = defaultdict(Counter)
        for topic in ind.get("disclosure_topics", []):
            dim = topic.get("dimension", "")
            gic = topic.get("gic_name", "")
            if dim and gic:
                result[name][dim][gic] += 1
    return result


def _primary_gic(counter: Counter) -> str:
    """Return the GIC key with the highest topic count; tie → alphabetical."""
    if not counter:
        return ""
    best = max(counter, key=lambda g: (counter[g], g))
    return _gic_key(best)


def _auto_description(gic_name: str, industry_name: str, dimension: str) -> str:
    """Generate a short description for auto-added sasb_topics entries."""
    readable_gic = gic_name.replace("_", " ")
    return (
        f"[Auto] {readable_gic} risks material to the {industry_name} industry "
        f"({dimension} dimension, SASB Navigator)."
    )


# ---------------------------------------------------------------------------
# Description matching: carry forward hand-authored text to official GIC entries
# ---------------------------------------------------------------------------

_STOPWORDS = {"the", "and", "of", "in", "for", "from", "to", "a", "an"}


def _norm_words(s: str) -> set[str]:
    return {
        w.lower()
        for w in re.findall(r"[a-zA-Z]+", s)
        if w.lower() not in _STOPWORDS and len(w) > 1
    }


def _match_description(
    gic_name: str,
    existing_topics: list[dict],
    threshold: float = 0.5,
) -> Optional[str]:
    """
    Find the best hand-authored description for a given official GIC name.

    Matching is word-overlap based: score = |overlap| / min(|gic_words|, |t_words|).
    Rationale: hand-authored names often use different phrasing than official GIC names
    (e.g. 'Workforce_Health_&_Safety' ↔ 'Employee Health & Safety'; both share
    'health', 'safety' → score 2/2 = 1.0).

    Returns the best description if score ≥ threshold, else None.
    """
    gic_words = _norm_words(gic_name)
    if not gic_words:
        return None

    best_score = 0.0
    best_desc: Optional[str] = None

    for t in existing_topics:
        t_words = _norm_words(t.get("name", ""))
        overlap = gic_words & t_words
        if not overlap:
            continue
        score = len(overlap) / min(len(gic_words), len(t_words))
        if score > best_score:
            best_score = score
            best_desc = t.get("description")

    return best_desc if best_score >= threshold else None


# ---------------------------------------------------------------------------
# Reconciliation report
# ---------------------------------------------------------------------------

def _all_arch_industries(arch: dict) -> set[str]:
    names: set[str] = set()
    for dim_data in arch.values():
        if isinstance(dim_data, dict):
            names.update(k for k in dim_data if k != "default")
    return names


def print_report(
    official_names: set[str],
    sics: dict,
    arch: dict,
    ind_dim_gic: dict[str, dict[str, Counter]],
) -> None:
    existing_sics  = set(sics.get("sasb_topics", {}).keys())
    existing_arch  = _all_arch_industries(arch)

    # Resolve existing names through aliases to find true coverage
    resolved_sics  = {_NAME_ALIASES.get(n, n) for n in existing_sics}
    resolved_arch  = {_NAME_ALIASES.get(n, n) for n in existing_arch}

    missing_sics   = official_names - resolved_sics
    missing_arch   = official_names - resolved_arch

    mismatch_sics  = [(n, _NAME_ALIASES[n]) for n in sorted(existing_sics)  if n in _NAME_ALIASES]
    mismatch_arch  = [(n, _NAME_ALIASES[n]) for n in sorted(existing_arch)  if n in _NAME_ALIASES]

    print()
    print("=" * 72)
    print("SASB TAXONOMY RECONCILIATION REPORT")
    print("=" * 72)
    print(f"  Official SASB industries (scrape):       {len(official_names):>3}")
    print(f"  sasb_sics_mapping.json  sasb_topics:     {len(existing_sics):>3}")
    print(f"  archetype_to_sasb.yaml  unique entries:  {len(existing_arch):>3}")

    # 1. Name mismatches
    print()
    print(f"NAME MISMATCHES — sasb_sics_mapping.json ({len(mismatch_sics)})")
    if mismatch_sics:
        for old, new in mismatch_sics:
            print(f"    '{old}'")
            print(f"      → '{new}'")
    else:
        print("    None.")

    print()
    print(f"NAME MISMATCHES — archetype_to_sasb.yaml ({len(mismatch_arch)})")
    if mismatch_arch:
        for old, new in mismatch_arch:
            print(f"    '{old}'")
            print(f"      → '{new}'")
    else:
        print("    None.")

    # 2. New industries not yet in either file
    print()
    print(f"NEW INDUSTRIES — not in sasb_sics_mapping.json ({len(missing_sics)})")
    for name in sorted(missing_sics):
        print(f"    {name}")

    print()
    print(f"NEW INDUSTRIES — not in archetype_to_sasb.yaml ({len(missing_arch)})")
    for name in sorted(missing_arch):
        print(f"    {name}")

    # 3. Primary GIC preview for new arch entries
    print()
    print("PRIMARY GIC PER DIMENSION — new archetype entries that would be added")
    print(f"  (computed from topic frequency per industry per dimension)")
    for ind_name in sorted(missing_arch):
        dim_map = ind_dim_gic.get(ind_name, {})
        if not dim_map:
            continue
        print(f"  {ind_name}:")
        for dim, arch_key in sorted(DIM_TO_ARCH.items(), key=lambda x: x[1]):
            counter = dim_map.get(dim)
            if not counter:
                continue
            pg = _primary_gic(counter)
            all_gics = ", ".join(
                f"{_gic_key(g)}({c})" for g, c in counter.most_common()
            )
            print(f"    {arch_key:20s} → {pg}  [{all_gics}]")

    print("=" * 72)
    print()


# ---------------------------------------------------------------------------
# Build enhanced sasb_sics_mapping.json
# ---------------------------------------------------------------------------

def build_enhanced_sics(
    sics: dict,
    industries: dict[str, dict],
) -> tuple[dict, list[str], list[str]]:
    """
    Rebuild sasb_topics for ALL 77 SASB industries following the SASB website hierarchy:

        Dimension → GIC (gic_code + gic_name) → Disclosure Topics

    Each entry in the output sasb_topics list represents one material GIC for that
    industry, structured as:
        {
          "dimension":        "Social Capital",          # SASB sustainability dimension
          "gic_code":         230,                       # official 3-digit GIC code
          "gic_name":         "Data Security",           # official GIC name
          "name":             "Data_Security",           # underscore key (backward compat)
          "description":      "...",                     # from hand-authored or auto-gen
          "disclosure_topics": [                         # industry-specific SASB metrics
            {"code": "TC-SI-230a", "name": "Data Security"}
          ]
        }

    Entries are ordered by SASB dimension order then ascending gic_code — matching
    the column/row layout of the SASB materiality finder.

    For industries already in the file: existing hand-authored descriptions are
    carried forward by word-overlap matching against official GIC names.
    For new industries: descriptions are auto-generated and tagged [Auto].

    Returns: (enhanced_dict, updated_industry_names, added_industry_names)
    """
    # SASB canonical dimension order (matches the website's left-to-right column order)
    _DIM_ORDER = [
        "Environment",
        "Social Capital",
        "Human Capital",
        "Business Model and Innovation",
        "Leadership & Governance",
        "Leadership and Governance",   # alternate spelling in some scrape records
    ]
    _DIM_RANK = {d: i for i, d in enumerate(_DIM_ORDER)}

    existing_topics: dict = sics.get("sasb_topics", {})

    # Build reverse lookup: official_name → old_name_in_file (via aliases)
    official_to_file_key: dict[str, str] = {}
    for file_key in existing_topics:
        official = _NAME_ALIASES.get(file_key, file_key)
        official_to_file_key[official] = file_key

    updated: list[str] = []
    added: list[str] = []
    new_sasb_topics: dict[str, list[dict]] = {}

    for ind in industries.values():
        official_name = ind["name"]
        file_key = official_to_file_key.get(official_name)      # None if brand-new
        old_entries: list[dict] = existing_topics.get(file_key, []) if file_key else []
        is_new = file_key is None

        # Build (gic_code, gic_name, dimension) → [disclosure topics], deduped
        gic_map: dict[tuple[int, str, str], list[dict]] = {}
        for topic in ind.get("disclosure_topics", []):
            gic_code = topic.get("gic_code")
            gic_name = topic.get("gic_name", "")
            dim      = topic.get("dimension", "")
            if not (gic_code and gic_name and dim):
                continue
            key = (int(gic_code), gic_name, dim)
            gic_map.setdefault(key, []).append({
                "code": topic["code"],
                "name": topic["name"],
            })

        if not gic_map:
            continue

        # Sort by dimension order then gic_code
        sorted_gics = sorted(
            gic_map.items(),
            key=lambda kv: (_DIM_RANK.get(kv[0][2], 99), kv[0][0]),
        )

        entries: list[dict] = []
        for (gic_code, gic_name, dim), disc_topics in sorted_gics:
            description = (
                _match_description(gic_name, old_entries)
                or _auto_description(gic_name, official_name, dim)
            )
            entries.append({
                "dimension":        dim,
                "gic_code":         gic_code,
                "gic_name":         gic_name,
                "name":             _gic_key(gic_name),
                "description":      description,
                "disclosure_topics": disc_topics,
            })

        # Store under the original file key (preserving old name) or official name
        out_key = file_key if file_key else official_name
        new_sasb_topics[out_key] = entries

        if is_new:
            added.append(official_name)
        else:
            updated.append(official_name)

    # Carry forward any file entries for industries NOT in scrape (shouldn't happen)
    for file_key, topics in existing_topics.items():
        if file_key not in new_sasb_topics:
            new_sasb_topics[file_key] = topics

    result = dict(sics)
    result["sasb_topics"] = new_sasb_topics
    return result, sorted(updated), sorted(added)


# ---------------------------------------------------------------------------
# Build enhanced archetype_to_sasb.yaml
# ---------------------------------------------------------------------------

def build_enhanced_arch(
    arch: dict,
    ind_dim_gic: dict[str, dict[str, Counter]],
) -> tuple[dict, list[str]]:
    """
    Adds new industry entries (official SASB names) to each dimension.
    Existing entries are kept exactly as-is (names and GIC values unchanged).

    Returns: (enhanced_dict, list_of_added_industry_names)
    """
    result: dict[str, dict | None] = {}
    added_names: set[str] = set()

    for arch_dim, official_dim in [
        ("environment",    "Environment"),
        ("social_capital", "Social Capital"),
        ("human_capital",  "Human Capital"),
        ("business_model", "Business Model and Innovation"),
        ("governance",     "Leadership & Governance"),
    ]:
        existing: dict = arch.get(arch_dim, {}) or {}
        default_val: Optional[str] = existing.get("default")

        # Collect all existing industry names (resolve to official for coverage check)
        covered_official: set[str] = {
            _NAME_ALIASES.get(k, k) for k in existing if k != "default"
        }

        new_dim: dict[str, str] = {}
        for ind_name, dim_map in ind_dim_gic.items():
            if ind_name in covered_official:
                continue  # existing entry covers this industry
            counter = dim_map.get(official_dim)
            if not counter:
                continue  # industry has no topics in this dimension
            pg = _primary_gic(counter)
            if pg:
                new_dim[ind_name] = pg
                added_names.add(ind_name)

        # Merge: existing first, then new (alphabetical within each group)
        merged: dict[str, str] = {}
        for k, v in existing.items():
            if k != "default":
                merged[k] = v
        for k in sorted(new_dim):
            merged[k] = new_dim[k]
        if default_val is not None:
            merged["default"] = default_val

        result[arch_dim] = merged

    # Preserve 'other' key
    if "other" in arch:
        result["other"] = arch["other"]

    return result, sorted(added_names)


# ---------------------------------------------------------------------------
# YAML writer — preserves human-readable format
# ---------------------------------------------------------------------------

def _write_arch_yaml(enhanced: dict, out_path: Path) -> None:
    """
    Write archetype_to_sasb.yaml in the same style as the original:
    dimension key, then indented "Industry Name": "GIC_Key" entries,
    values column-aligned per dimension block.
    """
    lines = [
        "# archetype_to_sasb.yaml — SASB 5-dimension crosswalk (ADR-016)",
        "#",
        "# Top-level keys are snake_case dimension codes matching ARCHETYPE_LABEL_MAP.",
        "# Values map SASB industry names to the single most-material SASB General Issue",
        "# Category for that (dimension, industry) pair.",
        "# 'default' is used when the filing's industry is Unknown or not listed here.",
        "# Industry name strings must match sasb_sics_mapping.json exactly.",
        "# [Auto] prefix on GIC values = computed from topic frequency (SASB Navigator).",
        "",
    ]

    dim_order = ["environment", "social_capital", "human_capital", "business_model", "governance"]

    for arch_dim in dim_order:
        dim_data = enhanced.get(arch_dim) or {}
        lines.append(f"{arch_dim}:")

        # Separate existing (no prefix) from auto-added
        # We don't track this distinction — just write all sorted, default last
        entries = {k: v for k, v in dim_data.items() if k != "default"}
        default = dim_data.get("default")

        if not entries and default is None:
            lines.append("  {}")
        else:
            # Compute alignment: longest key + 2 quotes + colon + space
            max_key_len = max((len(k) for k in entries), default=0)
            col = max_key_len + 4  # 2 quotes + colon + 1 space minimum

            for ind_name in sorted(entries):
                gic = entries[ind_name]
                quoted_key = f'"{ind_name}":'
                lines.append(f"  {quoted_key:<{col}} \"{gic}\"")
            if default is not None:
                lines.append(f"  default: \"{default}\"")

        lines.append("")

    # 'other' dimension
    if "other" in enhanced:
        other_val = enhanced["other"]
        if isinstance(other_val, dict) and not other_val:
            lines.append("other: {}")
        elif other_val is None:
            lines.append("other: {}")
        else:
            lines.append("other:")
            lines.append(yaml.dump(other_val, default_flow_style=False).rstrip())
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------

def _write_sics(enhanced: dict, in_place: bool) -> Path:
    if in_place:
        shutil.copy2(SICS_PATH, SICS_PATH.with_suffix(".json.bak"))
        out_path = SICS_PATH
    else:
        out_path = SICS_PATH.with_stem(SICS_PATH.stem + "_updated")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(enhanced, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return out_path


def _write_arch(enhanced: dict, in_place: bool) -> Path:
    if in_place:
        shutil.copy2(ARCH_PATH, ARCH_PATH.with_suffix(".yaml.bak"))
        out_path = ARCH_PATH
    else:
        out_path = ARCH_PATH.with_stem(ARCH_PATH.stem + "_updated")
    _write_arch_yaml(enhanced, out_path)
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Write *_updated.* files alongside originals in taxonomies dir",
    )
    parser.add_argument(
        "--in-place", action="store_true",
        help="Overwrite originals (creates .bak backups first)",
    )
    args = parser.parse_args()

    for p in (SCRAPE_PATH, SICS_PATH, ARCH_PATH):
        if not p.exists():
            raise FileNotFoundError(f"Required file missing: {p}")

    print("Loading source files …")
    scrape = _load_scrape()
    sics   = _load_sics()
    arch   = _load_arch()

    industries = _build_industries(scrape)
    print(f"  {len(industries)} official SASB industries (after deduplication)")
    n_topics_total = sum(len(ind["disclosure_topics"]) for ind in industries.values())
    print(f"  {n_topics_total} unique disclosure topics across all industries")

    ind_dim_gic = _build_dim_gic_map(industries)
    official_names = set(industries.keys())

    print_report(official_names, sics, arch, ind_dim_gic)

    if not args.write and not getattr(args, "in_place", False):
        print("Run with --write to produce *_updated.* files, or --in-place to overwrite.")
        return

    in_place = getattr(args, "in_place", False)

    # --- Enhanced sasb_sics_mapping.json ---
    enhanced_sics, updated_sics, added_sics = build_enhanced_sics(sics, industries)
    sics_out = _write_sics(enhanced_sics, in_place)
    n_before = len(sics.get("sasb_topics", {}))
    n_after  = len(enhanced_sics["sasb_topics"])
    print(f"sasb_sics_mapping: {n_before} → {n_after} industries "
          f"({len(updated_sics)} restructured to SASB hierarchy, +{len(added_sics)} new)")
    print(f"  → {sics_out}")

    # --- Enhanced archetype_to_sasb.yaml ---
    enhanced_arch, added_arch = build_enhanced_arch(arch, ind_dim_gic)
    arch_out = _write_arch(enhanced_arch, in_place)

    # Count entries per dimension in output
    dim_counts = {
        k: len([x for x in (v or {}) if x != "default"])
        for k, v in enhanced_arch.items()
        if k != "other"
    }
    print(f"archetype_to_sasb: {len(added_arch)} new industries added")
    for dim, count in dim_counts.items():
        print(f"  {dim}: {count} entries")
    print(f"  → {arch_out}")


if __name__ == "__main__":
    main()
