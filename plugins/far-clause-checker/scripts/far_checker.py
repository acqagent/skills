#!/usr/bin/env python3
"""FAR Clause Checker v4: FAR 52.2xx only, against the acquisition.gov (GSA) Smart Matrix CSV.
Standard library only.
  check mode (--clauses given): existence, alternate, date currency, Part 19 set-aside fit,
                                and missing set-aside clauses.
  checklist mode (no --clauses): expected set-aside clauses plus a FAR inventory for --parts.
"""
import argparse, csv, json, os, re, sys

MONTHS = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
NAMES = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
NUM_RE = re.compile(r"(\d{2,3}\.\d{3})[.-](\d+[A-Za-z]?)")
# (?<![A-Za-z]) instead of \b: "52.203-6_Alternate I" puts "_" (a word char) before "Alternate"
ALT_RE = re.compile(r"(?<![A-Za-z])ALT(?:ERNATE)?[\s._-]*([IVX]+|\d+)\b", re.I)
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
ROMAN_OUT = {v: k.upper() for k, v in ROMAN.items()}

# FAR Part 19 set-aside rules (hand-maintained; verify against Part 19 prescriptions)
ALWAYS = {"52.219-1", "52.219-8", "52.219-28"}
SPECIFIC = {"52.219-3": {"HUBZONE"}, "52.219-4": {"HUBZONE"}, "52.219-6": {"SB"},
            "52.219-7": {"SB"}, "52.219-17": {"8A"}, "52.219-18": {"8A"},
            "52.219-27": {"SDVOSB"}, "52.219-29": {"WOSB"}, "52.219-30": {"WOSB"}}
ANY_SETASIDE = {"52.219-14"}
NONE_ONLY = {"52.219-9", "52.219-16"}
SET_ASIDES = ["NONE", "SB", "8A", "HUBZONE", "SDVOSB", "WOSB"]


def clean(v):
    s = "" if v is None else str(v)
    s = s.replace("<br>", " ").replace(" ", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def clause_num(text):
    m = NUM_RE.search(str(text))
    return f"{m.group(1)}-{m.group(2)}" if m else None


def alternate(text):
    m = ALT_RE.search(str(text))
    if not m:
        return None
    t = m.group(1).lower()
    return int(t) if t.isdigit() else ROMAN.get(t)


def alt_label(a):
    return f"Alternate {ROMAN_OUT.get(a, a)}" if a else ""


def parse_date(s):
    """(month, year) from 'MAY 2014', 'June 2010', 'Oct  2020', '2-Jun-25'; else None."""
    s = clean(s)
    for m in re.finditer(r"([A-Za-z]{3})[A-Za-z]*\W*(\d{4})", s):
        if m.group(1).lower() in MONTHS:
            return (MONTHS[m.group(1).lower()], int(m.group(2)))
    m = re.search(r"(\d{1,2})\W+([A-Za-z]{3})\W+(\d{2})\b", s)
    if m and m.group(2).lower() in MONTHS:
        yy = int(m.group(3))
        return (MONTHS[m.group(2).lower()], 2000 + yy if yy < 80 else 1900 + yy)
    return None


def newer_or_equal(a, b):
    return (a[1], a[0]) >= (b[1], b[0])


def show(parsed, raw):
    return clean(raw) if raw else (f"{NAMES[parsed[0]]} {parsed[1]}" if parsed else "(no date)")


def far_part(n):
    m = re.match(r"52\.(\d)(\d{2})-", n or "")
    return str(int(m.group(2))) if m else None


def setaside_verdict(n, sb):
    if n in ALWAYS:
        return "ok", "Universal Part 19 clause (applies regardless of set-aside)"
    if n in SPECIFIC:
        if sb in SPECIFIC[n]:
            return "ok", f"Matches {sb} set-aside"
        return "excluded", f"Requires set-aside in {sorted(SPECIFIC[n])}; action is {sb}"
    if n in ANY_SETASIDE:
        return (("ok", f"Applies under {sb} small business set-aside") if sb != "NONE"
                else ("excluded", "Requires a small business set-aside; action has none"))
    if n in NONE_ONLY:
        return (("ok", "Large-business prime clause (no set-aside on action)") if sb == "NONE"
                else ("excluded", "Not used under a small business set-aside"))
    return "ok", ""


def expected_setaside(sb):
    exp = set(ALWAYS) | {n for n, req in SPECIFIC.items() if sb in req}
    return exp | (ANY_SETASIDE if sb != "NONE" else NONE_ONLY)


def load_matrix(path):
    """number -> {"base": entry|None, "alternates": {int: entry}}"""
    idx = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            label = clean(row.get("Provision or Clause (P or C)"))
            n = clause_num(label)
            if not n:
                continue
            a = alternate(label)
            title = re.sub(r"^[\s._-]+", "", NUM_RE.sub("", label, count=1)).strip()
            date_raw = clean(row.get("Effective Date"))
            # GSA data has stray commas ("42.709-7,") and one blank reference (",")
            presc = clean(row.get("Prescribed In")).strip(" ,;") or "not listed"
            e = {"number": n, "alternate": a, "title": alt_label(a) if a else title,
                 "date_raw": date_raw, "date": parse_date(date_raw),
                 "prescribed_in": presc,
                 "p_or_c": clean(row.get("P or C")).upper(), "part": far_part(n)}
            slot = idx.setdefault(n, {"base": None, "alternates": {}})
            if a:
                slot["alternates"][a] = e
            else:
                slot["base"] = e
    return idx


def parse_list(source):
    if os.path.isfile(source):
        with open(source, encoding="utf-8-sig") as f:
            pieces = f.read().splitlines()
    else:
        pieces = re.split(r"[;\n]+", source)
    items = []
    for p in pieces:
        raw = p.strip()
        if not raw or raw.startswith("#"):
            continue
        n = clause_num(raw)
        rest = NUM_RE.sub(" ", raw, count=1) if n else raw
        d = parse_date(rest)
        m = re.search(r"([A-Za-z]{3,9}\W*\d{4}|\d{1,2}\W+[A-Za-z]{3}\W+\d{2}\b)", clean(rest))
        fam = "FAR" if n and n.startswith("52.") else ("other" if n else "unparseable")
        items.append({"raw": raw, "number": n, "alternate": alternate(rest),
                      "date_raw": m.group(1).strip() if (m and d) else "", "date": d,
                      "family": fam})
    return items


def finding(sev, check, detail):
    return {"severity": sev, "check": check, "detail": detail}


def check_far(item, idx, sb):
    r = {"clause_number": item["number"], "family": "FAR", "alternate": alt_label(item["alternate"]),
         "user_date": item["date_raw"] or "(none)", "status": "valid", "title": "",
         "matrix_date": "", "prescribed_in": "", "p_or_c": "", "findings": []}
    slot = idx.get(item["number"])
    if not slot:
        r["status"] = "not_found"
        r["findings"].append(finding("CRITICAL", "Not in FAR Matrix",
            f"{item['number']} is not in the current Smart Matrix FAR baseline. Verify the number; "
            "the clause may have been removed or reserved in the restructured FAR, or it may be "
            "agency-unique."))
        return r
    e = slot["base"]
    if item["alternate"]:
        e = slot["alternates"].get(item["alternate"])
        if e is None:
            r["status"] = "review"
            known = [alt_label(a) for a in sorted(slot["alternates"])] or "none"
            r["findings"].append(finding("WARNING", "Alternate Not Found",
                f"{alt_label(item['alternate'])} of {item['number']} is not in the Smart Matrix. "
                f"Known alternates: {known}."))
            e = slot["base"]
    e = e or next(iter(slot["alternates"].values()))
    r.update(title=(slot["base"] or e)["title"], matrix_date=e["date_raw"],
             prescribed_in=e["prescribed_in"], p_or_c=e["p_or_c"])
    ud, md = item["date"], e["date"]
    if ud is None:
        r["status"] = "review" if r["status"] == "valid" else r["status"]
        r["findings"].append(finding("WARNING", "No Date Provided",
            f"No date given for {item['number']}. Current effective date is "
            f"{show(md, e['date_raw'])}. Verify the version in use."))
    elif md is None:
        r["status"] = "review"
        r["findings"].append(finding("WARNING", "Matrix Date Unparseable",
            f"Matrix date '{e['date_raw']}' could not be parsed; compare manually."))
    elif newer_or_equal(ud, md):
        r["findings"].append(finding("INFO", "Date Current",
            f"User date {show(ud, item['date_raw'])} matches or is newer than the matrix "
            f"effective date {show(md, e['date_raw'])}."))
    else:
        r["status"] = "action_needed"
        r["findings"].append(finding("CRITICAL", "Date Mismatch",
            f"User date {show(ud, item['date_raw'])} is older than the current effective date "
            f"{show(md, e['date_raw'])}. Update to the current version."))
    verdict, reason = setaside_verdict(item["number"], sb)
    if verdict == "excluded":
        r["status"] = "review" if r["status"] == "valid" else r["status"]
        r["findings"].append(finding("WARNING", "Set-Aside Mismatch",
            f"{reason}. Remove the clause or verify the set-aside."))
    elif reason:
        r["findings"].append(finding("INFO", "Set-Aside", reason))
    return r


def check_other(item):
    if item["family"] == "unparseable":
        return {"clause_number": "", "family": "other", "raw": item["raw"], "status": "review",
                "findings": [finding("WARNING", "Unparseable Entry",
                    f"Could not find a clause number in: '{item['raw']}'.")]}
    return {"clause_number": item["number"], "family": "other", "raw": item["raw"],
            "status": "review", "findings": [finding("WARNING", "Out of Scope",
                f"{item['number']} is not a FAR 52.x provision or clause. Agency supplements "
                "(HHSAR 352.x, DFARS 252.x, and others) are out of scope for this checker.")]}


def missing_setaside(items, idx, sb):
    listed = {i["number"] for i in items if i["family"] == "FAR"}
    out = []
    for n in sorted(expected_setaside(sb)):
        if n in listed:
            continue
        b = (idx.get(n) or {}).get("base")
        out.append({"clause_number": n, "title": b["title"] if b else "",
                    "date": b["date_raw"] if b else "",
                    "reason": setaside_verdict(n, sb)[1] or "Expected for this set-aside"})
    return out


def summarize(results):
    c = lambda s: sum(1 for r in results if r["status"] == s)
    has = lambda sev: sum(1 for r in results if any(f["severity"] == sev for f in r["findings"]))
    return {"total_checked": len(results),
            "far_clauses": sum(1 for r in results if r["family"] == "FAR"),
            "out_of_scope_or_unparseable": sum(1 for r in results if r["family"] == "other"),
            "valid_no_action": c("valid"), "action_needed_date_mismatch": c("action_needed"),
            "review": c("review"), "not_found": c("not_found"),
            "critical_findings": has("CRITICAL"), "warnings": has("WARNING")}


def checklist(idx, sb, parts):
    expected = []
    for n in sorted(expected_setaside(sb)):
        b = (idx.get(n) or {}).get("base")
        expected.append({"clause_number": n, "title": b["title"] if b else "(not in matrix)",
                         "date": b["date_raw"] if b else "",
                         "prescribed_in": b["prescribed_in"] if b else "",
                         "reason": setaside_verdict(n, sb)[1]})
    inv = []
    if parts != ["all"]:
        for n, slot in sorted(idx.items()):
            e = slot["base"] or next(iter(slot["alternates"].values()))
            if e["part"] not in parts:
                continue
            v, why = setaside_verdict(n, sb)
            inv.append({"clause_number": n, "title": e["title"], "date": e["date_raw"],
                        "p_or_c": e["p_or_c"], "prescribed_in": e["prescribed_in"],
                        "alternates": [alt_label(a) for a in sorted(slot["alternates"])],
                        "setaside_verdict": v, "setaside_reason": why})
    note = (f"FAR inventory for parts {', '.join(parts)}. The Smart Matrix has no applicability "
            "grid; confirm each clause against its 'Prescribed In' reference." if parts != ["all"]
            else "No --parts given, so no FAR inventory. Ask the user which FAR parts to list.")
    return {"expected_setaside_clauses": expected, "far_inventory": inv, "far_inventory_note": note}


def main():
    ap = argparse.ArgumentParser(description="FAR Clause Checker v4 (Smart Matrix only)")
    ap.add_argument("--matrix", help="Path to the Smart Matrix CSV (default: the .csv in "
                                     "references/ next to this script's folder)")
    ap.add_argument("--clauses", help="Clause-list file or inline ';'-separated list")
    ap.add_argument("--small-biz", default="NONE", type=str.upper, choices=SET_ASIDES)
    ap.add_argument("--parts", default="all", help="Comma-separated FAR parts, or 'all'")
    ap.add_argument("--output", default="report.json")
    for old in ("--contract-type", "--over-sat", "--commercial", "--purpose", "--method"):
        ap.add_argument(old, default=None, help=argparse.SUPPRESS)  # retired; fail soft
    a = ap.parse_args()
    retired = [o for o in ("contract_type", "over_sat", "commercial", "purpose", "method")
               if getattr(a, o)]
    if retired:
        print(f"NOTE: ignoring retired arguments {retired}; they only drove HHSAR or the old "
              "DAU grid. FAR applicability comes from each clause's prescription.")
    if not a.matrix:
        refs = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "references")
        csvs = sorted(f for f in os.listdir(refs) if f.lower().endswith(".csv")) \
            if os.path.isdir(refs) else []
        if not csvs:
            sys.exit("ERROR: pass --matrix with the path to the Smart Matrix CSV")
        a.matrix = os.path.normpath(os.path.join(refs, csvs[0]))
    if not os.path.isfile(a.matrix):
        sys.exit(f"ERROR: Smart Matrix CSV not found at {a.matrix}")
    idx = load_matrix(a.matrix)
    print(f"Loaded {len(idx)} FAR clause numbers "
          f"({sum(len(s['alternates']) for s in idx.values())} alternates) from {a.matrix}")
    parts = [p.strip() for p in a.parts.split(",")] if a.parts.lower() != "all" else ["all"]
    params = {"small_biz": a.small_biz, "parts": parts}
    if a.clauses:
        items = parse_list(a.clauses)
        results = [check_far(i, idx, a.small_biz) if i["family"] == "FAR" else check_other(i)
                   for i in items]
        out = {"mode": "check", "parameters": params, "summary": summarize(results),
               "results": results, "missing_setaside_clauses": missing_setaside(items, idx, a.small_biz)}
        print(json.dumps(out["summary"], indent=2))
        print(f"missing set-aside clauses: {len(out['missing_setaside_clauses'])}")
    else:
        out = {"mode": "checklist", "parameters": params, **checklist(idx, a.small_biz, parts)}
        print(f"expected set-aside clauses: {len(out['expected_setaside_clauses'])}; "
              f"FAR inventory rows: {len(out['far_inventory'])}")
    with open(a.output, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Report saved to: {a.output}")


if __name__ == "__main__":
    main()
