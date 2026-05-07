#!/usr/bin/env python3
"""Sync KiCad schematic BOM to Notion Bauteil-Bibliothek database."""

import os
import re
import sys
import json
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests not installed, using urllib")
    import urllib.request
    import urllib.error
    requests = None

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
DATABASE_ID = os.environ.get("NOTION_DB_ID", "359d2e49b98481cab9d9dbb713c3c048")
NOTION_VERSION = "2022-06-28"

# Map lib_id prefixes to component types for Notion
TYPE_MAP = {
    "Device:R": "Widerstand",
    "Device:C": "Kondensator",
    "Device:L": "Induktivität",
    "Device:D": "Diode",
    "Device:LED": "LED",
    "Device:Q_": "Transistor",
    "Transistor": "Transistor",
    "MCU": "Mikrocontroller",
    "Pico": "Mikrocontroller",
    "DRV": "IC / Treiber",
    "PC817": "Optokoppler",
    "L7805": "Spannungsregler",
    "IRF": "MOSFET",
    "1.5KE": "TVS-Diode",
    "1190297": "Steckverbinder",
    "1190298": "Steckverbinder",
}


def guess_type(lib_id: str, value: str) -> str:
    combined = lib_id + " " + value
    for key, t in TYPE_MAP.items():
        if key.lower() in combined.lower():
            return t
    if lib_id.startswith("Device:R"):
        return "Widerstand"
    if lib_id.startswith("Device:C"):
        return "Kondensator"
    if lib_id.startswith("Device:D") or "diode" in lib_id.lower():
        return "Diode"
    return "Sonstiges"


def parse_property(block: str, name: str) -> str:
    pattern = rf'\(property\s+"{re.escape(name)}"\s+"([^"]*)"'
    m = re.search(pattern, block)
    return m.group(1) if m else ""


def parse_schematic(sch_path: Path) -> list[dict]:
    content = sch_path.read_text(encoding="utf-8")

    # Find where lib_symbols ends and placed symbols begin
    lib_end = content.find("\n\t(symbol\n", content.find("(lib_symbols"))
    # Actually find the closing paren of lib_symbols
    # lib_symbols starts around line 7 and ends before the wires/symbols section
    # The placed symbols are at the top indent level: "\t(symbol\n"
    placed_section_start = content.rfind("\n\t(lib_symbols")
    # Skip past lib_symbols block
    depth = 0
    pos = placed_section_start + 1
    for i, ch in enumerate(content[placed_section_start:], placed_section_start):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                pos = i + 1
                break

    placed_content = content[pos:]

    components = []
    # Match each top-level (symbol ...) block
    symbol_pattern = re.compile(r"\n\t\(symbol\b")
    positions = [m.start() for m in symbol_pattern.finditer("\n" + placed_content)]

    for start in positions:
        # Extract the full symbol block by counting parens
        block_start = start + 1  # skip the leading newline
        depth = 0
        end = block_start
        for i, ch in enumerate(placed_content[block_start:], block_start):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        block = placed_content[block_start:end]

        # Skip power symbols and DNP
        if "(dnp yes)" in block:
            continue
        if "(in_bom no)" in block:
            continue

        lib_id_m = re.search(r'\(lib_id\s+"([^"]+)"', block)
        if not lib_id_m:
            continue
        lib_id = lib_id_m.group(1)

        # Skip power/ground symbols
        if lib_id.startswith("power:") or lib_id.startswith("PWR_FLAG"):
            continue

        reference = parse_property(block, "Reference")
        if reference.startswith("#"):
            continue  # Skip hidden power/flag refs

        value = parse_property(block, "Value")
        footprint = parse_property(block, "Footprint")
        description = parse_property(block, "Description")
        mf = parse_property(block, "MF")

        components.append({
            "lib_id": lib_id,
            "reference": reference,
            "value": value,
            "footprint": footprint,
            "description": description,
            "manufacturer": mf,
        })

    return components


def group_bom(components: list[dict]) -> list[dict]:
    """Group components by value+footprint, collect references."""
    groups: dict[str, dict] = {}
    for c in components:
        key = f"{c['value']}|{c['footprint']}"
        if key not in groups:
            groups[key] = {
                "lib_id": c["lib_id"],
                "value": c["value"],
                "footprint": c["footprint"],
                "description": c["description"],
                "manufacturer": c["manufacturer"],
                "references": [],
            }
        groups[key]["references"].append(c["reference"])
    return list(groups.values())


def notion_request(method: str, path: str, data: dict | None = None) -> dict:
    url = f"https://api.notion.com/v1{path}"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    if requests:
        resp = requests.request(method, url, headers=headers,
                                json=data, timeout=30)
        return resp.json()
    else:
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read())


def query_existing(name: str) -> str | None:
    """Return page ID if component with this name exists, else None."""
    result = notion_request("POST", f"/databases/{DATABASE_ID}/query", {
        "filter": {
            "property": "Name",
            "title": {"equals": name}
        },
        "page_size": 1,
    })
    results = result.get("results", [])
    return results[0]["id"] if results else None


def build_page_props(comp: dict) -> dict:
    typ = guess_type(comp["lib_id"], comp["value"])
    package = comp["footprint"].split(":")[-1] if ":" in comp["footprint"] else comp["footprint"]
    refs = ", ".join(sorted(comp["references"]))
    beschreibung = comp["description"] or f"{comp['value']} – {refs}"

    props: dict = {
        "Name": {"title": [{"text": {"content": comp["value"]}}]},
        "Typ": {"select": {"name": typ}},
        "Funktion": {"rich_text": [{"text": {"content": beschreibung[:2000]}}]},
    }
    if package:
        props["Package"] = {"select": {"name": package[:100]}}
    if comp["manufacturer"]:
        props["Hersteller"] = {"rich_text": [{"text": {"content": comp["manufacturer"]}}]}
    return props


def sync_component(comp: dict) -> str:
    name = comp["value"]
    existing_id = query_existing(name)
    props = build_page_props(comp)

    if existing_id:
        notion_request("PATCH", f"/pages/{existing_id}", {"properties": props})
        print(f"  updated: {name}")
        return "updated"
    else:
        notion_request("POST", "/pages", {
            "parent": {"database_id": DATABASE_ID},
            "properties": props,
        })
        print(f"  created: {name}")
        return "created"


def main():
    if not NOTION_TOKEN:
        print("ERROR: NOTION_TOKEN not set")
        sys.exit(1)

    sch_files = list(Path(".").glob("hardware/*.kicad_sch"))
    if not sch_files:
        sch_files = list(Path(".").glob("**/*.kicad_sch"))
    if not sch_files:
        print("No .kicad_sch files found")
        sys.exit(1)

    all_components: list[dict] = []
    for sch in sch_files:
        print(f"Parsing {sch}")
        all_components.extend(parse_schematic(sch))

    bom = group_bom(all_components)
    # Filter out generic passives without proper values
    bom = [c for c in bom if c["value"] not in ("R_Small", "C_Small", "L_Small", "")]

    print(f"\nFound {len(bom)} unique components:")
    for c in bom:
        print(f"  {c['value']} ({', '.join(c['references'])})")

    print(f"\nSyncing to Notion database {DATABASE_ID}...")
    counts = {"created": 0, "updated": 0}
    for comp in bom:
        status = sync_component(comp)
        counts[status] += 1
        time.sleep(0.34)  # stay within Notion rate limit (3 req/s)

    print(f"\nDone: {counts['created']} created, {counts['updated']} updated")


if __name__ == "__main__":
    main()
