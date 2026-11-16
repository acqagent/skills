---
name: far-clause-checker
description: FAR provision and clause compliance checker for the Revolutionary FAR Overhaul (RFO), using the acquisition.gov (GSA) Smart Matrix as its only baseline. Use whenever the user asks about FAR clauses, provisions, clause matrices, RFO compliance, clause dates or currency, alternates, removed or reserved FAR clauses, Section I validation, Part 19 set-aside clauses, or validating FAR 52.2xx provisions against the restructured FAR. Also trigger on 'check my clauses', 'run the FAR checker', 'clause compliance', 'RFO check', 'which clauses apply', 'is this clause still valid', 'what changed in the FAR overhaul', or mentions of the Smart Matrix or provision/clause worksheets. FAR 52.x only; HHSAR, DFARS, and other agency supplements are out of scope. Takes the user's clause list (or a set-aside and FAR parts for a checklist), validates it against the Smart Matrix, and produces a standalone compliance report.
---

# FAR Clause Checker (v4)

Validates FAR 52.2xx provisions and clauses against the acquisition.gov (GSA) Smart Matrix during the Revolutionary FAR Overhaul (RFO) period, and produces a standalone compliance report as a Word document.

## Version notes (v4)

- HHSAR removed. The JUL 2026 HHSAR deviation workbook, every 352.x check (status, class deviation currency, IBR, PCO fill-ins, applicability codes, missing required HHSAR clauses), and the HHSAR checklist are gone.
- The Smart Matrix CSV is the only data source. The checker is standard-library Python; openpyxl is no longer needed.
- `--contract-type`, `--over-sat`, and `--commercial` are retired because they only drove HHSAR applicability. They are accepted and ignored with a printed note. `--small-biz` and `--parts` remain.
- 352.x entries in a clause list are now reported as Out of Scope, the same as DFARS 252.x.
- Prescribed In references are cleaned: stray commas are stripped, and a blank reference (52.247-63 in the GSA data) shows as `not listed`.
- `references/HHSAR_Deviations_JUL_2026.xlsx` was deleted, and `references/DATA_DICTIONARY.md` now covers the Smart Matrix only. FAR results are identical to v3.

## Data source

`references/Smart_Matrix__Acquisition_GOV.csv` in this skill's folder: the FAR 52.2xx baseline (809 rows: 610 clause numbers plus 199 alternates). It is a static snapshot, **verified current on November 15, 2026**: it matched the live acquisition.gov Smart Matrix row for row (official FAR through FAC 2026-01, effective March 13, 2026; newest clause dates MAR 2026). If the user says a newer Smart Matrix has been published, or a clause date looks stale, tell them the check is only as current as this file and offer to compare their newer copy.

Columns (the script already handles all quirks):

| Column | Contents | Quirks |
|---|---|---|
| Provision or Clause (P or C) | Number and title in one cell, e.g. `52.203-5 Covenant Against Contingent Fees.` | Alternates are `52.203-6_Alternate I` with no title. The underscore defeats a regex `\b`, so the script anchors with `(?<![A-Za-z])`. Some titles have runs of spaces. |
| Effective Date | `May 2014`, `June 2010`, `NOV 2023` | A few contain non-breaking spaces or a tab. |
| Prescribed In | FAR prescription reference, e.g. `19.507(e)`; the only applicability signal in the file | 52.242-3 has a stray trailing comma and 52.247-63 has only a comma. The script strips the comma and shows the blank as `not listed`. |
| P or C | `P` (182 rows) or `C` (627 rows) | |

There is no applicability grid, no RFO flag, no IBR column, and no full text.

## Workflow

### Step 1: Gather inputs

Ask first for the user's clause list (solicitation or contract Section I, or any list of clause numbers with dates). Accept any reasonable format; the parser pulls each line's clause number, any Alternate, and any month-year date, and ignores titles.

Also collect, with defaults if the user does not care:

1. **Small business set-aside**: NONE, SB, 8A, HUBZONE, SDVOSB, or WOSB. Default NONE.
2. **FAR parts** (checklist mode): part numbers for the inventory, e.g. "19, 27".

If the user has no clause list, run checklist mode. Do not re-ask for anything the user already gave.

### Step 2: Run the checker

Run `scripts/far_checker.py` (standard-library Python). It finds the CSV in `references/` on its own; pass `--matrix` only to use a different copy, such as a newer Smart Matrix export the user provides.

Check mode (clause list provided; file path or inline `;`-separated list):

```bash
python3 scripts/far_checker.py \
  --clauses "52.212-5 (Mar 2026); 52.203-6 Alt I (Jun 2020); 52.219-14" \
  --small-biz NONE --output report.json
```

Checklist mode (no clause list):

```bash
python3 scripts/far_checker.py --small-biz 8A --parts 19,27 --output checklist.json
```

For column details and data quirks, see `references/DATA_DICTIONARY.md`; for normal runs the script is the parser.

### Step 3: Generate the report

Load the docx skill with the Skill tool and follow it. Build the Word report from the JSON using the structure below. Save the JSON alongside if the user wants the raw data.

## What the checker does

Check mode, per FAR 52.x entry:

1. **Existence**: numbers not in the Smart Matrix are CRITICAL Not Found (wrong number, removed or reserved in the restructured FAR, or agency-unique).
2. **Alternate existence**: a cited Alternate missing from the matrix is a Review finding that lists the known alternates.
3. **Date currency**: the user's date vs the matrix effective date. Older is a CRITICAL Date Mismatch; a missing date is Review.
4. **Set-aside fit** (Part 19): clauses that conflict with the stated set-aside are flagged for review.

List level: **missing set-aside clauses**, the expected 52.219 clauses for the stated set-aside that are absent.

Anything that is not 52.x (HHSAR 352.x, DFARS 252.x, other supplements) is Out of Scope; lines with no clause number are Unparseable.

Checklist mode outputs the expected set-aside clauses for the stated set-aside, plus a FAR inventory for the requested parts with dates, P or C, prescription references, alternates, and set-aside verdicts. Without `--parts` there is no inventory; ask which parts to list.

## Set-aside rules (FAR Part 19)

Hand-maintained in the script (all 15 numbers are present in the bundled Smart Matrix):

- 52.219-1, 52.219-8, 52.219-28: always expected
- 52.219-3, 52.219-4: HUBZone only
- 52.219-6, 52.219-7: small business set-aside (SB) only
- 52.219-14: any small business set-aside
- 52.219-17, 52.219-18: 8(a) only
- 52.219-27: SDVOSB only
- 52.219-29, 52.219-30: WOSB only
- 52.219-9, 52.219-16: NONE only (large-business prime with subcontracting plan)

If the user reports that RFO Part 19 changed any of these, update the rules table in the script for that run and say so in the report.

## Report structure

Title page: set-aside, FAR parts (if any), run date, data source (acquisition.gov Smart Matrix, verified current November 15, 2026).

Check mode:

1. **Executive summary**: counts by status, critical findings, warnings.
2. **Status legend**: Valid (green), Action Needed / Date Mismatch (red), Review (yellow), Not Found (gray).
3. **FAR clauses**: number, alternate, title, user date, current effective date, prescribed in, status, findings.
4. **Missing set-aside clauses** for the stated set-aside.
5. **Out-of-scope and unparseable entries** (HHSAR, DFARS, and lines without a clause number).

Checklist mode: parameters, expected set-aside clauses, FAR inventory by part.

Keep findings verbatim from the JSON where practical; they are written to be report-ready.

## Important notes

- Never claim a FAR clause "applies" to a contract type or purpose based on the matrix. Say "prescribed in X" and leave applicability to the prescription text.
- FAR 52.x only. If the user asks about HHSAR, DFARS, or another supplement, say it is out of scope for this skill rather than guessing.

