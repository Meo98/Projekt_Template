# Pico Template

A project template for Raspberry Pi Pico / Pico W with MicroPython firmware and KiCad PCB design.

> **Recommended:** Use `new_project.sh` (see below) instead of "Use this template" —
> it creates the repo, sets all secrets, and clones it in one command.

---

## Structure

```
project/
├── firmware/              # MicroPython code → deploy to Pico
│   ├── main.py            # Entry point
│   ├── blink.py           # Status LED
│   ├── pico_config.py     # All pin assignments (edit this first)
│   ├── boot.py            # Runs on every boot
│   ├── modules/           # Button, Fade – reusable drivers
│   ├── lib/               # Third-party libraries
│   └── utils/             # Helper functions
├── hardware/              # Hardware design (electrical + mechanical)
│   ├── kicad/             # KiCad project (electrical)
│   │   ├── Template.kicad_pro  # → rename to your project name
│   │   ├── Template.kicad_sch
│   │   ├── Template.kicad_pcb
│   │   ├── components/    # Custom symbol + footprint libraries
│   │   └── gerbers/       # PCB manufacturing files
│   ├── cad/               # Mechanical CAD (enclosure)
│   │   └── case.scad      # Parametric OpenSCAD enclosure → edit board dims
│   └── datasheets/        # Component PDFs (vendor reference)
├── scripts/
│   └── sync_notion.py  # Syncs BOM to Notion Bauteil-Bibliothek
└── .github/workflows/
    └── notion-bom-sync.yml    # Auto-runs on push when kicad/*.kicad_sch changes
```

**Aufteilung `hardware/`**: `kicad/` (elektrisch, inkl. Gerbers als generierter
Output) und `cad/` (mechanisch, OpenSCAD-Gehäuse) — getrennt, weil es zwei
Disziplinen sind. `datasheets/` bleibt eigenständig (Hersteller-Docs, kein Output).
Die KiCad lib-tables nutzen `${KIPRJMOD}/components/...`, was gültig bleibt weil
`.kicad_pro` und `components/` zusammen in `kicad/` liegen.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full code patterns, rules, and how to add features.

---

## Quick Start

### New project (one command)

**One-time setup** — add your Notion token to `~/.zshrc`:
```bash
export NOTION_TOKEN="ntn_..."
```

**Every new project:**
```bash
git clone https://github.com/Meo98/Pico_Template.git
cd Pico_Template
./new_project.sh MyProjectName
cd MyProjectName
```

This creates the GitHub repo, sets the `NOTION_TOKEN` secret automatically, and clones the project locally. Then rename `hardware/kicad/Template.*` to `hardware/kicad/MyProjectName.*`.

---

### Firmware

1. Flash [MicroPython](https://micropython.org/download/RPI_PICO2_W/) onto the Pico
2. Install the [MicroPico](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go) extension in VS Code / Antigravity
3. Edit `firmware/pico_config.py` — add your pin assignments
4. Add feature modules in `firmware/`, import and start them in `main.py`
5. Upload via MicroPico: "Upload Project to Pico"

### Hardware

1. Rename `hardware/kicad/Template.*` to `hardware/kicad/YourProjectName.*`
2. Open `hardware/kicad/YourProjectName.kicad_pro` in KiCad
3. Place custom footprints in `hardware/kicad/components/footprints/`
4. Export Gerbers to `hardware/kicad/gerbers/` (tested with JLCPCB)
5. Optional: enclosure in `hardware/cad/case.scad` — board dimensions eintragen,
   in OpenSCAD öffnen (`openscad hardware/cad/case.scad`), STL exportieren

### Notion BOM Sync

Automatically syncs all schematic components (`in_bom = yes`) to your Notion
**Bauteil-Bibliothek** on every push when `hardware/kicad/*.kicad_sch` changes.

If you used `new_project.sh`, the `NOTION_TOKEN` secret is already set.
If you created the repo manually via "Use this template", set it once:
```bash
gh secret set NOTION_TOKEN --repo Meo98/YourProjectName
```

---

## Included Modules

| Module | Description |
|---|---|
| `modules/button2.py` | Button with click / double-click / long-press callbacks |
| `modules/log_fade.py` | Logarithmic PWM fading for perceptually smooth LED brightness |
| `blink.py` | Status LED, supports both digital and PWM mode |
