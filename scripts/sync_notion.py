#!/usr/bin/env python3
"""
Sync KiCad project to Notion.

Builds a rich project page in the Projekte database:
  - Content from README.md (markdown → Notion blocks)
  - Auto-generated BOM table from .kicad_sch
  - Links section (GitHub, files)
  - Timestamp footer

Also syncs unique components to Bauteil-Bibliothek.

Required:  NOTION_TOKEN env var
Optional:  NOTION_PROJEKTE_DB_ID, NOTION_BAUTEIL_DB_ID
"""

import os, re, sys, json, time, subprocess
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    def _req(method, url, headers, data=None):
        r = requests.request(method, url, headers=headers, json=data, timeout=30)
        return r.json()
except ImportError:
    import urllib.request, urllib.error
    def _req(method, url, headers, data=None):
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e: return json.loads(e.read())

NOTION_TOKEN   = os.environ.get("NOTION_TOKEN", "")
PROJEKTE_DB    = os.environ.get("NOTION_PROJEKTE_DB_ID", "359d2e49b98481fb83c2e2e3f1a9edbb")
BAUTEIL_DB     = os.environ.get("NOTION_DB_ID",          "359d2e49b98481cab9d9dbb713c3c048")
NOTION_VER     = "2022-06-28"

TYPE_MAP = {
    "Device:R": "Widerstand",       "Device:C": "Kondensator",  "Device:L": "Induktivität",
    "Device:D": "Diode",            "Device:LED": "LED",
    "Transistor_FET": "MOSFET",     "Transistor_BJT": "Transistor",  "Transistor": "Transistor",
    "Pico": "Mikrocontroller",      "DRV": "IC / Treiber",      "PC817": "Optokoppler",
    "L7805": "Spannungsregler",     "IRF": "MOSFET",            "BTS": "High-Side Switch",
    "TB6612": "Motortreiber",       "1.5KE": "TVS-Diode",       "1190": "Steckverbinder",
}

# ── API ───────────────────────────────────────────────────────────────────────

def notion(method, path, data=None):
    h = {"Authorization": f"Bearer {NOTION_TOKEN}",
         "Notion-Version": NOTION_VER, "Content-Type": "application/json"}
    r = _req(method, f"https://api.notion.com/v1{path}", h, data)
    time.sleep(0.35)
    return r

# ── Git / project metadata ────────────────────────────────────────────────────

def git_cmd(cmd):
    try: return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except: return ""

def get_project_meta():
    remote = git_cmd(["git", "remote", "get-url", "origin"])
    m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
    slug = m.group(1) if m else ""
    github_url = f"https://github.com/{slug}" if slug else ""

    # Project name: prefer first H1 in README, fall back to repo name
    readme = Path("README.md")
    name = ""
    description = ""
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        h1 = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if h1:
            name = h1.group(1).strip()
        # First non-empty paragraph after the title
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        for p in paragraphs[1:]:
            if not p.startswith("#") and not p.startswith("```") and not p.startswith("|") and not p.startswith(">"):
                description = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", p)
                description = re.sub(r"[*_`]", "", description)[:500]
                break

    if not name:
        name = slug.split("/")[-1].replace("_", " ").replace("-", " ") if slug else Path.cwd().name

    return name, github_url, description

# ── KiCad parser ─────────────────────────────────────────────────────────────

def _prop(block, name):
    m = re.search(rf'\(property\s+"{re.escape(name)}"\s+"([^"]*)"', block)
    return m.group(1) if m else ""

def parse_schematic(path):
    content = Path(path).read_text(encoding="utf-8")
    ls = content.find("(lib_symbols")
    depth = pos = 0
    for i, ch in enumerate(content[ls:], ls):
        if ch == "(": depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0: pos = i + 1; break
    placed = content[pos:]
    components = []
    for sm in re.finditer(r"\n\t\(symbol\b", "\n" + placed):
        start = sm.start() + 1
        depth = end = 0
        for i, ch in enumerate(placed[start:], start):
            if ch == "(": depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0: end = i + 1; break
        block = placed[start:end]
        if "(dnp yes)" in block or "(in_bom no)" in block: continue
        lib_m = re.search(r'\(lib_id\s+"([^"]+)"', block)
        if not lib_m: continue
        lib_id = lib_m.group(1)
        if lib_id.startswith("power:") or "PWR_FLAG" in lib_id: continue
        ref = _prop(block, "Reference")
        if ref.startswith("#"): continue
        components.append({"lib_id": lib_id, "reference": ref,
            "value": _prop(block, "Value"), "footprint": _prop(block, "Footprint"),
            "description": _prop(block, "Description"), "manufacturer": _prop(block, "MF")})
    return components

def group_bom(components):
    groups = {}
    for c in components:
        key = f"{c['value']}|{c['footprint']}"
        if key not in groups: groups[key] = {**c, "references": []}
        groups[key]["references"].append(c["reference"])
    return [c for c in groups.values() if c["value"] not in ("R_Small","C_Small","L_Small","")]

def guess_type(lib_id, value):
    s = lib_id + " " + value
    for k, t in TYPE_MAP.items():
        if k.lower() in s.lower(): return t
    if lib_id.startswith("Device:R"): return "Widerstand"
    if lib_id.startswith("Device:C"): return "Kondensator"
    if lib_id.startswith("Device:D") or "diode" in lib_id.lower(): return "Diode"
    return "Sonstiges"

# ── Markdown → Notion blocks ──────────────────────────────────────────────────

def _rich(text):
    """Convert inline markdown (bold, italic, code, links) to Notion rich_text."""
    parts = []
    pos = 0
    pattern = re.compile(
        r"\[([^\]]+)\]\(([^)]+)\)"   # [text](url)
        r"|\*\*([^*]+)\*\*"          # **bold**
        r"|`([^`]+)`"                # `code`
        r"|\*([^*]+)\*"              # *italic*
    )
    for m in pattern.finditer(text):
        if pos < m.start():
            parts.append({"type": "text", "text": {"content": text[pos:m.start()]}})
        if m.group(1):   # link – only absolute URLs are valid in Notion
            url = m.group(2)
            if url.startswith("http://") or url.startswith("https://"):
                parts.append({"type": "text", "text": {"content": m.group(1), "link": {"url": url}}})
            else:
                parts.append({"type": "text", "text": {"content": m.group(1)}})
        elif m.group(3): # bold
            parts.append({"type": "text", "text": {"content": m.group(3)}, "annotations": {"bold": True}})
        elif m.group(4): # code
            parts.append({"type": "text", "text": {"content": m.group(4)}, "annotations": {"code": True}})
        elif m.group(5): # italic
            parts.append({"type": "text", "text": {"content": m.group(5)}, "annotations": {"italic": True}})
        pos = m.end()
    if pos < len(text):
        parts.append({"type": "text", "text": {"content": text[pos:]}})
    return parts or [{"type": "text", "text": {"content": text}}]

def _t(text): return [{"type": "text", "text": {"content": text}}]

def md_to_blocks(md_text):
    """Convert markdown to Notion blocks (headings, paragraphs, lists, tables, code, HR)."""
    blocks = []
    lines = md_text.splitlines()
    i = 0
    in_code = False
    code_buf = []
    code_lang = ""
    bullet_buf = []

    def flush_bullets():
        for line in bullet_buf:
            blocks.append({"type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _rich(line)}})
        bullet_buf.clear()

    while i < len(lines):
        line = lines[i]

        # Code block
        if line.startswith("```"):
            if not in_code:
                in_code = True
                code_lang = line[3:].strip()
                code_buf = []
            else:
                flush_bullets()
                blocks.append({"type": "code", "code": {
                    "rich_text": _t("\n".join(code_buf)),
                    "language": code_lang if code_lang in ("python","javascript","bash","json","nix","plain text") else "plain text"
                }})
                in_code = False
                code_buf = []
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # Markdown table
        if "|" in line and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|", lines[i+1]):
            flush_bullets()
            header_cells = [c.strip() for c in line.strip("|").split("|")]
            table_rows = [header_cells]
            i += 2  # skip separator row
            while i < len(lines) and "|" in lines[i]:
                row = [c.strip() for c in lines[i].strip("|").split("|")]
                table_rows.append(row)
                i += 1
            width = max(len(r) for r in table_rows)
            blocks.append({"type": "table", "table": {
                "table_width": width, "has_column_header": True, "has_row_header": False,
                "children": [{"type": "table_row", "table_row": {
                    "cells": [[{"type":"text","text":{"content": (row[j] if j < len(row) else "")}}]
                               for j in range(width)]
                }} for row in table_rows]
            }})
            continue

        # HR
        if re.match(r"^[-*_]{3,}$", line.strip()):
            flush_bullets()
            blocks.append({"type": "divider", "divider": {}})
            i += 1
            continue

        # Headings (skip H1 – it's the page title)
        h = re.match(r"^(#{2,6})\s+(.*)", line)
        if h:
            flush_bullets()
            level = len(h.group(1))
            content = h.group(2).strip()
            btype = "heading_2" if level == 2 else "heading_3"
            blocks.append({btype: {"rich_text": _rich(content)}, "type": btype})
            i += 1
            continue

        # Bullet / unordered list
        if re.match(r"^[-*+] ", line):
            bullet_buf.append(re.sub(r"^[-*+] ", "", line))
            i += 1
            continue

        # Numbered list → bullet
        if re.match(r"^\d+\. ", line):
            flush_bullets()
            text = re.sub(r"^\d+\. ", "", line)
            blocks.append({"type": "numbered_list_item",
                "numbered_list_item": {"rich_text": _rich(text)}})
            i += 1
            continue

        # Blockquote → callout
        if line.startswith("> "):
            flush_bullets()
            blocks.append({"type": "callout", "callout": {
                "rich_text": _rich(line[2:]),
                "icon": {"type": "emoji", "emoji": "💡"},
                "color": "blue_background"
            }})
            i += 1
            continue

        # Empty line
        if not line.strip():
            flush_bullets()
            i += 1
            continue

        # Paragraph (skip lone H1)
        if not line.startswith("#"):
            flush_bullets()
            blocks.append({"type": "paragraph",
                "paragraph": {"rich_text": _rich(line)}})
        i += 1

    flush_bullets()
    return blocks

# ── BOM table block ───────────────────────────────────────────────────────────

def bom_table_block(bom):
    header = ["Wert", "Referenz(en)", "Anz.", "Package", "Hersteller", "Typ"]
    rows = [header]
    for c in sorted(bom, key=lambda x: (guess_type(x["lib_id"], x["value"]), x["value"])):
        refs = ", ".join(sorted(c["references"]))
        pkg  = (c["footprint"].split(":")[-1] if ":" in c["footprint"] else c["footprint"])[:60]
        rows.append([c["value"], refs, str(len(c["references"])),
                     pkg, c["manufacturer"], guess_type(c["lib_id"], c["value"])])
    return {"type": "table", "table": {
        "table_width": len(header), "has_column_header": True, "has_row_header": False,
        "children": [{"type": "table_row", "table_row": {
            "cells": [[{"type":"text","text":{"content": cell}}] for cell in row]
        }} for row in rows]
    }}

# ── Page block builder ────────────────────────────────────────────────────────

def build_blocks(readme_md, bom, github_url, project_name):
    blocks = []

    # ── README content (skip H1 title) ──
    if readme_md:
        md = re.sub(r"^#[^#].*\n?", "", readme_md, count=1)  # strip first H1
        readme_blocks = md_to_blocks(md.strip())
        blocks.extend(readme_blocks)

    # ── BOM section ──
    if bom:
        blocks.append({"type": "divider", "divider": {}})
        blocks.append({"type": "heading_2", "heading_2": {
            "rich_text": [{"type":"text","text":{"content": f"Stückliste  ·  {len(bom)} Bauteile"}}]
        }})
        blocks.append(bom_table_block(bom))

    # ── Links section ──
    if github_url:
        blocks.append({"type": "divider", "divider": {}})
        blocks.append({"type": "heading_2", "heading_2": {
            "rich_text": _t("Links")
        }})
        repo_name = github_url.rstrip("/").split("/")[-1]
        links = [
            (f"GitHub – {repo_name}", github_url),
            ("hardware/", f"{github_url}/tree/main/hardware"),
            ("firmware/", f"{github_url}/tree/main/firmware"),
            ("Actions (BOM Sync)", f"{github_url}/actions"),
        ]
        for label, url in links:
            blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": [{"type":"text","text":{"content": label,"link":{"url": url}}}]
            }})

    # ── Footer ──
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    blocks.append({"type": "callout", "callout": {
        "rich_text": _t(f"Zuletzt synchronisiert: {now}"),
        "icon": {"type": "emoji", "emoji": "🤖"},
        "color": "gray_background"
    }})

    return blocks

# ── Notion page management ────────────────────────────────────────────────────

def find_project(name):
    r = notion("POST", f"/databases/{PROJEKTE_DB}/query", {
        "filter": {"property": "Name", "title": {"equals": name}}, "page_size": 1})
    res = r.get("results", [])
    return res[0]["id"] if res else None

def create_project(name, github_url, description):
    props = {"Name": {"title": [{"text": {"content": name}}]},
             "Status": {"select": {"name": "In Arbeit"}}}
    if github_url: props["GitHub URL"] = {"url": github_url}
    if description: props["Beschreibung"] = {"rich_text": [{"text": {"content": description[:2000]}}]}
    return notion("POST", "/pages", {"parent": {"database_id": PROJEKTE_DB}, "properties": props})["id"]

def clear_blocks(page_id):
    r = notion("GET", f"/blocks/{page_id}/children?page_size=100")
    for b in r.get("results", []):
        notion("DELETE", f"/blocks/{b['id']}")

def append_blocks(page_id, blocks):
    for i in range(0, len(blocks), 99):   # 99 to be safe (table children count against limit)
        notion("PATCH", f"/blocks/{page_id}/children", {"children": blocks[i:i+99]})

def sync_page(name, github_url, description, bom):
    readme = Path("README.md").read_text(encoding="utf-8") if Path("README.md").exists() else ""
    page_id = find_project(name)
    if page_id:
        print(f"  Updating existing page: {name}")
        # Update description property too
        props = {}
        if description: props["Beschreibung"] = {"rich_text": [{"text": {"content": description[:2000]}}]}
        if props: notion("PATCH", f"/pages/{page_id}", {"properties": props})
        clear_blocks(page_id)
    else:
        print(f"  Creating new page: {name}")
        page_id = create_project(name, github_url, description)
    blocks = build_blocks(readme, bom, github_url, name)
    append_blocks(page_id, blocks)
    print(f"  Page updated ({len(blocks)} blocks, {len(bom)} BOM entries).")

# ── Bauteil-Bibliothek sync ───────────────────────────────────────────────────

def find_bauteil(name):
    r = notion("POST", f"/databases/{BAUTEIL_DB}/query", {
        "filter": {"property": "Name", "title": {"equals": name}}, "page_size": 1})
    res = r.get("results", [])
    return res[0]["id"] if res else None

def sync_bauteil(comp):
    name = comp["value"]
    pkg  = (comp["footprint"].split(":")[-1] if ":" in comp["footprint"] else comp["footprint"])[:100]
    props = {
        "Name":     {"title":     [{"text": {"content": name}}]},
        "Typ":      {"select":    {"name": guess_type(comp["lib_id"], name)}},
        "Funktion": {"rich_text": [{"text": {"content": (comp["description"] or name)[:2000]}}]},
    }
    if pkg:         props["Package"]   = {"select":    {"name": pkg}}
    if comp["manufacturer"]: props["Hersteller"] = {"rich_text": [{"text": {"content": comp["manufacturer"]}}]}
    eid = find_bauteil(name)
    if eid:
        notion("PATCH", f"/pages/{eid}", {"properties": props}); return "updated"
    else:
        notion("POST", "/pages", {"parent": {"database_id": BAUTEIL_DB}, "properties": props}); return "created"

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not NOTION_TOKEN:
        print("ERROR: NOTION_TOKEN not set"); sys.exit(1)

    name, github_url, description = get_project_meta()
    print(f"Project: {name}")
    print(f"GitHub:  {github_url or '(none)'}")

    sch_files = list(Path(".").glob("hardware/kicad/*.kicad_sch")) or list(Path(".").glob("**/*.kicad_sch"))
    bom = []
    if sch_files:
        for sch in sch_files:
            print(f"Parsing {sch.name}...")
            bom.extend(parse_schematic(sch))
        bom = group_bom(bom)
        print(f"BOM: {len(bom)} unique components")

    print("\nSyncing Notion project page...")
    sync_page(name, github_url, description, bom)

    if bom:
        print("\nSyncing Bauteil-Bibliothek...")
        counts = {"created": 0, "updated": 0}
        for comp in bom:
            counts[sync_bauteil(comp)] += 1
        print(f"  {counts['created']} created, {counts['updated']} updated.")

    print("\nDone.")

if __name__ == "__main__":
    main()
