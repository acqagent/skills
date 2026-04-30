#!/usr/bin/env python3
"""
FAR Clause Checker — RFO Compliance Engine

Parses the DAU Matrix and HHS Deviation CSV, filters by user parameters,
and outputs a structured JSON report that can be used to generate a docx.

Usage:
    python3 far_checker.py --contract-type FP --purpose SUP --method NEG --commercial no --parts all --output report.json

Arguments:
    --contract-type   FP | CR | TM (Time & Materials/Labor Hour)
    --purpose         Comma-separated: SUP,SVC,RD,CON,LMV,COMSVC,DDR,AE,TRN,UTL
    --method          SAP | SLD | NEG | UNDER350K (can combine with comma)
    --commercial      yes | no
    --small-biz       Comma-separated: 8A,HUBZONE,SDVOSB,WOSB,SB,NONE
    --parts           Comma-separated FAR part numbers, or "all"
    --output          Output JSON path
    --data-dir        Directory containing the xlsx and csv files (default: same as script)
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("Installing openpyxl...")
    os.system(f"{sys.executable} -m pip install openpyxl --break-system-packages -q")
    import openpyxl


# Column index constants for the Matrix sheet
COL_CLAUSE_NUM = 1
COL_TITLE = 2
COL_DATE = 3
COL_PRESCRIBED_AT = 4
COL_PRESCRIPTION = 5
COL_TYPE = 6          # P or C
COL_RFO = 7
COL_COMM = 8
COL_IBR = 9
COL_UCF = 11
COL_FP = 12
COL_CR = 13
COL_TM = 14
COL_SUP = 15
COL_SVC = 16
COL_RD = 17
COL_CON = 18
COL_LMV = 19
COL_COMSVC = 20
COL_DDR = 21
COL_AE = 22
COL_TRN = 23
COL_UTL = 24
COL_COM_SUP = 25
COL_COM_SVC = 26
COL_SAP = 27
COL_SLD = 28
COL_NEG = 29
COL_UNDER350K = 30
COL_NCOM_SUBK = 31
COL_COM_SUBK = 32
COL_OCONUS = 33
COL_REGULATION = 34
COL_ORDER = 35
COL_FULL_TEXT = 37
COL_CLASS_DEV_URL = 38
COL_ALT_FLAG = 39
COL_ALT_VERSION = 40
COL_DEV_FLAG = 41
COL_DEV_VERSION = 42

# Map user-friendly purpose codes to column indices
PURPOSE_MAP = {
    "SUP": COL_SUP,
    "SVC": COL_SVC,
    "RD": COL_RD,
    "CON": COL_CON,
    "LMV": COL_LMV,
    "COMSVC": COL_COMSVC,
    "DDR": COL_DDR,
    "AE": COL_AE,
    "TRN": COL_TRN,
    "UTL": COL_UTL,
}

COMMERCIAL_PURPOSE_MAP = {
    "SUP": COL_COM_SUP,
    "SVC": COL_COM_SVC,
}

METHOD_MAP = {
    "SAP": COL_SAP,
    "SLD": COL_SLD,
    "NEG": COL_NEG,
    "UNDER350K": COL_UNDER350K,
}

CONTRACT_TYPE_MAP = {
    "FP": COL_FP,
    "CR": COL_CR,
    "TM": COL_TM,
}

# Set-aside rules for FAR Part 19 clauses.
# Maps set-aside-conditional clauses to the set-aside values that trigger them.
# Clauses not listed here are not set-aside-filtered and pass through normally.
#
# Mappings derived from FAR Part 19 prescriptions:
#   52.219-1, 52.219-8, 52.219-28: required regardless of set-aside (representations,
#       utilization of small business, post-award rerepresentation)
#   52.219-3, 52.219-4: HUBZONE only
#   52.219-6, 52.219-7: total/partial small business set-aside
#   52.219-14: applies to ANY small business set-aside (limitations on subcontracting)
#   52.219-17, 52.219-18: 8(a) only
#   52.219-27: SDVOSB only
#   52.219-29, 52.219-30: WOSB / EDWOSB only
#   52.219-9, 52.219-16: large-business prime with subcontracting plan (NONE only)
SETASIDE_RULES = {
    # Always applicable (regardless of set-aside) — let normal check_applicability handle these
    "always": {"52.219-1", "52.219-8", "52.219-28"},

    # Specific set-aside required — clause is applicable ONLY when the matching set-aside is selected
    "specific": {
        "52.219-3":  {"HUBZONE"},
        "52.219-4":  {"HUBZONE"},
        "52.219-6":  {"SB"},
        "52.219-7":  {"SB"},
        "52.219-17": {"8A"},
        "52.219-18": {"8A"},
        "52.219-27": {"SDVOSB"},
        "52.219-29": {"WOSB"},
        "52.219-30": {"WOSB"},
    },

    # Any small business set-aside required (i.e., not NONE)
    "any_setaside": {"52.219-14"},

    # Only when set-aside is NONE (large-business prime with subcontracting plan)
    "none_only": {"52.219-9", "52.219-16"},
}


def setaside_filter(clause_number, small_biz, base_applicable, base_reason):
    """
    Apply set-aside-specific filtering to a clause's applicability.

    Returns (applicable, reason) tuple. For clauses that are not set-aside
    conditional, returns the base applicability unchanged. For clauses with
    set-aside rules, may override the base decision.
    """
    sb = (small_biz or "NONE").upper()

    # "Always" clauses pass through normal check_applicability decision
    if clause_number in SETASIDE_RULES["always"]:
        return base_applicable, base_reason

    # Specific set-aside required
    if clause_number in SETASIDE_RULES["specific"]:
        required_setasides = SETASIDE_RULES["specific"][clause_number]
        if sb in required_setasides:
            # User has the required set-aside; clause applies regardless of
            # purpose/method match (set-aside trumps for these specific clauses)
            return True, f"Applicable due to {sb} set-aside"
        else:
            return False, f"Not applicable; requires set-aside in {sorted(required_setasides)}"

    # Any small business set-aside (52.219-14)
    if clause_number in SETASIDE_RULES["any_setaside"]:
        if sb != "NONE":
            return True, f"Applicable due to {sb} small business set-aside"
        else:
            return False, "Not applicable; requires a small business set-aside"

    # NONE only (large-business prime with subcontracting plan)
    if clause_number in SETASIDE_RULES["none_only"]:
        if sb == "NONE":
            return base_applicable, base_reason
        else:
            return False, "Not applicable under a small business set-aside"

    # Not set-aside conditional; pass through
    return base_applicable, base_reason

# Month abbreviation lookup
MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

import re

def normalize_date(date_str):
    """
    Parse a date string into (month, year) tuple for comparison.
    Handles formats: "Jan-2026 Deviation", "Nov 2025", "2-Jun-25",
    "JAN 2026", "MAY 2014", "Apr-1984", etc.
    Returns None for "--", empty, or unparseable strings.
    """
    if not date_str or date_str.strip() in ("--", ""):
        return None
    s = date_str.strip()
    # Strip "Deviation" and extra whitespace
    s = re.sub(r'\bDeviation\b', '', s, flags=re.IGNORECASE).strip()
    s = s.strip("-").strip()

    # Try: 3-letter month + 4-digit year (e.g., "Jan-2026", "NOV 2025", "May 2014")
    m = re.search(r'([A-Za-z]{3})\D*(\d{4})', s)
    if m:
        month_str = m.group(1).lower()
        year = int(m.group(2))
        month = MONTH_ABBR.get(month_str)
        if month:
            return (month, year)

    # Try: D-Mon-YY format (e.g., "2-Jun-25")
    m = re.search(r'(\d{1,2})\D+([A-Za-z]{3})\D+(\d{2})$', s)
    if m:
        month_str = m.group(2).lower()
        year_short = int(m.group(3))
        month = MONTH_ABBR.get(month_str)
        if month:
            # Assume 2000s for 2-digit years < 80, else 1900s
            year = 2000 + year_short if year_short < 80 else 1900 + year_short
            return (month, year)

    return None


def date_gte(user_date, hhs_date):
    """Return True if user_date >= hhs_date (year first, then month)."""
    if user_date is None or hhs_date is None:
        return False
    return (user_date[1], user_date[0]) >= (hhs_date[1], hhs_date[0])


def find_data_files(data_dir):
    """Locate the xlsx and csv files in the data directory."""
    xlsx_file = None
    csv_file = None
    for f in Path(data_dir).iterdir():
        if f.suffix in ('.xlsx', '.xlsm') and 'Provision' in f.name:
            xlsx_file = str(f)
        elif f.suffix == '.csv' and 'HHS' in f.name:
            csv_file = str(f)
    if not xlsx_file:
        # Try any xlsx/xlsm
        for f in Path(data_dir).iterdir():
            if f.suffix in ('.xlsx', '.xlsm'):
                xlsx_file = str(f)
                break
    if not csv_file:
        for f in Path(data_dir).iterdir():
            if f.suffix == '.csv':
                csv_file = str(f)
                break
    return xlsx_file, csv_file


def load_matrix(xlsx_path):
    """Load and parse the DAU Matrix sheet, returning FAR-only clause records."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb['Matrix']

    records = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=8, values_only=True)):  # data starts row 8 (1-indexed = row index 7 in 0-indexed)
        cells = list(row[:43]) if len(row) >= 43 else list(row) + [None] * (43 - len(row))

        # Skip non-FAR rows
        reg = str(cells[COL_REGULATION] or "").strip().upper()
        if reg != "FAR":
            continue

        clause_num = str(cells[COL_CLAUSE_NUM] or "").strip()
        # Skip note rows and empty rows
        if not clause_num or clause_num.startswith("See notes"):
            continue

        record = {
            "clause_number": clause_num,
            "title": str(cells[COL_TITLE] or "").strip(),
            "date": str(cells[COL_DATE] or "").strip(),
            "prescribed_at": str(cells[COL_PRESCRIBED_AT] or "").strip(),
            "prescription": str(cells[COL_PRESCRIPTION] or "").strip()[:500],  # truncate for report
            "type": str(cells[COL_TYPE] or "").strip(),  # P or C
            "rfo_flag": "RFO X" in str(cells[COL_RFO] or ""),
            "commercial": str(cells[COL_COMM] or "").strip(),
            "ibr": str(cells[COL_IBR] or "").strip(),
            "ucf_section": str(cells[COL_UCF] or "").strip(),
            "alt_flag": str(cells[COL_ALT_FLAG] or "").strip().upper() == "YES",
            "alt_version": str(cells[COL_ALT_VERSION] or "").strip(),
            "dev_flag": str(cells[COL_DEV_FLAG] or "").strip().upper() == "YES",
            "dev_version": str(cells[COL_DEV_VERSION] or "").strip(),
            "applicability": {}
        }

        # Store applicability codes for all relevant columns
        for col_name, col_idx in {**CONTRACT_TYPE_MAP, **PURPOSE_MAP, **METHOD_MAP}.items():
            val = str(cells[col_idx] or "").strip()
            record["applicability"][col_name] = val if val else ""

        # Commercial purpose columns
        for col_name, col_idx in COMMERCIAL_PURPOSE_MAP.items():
            val = str(cells[col_idx] or "").strip()
            record["applicability"][f"COM_{col_name}"] = val if val else ""

        # Flowdown
        record["applicability"]["NCOM_SUBK"] = str(cells[COL_NCOM_SUBK] or "").strip()
        record["applicability"]["COM_SUBK"] = str(cells[COL_COM_SUBK] or "").strip()
        record["applicability"]["OCONUS"] = str(cells[COL_OCONUS] or "").strip()

        records.append(record)

    wb.close()
    return records


def load_hhs_csv(csv_path):
    """Load the HHS deviation CSV, returning a dict keyed by clause number."""
    deviations = {}
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            num = row.get('Number', '').strip()
            if not num:
                continue
            deviations[num] = {
                "part": row.get('Part', '').strip(),
                "type": row.get('Type', '').strip(),
                "pre_rfo_title": row.get('Pre-RFO Title', '').strip(),
                "pre_rfo_date": row.get('Pre-RFO Date', '').strip(),
                "rfo_title": row.get('RFO Title', '').strip(),
                "hhs_deviation_date": row.get('HHS Deviation Date', '').strip(),
                "disposition": row.get('Disposition', '').strip(),
                "notes": row.get('Notes', '').strip(),
            }
    return deviations


def check_applicability(record, contract_type, purposes, methods, is_commercial):
    """Determine if a clause applies based on user parameters.

    Strict AND logic: a clause is applicable only when contract type matches
    AND at least one of (purpose, method) matches. Contract type alone does
    not qualify a clause; nor does contract type + a blank everywhere else.

    Commercial procurements (is_commercial=True) check the COM_<purpose>
    columns first. If none of the user's purposes have COM_ entries, the
    clause is treated as non-applicable for commercial work, since FAR
    Part 12 limits which provisions apply to commercial items.
    """
    # Check contract type
    ct_code = record["applicability"].get(contract_type, "")
    if not ct_code:
        return False, "not_applicable", "Not applicable for this contract type"

    # Check purpose. Commercial mode looks ONLY at COM_ columns; non-commercial
    # mode looks at the regular purpose columns.
    purpose_match = False
    if is_commercial:
        for p in purposes:
            com_key = f"COM_{p}"
            if record["applicability"].get(com_key, ""):
                purpose_match = True
                break
    else:
        for p in purposes:
            if record["applicability"].get(p, ""):
                purpose_match = True
                break

    # Check method
    method_match = False
    for m in methods:
        if record["applicability"].get(m, ""):
            method_match = True
            break

    # Strict AND: must match contract type AND (purpose OR method).
    # The previous elif-fallback that treated contract-type-alone as applicable
    # has been removed. It caused 18 of 23 FP profiles to collapse to the same
    # 756-clause output regardless of purpose, method, commercial flag, or
    # set-aside.
    if purpose_match or method_match:
        return True, ct_code, "Applicable"
    return False, "", "Not applicable for this purpose/method combination"


def run_checks(records, deviations, contract_type, purposes, methods, is_commercial, parts_filter, small_biz="NONE"):
    """Run all compliance checks and return findings."""
    results = []

    for rec in records:
        # Filter by FAR part if specified
        if parts_filter and parts_filter != ["all"]:
            clause_part = rec["clause_number"].split(".")[0].replace("52", "")
            # 52.2xx-y -> part is the 2xx portion, e.g. 52.219 -> Part 19
            try:
                part_num = rec["clause_number"].split(".")[1].split("-")[0]
                # Map 2xx to Part xx (e.g., 203 -> 3, 219 -> 19)
                if len(part_num) == 3:
                    mapped_part = str(int(part_num[1:]))  # 203 -> 03 -> 3
                else:
                    mapped_part = part_num
                if mapped_part not in parts_filter:
                    continue
            except (IndexError, ValueError):
                continue

        applicable, code, reason = check_applicability(
            rec, contract_type, purposes, methods, is_commercial
        )

        # Apply set-aside filter (Recommendation 2). For Part 19 clauses with
        # explicit set-aside rules, this can override the applicability decision.
        applicable, reason = setaside_filter(rec["clause_number"], small_biz, applicable, reason)

        # Look up HHS deviation data
        hhs = deviations.get(rec["clause_number"], {})

        finding = {
            "clause_number": rec["clause_number"],
            "title": rec["title"],
            "date": rec["date"],
            "type": rec["type"],
            "ibr": rec["ibr"],
            "ucf_section": rec["ucf_section"],
            "rfo_flag": rec["rfo_flag"],
            "applicable": applicable,
            "applicability_code": code,
            "applicability_reason": reason,
            "alt_flag": rec["alt_flag"],
            "alt_version": rec["alt_version"],
            "dev_flag": rec["dev_flag"],
            "prescribed_at": rec["prescribed_at"],
            "prescription_excerpt": rec["prescription"][:300],
            "status": "valid",
            "findings": [],
        }

        # HHS disposition
        if hhs:
            finding["hhs_disposition"] = hhs["disposition"]
            finding["hhs_deviation_date"] = hhs["hhs_deviation_date"]
            finding["hhs_rfo_title"] = hhs["rfo_title"]
            finding["hhs_pre_rfo_title"] = hhs["pre_rfo_title"]
            finding["hhs_pre_rfo_date"] = hhs["pre_rfo_date"]
            finding["hhs_notes"] = hhs["notes"]

            # Check: Removed
            if hhs["disposition"] == "Removed":
                finding["status"] = "removed"
                finding["findings"].append({
                    "severity": "CRITICAL",
                    "check": "Removed Clause",
                    "detail": f"This clause was REMOVED in the RFO. RFO Title is [{hhs['rfo_title']}]. Do NOT include in new solicitations/contracts."
                })

            # Check: Updated — date-aware logic
            elif hhs["disposition"] == "Updated":
                user_date_str = rec["date"]
                hhs_date_str = hhs["hhs_deviation_date"]
                user_parsed = normalize_date(user_date_str)
                hhs_parsed = normalize_date(hhs_date_str)
                user_has_deviation = "deviation" in user_date_str.lower() if user_date_str else False

                if hhs_parsed is not None and user_parsed is not None and date_gte(user_parsed, hhs_parsed) and user_has_deviation:
                    # User date matches or is newer + has deviation tag → Valid
                    finding["status"] = "valid"
                    finding["findings"].append({
                        "severity": "INFO",
                        "check": "Updated Clause — Current",
                        "detail": f"No action required — user date ({user_date_str}) matches current deviation version ({hhs_date_str})."
                    })
                elif hhs_date_str in ("--", "") and user_has_deviation:
                    # HHS has no deviation date but user claims deviation → Review
                    finding["status"] = "review"
                    finding["findings"].append({
                        "severity": "WARNING",
                        "check": "Verify Deviation Source",
                        "detail": f"HHS shows no agency deviation for this clause, but user references a deviation ({user_date_str}). Verify deviation source and authority."
                    })
                elif hhs_parsed is not None and (user_parsed is None or not date_gte(user_parsed, hhs_parsed)):
                    # User date is older than HHS deviation date → Action Needed
                    finding["status"] = "action_needed"
                    finding["findings"].append({
                        "severity": "CRITICAL",
                        "check": "Date Mismatch",
                        "detail": f"User date ({user_date_str}) is older than current HHS deviation date ({hhs_date_str}). Update to current version."
                    })
                else:
                    # Fallback for Updated with no clear date comparison
                    finding["status"] = "updated"
                    finding["findings"].append({
                        "severity": "WARNING",
                        "check": "Updated Clause",
                        "detail": f"This clause was UPDATED in the RFO. HHS deviation date: {hhs_date_str}. Verify you are using the current version."
                    })
        else:
            finding["hhs_disposition"] = "N/A (not in HHS matrix)"
            finding["hhs_deviation_date"] = ""
            finding["hhs_rfo_title"] = ""
            finding["hhs_pre_rfo_title"] = ""
            finding["hhs_pre_rfo_date"] = ""
            finding["hhs_notes"] = ""

        # RFO impact check
        if rec["rfo_flag"] and finding["status"] == "valid":
            finding["findings"].append({
                "severity": "INFO",
                "check": "RFO Affected",
                "detail": "This clause is flagged as affected by the FAR RFO. Review for any structural or content changes."
            })

        # IBR check
        if rec["ibr"] == "No" and applicable:
            finding["findings"].append({
                "severity": "WARNING",
                "check": "Full Text Required",
                "detail": "This clause is NOT authorized for incorporation by reference. Must include full text in the solicitation/contract."
            })
        elif rec["ibr"] == "Yes*" and applicable:
            finding["findings"].append({
                "severity": "INFO",
                "check": "Conditional IBR",
                "detail": "IBR is authorized only under conditions specified at FAR 52.102(c). Verify conditions are met."
            })

        # Deviation flag
        if rec["dev_flag"]:
            finding["findings"].append({
                "severity": "WARNING",
                "check": "Deviation Flagged",
                "detail": f"A deviation is flagged for this clause. Deviation version: {rec['dev_version']}."
            })

        results.append(finding)

    return results


def generate_summary(results):
    """Generate summary statistics."""
    total = len(results)
    applicable = [r for r in results if r["applicable"]]
    valid = [r for r in applicable if r["status"] == "valid"]
    action_needed = [r for r in applicable if r["status"] == "action_needed"]
    review = [r for r in applicable if r["status"] == "review"]
    removed = [r for r in applicable if r["status"] == "removed"]
    not_found = [r for r in applicable if r["status"] == "not_found"]
    # Legacy: count any still-"updated" as fallback
    updated_fallback = [r for r in applicable if r["status"] == "updated"]
    critical = [r for r in applicable if any(f["severity"] == "CRITICAL" for f in r["findings"])]
    warnings = [r for r in applicable if any(f["severity"] == "WARNING" for f in r["findings"])]

    return {
        "total_checked": total,
        "total_applicable": len(applicable),
        "valid_no_action": len(valid),
        "action_needed_date_mismatch": len(action_needed),
        "review_verify_deviation": len(review),
        "removed": len(removed),
        "not_found_in_matrix": len(not_found),
        "updated_fallback": len(updated_fallback),
        "critical_findings": len(critical),
        "warnings": len(warnings),
    }


def main():
    parser = argparse.ArgumentParser(description="FAR Clause Checker — RFO Compliance")
    parser.add_argument("--contract-type", required=True, choices=["FP", "CR", "TM"])
    parser.add_argument("--purpose", required=True, help="Comma-separated: SUP,SVC,RD,CON,LMV,COMSVC,DDR,AE,TRN,UTL")
    parser.add_argument("--method", required=True, help="SAP,SLD,NEG,UNDER350K")
    parser.add_argument("--commercial", required=True, choices=["yes", "no"])
    parser.add_argument("--small-biz", default="NONE", help="8A,HUBZONE,SDVOSB,WOSB,SB,NONE")
    parser.add_argument("--parts", default="all", help="Comma-separated part numbers or 'all'")
    parser.add_argument("--output", default="report.json")
    parser.add_argument("--data-dir", default=None, help="Directory with xlsx and csv files")

    args = parser.parse_args()

    # Find data files
    data_dir = args.data_dir or os.path.dirname(os.path.abspath(__file__))
    # Also check references/ subdirectory
    refs_dir = os.path.join(data_dir, "references")
    if os.path.isdir(refs_dir):
        xlsx_file, csv_file = find_data_files(refs_dir)
    else:
        xlsx_file, csv_file = find_data_files(data_dir)

    if not xlsx_file:
        print("ERROR: Could not find the DAU Matrix xlsx/xlsm file")
        sys.exit(1)
    if not csv_file:
        print("ERROR: Could not find the HHS deviation CSV file")
        sys.exit(1)

    print(f"Loading Matrix from: {xlsx_file}")
    records = load_matrix(xlsx_file)
    print(f"  Loaded {len(records)} FAR clause records")

    print(f"Loading HHS deviations from: {csv_file}")
    deviations = load_hhs_csv(csv_file)
    print(f"  Loaded {len(deviations)} deviation records")

    # Parse arguments
    purposes = [p.strip().upper() for p in args.purpose.split(",")]
    methods = [m.strip().upper() for m in args.method.split(",")]
    is_commercial = args.commercial.lower() == "yes"
    parts_filter = [p.strip() for p in args.parts.split(",")] if args.parts.lower() != "all" else ["all"]

    print(f"\nRunning checks...")
    print(f"  Contract Type: {args.contract_type}")
    print(f"  Purpose: {purposes}")
    print(f"  Method: {methods}")
    print(f"  Commercial: {is_commercial}")
    print(f"  Small Business: {args.small_biz}")
    print(f"  Parts Filter: {parts_filter}")

    results = run_checks(records, deviations, args.contract_type, purposes, methods, is_commercial, parts_filter, args.small_biz)
    summary = generate_summary(results)

    output = {
        "parameters": {
            "contract_type": args.contract_type,
            "purpose": purposes,
            "method": methods,
            "commercial": is_commercial,
            "small_business": args.small_biz,
            "parts_filter": parts_filter,
        },
        "summary": summary,
        "results": results,
    }

    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nSummary:")
    print(f"  Total clauses checked: {summary['total_checked']}")
    print(f"  Applicable: {summary['total_applicable']}")
    print(f"  Valid (no action required): {summary['valid_no_action']}")
    print(f"  Action Needed (date mismatch): {summary['action_needed_date_mismatch']}")
    print(f"  Review (verify deviation): {summary['review_verify_deviation']}")
    print(f"  Removed: {summary['removed']}")
    print(f"  Not Found in Matrix: {summary['not_found_in_matrix']}")
    if summary['updated_fallback']:
        print(f"  Updated (fallback): {summary['updated_fallback']}")
    print(f"  Critical findings: {summary['critical_findings']}")
    print(f"  Warnings: {summary['warnings']}")
    print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
