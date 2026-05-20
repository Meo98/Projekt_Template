# Architecture Guide

This document describes how this project is structured and how new code should be written.
It exists so that both humans and AI assistants produce consistent, readable code.

---

## Project Structure

```
project/
├── firmware/              # All MicroPython code for the Pico
│   ├── main.py            # Entry point: creates tasks and starts the event loop
│   ├── blink.py           # Status LED module (reusable, do not modify for features)
│   ├── pico_config.py     # SINGLE source of truth for all pin assignments
│   ├── boot.py            # Runs on every boot before main.py
│   ├── modules/           # Reusable low-level drivers
│   │   ├── button2.py     # Button class (click / double-click / long-press callbacks)
│   │   └── log_fade.py    # Logarithmic PWM fade helper
│   ├── lib/               # Third-party MicroPython libraries (e.g. from PyPI)
│   └── utils/             # Small helper functions (math, conversion, etc.)
├── hardware/              # Hardware design (electrical + mechanical)
│   ├── kicad/             # KiCad project (electrical)
│   │   ├── *.kicad_pro    # KiCad project file
│   │   ├── *.kicad_sch    # Schematic
│   │   ├── *.kicad_pcb    # PCB layout
│   │   ├── components/    # Custom KiCad symbol + footprint libraries
│   │   │   └── footprints/  # *.pretty folders go here
│   │   └── gerbers/       # Manufacturing files for PCB order (auto-generated)
│   ├── cad/               # Mechanical CAD
│   │   └── case.scad      # Parametric OpenSCAD enclosure
│   └── datasheets/        # PDF datasheets for all components (vendor reference)
├── scripts/               # Automation scripts (not deployed to Pico)
│   └── sync_bom_to_notion.py
└── .github/workflows/     # GitHub Actions CI/CD
    └── notion-bom-sync.yml
```

---

## Firmware Architecture

### Core pattern: asyncio tasks

All features run as concurrent `asyncio` tasks. The `main.py` is purely the
orchestrator — it creates tasks and keeps the event loop running. It contains
no feature logic itself.

```python
# main.py
asyncio.create_task(blink.run())      # status LED
asyncio.create_task(my_feature.run()) # your feature
while True:
    await asyncio.sleep(1)            # heartbeat
```

**Rule:** every feature module must have an `async def run(self)` method with an
infinite `while True` loop. This is the task entry point.

---

### PinConfig — single source of truth for hardware

`pico_config.py` contains ONE class `PinConfig` with ALL pin assignments as
class-level attributes. No pin number should appear anywhere else in the code.

```python
# pico_config.py
class PinConfig:
    status_led = Pin("LED", Pin.OUT)
    motor_en   = Pin(2, Pin.OUT)
    motor_pwm  = PWM(Pin(3))
    btn_pin    = Pin(14, Pin.IN, Pin.PULL_UP)
    my_button  = Button(btn_pin, active_low=True)
```

**Rule:** feature modules inherit from `PinConfig` to access pins:

```python
# my_feature.py
from pico_config import PinConfig

class MyFeature(PinConfig):   # inherits all pins
    async def run(self):
        while True:
            self.motor_en.value(1)
            await asyncio.sleep(1)
```

---

### Adding a new feature

1. Create `firmware/my_feature.py`:

```python
import asyncio
from pico_config import PinConfig

class MyFeature(PinConfig):

    def __init__(self):
        # register button callbacks here if needed
        self.my_button.on_click(self._on_click)

    async def _on_click(self):
        # called when button is clicked – can be async
        print("clicked")

    async def run(self):
        while True:
            # main feature logic
            await asyncio.sleep(0.1)
```

2. Add the pin(s) it needs to `PinConfig` in `pico_config.py`.
3. Import and start the task in `main.py`.

---

### Button module (modules/button2.py)

The `Button` class wraps a pin and detects click / double-click / long-press.
Callbacks are registered with `on_click`, `on_double_click`, `on_long_press`.
Callbacks can be regular functions or `async` coroutines — both work.

```python
btn = Button(Pin(14, Pin.IN, Pin.PULL_UP), active_low=True)
btn.on_click(my_async_handler)
btn.on_long_press(lambda: print("held"))
```

The Button automatically starts its own background task in `__init__`.
Do not call `btn.run()` manually.

---

### Fade module (modules/log_fade.py)

`Fade` produces a perceptually linear (logarithmic) brightness curve for PWM LEDs.

```python
from machine import PWM, Pin
from modules import Fade

pwm = PWM(Pin(3))
fader = Fade(pwm, start_value=1, end_value=65535, steps=100)

fader.fade(target_index=99, speed_ms=10)  # fade to full brightness
fader.fade(target_index=0,  speed_ms=5)   # fade to off
fader.set_value(50)                        # jump to middle instantly
```

`Fade` starts its own background task automatically.

---

## Code style rules

- **No magic numbers** outside `pico_config.py`. All pins, frequencies, and
  hardware-specific constants belong in `PinConfig`.
- **One class per file.** File name = class name in snake_case.
- **No blocking calls** (`time.sleep`, busy loops) inside async functions.
  Always use `await asyncio.sleep_ms(n)`.
- **Comments only where the WHY is not obvious** — not what the code does.
- **Print statements** in `boot.py` / `pico_config.py` are fine for debug info.
  Remove prints from production feature code.

---

## Hardware

Rename the KiCad files in `hardware/kicad/` from `Template.*` to your project name.

| Folder | Contents |
|---|---|
| `hardware/kicad/` | KiCad project (`.kicad_pro/_sch/_pcb`), lib-tables |
| `hardware/kicad/components/footprints/` | Custom `.pretty` footprint libraries (ZIP extracted from SnapEDA etc.) |
| `hardware/kicad/gerbers/` | Gerber + drill files for PCB ordering (JLCPCB compatible) |
| `hardware/cad/` | Mechanical CAD — `case.scad` (parametric OpenSCAD enclosure) |
| `hardware/datasheets/` | PDF datasheets for every component on the schematic (vendor reference) |

> **`${KIPRJMOD}`-Hinweis**: KiCads lib-tables referenzieren Bibliotheken über
> `${KIPRJMOD}/components/...` (relativ zum `.kicad_pro`-Ordner). Da `.kicad_pro`
> und `components/` zusammen in `hardware/kicad/` liegen, bleiben die Pfade gültig.
> Verschiebe sie nie einzeln.

**fp-lib-table:** Project-specific footprint libraries are registered in
`hardware/kicad/fp-lib-table` using the `${KIPRJMOD}` relative path so the project
works on any machine without reconfiguring KiCad.

---

## Notion BOM Sync (GitHub Actions)

On every push that modifies `hardware/kicad/*.kicad_sch`, GitHub Actions automatically
parses the schematic and syncs all `in_bom=yes` components to the shared
Notion **Bauteil-Bibliothek** database.

**Required GitHub repository secrets:**

| Secret | Value |
|---|---|
| `NOTION_TOKEN` | Your Notion internal integration token |
| `NOTION_DB_ID` | Notion database ID (optional – hardcoded default already set) |

Set these under: `github.com/<user>/<repo>/settings/secrets/actions`

The workflow can also be triggered manually from the GitHub Actions tab.
