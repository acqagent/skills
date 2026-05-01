---
name: far-clause-checker
description: FAR provision and clause compliance checker for the Revolutionary FAR Overhaul (RFO). Use this skill whenever the user asks about FAR clauses, provisions, clause matrices, RFO compliance, clause applicability, incorporation by reference, FAR deviation dates, removed or consolidated clauses, contract clause checks, or anything related to validating FAR 52.2xx provisions against the restructured FAR. Also trigger when the user says things like 'check my clauses', 'run the FAR checker', 'clause compliance', 'RFO check', 'which clauses apply', 'is this clause still valid', 'what changed in the FAR overhaul', or mentions HHS deviations, DAU matrix, or provision/clause worksheets. This skill works with FAR clauses only — disregard any DFARS content. The skill prompts the user for contract parameters (contract type, FAR parts, small business requirements) and then cross-references against the DAU Provision & Clause Matrix and HHS deviation data to produce a standalone compliance report.
---

# FAR Clause Checker — RFO Compliance Skill

This skill validates FAR provisions and clauses against the restructured FAR (post-RFO) using two authoritative data sources bundled in the `references/` directory. It produces a standalone compliance report as a `.docx` file.

**Important**: This skill covers FAR (Federal Acquisition Regulation) clauses only. Disregard all DFARS content in the source data.

## Version Notes (v2.2)

This is version 2.2 of the skill. Compared to v1, the applicability logic was hardened, a Part 19 set-aside filter was added, and the bundled DAU Matrix has been refreshed through the 29 April 2026 release. Key behavioral changes:

- **Strict AND applicability.** A clause is now applicable only when contract type matches AND at least one of (purpose, method) matches. The previous fallback that returned Applicable on contract type alone was removed. This makes `--purpose`, `--method`, and `--commercial` actually filter output instead of being silently ignored.
- **Commercial flag isolation.** Commercial procurements now check ONLY the COM_<purpose> columns. The previous fall-through to non-commercial columns has been removed.
- **Set-aside filter.** The `--small-biz` parameter now filters Part 19 socioeconomic clauses based on the set-aside value. See "Set-Aside Filtering" below for the rule table.
- **Data caveat.** The bundled DAU Matrix has very flat method-column distribution (about 93% of FAR clauses have NEG set as a method). This means the AND-logic fix does not narrow the applicable-clause list as aggressively as one might intuit from reading FAR Part prescriptions. Niche purposes like Architect-Engineering still return roughly 700 clauses rather than the 30 to 50 a CO might expect from Part 36 alone. The fix is correct relative to the spec; the data is what it is.
- **Bundled matrix version.** The DAU Provision & Clause Matrix bundled in v2.2 is the 29 April 2026 release. Prior v2.1 shipped with the 22 April 2026 release; v2 originally shipped with the 9 March 2026 release. The script auto-discovers any xlsx file in references/ matching the "Provision" pattern, so swapping in a newer DAU release does not require code changes — just drop it into references/ and remove the old one.
- **What was NOT fixed.** The date-comparison anchor (Recommendation 3 from the stress test) and the Updated-clause branching gaps (Recommendation 4) remain open. The "Action Needed (Date Mismatch)" counts in reports are still inflated because the script compares the Matrix Date against the HHS Deviation Date rather than a true user-supplied clause date. Treat critical findings as suggestive, not authoritative, until that fix is made.

## Data Sources

Before running any checks, read the column mapping and data dictionary in `references/DATA_DICTIONARY.md`. This explains exactly how to parse both source files.

1. **DAU Provision & Clause Matrix** (`references/` — the `.xlsx` file)
   - The master reference for all FAR provisions and clauses
   - Contains: clause numbers, titles, dates, prescriptions, P/C type, RFO flags, IBR authorization, UCF sections, applicability by contract type/purpose/method, full text, alternate/deviation flags
   - **Matrix sheet** is the primary data sheet; header row is row 6 (0-indexed), data starts at row 7
   - Filter to `Regulation == "FAR"` only (column index 34)

2. **HHS Agency Deviation Matrix** (`references/` — the `.csv` file)
   - Agency-specific (HHS) disposition tracking for each clause post-RFO
   - Columns: Part, Type, Number, Pre-RFO Title, Pre-RFO Date, RFO Title, HHS Deviation Date, Disposition, Notes
   - Disposition values: `No Change`, `Removed`, `Updated`
   - `--` in HHS Deviation Date means no agency deviation applies

## Workflow

### Step 1: Gather User Inputs

Prompt the user for these parameters (since actual acquisition data is not included, these general inputs drive applicability logic):

1. **Contract Type** — which of: Fixed-Price (FP), Cost-Reimbursement (CR), Time & Materials / Labor Hour (T&M/LH)
2. **Contract Purpose** — which of: Supplies (SUP), Services (SVC), R&D, Construction (CON), Leasehold/Motor Vehicle (LMV), Commercial Services (COM SVC), Dismantling/Demolition/Removal (DDR), Architect-Engineering (A-E), Transportation (TRN), Utility Services (UTL SVC), Commercial Supplies, Commercial Services
3. **Solicitation Method** — which of: Simplified Acquisition Procedures (SAP), Sealed Bidding (SLD BID), Negotiated (NEG CON), or ≤$350K threshold
4. **Small Business Requirements** — which of: NONE, SB (total small business set-aside), 8A, HUBZONE, SDVOSB, WOSB. This now actively filters Part 19 clauses; see "Set-Aside Filtering" below.
5. **Is this a commercial acquisition?** — Yes/No (determines whether COMM column and commercial purpose columns apply). With v2 this is a hard switch: commercial=yes checks ONLY commercial columns.
6. **Any specific FAR Part focus?** — e.g., Part 12, Part 15, Part 19, or "all"

If the user has already provided some of these in their message, don't re-ask — just confirm and proceed.

### Step 2: Parse the Data Sources

Read the data dictionary first: `references/DATA_DICTIONARY.md`

Load and parse both files using Python (openpyxl for xlsx, csv module for csv). Key parsing rules:

- **Excel Matrix**: Read the "Matrix" sheet. Row 6 (0-indexed) contains column headers. Data rows start at row 7. Filter rows where column 34 (Regulation) == "FAR".
- **Applicability codes**: `A` = Required when applicable, `R` = Required, `O` = Optional, blank = Not applicable
- **RFO column** (index 7): `RFO X` means affected by the FAR overhaul
- **IBR column** (index 9): `Yes` = authorized for IBR, `No` = must use full text, `Yes*` = IBR authorized under conditions at FAR 52.102(c)
- **CSV**: Parse all rows. Join to Excel data on clause Number matching column index 1.

### Step 3: Run the Compliance Checks

For each FAR clause/provision that is applicable based on user inputs, perform these checks:

#### Check 1: Applicability (v2 strict AND-logic)
A clause is applicable only when ALL of the following hold:
- The contract-type column for the user's contract type is non-blank, AND
- Either at least one of the user's purposes matches a non-blank purpose column (using COM_<purpose> columns when commercial=yes, regular purpose columns when commercial=no), OR at least one of the user's methods matches a non-blank method column.

Contract type alone does NOT make a clause applicable. Purpose alone or method alone matched without contract type does NOT make a clause applicable.

After the base applicability decision, the set-aside filter (see below) may override the result for certain Part 19 clauses.

#### Check 2: RFO Impact (Date-Aware)
Check the RFO column (index 7). If `RFO X`, the clause was affected by the FAR overhaul. Cross-reference with the HHS CSV Disposition column:
- **No Change** → Status = "Valid" (green). No action required.
- **Removed** → Status = "REMOVED" (red). Critical finding.
- **Updated** → Apply date-aware comparison logic:

**Date normalization:** Parse both the user-provided date and the HHS Deviation Date into (month, year) pairs. Handle formats like "Jan-2026 Deviation", "Nov 2025", "2-Jun-25", "Jul 2025", "JAN 2026", "MAY 2014", etc. Strip the word "Deviation" before parsing. Return None for "--", empty, or unparseable strings.

**For clauses where HHS Disposition = "Updated":**

1. **If the user's date matches or is newer than the HHS deviation date, AND the user includes a "Deviation" tag** → Status = "Valid" (green). Note: "No action required — user date matches current deviation version."

2. **If there is no HHS deviation date (value is "--") but the user lists a "Deviation" tag** → Status = "Review" (yellow). Note: "HHS shows no agency deviation. Verify deviation source and authority."

3. **If the user's date is older than the HHS deviation date** → Status = "Action Needed" (red). Note: "User date (X) is older than current HHS deviation date (Y). Update to current version." Add to critical findings.

**Comparison rule:** User date >= HHS deviation date (by year first, then month) means the user has the current or newer version.

**Known limitation (v2):** The script currently uses the Matrix Date column as a proxy for the user clause date because no real user-clause-list input has been implemented. This causes Updated clauses where the HHS deviation is newer than the Matrix baseline to flag as Action Needed even when the user has not actually been asked for a date. Treat these critical findings as suggestive until a real user-clause-list input is added.

#### Check 3: Incorporation Method
Check IBR column (index 9):
- `Yes` → can be incorporated by reference
- `No` → must be incorporated by full text
- `Yes*` → conditional IBR per FAR 52.102(c)
Flag any mismatch if the user indicates they're incorporating by reference a clause that requires full text.

#### Check 4: Date Validation
Date comparison for Updated clauses is now handled in Check 2. Only flag date issues here when there is an actual mismatch between the Matrix date (column 3) and HHS Deviation Date (CSV) that was NOT already caught by Check 2's Updated-clause logic.

#### Check 5: Deviation Status
Check the Deviation Flag (column 41) and HHS Deviation Date in the CSV. Flag any clause where:
- An agency deviation date exists (not `--`)
- The deviation flag is set in the Matrix
- The disposition is anything other than "No Change"

#### Check 6: Removed / Consolidated Clauses
For any clause where the HHS Disposition is `Removed` or the RFO Title is `[Reserved]`:
- Flag the clause as no longer valid
- Check if the Notes column in the CSV provides guidance on where the content was consolidated
- If the Pre-RFO Title differs significantly from the RFO Title, note the change

### Set-Aside Filtering (v2)

The `--small-biz` parameter filters a specific subset of Part 19 clauses. The rules:

| Clause | Set-aside required |
|---|---|
| 52.219-1, 52.219-8, 52.219-28 | Always applicable (universal representations and reporting) |
| 52.219-3, 52.219-4 | HUBZONE only |
| 52.219-6, 52.219-7 | SB (total small business set-aside) only |
| 52.219-14 | Any small business set-aside (anything other than NONE) |
| 52.219-17, 52.219-18 | 8A only |
| 52.219-27 | SDVOSB only |
| 52.219-29, 52.219-30 | WOSB only |
| 52.219-9, 52.219-16 | NONE only (large-business prime with subcontracting plan) |

Other Part 19 clauses (52.219-10, -11, -12, -13, -31, -32, -33) are not set-aside-conditional in this filter and pass through based on the standard applicability logic.

If a user specifies a set-aside that does not match a clause's required set-aside, the clause is excluded from the report regardless of other applicability factors. If a clause is not in the set-aside rule table, the set-aside parameter has no effect on that clause.

### Step 4: Generate the Compliance Report

Read the docx SKILL.md at `/mnt/skills/public/docx/SKILL.md` before generating the report.

Produce a `.docx` compliance report with these sections:

1. **Report Header**
   - Title: "FAR Clause Compliance Report — RFO Validation"
   - Date generated
   - Contract parameters used (contract type, purpose, method, etc.)

2. **Executive Summary**
   - Total clauses checked
   - Count by status: Valid (No Action Required), Action Needed (Date Mismatch), Review (Verify Deviation Source), Removed by RFO, Not Found in Matrix
   - Critical findings count
   - Note: Clauses are marked Valid when the user's date matches the current deviation version, not only when the HHS disposition says "No Change."

3. **Applicable Clauses Table (Clause-by-Clause Analysis)**
   - Clause Number | Title | Date | P/C | IBR | Status | Notes
   - Status legend:
     - **Green = Valid (No Action)** — Clause is current. Includes both unchanged clauses AND updated clauses where the user already has the correct deviation version.
     - **Yellow = Review (Verify Deviation Source)** — User lists a deviation but HHS has no corresponding deviation on file. Needs verification.
     - **Red = Action Needed (Date Mismatch)** — User's date is older than the current HHS deviation date. Must update.
     - **Red = Removed by RFO** — Clause was removed. Critical.
     - **Gray = Not Found in Matrix** — Clause not in DAU Matrix (may be agency-specific).

4. **Clauses Requiring Attention**
   - Only show clauses with Status = "Action Needed" or "Review" — not every Updated clause
   - This section is actionable, not noisy

5. **Deviation Summary**
   - HHS-specific deviations with dates and notes

6. **Recommendations**
   1. Date Mismatches — list the specific clauses and what dates need updating
   2. Verify Deviation Source — list clauses where the user has a deviation but HHS doesn't
   3. Missing Required Clauses — any required clauses not present
   4. Incorporation by Reference — any IBR method mismatches
   5. Hybrid/Commercial Considerations — as applicable

## Important Notes

- Always filter to FAR only (ignore DFARS, VAAR, DEAR rows in the Matrix)
- The Matrix contains alternate versions of clauses (column 39/40) — treat these as separate entries
- When a clause shows `[Reserved]` in the RFO Title, it has been removed
- The `COMM` column (index 8) indicates commercial applicability — `IAP` means "if acquisition is for commercial products/services"
- Small business related clauses are primarily in FAR Part 19 (52.219-xx); see "Set-Aside Filtering" above for which ones are filtered by `--small-biz`
- The ≤$350K column (index 30) applies to simplified acquisitions under that threshold
