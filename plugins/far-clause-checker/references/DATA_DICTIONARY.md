# Data Dictionary (v4) - FAR Clause Checker

The checker has one data source: the acquisition.gov (GSA) Smart Matrix export. It covers FAR 52.2xx provisions and clauses only. HHSAR (352.x), DFARS (252.x), and other agency supplements are out of scope; the checker reports them as Out of Scope.

---

## Smart Matrix (CSV) - FAR baseline

**File:** the `.csv` in `references/` (currently `Smart_Matrix__Acquisition_GOV.csv`)
**Source:** acquisition.gov Smart Matrix export
**Currency:** verified current on November 15, 2026. It matched the live Smart Matrix row for row (official FAR through FAC 2026-01, effective March 13, 2026; newest clause dates Mar 2026).
**Format:** standard CSV, UTF-8, header row first. The bundled copy has Windows line endings (\r\n); fresh exports may have Unix line endings (\n). The script reads both.
**Rows:** 809 (610 base clause numbers plus 199 alternate rows), FAR only

### Column Map

| Column Name | Description | Values / Notes |
|-------------|-------------|----------------|
| Provision or Clause (P or C) | Clause number and title in ONE cell | e.g., `52.203-5 Covenant Against Contingent Fees.` Alternates use an underscore form: `52.203-6_Alternate I` (no title of their own). |
| Effective Date | Current effective date | `Mon YYYY` mostly (`May 2014`); some full month names (`June 2010`) or `Sept`; a handful contain non-breaking spaces (`Oct\xa0 2020`), a stray tab, or all caps (`NOV 2023`). Normalize whitespace before parsing. |
| Prescribed In | FAR prescription reference | e.g., `3.404`, `19.507(e)`, `12.301(b)(4)`. This is the only applicability signal the file carries. Two defects in the GSA data: `52.242-3` reads `42.709-7,` (stray trailing comma) and `52.247-63` reads `,` (no reference). The script strips stray commas and reports the blank as `not listed`. |
| P or C | Type | `P` = Provision (182 rows), `C` = Clause (627 rows) |

### Parsing rules

- Extract the clause number with a pattern like `(\d{2}\.\d{3})-(\d+)`; the remainder of the cell is the title.
- Alternate rows: `NUMBER_Alternate I` / `II` / `III`. The underscore before "Alternate" defeats a regex `\b` boundary (underscore is a word character); anchor with a negative lookbehind such as `(?<![A-Za-z])` instead.
- Some titles carry erratic internal whitespace (e.g., `52.219-14           Limitations on Subcontracting.`). Collapse runs of whitespace.
- No duplicate full-cell values; each (number, alternate) pair appears once.
- There is NO applicability grid (no contract type, purpose, or method columns), no RFO flag, no IBR column, no Regulation column, and no full text. Applicability for FAR clauses must come from the prescription at the `Prescribed In` reference.
- The matrix tracks the official FAR only. Revolutionary FAR Overhaul model class deviation clauses (for example, RFO 52.222-90) are not in it, so they come back as Not Found.

### Part 19 set-aside rules

The set-aside rules table in `scripts/far_checker.py` is hand-maintained, not read from this file. All 15 numbers it uses (52.219-1, -3, -4, -6, -7, -8, -9, -14, -16, -17, -18, -27, -28, -29, -30) are present in the bundled matrix.
