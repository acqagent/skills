# CHANGELOG

## v2.2 (current)

DAU Provision & Clause Matrix updated from the 22 April 2026 release to the 29 April 2026 release. Sourced from dau.edu per the matrix's own Change Summary sheet (most recent update: 2026-04-29). The Change Summary describes this release as containing "various corrections to the commercial columns."

### Matrix changes

Compared to the 22 April 2026 matrix:

- **1 new FAR clause added:** 52.222-90 (Addressing DEI Discrimination by Federal Contractors), dated JAN 2022, marked RFO=ADD.
- **0 clauses removed.**
- **0 date changes** to existing clauses.
- **0 title changes.**
- **1 P/C reclassification:** 52.240-92 Alt II (Security Requirements) flipped from Provision (P) to Clause (C).
- **1 prescription text rewrite:** 52.204-10 (Reporting Executive Compensation and First-Tier Subcontract Awards) prescription was reworded.
- **37 commercial-column corrections** spread across 19 unique clauses (each cell affecting COM_SUP, COM_SVC, or both):
  - 6 clauses gained applicability in both commercial columns: 52.203-18, 52.204-9, 52.219-2, 52.222-18, 52.222-48, 52.244-6.
  - 12 clauses had applicability removed from both commercial columns: 52.204-10, 52.209-7, 52.209-9, 52.214-29, 52.219-7 Alt I, 52.222-1, 52.223-1, 52.225-14, 52.226-6, 52.232-31, 52.232-39, 52.252-5.
  - 1 clause had applicability removed from COM_SUP only: 52.222-20 (Contracts for Materials, Supplies, Articles, and Equipment).
- **0 deviation-flag changes.**

These commercial-column corrections matter operationally because v2 made `--commercial yes` check ONLY the COM_<purpose> columns. Prior to 22 April these columns had inconsistencies that this DAU release is now patching.

### Regression results

Re-ran a 20-profile regression panel (mix of contract types, purposes, methods, set-asides, and parts filters) against both the 22 April matrix and the 29 April matrix:

- All 20 profiles completed without errors.
- Total applicable clauses across the 20 profiles: 12,060 to 12,078 (+18, dominated by 52.222-90 newly applying in 18 of 20 profiles).
- Total critical findings: 5,552 to 5,554 (+2).
- Commercial-only deltas isolated cleanly to the two commercial profiles in the panel: 52.219-2 (Equal Low Bids) now applies on commercial procurements; 52.214-29 (Order of Precedence-Sealed Bidding) no longer applies on commercial procurements.
- Parts-19 and Parts-52 filtered runs showed zero delta, as expected: the new clause (52.222-90) sits outside both filters.

### File rename

The bundled matrix filename changed:

- Before: `WarU_Provision___Clause_Matrix__22_Apr_2026.xlsx`
- After: `WarU_Provision___Clause_Matrix__29_Apr_2026.xlsx`

The script's `find_data_files()` function globs for any xlsx in references/ matching the "Provision" pattern, so the rename is cosmetic. No code change required.

## v2.1

DAU Provision & Clause Matrix updated from the 9 March 2026 release to the 22 April 2026 release. Sourced from dau.edu per the matrix's own Change Summary sheet (most recent update: 2026-04-22).

### Matrix changes

Compared to the 9 March 2026 matrix:

- **2 new FAR clauses added:** 52.208-91 (GSA Fleet Vehicles and Related Services) and 52.232-90 (Fast Payment Procedure).
- **5 date changes:**
  - 52.213-4 (Terms and Conditions for Simplified Acquisitions): DEC 2025 -> MAR 2026
  - 52.232-40 (Providing Accelerated Payments to Small Business): DEC 2025 -> MAR 2023 (this looks like a correction back to an earlier authoritative date)
  - 52.222-19 (Child Labor — Cooperation with Authorities): JAN 2025 -> MAR 2026
  - 52.204-8 (Annual Representations and Certifications): OCT 2025 -> MAR 2026
  - 52.212-5 (Contract Terms and Conditions Required to Implement Statutes): OCT 2025 -> MAR 2026
- **3 title changes** (52.232-40, 52.204-91, 52.223-23 — all retitled).
- **2 RFO column changes.**
- **0 deviation-flag changes**, **0 clauses removed**.

The MAR 2026 date sweep on 52.204-8 and 52.212-5 corresponds to Federal Register notice FR 2026-04912, per the matrix's Change Summary sheet.

### Regression results

All 28 stress-test agent profiles re-ran cleanly against the new matrix:

- All 28 runs completed without errors.
- Total applicable across 28 agents: 15,405 -> 15,452 (+47, consistent with 2 new clauses added).
- Total critical findings: 7,152 -> 7,131 (-21, mostly from one clause's date moving closer to the HHS deviation date).
- Parts-filtered runs (Agents 15, 16, 23, 24, 25) showed zero delta, as expected — the new clauses fall outside those parts.

### File rename

The bundled matrix filename changed:

- Before: `WarU_Provision___Clause_Matrix__9_Mar_2026__xlsm.xlsx`
- After: `WarU_Provision___Clause_Matrix__22_Apr_2026.xlsx`

This is cosmetic. The script's `find_data_files()` function globs for any xlsx in references/ matching the "Provision" pattern, so it picks up either name automatically. No code change required.

## v2

Two fixes implemented based on the three-round stress test synthesis (Recommendations 1 and 2 Path A from the synthesis report).

### Recommendation 1: Strict AND-logic in check_applicability()

**Before:** A clause was returned as Applicable whenever the contract-type column was non-blank, even when neither purpose nor method matched. This caused 18 of 23 fixed-price profiles in the stress test to collapse to identical 756-clause output regardless of purpose, method, commercial flag, or set-aside.

**After:** A clause is applicable only when contract type matches AND at least one of (purpose, method) matches. The elif-fallback was removed.

**Companion change:** Commercial procurements now check ONLY the COM_<purpose> columns. The previous fall-through to non-commercial columns made the `--commercial` flag silently ineffective.

**Effect:** `--purpose`, `--method`, and `--commercial` are now real filters. Different procurement profiles produce different outputs. Across the 28-agent regression suite, total applicable clauses dropped by 911 and total critical findings dropped by 476.

**Caveat:** The bundled DAU Matrix has very flat method-column distribution (~93% of clauses have NEG set), so the AND-logic fix prunes less aggressively than one might intuit. Niche purposes like Architect-Engineering still return roughly 700 applicable clauses, not the 30 to 50 that a Part 36 prescription review might suggest. The fix is correct relative to the spec; the data is what it is.

### Recommendation 2 Path A: --small-biz set-aside filtering

**Before:** The `--small-biz` parameter was parsed and printed in the run header but never filtered any output. Specifying HUBZONE produced the same clause list as NONE.

**After:** Added a `SETASIDE_RULES` table and `setaside_filter()` function. Twelve Part 19 clauses are now filtered based on the set-aside value:

- 52.219-3, 52.219-4: HUBZONE only
- 52.219-6, 52.219-7: SB (total small business set-aside) only
- 52.219-9, 52.219-16: NONE only (large-business prime with subcontracting plan)
- 52.219-14: any small business set-aside
- 52.219-17, 52.219-18: 8(a) only
- 52.219-27: SDVOSB only
- 52.219-29, 52.219-30: WOSB only
- 52.219-1, 52.219-8, 52.219-28: always applicable (universal)

Other Part 19 clauses pass through unchanged.

**Effect:** Each set-aside value now produces visibly different Part 19 output. Verified on a CR/SVC/NEG run filtered to Part 19: HUBZONE adds 52.219-3, -4, -14 and removes 52.219-9, -16; 8(a) adds 52.219-17, -18, -14 and removes 52.219-9, -16. Universal clauses (52.219-1, -8, -28) preserved across all set-asides.

### What was NOT changed

The following items from the stress test synthesis remain open work:

- **Recommendation 3 (date-comparison anchor).** The script still uses Matrix dates as a proxy for the user clause date, which causes most "Action Needed (Date Mismatch)" findings to be false positives. This is the next-highest-leverage fix.
- **Recommendation 4 (Updated-clause branching).** The fallback bucket and unreachable Review status still exist in the Updated-disposition logic.
- **Recommendation 5 (UX warnings).** Silent zero on bad Parts filter, alternate-clause grouping in reports, and other minor UX items.

### Backwards compatibility

The CLI signature is unchanged. All v1 invocations work against v2. The output JSON schema is unchanged. Reports generated from v2 output will look the same as v1 reports, just with different (more correct) clause counts.

## v1 (original)

Initial implementation. See three-round stress test reports for documented behavior gaps.
