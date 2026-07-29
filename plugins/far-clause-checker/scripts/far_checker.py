#!/usr/bin/env python3
"""
FAR Clause Checker v3 - RFO Compliance Engine

Data sources (in references/):
  1. Smart Matrix (CSV)  - FAR 52.2xx baseline: number+title, effective date,
     prescribed-in reference, P or C. No applicability grid.
  2. HHSAR Deviations (XLSX, "Matrix" sheet) - HHSAR 352.2xx clauses with
     status (Active/Removed/Reserved), class deviation numbers, dated
     deviation annotations, IBR, PCO fill-in, applicability codes, UCF.

The two files cover disjoint clause families (FAR 52.x vs HHSAR 352.x).
There is no join key between them.

Modes:
  check     (default when --clauses is given) Validate a user clause list.
            Each FAR clause is checked against the Smart Matrix for existence
            and date currency. Each HHSAR clause is checked for status,
            deviation currency, IBR, fill-in, and applicability fit.
            Missing required HHSAR clauses and missing set-aside clauses
            are also reported.
  checklist (default when --clauses is absent) Build the HHSAR
            required / as-applicable checklist for the given contract
            parameters, plus a FAR clause inventory filtered by --parts.

Usage:
    python3 far_checker.py --clauses my_section_i.txt --contract-type FFP \
        --over-sat yes --commercial no --small-biz NONE --output report.json

    python3 far_checker.py --contract-type COST --over-sat yes \
        --parts 19,27 --output checklist.json

Clause list format (file: one per line; inline: separate with ";"):
    52.203-5 Covenant Against Contingent Fees (MAY 2014)
    52.204-8 Alt I (Mar 2026)
    352.203-70 (JUN 2026) Deviation
    52.219-14
Titles are ignored; the parser extracts the number, any Alternate, any
month-year date, and whether the entry cites a deviation.

Arguments:
    --clauses         Path to a clause-list file, or an inline ";"-separated list
    --contract-type   FFP | FFP_LOE | COST | TM        (default FFP)
    --over-sat        yes | no  (action over the simplified acquisition
                      threshold; "no" also stands in for simplified
                      acquisitions)                     (default yes)
    --commercial      yes | no                          (default no)
    --small-biz       NONE | SB | 8A | HUBZONE | SDVOSB | WOSB  (default NONE)
    --parts           Comma-separated FAR part numbers, or "all" (default all)
    --output          Output JSON path (default report.json)
    --data-dir        Directory containing the data files or a references/
                      subdirectory (default: the skill root above this script)

Removed in v3 (no applicability grid in the Smart Matrix):
    --purpose, --method   Accepted but ignored, with a warning.
"""

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("Installing openpyxl...")
    os.system(f"{sys.executable} -m pip install openpyxl --break-system-packages -q")
    import openpyxl


# ---------------------------------------------------------------------------
# Shared parsing helpers
# ---------------------------------------------------------------------------

MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# FAR numbers: 52.203-5     HHSAR numbers: 352.203-70, 352.270-5a
# Tolerates the 352.215.70 typo (period instead of hyphen) found in the
# JUL 2026 HHSAR matrix by accepting either separator and normalizing.
CLAUSE_NUM_RE = re.compile(r"(\d{2,3}\.\d{3})[.-](\d+[A-Za-z]?)")

# (?<![A-Za-z]) instead of \b: labels like "52.203-6_Alternate I" put a
# word character (_) before "Alternate", which defeats a \b boundary.
ALT_RE = re.compile(r"(?<![A-Za-z])ALT(?:ERNATE)?[\s._-]*([IVX]+|\d+)\b",
                    re.IGNORECASE)

ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
         "vii": 7, "viii": 8, "ix": 9, "x": 10}


def clean_text(val):
    """Collapse odd whitespace (nbsp, narrow nbsp, tabs) and <br> artifacts."""
    if val is None:
        return ""
    s = str(val)
    s = s.replace("<br>", " ").replace("\u202f", " ").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_clause_number(text):
    """Return the canonical clause number (hyphen-normalized) or None."""
    m = CLAUSE_NUM_RE.search(str(text))
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}"


def extract_alternate(text):
    """Return the alternate as an int (Alt I -> 1, Alt 2 -> 2) or None."""
    m = ALT_RE.search(str(text))
    if not m:
        return None
    token = m.group(1).lower()
    if token.isdigit():
        return int(token)
    return ROMAN.get(token)


def alt_label(alt):
    """Human label for an alternate int."""
    if not alt:
        return ""
    romans = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
              6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}
    return f"Alternate {romans.get(alt, alt)}"


def normalize_date(date_str):
    """
    Parse a date string into a (month, year) tuple for comparison.
    Handles: "MAY 2014", "Mar 2026", "June 2010", "Oct\xa0 2020",
    "JUN 2026 (RFO DEVIATION)", "FEB 2024 (Deviation)",
    "AUG 2025 Court Order", "2-Jun-25", "Jan-2026 Deviation".
    Returns None for "--", empty, or unparseable strings.
    """
    if not date_str:
        return None
    s = clean_text(date_str)
    if s in ("--", ""):
        return None

    # 3-letter month prefix + 4-digit year (also matches "June", "MARCH")
    m = re.search(r"([A-Za-z]{3})[A-Za-z]*\W*(\d{4})", s)
    if m:
        month = MONTH_ABBR.get(m.group(1).lower())
        if month:
            return (month, int(m.group(2)))

    # D-Mon-YY (e.g., "2-Jun-25")
    m = re.search(r"(\d{1,2})\W+([A-Za-z]{3})\W+(\d{2})\b", s)
    if m:
        month = MONTH_ABBR.get(m.group(2).lower())
        if month:
            yy = int(m.group(3))
            year = 2000 + yy if yy < 80 else 1900 + yy
            return (month, year)

    return None


def date_gte(a, b):
    """True if date a >= date b (year first, then month)."""
    if a is None or b is None:
        return False
    return (a[1], a[0]) >= (b[1], b[0])


def fmt_date(parsed, raw):
    """Prefer the cleaned raw string for display, fall back to parsed."""
    if raw:
        return clean_text(raw)
    if parsed:
        names = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                 "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        return f"{names[parsed[0]]} {parsed[1]}"
    return "(no date)"


def deviation_kind(date_str, cd_flag):
    """Classify the deviation annotation carried in an HHSAR date cell."""
    s = clean_text(date_str).lower()
    if "rfo" in s:
        return "RFO deviation"
    if "court order" in s:
        return "court order"
    if "deviation" in s or clean_text(cd_flag).upper() == "Y":
        return "deviation"
    return ""


def far_part(clause_number):
    """52.219-14 -> '19'; 352.235-70 -> '35'. Returns None if unparseable."""
    m = re.match(r"\d{2,3}\.(\d)(\d{2})-", clause_number or "")
    if not m:
        return None
    return str(int(m.group(2)))


# ---------------------------------------------------------------------------
# Set-aside rules (FAR Part 19) - unchanged from v2
# ---------------------------------------------------------------------------

SETASIDE_RULES = {
    # Required regardless of set-aside (representations, utilization,
    # post-award rerepresentation)
    "always": {"52.219-1", "52.219-8", "52.219-28"},

    # Applicable ONLY under the matching set-aside
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

    # Any small business set-aside (i.e., not NONE)
    "any_setaside": {"52.219-14"},

    # Only when set-aside is NONE (large-business prime, subcontracting plan)
    "none_only": {"52.219-9", "52.219-16"},
}


def setaside_verdict(clause_number, small_biz):
    """
    Returns (verdict, reason) for a Part 19 clause under the given set-aside.
    verdict: "ok" (passes through), "excluded" (should not be in this action),
             or "ok" for clauses with no set-aside rule.
    """
    sb = (small_biz or "NONE").upper()
    if clause_number in SETASIDE_RULES["always"]:
        return "ok", "Universal Part 19 clause (applies regardless of set-aside)"
    if clause_number in SETASIDE_RULES["specific"]:
        req = SETASIDE_RULES["specific"][clause_number]
        if sb in req:
            return "ok", f"Matches {sb} set-aside"
        return "excluded", f"Requires set-aside in {sorted(req)}; action is {sb}"
    if clause_number in SETASIDE_RULES["any_setaside"]:
        if sb != "NONE":
            return "ok", f"Applies under {sb} small business set-aside"
        return "excluded", "Requires a small business set-aside; action has none"
    if clause_number in SETASIDE_RULES["none_only"]:
        if sb == "NONE":
            return "ok", "Large-business prime clause (no set-aside on action)"
        return "excluded", "Not used under a small business set-aside"
    return "ok", ""


def expected_setaside_clauses(small_biz):
    """The 52.219 clauses a CO should expect in a solicitation for this set-aside."""
    sb = (small_biz or "NONE").upper()
    expected = set(SETASIDE_RULES["always"])
    for clause, req in SETASIDE_RULES["specific"].items():
        if sb in req:
            expected.add(clause)
    if sb != "NONE":
        expected |= SETASIDE_RULES["any_setaside"]
    else:
        expected |= SETASIDE_RULES["none_only"]
    return expected


# ---------------------------------------------------------------------------
# HHSAR applicability codes
# ---------------------------------------------------------------------------

def canon_applicability(code):
    """Normalize an HHSAR applicability code for matching."""
    s = clean_text(code).upper()
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s*,\s*", ",", s)
    s = re.sub(r"\s+", " ", s)
    return s


def map_hhsar_applicability(code, contract_type, over_sat, commercial):
    """
    Evaluate an HHSAR applicability code against the action parameters.

    Returns (fit, requirement, reason):
      fit         True / False / None (None = unknown code, review manually)
      requirement "required" | "as_applicable" | "" (for unknown)
    """
    c = canon_applicability(code)
    ct = contract_type.upper()
    cost_tm = ct in ("COST", "TM")
    cost_tm_loe = ct in ("COST", "TM", "FFP_LOE")

    if not c:
        return None, "", "No applicability code in the HHSAR matrix"

    if c == "R-ALL":
        return True, "required", "Required in all action types"
    if c == "R-OVER SAT":
        if over_sat:
            return True, "required", "Required in actions over the SAT"
        return False, "required", "Only required over the SAT; this action is at or below it"
    if c in ("R-COST AND T&M/LH", "R-COST AND T&M/LH-NONCOMMERCIAL"):
        noncommercial_only = "NONCOMMERCIAL" in c
        if noncommercial_only and commercial:
            return False, "required", "Applies to noncommercial Cost and T&M/LH actions only"
        if cost_tm:
            return True, "required", "Required in Cost and T&M/LH actions"
        return False, "required", "Applies to Cost and T&M/LH actions only"
    if c == "A-ALL":
        return True, "as_applicable", "As applicable in all action types"
    if c == "A-ALL EXCEPT COMMERCIAL AND SAT":
        if commercial:
            return False, "as_applicable", "Not used in commercial acquisitions"
        if not over_sat:
            return False, "as_applicable", "Not used in simplified acquisitions"
        return True, "as_applicable", "As applicable (noncommercial, over the SAT)"
    if c in ("A-COST,T&M/LH,SIMPLIFIED ACQUISITION", "A-COST,T&M/LH,SIMPLIFIED ACQUISITIONS"):
        if cost_tm or not over_sat:
            return True, "as_applicable", "As applicable to Cost, T&M/LH, and simplified acquisitions"
        return False, "as_applicable", "Applies to Cost, T&M/LH, or simplified acquisitions only"
    if c == "A-ALL OVER SAT":
        if over_sat:
            return True, "as_applicable", "As applicable in actions over the SAT"
        return False, "as_applicable", "Only used over the SAT; this action is at or below it"
    if c in ("A-COST,T&M/LH,AND FFP LOE", "A-COST,T&M/LH AND FFP LOE"):
        if cost_tm_loe:
            return True, "as_applicable", "As applicable to Cost, T&M/LH, and FFP LOE actions"
        return False, "as_applicable", "Applies to Cost, T&M/LH, and FFP LOE actions only"
    if c == "A-COST ONLY":
        if ct == "COST":
            return True, "as_applicable", "As applicable to Cost-type actions"
        return False, "as_applicable", "Applies to Cost-type actions only"

    return None, "", f"Unrecognized applicability code '{clean_text(code)}'; review manually"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def find_data_files(data_dir):
    """
    Locate the Smart Matrix CSV and the HHSAR deviations XLSX.
    v3 role swap vs v2: the CSV is now the FAR matrix, the XLSX is the
    agency (HHSAR) file.
    """
    csv_file = None
    xlsx_file = None
    entries = list(Path(data_dir).iterdir())
    for f in entries:
        name = f.name.lower()
        if f.suffix == ".csv" and ("matrix" in name or "smart" in name):
            csv_file = str(f)
        elif f.suffix in (".xlsx", ".xlsm") and ("hhsar" in name or "deviation" in name):
            xlsx_file = str(f)
    if not csv_file:
        for f in entries:
            if f.suffix == ".csv":
                csv_file = str(f)
                break
    if not xlsx_file:
        for f in entries:
            if f.suffix in (".xlsx", ".xlsm"):
                xlsx_file = str(f)
                break
    return csv_file, xlsx_file


def load_smart_matrix(csv_path):
    """
    Load the Smart Matrix CSV.

    Returns dict: base_number -> {"base": entry or None,
                                  "alternates": {alt_int: entry}}
    entry: {number, alternate, label, title, date_raw, date_parsed,
            prescribed_in, p_or_c, part}
    """
    index = {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = clean_text(row.get("Provision or Clause (P or C)"))
            if not label:
                continue
            number = extract_clause_number(label)
            if not number:
                continue
            alternate = extract_alternate(label)
            # Title = label minus the number token (alternate rows carry no
            # title of their own, so they display as "Alternate N")
            title = CLAUSE_NUM_RE.sub("", label, count=1)
            title = re.sub(r"^[\s._-]+", "", title).strip()
            date_raw = clean_text(row.get("Effective Date"))
            entry = {
                "number": number,
                "alternate": alternate,
                "label": label,
                "title": title if not alternate else alt_label(alternate),
                "date_raw": date_raw,
                "date_parsed": normalize_date(date_raw),
                "prescribed_in": clean_text(row.get("Prescribed In")),
                "p_or_c": clean_text(row.get("P or C")).upper(),
                "part": far_part(number),
            }
            slot = index.setdefault(number, {"base": None, "alternates": {}})
            if alternate:
                slot["alternates"][alternate] = entry
            else:
                slot["base"] = entry
    return index


HHSAR_HEADER = [
    "number_raw", "title", "date_raw", "prescribed_at", "prescription",
    "p_or_c", "ibr", "pco_fill_in", "applicability", "ucf", "link",
    "class_dev", "class_dev_number", "status",
]


def load_hhsar_matrix(xlsx_path):
    """
    Load the HHSAR deviations workbook ("Matrix" sheet).
    Header block: rows 0-10 are a legend; row 11 is the header; data at 12+.

    Returns dict: base_number -> [entry, ...]
    entry adds: number, alternate, date_parsed, dev_kind, do_not_use,
                reserved_flag, cleaned strings for every column.
    """
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb["Matrix"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Find the header row defensively (first row whose col0 mentions
    # "Provision or Clause Number") instead of hard-coding index 11.
    header_idx = None
    for i, r in enumerate(rows):
        if r and "provision or clause number" in clean_text(r[0]).lower():
            header_idx = i
            break
    if header_idx is None:
        header_idx = 11  # documented layout of the JUL 2026 file

    index = {}
    for r in rows[header_idx + 1:]:
        if not r or r[0] is None:
            continue
        vals = [clean_text(v) for v in (list(r) + [None] * 14)[:14]]
        rec = dict(zip(HHSAR_HEADER, vals))
        raw = rec["number_raw"]
        number = extract_clause_number(raw)
        if not number:
            continue
        alternate = extract_alternate(raw) or extract_alternate(rec["title"])
        upper_label = (raw + " " + rec["title"]).upper()
        rec.update({
            "number": number,
            "alternate": alternate,
            "date_parsed": normalize_date(rec["date_raw"]),
            "dev_kind": deviation_kind(rec["date_raw"], rec["class_dev"]),
            "do_not_use": "DO NOT USE" in upper_label,
            "reserved_flag": "RESERVED" in upper_label,
            "status": rec["status"] or "",
            "part": far_part(number),
        })
        index.setdefault(number, []).append(rec)
    return index


def pick_hhsar_entry(entries, alternate):
    """
    Choose the best HHSAR entry for a lookup.
    Preference: exact alternate match; else the non-alternate entry;
    Active entries beat Reserved/Removed at the same specificity;
    else the first entry.
    """
    def rank(e):
        alt_match = 0 if (e["alternate"] or None) == (alternate or None) else 1
        active = 0 if e["status"] == "Active" else 1
        return (alt_match, active)
    return sorted(entries, key=rank)[0]


# ---------------------------------------------------------------------------
# User clause-list parsing
# ---------------------------------------------------------------------------

def parse_clause_list(source):
    """
    Parse the user's clause list from a file path or an inline string.
    File: one clause per line ("#" comments allowed).
    Inline: entries separated by ";" or newlines.

    Each entry yields: {raw, number, alternate, date_raw, date_parsed,
                        cites_deviation, family}
    family: "FAR" (52.x), "HHSAR" (352.x), or "other".
    """
    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8-sig") as f:
            text = f.read()
        pieces = text.splitlines()
    else:
        pieces = re.split(r"[;\n]+", source)

    items = []
    for piece in pieces:
        raw = piece.strip()
        if not raw or raw.startswith("#"):
            continue
        number = extract_clause_number(raw)
        remainder = raw
        if number:
            remainder = CLAUSE_NUM_RE.sub(" ", raw, count=1)
        date_parsed = normalize_date(remainder)
        # Recover the display form of the date from the remainder
        date_raw = ""
        m = re.search(r"([A-Za-z]{3,9}\W*\d{4}|\d{1,2}\W+[A-Za-z]{3}\W+\d{2}\b)",
                      clean_text(remainder))
        if m and date_parsed:
            date_raw = m.group(1).strip()
        family = "other"
        if number:
            if number.startswith("52."):
                family = "FAR"
            elif number.startswith("352."):
                family = "HHSAR"
        items.append({
            "raw": raw,
            "number": number,
            "alternate": extract_alternate(remainder),
            "date_raw": date_raw,
            "date_parsed": date_parsed,
            "cites_deviation": "deviation" in remainder.lower(),
            "family": family,
        })
    return items


# ---------------------------------------------------------------------------
# Check mode
# ---------------------------------------------------------------------------

def check_far_clause(item, far_index, small_biz):
    """Validate one FAR 52.x clause from the user's list."""
    finding = {
        "clause_number": item["number"],
        "family": "FAR",
        "alternate": alt_label(item["alternate"]),
        "user_date": item["date_raw"] or "(none)",
        "status": "valid",
        "title": "",
        "matrix_date": "",
        "prescribed_in": "",
        "p_or_c": "",
        "findings": [],
    }
    slot = far_index.get(item["number"])
    if not slot:
        finding["status"] = "not_found"
        finding["findings"].append({
            "severity": "CRITICAL",
            "check": "Not in FAR Matrix",
            "detail": (f"{item['number']} is not in the current Smart Matrix FAR baseline. "
                       "Verify the number; the clause may have been removed or reserved "
                       "in the restructured FAR, or it may be agency-unique."),
        })
        return finding

    entry = slot["base"]
    if item["alternate"]:
        entry = slot["alternates"].get(item["alternate"])
        if entry is None:
            finding["status"] = "review"
            finding["findings"].append({
                "severity": "WARNING",
                "check": "Alternate Not Found",
                "detail": (f"{alt_label(item['alternate'])} of {item['number']} is not in the "
                           f"Smart Matrix. Known alternates: "
                           f"{[alt_label(a) for a in sorted(slot['alternates'])] or 'none'}."),
            })
            entry = slot["base"]
    if entry is None:
        # Alternate rows exist but no base row (not observed in current data)
        entry = next(iter(slot["alternates"].values()))

    base_title = slot["base"]["title"] if slot["base"] else entry["title"]
    finding["title"] = base_title
    finding["matrix_date"] = entry["date_raw"]
    finding["prescribed_in"] = entry["prescribed_in"]
    finding["p_or_c"] = entry["p_or_c"]

    # Date currency
    user_d, matrix_d = item["date_parsed"], entry["date_parsed"]
    if user_d is None:
        if finding["status"] == "valid":
            finding["status"] = "review"
        finding["findings"].append({
            "severity": "WARNING",
            "check": "No Date Provided",
            "detail": (f"No date given for {item['number']}. Current effective date is "
                       f"{fmt_date(matrix_d, entry['date_raw'])}. Verify the version in use."),
        })
    elif matrix_d is None:
        finding["status"] = "review"
        finding["findings"].append({
            "severity": "WARNING",
            "check": "Matrix Date Unparseable",
            "detail": f"Matrix date '{entry['date_raw']}' could not be parsed; compare manually.",
        })
    elif date_gte(user_d, matrix_d):
        finding["findings"].append({
            "severity": "INFO",
            "check": "Date Current",
            "detail": (f"User date {fmt_date(user_d, item['date_raw'])} matches or is newer than "
                       f"the matrix effective date {fmt_date(matrix_d, entry['date_raw'])}."),
        })
    else:
        finding["status"] = "action_needed"
        finding["findings"].append({
            "severity": "CRITICAL",
            "check": "Date Mismatch",
            "detail": (f"User date {fmt_date(user_d, item['date_raw'])} is older than the current "
                       f"effective date {fmt_date(matrix_d, entry['date_raw'])}. "
                       "Update to the current version."),
        })

    # Set-aside fit (Part 19 only)
    verdict, reason = setaside_verdict(item["number"], small_biz)
    if verdict == "excluded":
        if finding["status"] == "valid":
            finding["status"] = "review"
        finding["findings"].append({
            "severity": "WARNING",
            "check": "Set-Aside Mismatch",
            "detail": f"{reason}. Remove the clause or verify the set-aside.",
        })
    elif reason:
        finding["findings"].append({
            "severity": "INFO",
            "check": "Set-Aside",
            "detail": reason,
        })
    return finding


def check_hhsar_clause(item, hhsar_index, contract_type, over_sat, commercial):
    """Validate one HHSAR 352.x clause from the user's list."""
    finding = {
        "clause_number": item["number"],
        "family": "HHSAR",
        "alternate": alt_label(item["alternate"]),
        "user_date": item["date_raw"] or "(none)",
        "status": "valid",
        "title": "",
        "matrix_date": "",
        "hhsar_status": "",
        "class_deviation": "",
        "ibr": "",
        "ucf": "",
        "applicability": "",
        "findings": [],
    }
    entries = hhsar_index.get(item["number"])
    if not entries:
        finding["status"] = "not_found"
        finding["findings"].append({
            "severity": "CRITICAL",
            "check": "Not in HHSAR Matrix",
            "detail": (f"{item['number']} is not in the JUL 2026 HHSAR deviation matrix. "
                       "Verify the number and whether the clause still exists."),
        })
        return finding

    e = pick_hhsar_entry(entries, item["alternate"])
    finding["title"] = e["title"]
    finding["matrix_date"] = e["date_raw"]
    finding["hhsar_status"] = e["status"]
    finding["class_deviation"] = e["class_dev_number"] if e["class_dev"] == "Y" else ""
    finding["ibr"] = e["ibr"]
    finding["ucf"] = e["ucf"]
    finding["applicability"] = e["applicability"]

    # Status: Removed / Reserved are do-not-use
    if e["status"] == "Removed" or e["do_not_use"]:
        finding["status"] = "removed"
        cd = f" (see {e['class_dev_number']})" if e["class_dev_number"] else ""
        kind = f"; {e['dev_kind']}" if e["dev_kind"] else ""
        finding["findings"].append({
            "severity": "CRITICAL",
            "check": "Removed Clause",
            "detail": (f"HHSAR marks this clause DO NOT USE OR ENFORCE{cd}"
                       f"{kind}, dated {fmt_date(e['date_parsed'], e['date_raw'])}. "
                       "Do not include or enforce it."),
        })
        return finding
    if e["status"] == "Reserved" or e["reserved_flag"]:
        finding["status"] = "removed"
        cd = f" under {e['class_dev_number']}" if e["class_dev_number"] else ""
        finding["findings"].append({
            "severity": "CRITICAL",
            "check": "Reserved Clause",
            "detail": (f"This clause is RESERVED{cd}, dated "
                       f"{fmt_date(e['date_parsed'], e['date_raw'])}. "
                       "Do not include it in new solicitations or contracts."),
        })
        return finding

    # Deviation / version currency
    user_d, hhsar_d = item["date_parsed"], e["date_parsed"]
    is_deviation = e["class_dev"] == "Y"
    version_desc = (f"class deviation {e['class_dev_number']}".strip()
                    if is_deviation and e["class_dev_number"]
                    else ("current deviation" if is_deviation else "current HHSAR version"))
    if user_d is None:
        finding["status"] = "review"
        finding["findings"].append({
            "severity": "WARNING",
            "check": "No Date Provided",
            "detail": (f"No date given. The {version_desc} is dated "
                       f"{fmt_date(hhsar_d, e['date_raw'])}. Verify the version in use."),
        })
    elif hhsar_d is None:
        finding["status"] = "review"
        finding["findings"].append({
            "severity": "WARNING",
            "check": "Matrix Date Unparseable",
            "detail": f"HHSAR date '{e['date_raw']}' could not be parsed; compare manually.",
        })
    elif date_gte(user_d, hhsar_d):
        finding["findings"].append({
            "severity": "INFO",
            "check": "Date Current",
            "detail": (f"User date {fmt_date(user_d, item['date_raw'])} matches or is newer than "
                       f"the {version_desc} dated {fmt_date(hhsar_d, e['date_raw'])}."),
        })
    else:
        finding["status"] = "action_needed"
        finding["findings"].append({
            "severity": "CRITICAL",
            "check": "Date Mismatch",
            "detail": (f"User date {fmt_date(user_d, item['date_raw'])} is older than the "
                       f"{version_desc} dated {fmt_date(hhsar_d, e['date_raw'])}. "
                       "Update to the current version."),
        })

    # User cites a deviation the HHSAR matrix does not show
    if item["cites_deviation"] and not is_deviation:
        if finding["status"] == "valid":
            finding["status"] = "review"
        finding["findings"].append({
            "severity": "WARNING",
            "check": "Verify Deviation Source",
            "detail": ("The clause list cites a deviation, but the HHSAR matrix shows no "
                       "class deviation for this clause. Verify the deviation source and authority."),
        })
    # HHSAR shows a deviation the user did not cite (informational nudge)
    if is_deviation and not item["cites_deviation"] and finding["status"] == "valid":
        finding["findings"].append({
            "severity": "INFO",
            "check": "Cite the Deviation",
            "detail": (f"This clause is issued under {version_desc} "
                       f"({e['dev_kind'] or 'deviation'}). Cite it accordingly."),
        })

    # IBR
    if e["ibr"] == "No":
        finding["findings"].append({
            "severity": "WARNING",
            "check": "Full Text Required",
            "detail": "Not authorized for incorporation by reference. Include the full text.",
        })
    # PCO fill-in
    if e["pco_fill_in"] == "Yes":
        finding["findings"].append({
            "severity": "INFO",
            "check": "PCO Fill-In",
            "detail": "This clause contains contracting officer fill-ins. Verify they are completed.",
        })

    # Applicability fit
    fit, requirement, reason = map_hhsar_applicability(
        e["applicability"], contract_type, over_sat, commercial)
    if fit is False:
        if finding["status"] == "valid":
            finding["status"] = "review"
        finding["findings"].append({
            "severity": "WARNING",
            "check": "Applicability Mismatch",
            "detail": (f"HHSAR applicability is '{e['applicability']}': {reason}. "
                       "Verify this clause belongs in this action."),
        })
    elif fit is None:
        finding["findings"].append({
            "severity": "INFO",
            "check": "Applicability",
            "detail": reason,
        })
    else:
        finding["findings"].append({
            "severity": "INFO",
            "check": "Applicability",
            "detail": f"{reason} ({e['applicability']}).",
        })
    return finding


def missing_required_hhsar(items, hhsar_index, contract_type, over_sat, commercial):
    """Active HHSAR clauses whose R-* code fits this action but are absent from the list."""
    listed = {i["number"] for i in items if i["family"] == "HHSAR" and i["number"]}
    missing = []
    for number, entries in sorted(hhsar_index.items()):
        active = [e for e in entries
                  if e["status"] == "Active" and not e["alternate"]
                  and not e["do_not_use"] and not e["reserved_flag"]]
        if not active:
            continue
        e = active[0]
        fit, requirement, reason = map_hhsar_applicability(
            e["applicability"], contract_type, over_sat, commercial)
        if fit and requirement == "required" and number not in listed:
            missing.append({
                "clause_number": number,
                "title": e["title"],
                "date": e["date_raw"],
                "applicability": e["applicability"],
                "class_deviation": e["class_dev_number"] if e["class_dev"] == "Y" else "",
                "reason": reason,
            })
    return missing


def missing_setaside_clauses(items, far_index, small_biz):
    """Expected 52.219 clauses for this set-aside that are absent from the list."""
    listed = {i["number"] for i in items if i["family"] == "FAR" and i["number"]}
    missing = []
    for number in sorted(expected_setaside_clauses(small_biz)):
        if number in listed:
            continue
        slot = far_index.get(number)
        entry = slot["base"] if slot and slot["base"] else None
        _, reason = setaside_verdict(number, small_biz)
        missing.append({
            "clause_number": number,
            "title": entry["title"] if entry else "",
            "date": entry["date_raw"] if entry else "",
            "reason": reason or "Expected for this set-aside",
        })
    return missing


def run_check_mode(items, far_index, hhsar_index, params):
    results = []
    for item in items:
        if not item["number"]:
            results.append({
                "clause_number": "",
                "family": "other",
                "raw": item["raw"],
                "status": "review",
                "findings": [{
                    "severity": "WARNING",
                    "check": "Unparseable Entry",
                    "detail": f"Could not find a clause number in: '{item['raw']}'.",
                }],
            })
        elif item["family"] == "FAR":
            results.append(check_far_clause(item, far_index, params["small_biz"]))
        elif item["family"] == "HHSAR":
            results.append(check_hhsar_clause(
                item, hhsar_index, params["contract_type"],
                params["over_sat"], params["commercial"]))
        else:
            results.append({
                "clause_number": item["number"],
                "family": "other",
                "raw": item["raw"],
                "status": "review",
                "findings": [{
                    "severity": "WARNING",
                    "check": "Out of Scope",
                    "detail": (f"{item['number']} is neither a FAR 52.x nor an HHSAR 352.x "
                               "clause. DFARS and other supplements are out of scope."),
                }],
            })
    return results


# ---------------------------------------------------------------------------
# Checklist mode
# ---------------------------------------------------------------------------

def run_checklist_mode(far_index, hhsar_index, params):
    """HHSAR required / as-applicable checklist plus a FAR inventory by part."""
    required, as_applicable, not_applicable, review = [], [], [], []
    for number, entries in sorted(hhsar_index.items()):
        active = [e for e in entries
                  if e["status"] == "Active" and not e["do_not_use"]
                  and not e["reserved_flag"]]
        base_active = [e for e in active if not e["alternate"]]
        if not active:
            continue
        e = (base_active or active)[0]
        fit, requirement, reason = map_hhsar_applicability(
            e["applicability"], params["contract_type"],
            params["over_sat"], params["commercial"])
        row = {
            "clause_number": number,
            "title": e["title"],
            "date": e["date_raw"],
            "p_or_c": e["p_or_c"],
            "ibr": e["ibr"],
            "pco_fill_in": e["pco_fill_in"],
            "ucf": e["ucf"],
            "applicability": e["applicability"],
            "class_deviation": e["class_dev_number"] if e["class_dev"] == "Y" else "",
            "deviation_kind": e["dev_kind"],
            "reason": reason,
            "prescription_excerpt": e["prescription"][:300],
            "alternates": [alt_label(a["alternate"]) for a in active if a["alternate"]],
        }
        if fit is None:
            review.append(row)
        elif not fit:
            not_applicable.append(row)
        elif requirement == "required":
            required.append(row)
        else:
            as_applicable.append(row)

    far_inventory = []
    parts = params["parts"]
    if parts != ["all"]:
        for number, slot in sorted(far_index.items()):
            entry = slot["base"] or next(iter(slot["alternates"].values()))
            if entry["part"] not in parts:
                continue
            verdict, reason = setaside_verdict(number, params["small_biz"])
            far_inventory.append({
                "clause_number": number,
                "title": entry["title"],
                "date": entry["date_raw"],
                "p_or_c": entry["p_or_c"],
                "prescribed_in": entry["prescribed_in"],
                "alternates": [alt_label(a) for a in sorted(slot["alternates"])],
                "setaside_verdict": verdict,
                "setaside_reason": reason,
            })

    return {
        "hhsar_required": required,
        "hhsar_as_applicable": as_applicable,
        "hhsar_not_applicable": not_applicable,
        "hhsar_review": review,
        "far_inventory": far_inventory,
        "far_inventory_note": ("FAR inventory included for parts "
                               f"{', '.join(parts)}. The Smart Matrix has no "
                               "applicability grid, so review each clause's "
                               "'Prescribed In' reference to confirm applicability."
                               if parts != ["all"] else
                               "Pass --parts to include a FAR clause inventory. "
                               "The Smart Matrix has no applicability grid, so "
                               "FAR applicability must come from the prescriptions."),
    }


# ---------------------------------------------------------------------------
# Summary and main
# ---------------------------------------------------------------------------

def generate_summary(results):
    def count(status):
        return sum(1 for r in results if r["status"] == status)
    return {
        "total_checked": len(results),
        "far_clauses": sum(1 for r in results if r.get("family") == "FAR"),
        "hhsar_clauses": sum(1 for r in results if r.get("family") == "HHSAR"),
        "valid_no_action": count("valid"),
        "action_needed_date_mismatch": count("action_needed"),
        "review": count("review"),
        "removed_or_reserved": count("removed"),
        "not_found": count("not_found"),
        "critical_findings": sum(
            1 for r in results
            if any(f["severity"] == "CRITICAL" for f in r["findings"])),
        "warnings": sum(
            1 for r in results
            if any(f["severity"] == "WARNING" for f in r["findings"])),
    }


def main():
    parser = argparse.ArgumentParser(
        description="FAR Clause Checker v3 - Smart Matrix + HHSAR JUL 2026")
    parser.add_argument("--clauses", default=None,
                        help="Clause-list file path or inline ';'-separated list. "
                             "If omitted, runs checklist mode.")
    parser.add_argument("--contract-type", default="FFP",
                        choices=["FFP", "FFP_LOE", "COST", "TM"])
    parser.add_argument("--over-sat", default="yes", choices=["yes", "no"],
                        help="Over the simplified acquisition threshold "
                             "('no' also covers simplified acquisitions)")
    parser.add_argument("--commercial", default="no", choices=["yes", "no"])
    parser.add_argument("--small-biz", default="NONE",
                        help="NONE | SB | 8A | HUBZONE | SDVOSB | WOSB")
    parser.add_argument("--parts", default="all",
                        help="Comma-separated FAR part numbers, or 'all'")
    parser.add_argument("--output", default="report.json")
    parser.add_argument("--data-dir", default=None,
                        help="Directory with the data files or a references/ subdir")
    # Retired v2 arguments, accepted so old invocations fail soft
    parser.add_argument("--purpose", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--method", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.purpose or args.method:
        print("NOTE: --purpose and --method are ignored in v3. The Smart Matrix "
              "has no applicability grid; FAR applicability comes from the "
              "prescriptions, and HHSAR applicability from the coded column.")

    # Locate data
    data_dir = args.data_dir or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir)
    refs_dir = os.path.join(data_dir, "references")
    search_dir = refs_dir if os.path.isdir(refs_dir) else data_dir
    csv_file, xlsx_file = find_data_files(search_dir)
    if not csv_file:
        print("ERROR: Could not find the Smart Matrix CSV in", search_dir)
        sys.exit(1)
    if not xlsx_file:
        print("ERROR: Could not find the HHSAR deviations XLSX in", search_dir)
        sys.exit(1)

    print(f"Loading Smart Matrix (FAR) from: {csv_file}")
    far_index = load_smart_matrix(csv_file)
    n_alts = sum(len(s["alternates"]) for s in far_index.values())
    print(f"  Loaded {len(far_index)} FAR clause numbers ({n_alts} alternates)")

    print(f"Loading HHSAR deviations from: {xlsx_file}")
    hhsar_index = load_hhsar_matrix(xlsx_file)
    n_entries = sum(len(v) for v in hhsar_index.values())
    print(f"  Loaded {len(hhsar_index)} HHSAR clause numbers ({n_entries} rows)")

    params = {
        "contract_type": args.contract_type,
        "over_sat": args.over_sat == "yes",
        "commercial": args.commercial == "yes",
        "small_biz": args.small_biz.upper(),
        "parts": ([p.strip() for p in args.parts.split(",")]
                  if args.parts.lower() != "all" else ["all"]),
    }
    print("\nParameters:", json.dumps(params))

    if args.clauses:
        items = parse_clause_list(args.clauses)
        print(f"Parsed {len(items)} clause-list entries")
        results = run_check_mode(items, far_index, hhsar_index, params)
        summary = generate_summary(results)
        output = {
            "mode": "check",
            "parameters": params,
            "summary": summary,
            "results": results,
            "missing_required_hhsar": missing_required_hhsar(
                items, hhsar_index, params["contract_type"],
                params["over_sat"], params["commercial"]),
            "missing_setaside_clauses": missing_setaside_clauses(
                items, far_index, params["small_biz"]),
        }
        print("\nSummary:")
        for k, v in summary.items():
            print(f"  {k}: {v}")
        print(f"  missing required HHSAR: {len(output['missing_required_hhsar'])}")
        print(f"  missing set-aside clauses: {len(output['missing_setaside_clauses'])}")
    else:
        checklist = run_checklist_mode(far_index, hhsar_index, params)
        output = {"mode": "checklist", "parameters": params, **checklist}
        print("\nChecklist:")
        print(f"  HHSAR required: {len(checklist['hhsar_required'])}")
        print(f"  HHSAR as applicable: {len(checklist['hhsar_as_applicable'])}")
        print(f"  HHSAR not applicable to this action: {len(checklist['hhsar_not_applicable'])}")
        print(f"  HHSAR review (unknown code): {len(checklist['hhsar_review'])}")
        print(f"  FAR inventory rows: {len(checklist['far_inventory'])}")

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
