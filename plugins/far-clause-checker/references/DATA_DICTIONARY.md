# Data Dictionary — FAR Clause Checker

This document maps the columns in both source files so the skill can parse them correctly.

## DAU Provision & Clause Matrix (Excel — Matrix Sheet)

**Sheet**: `Matrix`
**Header row**: Row index 6 (0-indexed from openpyxl's iter_rows)
**Data starts**: Row index 7
**Total columns used**: 43 (indices 0–42)
**Filter**: Only use rows where column 34 == "FAR" (ignore DFARS, VAAR, DEAR)

### Column Map

| Index | Header | Description | Values / Notes |
|-------|--------|-------------|----------------|
| 0 | X | Include filter | User marking |
| 1 | Located at 48 CFR | Clause/provision number | e.g., `52.203-5` |
| 2 | Title | Clause/provision title | Full title text; alternates append `--Alternate I` etc. |
| 3 | Date | Effective date | Format: `MMM YYYY` (e.g., `MAY 2014`, `JUN 2020`) |
| 4 | Prescribed at 48 CFR | FAR prescription reference | e.g., `3.404`, `22.810(e)` |
| 5 | Prescription | Full prescription text | Describes when/how to use the clause |
| 6 | P or C | Type | `P` = Provision, `C` = Clause |
| 7 | RFO | Revolutionary FAR Overhaul flag | `RFO X` = affected by RFO; blank = not affected |
| 8 | COMM | Commercial applicability | `IAP` = if acquisition is commercial products/services; blank = not specific to commercial |
| 9 | IBR | Incorporation by Reference | `Yes` = authorized, `No` = full text required, `Yes*` = conditional per FAR 52.102(c) |
| 10 | USACE CSI | USACE Construction Specifications Institute code | e.g., `00 72 00` |
| 11 | UCF | Uniform Contract Format section | `I` = Section I, `K` = Section K, etc. |

### Contract Type Columns (indices 12–14)

| Index | Header | Description |
|-------|--------|-------------|
| 12 | FP | Fixed-Price |
| 13 | CR | Cost-Reimbursement |
| 14 | T&M/LH | Time & Materials / Labor Hour |

### Contract Purpose — Non-Commercial (indices 15–24)

| Index | Header | Full Name |
|-------|--------|-----------|
| 15 | SUP | Supplies |
| 16 | SVC | Services |
| 17 | R&D | Research & Development |
| 18 | CON | Construction |
| 19 | LMV | Leasehold/Motor Vehicle |
| 20 | COM SVC | Commercial Services (non-commercial context) |
| 21 | DDR | Dismantling, Demolition, Removal |
| 22 | A-E | Architect-Engineering |
| 23 | TRN | Transportation |
| 24 | UTL SVC | Utility Services |

### Contract Purpose — Commercial (indices 25–26)

| Index | Header | Full Name |
|-------|--------|-----------|
| 25 | SUP | Commercial Supplies |
| 26 | SVC | Commercial Services |

### Solicitation Method (indices 27–30)

| Index | Header | Full Name |
|-------|--------|-----------|
| 27 | SAP | Simplified Acquisition Procedures |
| 28 | SLD BID | Sealed Bidding |
| 29 | NEG CON | Negotiated Contracting |
| 30 | <=$350K | Simplified threshold (at or below $350K) |

### Other Columns (indices 31–42)

| Index | Header | Description |
|-------|--------|-------------|
| 31 | NCOM SUBK | Non-commercial subcontract flowdown |
| 32 | COM SUBK | Commercial subcontract flowdown |
| 33 | OCONUS | Outside Continental US applicability |
| 34 | Regulation | Source regulation: `FAR`, `DFARS`, `VAAR`, `DEAR` |
| 35 | Order | Sort order number |
| 36 | (unused) | — |
| 37 | Full Text | Complete clause/provision text |
| 38 | Class Deviations URL | Link to class deviation if applicable |
| 39 | Alternate Variation Flag | `Yes` or `No` — whether this row is an alternate |
| 40 | Alternate Version | Alternate identifier (e.g., `I`, `II`) |
| 41 | Deviation Flag | `Yes` or `No` — whether a deviation applies |
| 42 | Deviation Version | Deviation identifier |

### Applicability Code Values

Used in columns 12–33:

| Code | Meaning |
|------|---------|
| `A` | Required when applicable |
| `R` | Required |
| `O` | Optional |
| (blank) | Not applicable for this contract type/purpose |

### Special Rows

- Rows where column 1 contains `See notes>>>` are supplementary notes for the preceding clause, not separate clauses
- Rows where column 1 contains `[Reserved]` are reserved/removed clause numbers
- Alternate versions of a clause share the same clause number in column 1 but have different titles (e.g., `--Alternate I`)

---

## HHS Agency Deviation Matrix (CSV)

**Format**: Standard CSV with header row
**Encoding**: UTF-8 with possible Windows line endings (\r\n)

### Column Map

| Column Name | Description | Values / Notes |
|-------------|-------------|----------------|
| Part | FAR Part number | Integer (e.g., `1`, `3`, `4`, `19`) |
| Type | Provision, Clause, or reserved | `Provision`, `Clause`, `--` (reserved) |
| Number | Clause/provision number | e.g., `52.203-5` — use this to join to Excel column 1 |
| Pre-RFO Title | Title before the FAR overhaul | Original title text; `[Reserved]` if was already reserved |
| Pre-RFO Date | Date of pre-RFO version | Format: `MMM YYYY` or `--` if N/A |
| RFO Title | Title after the FAR overhaul | New title; `[Reserved]` if removed |
| HHS Deviation Date | Agency-specific deviation date | Date format varies (e.g., `2-Jun-25`, `Nov 2025`), or `--` if no deviation |
| Disposition | RFO change status | `No Change`, `Removed`, `Updated` |
| Notes | Additional context | Free text; may be empty |

### Key Disposition Logic

- **No Change**: Clause survived the RFO without modification. If HHS Deviation Date is `--`, no agency action needed.
- **Removed**: Clause was removed (reserved) in the restructured FAR. RFO Title will be `[Reserved]`. These clauses should NOT be included in new solicitations/contracts.
- **Updated**: Clause was modified in the RFO. Compare Pre-RFO Date vs HHS Deviation Date to identify timing. The new date in the Matrix (Excel) reflects the current version.

### Join Key

Join the CSV `Number` column to the Excel `Located at 48 CFR` column (index 1) to correlate disposition data with the full clause details.

Note: The CSV may contain rows where Type is `--` — these are reserved clause numbers with no active provision/clause. Skip these unless checking for removed clauses.
