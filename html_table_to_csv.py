#!/usr/bin/env python3
"""
Extract all tables from an HTML file and save each as a CSV.
Handles both static <tr>/<td> tables AND tables whose rows are written
dynamically via JavaScript function calls (e.g. the RuneScape server-list
pattern where every row is emitted by a JS helper like:
    e(369, true, 0, "oldschool69", 1191, "United States", "US", "Old School 69");

Strategy
--------
1. Parse static HTML tables with BeautifulSoup as before.
2. For every <script> block in the file:
   a. Extract the JS function signature to learn the parameter names.
   b. Find every call to that function in the file.
   c. Parse the argument list and map names -> values.
   d. Look for d.write(...) calls in the function body to discover which
      parameters become which columns, and in what order.
   If step (d) fails (unknown d.write structure), fall back to emitting all
   named parameters as columns in declaration order.

Output naming
-------------
  - One table  -> <stem>.csv
  - Many tables -> <stem>_table_1.csv, <stem>_table_2.csv, ...

Usage
-----
    python html_tables_to_csv.py input.html
"""

import csv
import re
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing dependency: install it with  pip install beautifulsoup4")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_cell(cell) -> str:
    return cell.get_text(separator=" ", strip=True)


def _parse_js_args(raw: str) -> list:
    """
    Split a raw JS argument string into individual values.
    Handles quoted strings (with escaped quotes) and bare literals.
    Returns each value as a plain Python string.
    """
    args = []
    current = []
    in_str = False
    str_char = None
    i = 0
    while i < len(raw):
        ch = raw[i]
        if in_str:
            if ch == '\\':
                current.append(ch)
                i += 1
                if i < len(raw):
                    current.append(raw[i])
            elif ch == str_char:
                in_str = False
                current.append(ch)
            else:
                current.append(ch)
        else:
            if ch in ('"', "'"):
                in_str = True
                str_char = ch
                current.append(ch)
            elif ch == ',':
                args.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        i += 1
    if current:
        args.append(''.join(current).strip())

    result = []
    for a in args:
        a = a.strip()
        if (a.startswith('"') and a.endswith('"')) or \
           (a.startswith("'") and a.endswith("'")):
            result.append(a[1:-1])
        else:
            result.append(a)
    return result


def _infer_columns_from_body(func_body: str, param_names: list) -> list:
    """
    Scan d.write(...) calls in a JS function body to figure out the column
    order.  Returns an ordered list of column names, or None if we can't tell.
    """
    cols = []
    for m in re.finditer(r'd\.write\((.+?)\)', func_body):
        expr = m.group(1)
        found = [p for p in param_names if re.search(r'\b' + re.escape(p) + r'\b', expr)]
        for f in found:
            if f not in cols:
                cols.append(f)
    return cols if cols else None


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_static_tables(soup) -> list:
    tables = []
    for table_tag in soup.find_all("table"):
        rows = []
        for tr in table_tag.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if cells:
                rows.append([parse_cell(c) for c in cells])
        if rows:
            tables.append(rows)
    return tables


def extract_js_tables(html_text: str, soup) -> list:
    """
    Find JS helper functions that use d.write() to emit <tr> rows, then
    collect every call site to reconstruct the table data.
    """
    tables = []

    for script_tag in soup.find_all("script"):
        script_src = script_tag.string or ""
        if not script_src or "d.write" not in script_src:
            continue

        func_pat = re.compile(
            r'function\s+(\w+)\s*\(([^)]*)\)\s*\{(.+?)\}',
            re.DOTALL
        )
        for func_m in func_pat.finditer(script_src):
            func_name  = func_m.group(1)
            params_raw = func_m.group(2)
            func_body  = func_m.group(3)

            param_names = [p.strip() for p in params_raw.split(',') if p.strip()]
            if not param_names or "d.write" not in func_body:
                continue

            col_order = _infer_columns_from_body(func_body, param_names)
            if col_order is None:
                col_order = param_names

            call_pat = re.compile(
                r'\b' + re.escape(func_name) + r'\s*\(([^)]+)\)\s*;',
                re.DOTALL
            )
            rows = [col_order]
            for call_m in re.finditer(call_pat, html_text):
                values  = _parse_js_args(call_m.group(1))
                arg_map = dict(zip(param_names, values))
                rows.append([arg_map.get(c, "") for c in col_order])

            if len(rows) > 1:
                tables.append(rows)

    return tables


def extract_all_tables(html_path: Path) -> list:
    text = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    return extract_static_tables(soup) + extract_js_tables(text, soup)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: list, out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    html_path = Path(sys.argv[1])
    if not html_path.exists():
        sys.exit(f"Error: file not found — {html_path}")
    if html_path.suffix.lower() not in {".html", ".htm"}:
        print(f"Warning: '{html_path.suffix}' is not a recognised HTML extension, continuing anyway.")

    tables = extract_all_tables(html_path)

    if not tables:
        print("No tables found in the HTML file.")
        sys.exit(0)

    stem    = html_path.stem
    out_dir = html_path.parent

    if len(tables) == 1:
        out_path = out_dir / f"{stem}.csv"
        write_csv(tables[0], out_path)
        print(f"Saved 1 table -> {out_path}")
    else:
        for i, rows in enumerate(tables, start=1):
            out_path = out_dir / f"{stem}_table_{i}.csv"
            write_csv(rows, out_path)
            print(f"Saved table {i:>2} ({len(rows)} rows) -> {out_path}")
        print(f"\n{len(tables)} tables extracted from '{html_path.name}'.")


if __name__ == "__main__":
    main()