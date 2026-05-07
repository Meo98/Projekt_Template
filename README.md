# Pico Template

A project template for Raspberry Pi Pico / Pico W with MicroPython firmware and KiCad PCB design.

> **GitHub Template:** Click "Use this template" to create a new repo from this structure.
> Then rename the `hardware/Template.*` files to match your project name.

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
├── hardware/              # KiCad project
│   ├── Template.kicad_pro # → rename to your project name
│   ├── Template.kicad_sch
│   ├── Template.kicad_pcb
│   ├── components/        # Custom footprint libraries
│   ├── datasheets/        # Component PDFs
│   └── gerbers/           # PCB manufacturing files
├── scripts/
│   └── sync_bom_to_notion.py  # Syncs BOM to Notion Bauteil-Bibliothek
└── .github/workflows/
    └── notion-bom-sync.yml    # Auto-runs on push when .kicad_sch changes
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full code patterns, rules, and how to add features.

---

## Quick Start

### Firmware

1. Flash [MicroPython](https://micropython.org/download/RPI_PICO2_W/) onto the Pico
2. Install the [MicroPico](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go) extension in VS Code / Antigravity
3. Edit `firmware/pico_config.py` — add your pin assignments
4. Add feature modules in `firmware/`, import and start them in `main.py`
5. Upload via MicroPico: "Upload Project to Pico"

### Hardware

1. Rename `hardware/Template.*` to `hardware/YourProjectName.*`
2. Open `hardware/YourProjectName.kicad_pro` in KiCad
3. Place custom footprints in `hardware/components/footprints/`
4. Export Gerbers to `hardware/gerbers/` (tested with JLCPCB)

### Notion BOM Sync

Automatically syncs all schematic components (`in_bom = yes`) to your Notion
**Bauteil-Bibliothek** on every push.

Add these secrets to your GitHub repo (`Settings → Secrets → Actions`):

| Secret | Value |
|---|---|
| `NOTION_TOKEN` | Your Notion internal integration token |
| `NOTION_DB_ID` | Notion database ID (optional – default already configured) |

---

## Included Modules

| Module | Description |
|---|---|
| `modules/button2.py` | Button with click / double-click / long-press callbacks |
| `modules/log_fade.py` | Logarithmic PWM fading for perceptually smooth LED brightness |
| `blink.py` | Status LED, supports both digital and PWM mode |
