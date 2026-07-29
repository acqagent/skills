# Data Dictionary (v3) - FAR Clause Checker

This document maps the columns in both source files so the skill can parse them correctly.

**Important structural note:** the two files cover disjoint clause families. The Smart Matrix holds FAR 52.2xx provisions and clauses; the HHSAR matrix holds HHSAR 352.2xx provisions and clauses. There is NO join key between them. Route lookups by prefix: 52.x goes to the Smart Matrix, 352.x goes to the HHSAR matrix. DFARS (252.x) and other supplements are out of scope.

---

## 1. Smart Matrix (CSV) - FAR baseline

**File:** the `.csv` in `references/` (currently `Smart_Matrix__Acquisition_GOV.csv`)
**Source:** acquisition.gov Smart Matrix export
**Format:** standard CSV, UTF-8, header row first, Windows line endings (\r\n)
**Rows:** 809 (610 base clause numbers plus 199 alternate rows), FAR only

### Column Map

| Column Name | Description | Values / Notes |
|-------------|-------------|----------------|
| Provision or Clause (P or C) | Clause number and title in ONE cell | e.g., `52.203-5 Covenant Against Contingent Fees.` Alternates use an underscore form: `52.203-6_Alternate I` (no title of their own). |
| Effective Date | Current effective date | `Mon YYYY` mostly (`May 2014`); some full month names (`June 2010`); a handful contain non-breaking spaces (`Oct\xa0 2020`), a stray tab, or all caps (`NOV 2023`). Normalize whitespace before parsing. |
| Prescribed In | FAR prescription reference | e.g., `3.404`, `19.507(e)`, `12.301(b)(4)`. This is the only applicability signal the file carries. |
| P or C | Type | `P` = Provision (182 rows), `C` = Clause (627 rows) |

### Parsing rules

- Extract the clause number with a pattern like `(\d{2}\.\d{3})-(\d+)`; the remainder of the cell is the title.
- Alternate rows: `NUMBER_Alternate I` / `II` / `III`. The underscore before "Alternate" defeats a regex `\b` boundary (underscore is a word character); anchor with a negative lookbehind such as `(?<![A-Za-z])` instead.
- Some titles carry erratic internal whitespace (e.g., `52.219-14           Limitations on Subcontracting.`). Collapse runs of whitespace.
- No duplicate full-cell values; each (number, alternate) pair appears once.
- There is NO applicability grid (no contract type, purpose, or method columns), no RFO flag, no IBR column, no Regulation column, and no full text. Applicability for FAR clauses must come from the prescription at the `Prescribed In` reference.

---

## 2. HHSAR Deviations Matrix (XLSX)

**File:** the `.xlsx` in `references/` (currently `HHSAR_Deviations_JUL_2026.xlsx`)
**Sheet:** `Matrix` (the only sheet)
**Layout:** rows 0 to 9 (0-indexed) are a legend explaining the applicability codes; row 10 is blank; row 11 is the header row; data starts at row 12. Parse defensively: find the header row by locating the cell containing `Provision or Clause Number` rather than hard-coding the index.
**Rows:** 85 data rows covering 75 distinct clause numbers (some numbers have multiple rows for alternates or paired Removed/Reserved entries)

### Column Map (14 columns, indices 0 to 13)

| Index | Header | Description | Values / Notes |
|-------|--------|-------------|----------------|
| 0 | Provision or Clause Number | HHSAR number, possibly prefixed | e.g., `352.203-70`. Reserved rows: `RESERVED-352.270-9` or `RESERVED- 352.209-1` (space varies). Removed rows: `DO NOT USE OR ENFORCE-352.209-1`. One row has a typo: `352.215.70` (period instead of hyphen); normalize to `352.215-70`. Suffix letters occur: `352.270-5a`. Alternates may appear in this cell (`352.235-70 Alt 1`) or only in the Title. |
| 1 | Title | Clause title | May repeat the RESERVED / DO NOT USE prefix and may carry the alternate (`... Alt III`). May contain narrow no-break spaces (\u202f). |
| 2 | Date | Date with deviation annotation | `DEC 2015`, `FEB 2024 (Deviation)`, `JUN 2026 (RFO DEVIATION)`, `MAR 2026 (RFO Deviation)`, `AUG 2025 Court Order`. Parse the month and year; keep the annotation to classify the deviation kind (RFO deviation, deviation, court order). |
| 3 | Prescribed at HHSAR | HHSAR prescription reference | e.g., `303.808-70`. May be None on Reserved rows. |
| 4 | Prescription | Full prescription text | When and how to use the clause. |
| 5 | Provision or Clause | Type | `P` or `C`. None on Reserved rows. |
| 6 | IBR | Incorporation by reference | `Yes` = may incorporate by reference, `No` = full text required. None on Reserved rows. No `Yes*` values in this file. |
| 7 | PCO Fill in | Contracting officer fill-in | `Yes` (14 rows) / `No`. `Yes` means the clause has blanks the CO must complete. |
| 8 | Applicability | Coded applicability | See vocabulary below. None on Reserved rows. |
| 9 | UCF | Uniform Contract Format section | `I` (32), `H` (13), `L` (10), `K` (3), `G` (1). |
| 10 | Link | Reference URL | acquisition.gov or the HHS SharePoint class deviation page. Sometimes the cell holds a plain clause label instead of a URL. |
| 11 | Class Deviation | Deviation flag | `Y` (65) / `N` (17) / None (3). |
| 12 | Class Deviation Number | Deviation citation | e.g., `HHSAR CD 2026-11`, `HHSAR Class Deviation 2024-01, Amendment 1`. One value contains literal `<br>` HTML tags (`HHSAR CD<br>not numbered<br>(2023-02)`); strip them. Numbering style is inconsistent (`2026-02` vs `2026-2`). |
| 13 | Status | Row status | `Active` (58), `Reserved` (25), `Removed` (2). |

### Applicability code vocabulary (column 8)

From the legend block plus values observed in data. Spacing around hyphens and commas is inconsistent (`R- All`, `A- Cost, T&M/LH, and FFP LOE`); normalize before matching.

| Code | Meaning |
|------|---------|
| `R-All` | Required in all action types |
| `R-Over SAT` | Required in all actions over the simplified acquisition threshold |
| `R-Cost and T&M/LH` | Required in Cost and T&M/LH actions |
| `R-Cost and T&M/LH-Noncommercial` | Required in noncommercial Cost and T&M/LH actions |
| `A-All` | As applicable in all action types |
| `A-All except Commercial and SAT` | As applicable except commercial and simplified acquisitions |
| `A-Cost, T&M/LH, Simplified Acquisition` | As applicable to Cost, T&M/LH, and simplified acquisitions |
| `A-All over SAT` | As applicable in all actions over the SAT |
| `A-Cost, T&M/LH, and FFP LOE` | As applicable to Cost, T&M/LH, and FFP Level of Effort |
| `A-Cost Only` | As applicable to Cost-type actions |

Treat any other value as unknown and route it to manual review rather than guessing.

### Status semantics

- **Active:** usable. If `Class Deviation` = `Y`, the current version is the deviation cited in column 12, dated per column 2; a clause list should carry that date (or newer) and cite the deviation.
- **Reserved:** the number is reserved, usually under an RFO class deviation (e.g., `HHSAR Class Deviation 2026-06`). Do not include in new solicitations or contracts.
- **Removed:** do-not-use rows. In the JUL 2026 file both Removed rows are the `DO NOT USE OR ENFORCE` pair for 352.209-1 and 352.209-2 under an AUG 2025 court order.

### Duplicate-number handling

Some numbers appear in multiple rows. Handle by keeping a list of rows per number and picking the best match at lookup time (exact alternate first, then the non-alternate row, then Active over Reserved/Removed):

- `352.235-70`: Active base row plus an Active `Alt 1` row.
- `352.236-70`: Active base row plus a Reserved `Alt I` row.
- `352.209-1`: a Removed `DO NOT USE OR ENFORCE` row plus a Reserved row. Either way, do not use.
- `352.227-11`, `352.227-14`, `352.270-4a`: multiple Reserved rows covering the base and its alternates.
