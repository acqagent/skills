---
name: far-clause-checker
description: FAR and HHSAR provision and clause compliance checker for the Revolutionary FAR Overhaul (RFO). Use this skill whenever the user asks about FAR clauses, HHSAR clauses, provisions, clause matrices, RFO compliance, clause applicability, incorporation by reference, deviation dates, class deviations, removed or reserved clauses, contract clause checks, Section I validation, or validating FAR 52.2xx or HHSAR 352.2xx provisions against the restructured FAR. Also trigger when the user says things like 'check my clauses', 'run the FAR checker', 'clause compliance', 'RFO check', 'which clauses apply', 'is this clause still valid', 'what changed in the FAR overhaul', or mentions HHSAR deviations, the Smart Matrix, or provision/clause worksheets. FAR and HHSAR only; disregard DFARS content. Takes the user's clause list (or contract parameters for a checklist), validates against the acquisition.gov Smart Matrix and JUL 2026 HHSAR deviation matrix, and produces a standalone compliance report.
---

# FAR Clause Checker (v3)

Validates FAR 52.2xx and HHSAR 352.2xx provisions and clauses against current baselines during the Revolutionary FAR Overhaul (RFO) period, and produces a standalone compliance report as a Word document.

## Version notes (v3)

The v3 data sources replaced both v2 files, and the two new files have different shapes AND different semantics:

- The old DAU matrix (xlsx, applicability grid, RFO flags, IBR, full text) was replaced by the acquisition.gov **Smart Matrix** (csv). The Smart Matrix is a lean FAR 52.2xx baseline: number, title, effective date, prescription reference, P or C. It has NO applicability grid, so the v2 parameter-driven "generate the applicable clause list" workflow no longer exists for FAR clauses.
- The old HHS disposition csv (FAR clause dispositions) was replaced by the **HHSAR Deviations JUL 2026** workbook (xlsx). This file covers HHSAR 352.2xx clauses, not FAR clause dispositions: status (Active, Reserved, Removed), class deviation citations, dated deviation annotations, IBR, PCO fill-ins, UCF sections, and coded applicability.
- The two files are disjoint clause families with no join key. 52.x lookups go to the Smart Matrix; 352.x lookups go to the HHSAR matrix.
- The primary input is now the user's clause list. Real user-supplied dates anchor the date checks, which fixes the v2.1 known issue where matrix dates were used as a proxy and inflated the Action Needed count.

## Data sources

Two files in `references/`:

1. **Smart Matrix (csv)**: the FAR 52.2xx baseline (809 rows: 610 clause numbers plus 199 alternates).
2. **HHSAR Deviations JUL 2026 (xlsx)**: HHSAR 352.2xx clauses (85 rows, 75 distinct numbers) with status, deviations, and applicability codes.

Before parsing either file directly, read `references/DATA_DICTIONARY.md`. It documents the column maps, the applicability code vocabulary, and the data quirks (a typo'd clause number, RESERVED and DO NOT USE prefixes, HTML artifacts, duplicate numbers, messy dates). The bundled script already handles all of these.

## Workflow

### Step 1: Gather inputs

The most useful input is the user's actual clause list (their solicitation or contract Section I, or any list of clause numbers with dates). Ask for it first. Accept any reasonable format; the script parses each line for a clause number, an optional Alternate, an optional month-year date, and the word "deviation" if cited. Titles are ignored.

Also collect, with defaults if the user does not care:

1. **Contract type**: FFP, FFP_LOE (level of effort), COST, or TM (time and materials / labor hour). Default FFP.
2. **Over the SAT?**: yes or no. "No" also stands in for simplified acquisitions. Default yes.
3. **Commercial?**: yes or no. Default no.
4. **Small business set-aside**: NONE, SB, 8A, HUBZONE, SDVOSB, or WOSB. Default NONE.
5. **FAR parts focus** (optional): part numbers for the FAR inventory in checklist mode, e.g., "19, 27".

These parameters drive the HHSAR applicability checks and the set-aside checks. They cannot filter FAR clauses (the Smart Matrix has no applicability grid); FAR applicability comes from each clause's prescription reference.

If the user has no clause list, run checklist mode instead (Step 3) to build an HHSAR checklist and a FAR inventory for their parts of interest.

Do not re-ask for anything the user already provided.

### Step 2: Know the data

Read `references/DATA_DICTIONARY.md` if you need to parse the files directly or explain a finding's provenance. For normal runs the script is the parser; do not hand-roll pandas over the xlsx.

### Step 3: Run the checker

Check mode (clause list provided):

```bash
python3 scripts/far_checker.py \
  --clauses /path/to/clause_list.txt \
  --contract-type FFP --over-sat yes --commercial no \
  --small-biz NONE --output report.json
```

`--clauses` also accepts an inline list, entries separated by semicolons:

```bash
python3 scripts/far_checker.py \
  --clauses "52.212-5 (Mar 2026); 352.203-70 (JUN 2026) Deviation" \
  --contract-type FFP --over-sat yes --output report.json
```

Checklist mode (no clause list):

```bash
python3 scripts/far_checker.py \
  --contract-type COST --over-sat yes --commercial no \
  --small-biz 8A --parts 19,27 --output checklist.json
```

Notes:

- The script auto-discovers the data files in `references/` (csv with "matrix" or "smart" in the name; xlsx with "hhsar" or "deviation"). Point `--data-dir` elsewhere to override.
- The v2 arguments `--purpose` and `--method` are retired. They are accepted but ignored, with a printed note, because the Smart Matrix carries no purpose or method columns.
- `--contract-type` values changed in v3: FFP, FFP_LOE, COST, TM (v2 used FP, CR, TM).

### Step 4: Generate the report

Read the output JSON and generate a Word document. Read `/mnt/skills/public/docx/SKILL.md` first and follow it. Structure the report as described under "Report structure" below. Save the JSON alongside the docx if the user wants the raw data.

## What the checker does

Check mode, per clause:

**FAR 52.2xx (against the Smart Matrix)**

1. **Existence**: unknown numbers are flagged CRITICAL (wrong number, removed or reserved in the restructured FAR, or agency-unique).
2. **Alternate existence**: a cited Alternate that is not in the matrix is flagged, and the known alternates are listed.
3. **Date currency**: the user's date vs the matrix effective date. Older is a CRITICAL Date Mismatch; missing or unparseable dates go to Review.
4. **Set-aside fit** (Part 19): clauses that conflict with the stated set-aside are flagged (e.g., 52.219-3 in a non-HUBZone action).

**HHSAR 352.2xx (against the HHSAR matrix)**

5. **Status**: Reserved and Removed (DO NOT USE OR ENFORCE) clauses are CRITICAL; the report cites the class deviation or court order behind the status.
6. **Deviation currency**: the user's date vs the current version or class deviation date. Older is a CRITICAL Date Mismatch. If the user cites a deviation the matrix does not show, that is a Review finding; if the matrix shows a deviation the user did not cite, the report notes the citation to add.
7. **IBR**: clauses not authorized for incorporation by reference get a full-text-required warning.
8. **PCO fill-ins**: clauses with contracting officer fill-ins get a verify-completed note.
9. **Applicability fit**: the coded applicability (e.g., R-Over SAT, A-Cost Only) is evaluated against the contract type, SAT position, and commercial flag; mismatches are flagged for review.

**List-level checks**

10. **Missing required HHSAR clauses**: Active HHSAR clauses whose R-code fits the action but that are absent from the list.
11. **Missing set-aside clauses**: expected 52.219 clauses for the stated set-aside that are absent from the list.

Checklist mode instead outputs: HHSAR clauses grouped into required, as-applicable, and not-applicable for the given parameters (with prescriptions, IBR, UCF, fill-in flags, and deviation citations), plus a FAR clause inventory for the requested parts with prescription references and set-aside annotations.

## Set-aside filtering (FAR Part 19)

Unchanged from v2. The rules table in the script maps twelve Part 19 clauses:

- 52.219-1, 52.219-8, 52.219-28: always expected (universal)
- 52.219-3, 52.219-4: HUBZone only
- 52.219-6, 52.219-7: total or partial small business set-aside only
- 52.219-14: any small business set-aside
- 52.219-17, 52.219-18: 8(a) only
- 52.219-27: SDVOSB only
- 52.219-29, 52.219-30: WOSB only
- 52.219-9, 52.219-16: NONE only (large-business prime with subcontracting plan)

## Report structure

Title page: procurement parameters, run date, data sources (Smart Matrix; HHSAR Deviations JUL 2026).

Check-mode sections:

1. **Executive summary**: counts by status, critical findings, warnings.
2. **Status legend**: Valid (green), Action Needed / Date Mismatch (red), Removed or Reserved (red), Review (yellow), Not Found (gray).
3. **FAR clauses**: table with number, alternate, title, user date, current effective date, status, findings.
4. **HHSAR clauses**: table with number, title, user date, current date, HHSAR status, class deviation citation, IBR, UCF, applicability code, status, findings.
5. **Missing required HHSAR clauses** for this action type.
6. **Missing set-aside clauses** for the stated set-aside.
7. **Out-of-scope and unparseable entries** (DFARS numbers, garbage lines).

Checklist-mode sections: parameters, HHSAR required, HHSAR as-applicable (with prescriptions), HHSAR not-applicable to this action, FAR inventory by part.

Keep findings verbatim from the JSON where practical; they are written to be report-ready.

## Important notes

- The Smart Matrix carries no applicability grid. Never claim a FAR clause "applies" to a contract type or purpose based on the matrix; applicability comes from the prescription at the cited FAR reference. The report should say "prescribed in X" and leave FAR applicability judgments to the prescription text.
- HHSAR applicability codes ARE authoritative for HHSAR clauses and the checker evaluates them.
- Clause families never cross files: 52.x is FAR (Smart Matrix), 352.x is HHSAR. DFARS 252.x is out of scope; say so rather than guessing.
- Dates in both files are messy (mixed casing, full month names, non-breaking spaces, annotations like "(RFO DEVIATION)" and "Court Order"). The script normalizes these; if parsing by hand, see the data dictionary.
- The JUL 2026 HHSAR file contains one typo'd number (352.215.70 with a period). The script normalizes it to 352.215-70 on load and on user input.
- If the user's clause list includes titles, that is fine; the parser ignores everything except the number, the Alternate, the date, and the word "deviation".
