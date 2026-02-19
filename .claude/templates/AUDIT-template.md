# 🛡️ V&V Audit Report: {SUBJECT_NAME}

**Date:** {YYYY-MM-DD}
**Auditor:** Automated Governance Agent
**Scope:** {SCOPE_DESCRIPTION}
**Coverage:** {N}% of documented requirements reachable/verifiable in this audit
**Status:** 🔴 FAILED / 🟠 CONDITIONAL PASS / 🟢 PASSED

---

## 1. Executive Summary

- **Compliance Score:** {X}/100  (−10/Critical · −5/High · −2/Medium · −1/Low)
- **Critical Defects:** {COUNT}
- **High Defects:** {COUNT}
- **Primary Risk:** {One sentence — the single biggest systemic risk found}

---

## 2. Requirements Traceability Matrix (RTM)

*Req IDs: G-NN from PRD Goals tables · US-NNN from story files*

| Req ID | Description | Verification Method | Status | Evidence |
|:-------|:------------|:--------------------|:------:|:---------|
| G-01   | {text from PRD Goals table} | Static analysis: `src/foo.py:42` | 🟢 Verified | Imported and active in pipeline |
| US-005 | {story title} | Import / test trace | 🔴 Missing | No implementation or test file found |
| G-03   | {text} | Math / Logic | ⚠️ Unverified | No benchmark data or test coverage found |

---

## 3. Defects & Contradictions

### 🔴 Critical — Feasibility & Architecture (F-XX)

> **F-01: {Title}**
> - **Claim:** "{exact quote from document}"
> - **Reality:** {evidence or back-of-napkin calculation}
> - **Impact:** {consequence if unresolved}
> - **Source:** `{file_path:line}`

### 🟠 High — Logical Contradictions (C-XX)

> **C-01: {Title}**
> - **Source A:** {Document} says "{quote}"
> - **Source B:** {Document} says "{quote}"
> - **Impact:** {which behavior would actually execute; what would silently break}
> - **Resolution needed:** ADR / PRD amendment / code change

### 🟡 Medium — Documentation Gaps (D-XX)

> **D-01: {Title}**
> - **Location:** `{file_path:line}`
> - **Gap:** {what is missing or ambiguous}
> - **Risk:** {what could go wrong if left unresolved}

### 🔵 Low (L-XX)

> **L-01:** {short description} — `{file_path:line}`

---

## 4. Recommendations

| # | Severity | Action | Owner | Linked Doc |
|:--|:--------:|:-------|:------|:-----------|
| 1 | 🔴       | {Concrete imperative action} | @bethCoderNewbie | {ADR-NNN / PRD-NNN} |
| 2 | 🟠       | {action} | @bethCoderNewbie | {document} |

---

## 5. Auditor's Notes

{Coverage gaps, documents not audited, caveats about what could not be verified and why.
 If full coverage was achieved, state: "All documented requirements within scope were reachable."}

---

*Generated via IEEE 1028 Technical Audit Protocol*
