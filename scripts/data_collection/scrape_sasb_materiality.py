"""
Scrape SASB Navigator materiality finder — all data including authenticated data.

DATA SOURCES:
  Public (no auth):
    1. AWS API: sectorIndustry  → 77 industries + sector names + descriptions
    2. AWS API: sustainability-dimensions → 26 GICs with descriptions

  Authenticated (MSAL / Azure AD B2C):
    3. AWS AppSync GraphQL: listDisclosureTopics
       → 448 disclosure topics (code, name, industry) for all 77 industries

  Auth method:
    - PKCE Authorization Code Flow via ifrsclient.b2clogin.com
    - Chromium with forced IPv4 (MAP ifrsclient.b2clogin.com 40.126.28.13)

Usage:
    # Full scrape with credentials
    python scripts/data_collection/scrape_sasb_materiality.py \\
        --username user@example.com --password "secret"

    # Public data only (no login required)
    python scripts/data_collection/scrape_sasb_materiality.py --no-auth

    # Custom output path
    python scripts/data_collection/scrape_sasb_materiality.py \\
        --username user@example.com --password "secret" \\
        --output path/to/out.json

Requires:
    pip install playwright
    playwright install chromium
"""

import argparse
import base64
import getpass
import hashlib
import json
import re
import secrets
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_API_BASE = "https://owaeaasu09.execute-api.us-west-2.amazonaws.com/prod/navigator-data"
_SECTOR_INDUSTRY_URL = f"{_API_BASE}/sectorIndustry?locale=en-gb"
_DIMENSIONS_URL = f"{_API_BASE}/sustainability-dimensions?locale=en-gb"
_NAVIGATOR_URL = "https://navigator.sasb.ifrs.org/materiality-finder"

_B2C_CLIENT_ID = "48e0c770-d7be-423b-a7a2-ccecf4814416"
_B2C_AUTHORITY = (
    "https://ifrsclient.b2clogin.com/ifrsclient.onmicrosoft.com"
    "/B2C_1A_SignUp_SignIn/oauth2/v2.0/authorize"
)
_B2C_REDIRECT = "https://navigator.sasb.ifrs.org/auth-success"
_B2C_SCOPE = "openid profile email offline_access"
_B2C_IPv4_RULE = "MAP ifrsclient.b2clogin.com 40.126.28.13"


# ---------------------------------------------------------------------------
# Public API helpers
# ---------------------------------------------------------------------------

def _get_json(url: str) -> list | dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; SEC-scraper/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_sector_industry() -> dict[str, dict]:
    """Returns flat dict { code → {code, name, sector, description} } for all 77 industries."""
    data = _get_json(_SECTOR_INDUSTRY_URL)
    out = {}
    for sector_obj in data:
        sector_name = sector_obj["sector"]
        for ind in sector_obj.get("industries", []):
            code = ind["code"]
            out[code] = {
                "code": code,
                "name": ind["name"],
                "sector": sector_name,
                "description": ind.get("description", ""),
            }
    return out


def fetch_dimensions() -> list[dict]:
    """Returns all 26 GICs as [{code, name, dimension, description}]."""
    data = _get_json(_DIMENSIONS_URL)
    out = []
    for dim_obj in data:
        dim_name = dim_obj["name"]
        for gic in dim_obj.get("issueCategories", []):
            out.append({
                "code": gic["code"],
                "name": gic["name"],
                "dimension": dim_name,
                "description": gic.get("description", ""),
            })
    return out


# ---------------------------------------------------------------------------
# GIC code extraction
# ---------------------------------------------------------------------------

def topic_gic_code(topic_code: str) -> int | None:
    """Extract the 3-digit GIC numeric code from a disclosure topic code.

    E.g.: "CG-EC-130a" → 130, "FB-AG-110a" → 110
    """
    m = re.search(r"-(\d{3})", topic_code)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Authenticated GraphQL scrape (PKCE + AppSync)
# ---------------------------------------------------------------------------

def _build_auth_url() -> tuple[str, str]:
    """Generate a PKCE pair and return (auth_url, code_verifier)."""
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    scope_encoded = _B2C_SCOPE.replace(" ", "+")
    redirect_encoded = _B2C_REDIRECT.replace(":", "%3A").replace("/", "%2F")

    auth_url = (
        f"{_B2C_AUTHORITY}"
        f"?client_id={_B2C_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={redirect_encoded}"
        f"&scope={scope_encoded}"
        f"&response_mode=query"
        f"&nonce=s&state=s"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )
    return auth_url, code_verifier


def fetch_disclosure_topics(username: str, password: str) -> list[dict] | None:
    """
    Authenticate via PKCE and intercept the AppSync GraphQL response.

    Returns a list of raw disclosure topic dicts from listDisclosureTopics,
    or None on failure. Each topic has at minimum: code, name, industryCode.
    """
    auth_url, _code_verifier = _build_auth_url()
    gql_data: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[f"--host-resolver-rules={_B2C_IPv4_RULE}"],
        )
        context = browser.new_context()
        page = context.new_page()

        # Intercept AppSync GraphQL responses
        def handle_response(resp):
            if "appsync" in resp.url and resp.status == 200:
                try:
                    body = resp.json()
                    if body.get("data"):
                        gql_data.append(body)
                        print(f"  Captured GraphQL response (keys: {list(body['data'].keys())})")
                except Exception as e:
                    print(f"  Failed to parse GraphQL response: {e}")

        page.on("response", handle_response)

        # Step 1: Navigate to B2C login page
        print("  Navigating to B2C login page …")
        try:
            page.goto(auth_url, wait_until="domcontentloaded", timeout=20_000)
        except PlaywrightTimeout:
            print("  Warning: timed out waiting for B2C page; attempting login anyway")

        time.sleep(2)
        print(f"  Login page URL: {page.url[:80]}")

        # Step 2: Fill credentials
        try:
            page.locator("#signInName").fill(username)
            page.locator("#password").fill(password)
            print("  Filled credentials")
        except Exception as e:
            print(f"  Error filling credentials: {e}")
            browser.close()
            return None

        # Step 3: Submit — dispatch_event bypasses Playwright's element-stability checks
        page.locator("#next").dispatch_event("click")
        print("  Submitted login form")

        # Step 4: Wait for redirect back to navigator
        try:
            page.wait_for_url("**/navigator.sasb.ifrs.org/**", timeout=30_000)
        except PlaywrightTimeout:
            print(f"  Warning: redirect timed out; current URL: {page.url[:80]}")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        print(f"  After login URL: {page.url[:80]}")

        # Step 5: Navigate to an industry page to trigger the GraphQL call
        if not gql_data:
            print("  Navigating to industry page to trigger GraphQL …")
            try:
                page.goto(
                    f"{_NAVIGATOR_URL}?industry=CG-EC",
                    wait_until="networkidle",
                    timeout=30_000,
                )
            except PlaywrightTimeout:
                print("  Warning: industry page timed out")
            time.sleep(10)

        if not gql_data:
            print("  Warning: no GraphQL data captured")

        browser.close()

    if not gql_data:
        return None

    # The SASB Navigator React app issues two identical GraphQL calls on page
    # load (a prefetch and a component-mount fetch), so gql_data typically
    # contains N copies of the same 448-topic payload.  Deduplicate here at
    # the source so downstream consumers receive a clean, single-pass list.
    # Dedup key: (topic code, industry code) — uniquely identifies a topic
    # within its industry across all captured responses.
    topics: list[dict] = []
    seen: set[tuple] = set()
    n_responses = 0
    n_skipped = 0
    for response_body in gql_data:
        data = response_body.get("data", {})
        # API returns either listDisclosureTopics.items or disclosureTopics (list)
        raw = data.get("listDisclosureTopics") or data.get("disclosureTopics")
        if isinstance(raw, dict):
            items = raw.get("items", [])
        elif isinstance(raw, list):
            items = raw
        else:
            items = []
        if not items:
            continue
        n_responses += 1
        added = 0
        for item in items:
            ind = item.get("industryCode") or item.get("industry") or ""
            if isinstance(ind, dict):
                ind = ind.get("code", "")
            key = (item.get("code", ""), str(ind))
            if key not in seen:
                seen.add(key)
                topics.append(item)
                added += 1
            else:
                n_skipped += 1
        print(f"  Response {n_responses}: {len(items)} raw topics, {added} new, "
              f"{len(items) - added} duplicates skipped")

    if n_skipped:
        print(f"  Total duplicates removed: {n_skipped} "
              f"(page fired {n_responses} identical GraphQL calls)")
    print(f"  Unique disclosure topics: {len(topics)}")
    return topics if topics else None


def parse_disclosure_topics(
    raw_topics: list[dict],
    gics_by_code: dict[int, dict],
) -> dict[str, list[dict]]:
    """
    Convert raw AppSync disclosure topics into a per-industry mapping.

    Returns: { industry_code → [{ code, name, gic_code, gic_name, dimension }] }
    """
    by_industry: dict[str, list[dict]] = {}
    for t in raw_topics:
        code = t.get("code", "")
        name = t.get("name", t.get("disclosureTopic", ""))
        industry_code = t.get("industryCode", t.get("industry", ""))
        if isinstance(industry_code, dict):
            industry_code = industry_code.get("code", "")
        if not industry_code:
            # Fall back: extract from topic code prefix ("CG-EC-130a" → "CG-EC")
            m = re.match(r"^([A-Z]{2}-[A-Z]{2,4})-\d{3}", code)
            industry_code = m.group(1) if m else ""
        if not industry_code:
            continue

        gic_num = topic_gic_code(code)
        gic = gics_by_code.get(gic_num, {}) if gic_num is not None else {}

        entry = {
            "code": code,
            "name": name,
            "gic_code": gic_num,
            "gic_name": gic.get("name", ""),
            "dimension": gic.get("dimension", ""),
        }
        by_industry.setdefault(industry_code, []).append(entry)

    for ind_code in by_industry:
        by_industry[ind_code].sort(key=lambda x: x["code"])

    return by_industry


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------

def collect_all(username: str | None, password: str | None,
                skip_auth: bool = False, verbose: bool = False) -> dict:
    print("Fetching sector/industry list from public API …")
    industries = fetch_sector_industry()
    n_sectors = len({v["sector"] for v in industries.values()})
    print(f"  {len(industries)} industries across {n_sectors} sectors")

    print("Fetching General Issue Categories (GICs) from public API …")
    gics = fetch_dimensions()
    n_dims = len({g["dimension"] for g in gics})
    print(f"  {len(gics)} GICs across {n_dims} dimensions")

    # Build GIC lookup by numeric code for topic enrichment
    gics_by_code: dict[int, dict] = {}
    for g in gics:
        try:
            gics_by_code[int(g["code"])] = g
        except (ValueError, TypeError):
            pass

    # --- Authenticated GraphQL ---
    topics_by_industry: dict[str, list[dict]] = {}
    if not skip_auth:
        if not username:
            username = input("SASB Navigator username: ")
        if not password:
            password = getpass.getpass("SASB Navigator password: ")

        print("Authenticating and fetching disclosure topics via GraphQL …")
        raw_topics = fetch_disclosure_topics(username, password)
        if raw_topics is not None:
            topics_by_industry = parse_disclosure_topics(raw_topics, gics_by_code)
            total = sum(len(v) for v in topics_by_industry.values())
            print(f"  {total} disclosure topics across {len(topics_by_industry)} industries")
        else:
            print("  Could not retrieve disclosure topics — proceeding without them")

    # Merge topics into industry records
    for code, ind in industries.items():
        ind["disclosure_topics"] = topics_by_industry.get(code, [])

    # Build sector groupings
    sectors: dict[str, list] = {}
    for ind in industries.values():
        sectors.setdefault(ind["sector"], []).append(ind)

    total_topics = sum(len(ind.get("disclosure_topics", [])) for ind in industries.values())

    result = {
        "meta": {
            "source": _NAVIGATOR_URL,
            "has_disclosure_topics": bool(topics_by_industry),
            "total_industries": len(industries),
            "total_sectors": len(sectors),
            "total_gics": len(gics),
            "total_disclosure_topics": total_topics,
        },
        "sectors": [
            {"name": s, "industries": sorted(inds, key=lambda x: x["code"])}
            for s, inds in sorted(sectors.items())
        ],
        "industries": dict(sorted(industries.items())),
        "general_issue_categories": gics,
    }

    if verbose:
        print("\n=== Industries by sector ===")
        for s in result["sectors"]:
            print(f"\n  {s['name']}:")
            for ind in s["industries"]:
                n_topics = len(ind.get("disclosure_topics", []))
                print(f"    [{ind['code']}] {ind['name']}"
                      + (f" — {n_topics} disclosure topics" if n_topics else ""))

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape all SASB Navigator materiality data (public + authenticated)"
    )
    parser.add_argument("--username", help="SASB Navigator login email")
    parser.add_argument("--password", help="SASB Navigator login password")
    parser.add_argument("--no-auth", action="store_true",
                        help="Skip authentication (public data only: industries + GICs)")
    parser.add_argument("--output",
                        default="scripts/data_collection/data/sasb_materiality_all.json",
                        help="Output JSON file path")
    parser.add_argument("--verbose", action="store_true",
                        help="Print full industry/topic summary to stdout")
    args = parser.parse_args()

    data = collect_all(
        username=args.username,
        password=args.password,
        skip_auth=args.no_auth,
        verbose=args.verbose,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if data["meta"]["has_disclosure_topics"]:
        auth_str = f" + {data['meta']['total_disclosure_topics']} disclosure topics"
    else:
        auth_str = " (no auth)"
    print(
        f"\nSaved {data['meta']['total_industries']} industries, "
        f"{data['meta']['total_sectors']} sectors, "
        f"{data['meta']['total_gics']} GICs{auth_str} → {out_path}"
    )


if __name__ == "__main__":
    main()
