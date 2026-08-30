# Developer Setup Guide

Everything you need to go from zero to flashing and running real firmware on real ESP32-C6 hardware. This covers the **bring-up kit** for developing M1–M4 (firmware + hub software) — not the final per-plant BOM (solar panel, battery, enclosure), which is decided later in M6 once real power/range data exists.

## TL;DR

1. Buy 4× **ESP32-C6-DevKitC-1** boards + 2× capacitive soil moisture sensors + a small breadboard/jumper kit (table below).
2. Install ESP-IDF **v6.0.2** (stable) for your OS.
3. `git clone` this repo, `cd firmware`, `idf.py set-target esp32c6 && idf.py build`.
4. `idf.py -p <PORT> flash monitor` to flash and watch logs.

Full detail below.

## 1. What to buy

This is a development/bring-up kit — enough to build and test M1 (single-node), M2 (two-node link), and M3/M4 (hub + provisioning with more than one node) on real hardware. It is deliberately **not** the final production BOM (no solar panel, no LiPo battery, no enclosure) — that's M6's job, once M1's power measurements and M5's range/placement data exist to size them correctly.

| Item | Recommended part | Qty | Why this one |
|---|---|---|---|
| Dev board | **ESP32-C6-DevKitC-1** (Espressif official) | 4 | Espressif's own reference board for the ESP32-C6 — the raw `esp_ieee802154` radio component is validated against exactly this board, which matters since we're bypassing Zigbee/Thread and driving the radio directly. Built-in USB-JTAG/serial over a single USB-C cable, no extra USB-serial driver hassle. All pins broken out on breadboard-friendly headers. |
| Moisture sensor | Capacitive soil moisture sensor (analog output, 3-pin: VCC/GND/AOUT) — sold generically as "Capacitive Soil Moisture Sensor v1.2" by many suppliers (Adafruit, SparkFun, generic AliExpress/Amazon listings all carry the same design) | 2 | Analog output plugs straight into an ADC pin; corrosion-resistant unlike the cheaper resistive-probe sensors, matching the spec's hardware choice (Section 3). |
| USB-C cables | Any data-capable (not charge-only) USB-C cable | 3 | One per board you're actively flashing/monitoring at once, plus a spare — "charge-only" cables are a classic silent failure mode here. |
| Breadboard + jumper wire kit | Any small breadboard + male-to-female jumper wires | 1 kit | For wiring the moisture sensor, LED, and dongle-UART bridge (below) to each board's pins. |
| Multimeter with µA range | Any multimeter that reads down to µA (most "auto-ranging" multimeters do) | 1 (skip if you already own one) | Needed for M1 Task 6's real power-draw measurement — this is the actual acceptance test for M1. |
| 5mm LED + 220-330Ω resistor | Any color LED, any through-hole resistor in that range | 1 (per leaf node you'll provision) | M4's pairing-mode "tap to confirm" flow (`firmware/main/pairing_mode.c`) drives a discrete LED on `BLINK_LED_GPIO` (currently `GPIO2`, a placeholder — confirm against your board's schematic, same caveat status as Section 6 below). The DevKitC-1's *onboard* LED is an addressable WS2812 needing the `led_strip` component, which the M4 plan deliberately left out of scope — you need a real discrete LED wired in to actually see BLINK confirmations. |
| USB-to-TTL serial adapter (3.3V logic!) | Any CP2102/CH340/FTDI-based adapter, e.g. "USB to TTL 3.3V" — **do not use a 5V-logic adapter**, it can damage the ESP32-C6 | 1 | M3's dongle↔Pi link (`firmware/main/dongle_uart.c`) uses a *second*, separate UART (`UART_NUM_1`, currently GPIO4 TX / GPIO5 RX — also placeholders, see below) from the one used for flashing/console. Nothing bridges that second UART to your dev machine's USB port without this adapter — plug it into the dongle board's UART1 TX/RX/GND pins, then the other end's serial device path is what you pass to `python -m hub.main --serial-port <path>`. |

**Quantity reasoning, so you're not guessing why it's 4 boards:** 1 for M1 bring-up, 2 for M2's root+leaf link test, and a 4th so M4's provisioning flow can be tested realistically (one already-claimed node still reporting, plus a factory-fresh node being provisioned, plus the dongle) without constantly reflashing the same board back and forth between roles. This does **not** cover M5 — that plan explicitly leaves node count as "whatever's practical," since it depends on how many rooms you're actually testing across; buy more boards + moisture sensors (same part) incrementally once you're ready for that milestone, rather than guessing a count now.

**What you don't need yet:** Raspberry Pi (M3's plan explicitly allows running the hub backend directly on your dev machine for bench testing — a Pi only matters once you want a standalone always-on hub), solar panels, LiPo batteries, enclosures (all M6/M7 scope, once real data from M1–M5 exists to size them).

## 2. Firmware development environment (ESP-IDF)

We target ESP-IDF **v6.0.2** (current stable at time of writing). Follow Espressif's official installer for your OS — it changed recently to a new installer tool (EIM) and the exact commands are best kept authoritative at the source rather than copied here and left to go stale:

- **Get-started guide (all platforms):** `https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/get-started/index.html`

Whichever install path you follow, confirm it at the end with:

```bash
idf.py --version
# should report v6.0.2 (or newer stable)
```

You do **not** need to manually enable the raw 802.15.4 radio — `firmware/sdkconfig.defaults` already sets `CONFIG_IEEE802154_ENABLED=y` and targets `esp32c6`, so a fresh `idf.py build` picks both up automatically.

### VS Code (optional, but makes this much smoother)

Install the official **Espressif IDF VS Code extension** — it wraps `idf.py` (build/flash/monitor buttons, no terminal juggling), gives you IntelliSense against the real ESP-IDF headers, and a built-in serial monitor. Not required — everything below also works from a plain terminal — but recommended if you don't already have a preferred embedded workflow.

## 3. Build, flash, monitor

Once ESP-IDF is installed and its environment is sourced (per the installer's own instructions — this is the one step every ESP-IDF install method ends with, regardless of which installer you used):

```bash
cd firmware
idf.py set-target esp32c6   # one-time per project checkout
idf.py build
idf.py -p <PORT> flash monitor
```

`<PORT>` is the board's serial device:
- **Linux:** usually `/dev/ttyACM0` (run `ls /dev/ttyACM*` after plugging in; DevKitC-1 uses USB-JTAG/serial, so it shows up as `ttyACM`, not `ttyUSB`).
- **macOS:** usually `/dev/cu.usbmodem*` (run `ls /dev/cu.usbmodem*`).
- **Windows:** a `COM#` port, visible in Device Manager.

Exit the monitor with `Ctrl+]`.

### Linux: serial port permission denied

If `flash`/`monitor` fails with a permission error on `/dev/ttyACM0`, your user isn't in the `dialout` group yet:

```bash
sudo usermod -aG dialout $USER
```

Then **log out and back in** (group membership doesn't apply to your current session until you do) and try again.

## 4. Hub software environment (Python) — needed starting M3

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r hub/requirements.txt
pip install pytest  # for tests/test_hub_*.py
```

Run the hub's own test suite (no serial hardware needed — `tests/test_hub_serial_bridge.py` uses a fake in-memory port):

```bash
pytest tests/test_hub_*.py -v
```

Run the dashboard against a local SQLite file for bench testing (M3's plan explicitly allows this on your dev machine — a Raspberry Pi only matters once you want a standalone always-on hub):

```bash
python -c "from hub.api import create_app; import uvicorn; uvicorn.run(create_app('hub.db'), host='127.0.0.1', port=8000)"
```

Then open `http://127.0.0.1:8000/` in a browser. With no real dongle attached yet, you can exercise the ingest path directly:

```bash
python -c "
from hub.ingest import ingest_data_frame
from hub.models import connect
from hub.protocol_frame import DataFrame, NeedsWater
import time

conn = connect('hub.db')
ingest_data_frame(conn, DataFrame(sender_id=1, needs_water=NeedsWater.TRUE, battery_pct=80, timestamp=0), int(time.time()))
"
```

Refresh the dashboard page — node 1 should now show up needing water.

**Not yet wired up**: `hub/serial_bridge.py` talks to the dongle's serial port via any pyserial-shaped object (`readline()`/`write()`), but nothing yet opens a real `serial.Serial(...)` and feeds it into `SerialBridge` + `ingest_data_frame` in a running loop — that glue, plus flashing the extended `root_main.c` (now speaking the `RX`/`TX` line protocol over a secondary UART — see `firmware/main/dongle_uart.c`) to a real dongle, is M3 Task 5's bench test and needs real hardware to do and verify.

## 5. Sanity-check your setup

Before starting on any real milestone task, confirm the whole chain works with the simplest possible check:

```bash
cd firmware
idf.py set-target esp32c6
idf.py build
```

A clean build with no errors confirms: ESP-IDF is installed correctly, the `esp32c6` target and `IEEE802154_ENABLED` config are picked up, and the project structure (once M1's tasks are implemented) compiles. If this fails, fix it before going any further — every other milestone's firmware work builds on this.

## 6. GPIO note for the moisture sensor wiring

M1's plan wires the moisture sensor to `ADC1_CHANNEL_0` (GPIO0). On many Espressif chips, low-numbered GPIOs like GPIO0 can double as boot-mode strapping pins — we could not confirm from official docs during authoring of this guide whether that applies to the ESP32-C6-DevKitC-1's GPIO0 specifically. If you see erratic boot behavior only when the sensor is connected, that's the likely cause — switch the sensor to `ADC1_CHANNEL_1` (GPIO1) instead and update `MOISTURE_SENSOR_ADC_CHANNEL` in `firmware/main/moisture_sensor.h` accordingly. This is the one hardware detail in the plans that should be double-checked against the board's actual schematic once you have it in hand, rather than taken purely on faith.

## 7. GPIO note for M4's LED and dongle-UART wiring

Same caveat as above, for three more GPIOs picked without a board in hand: `BLINK_LED_GPIO` (`GPIO2`, `firmware/main/pairing_mode.c`) and `DONGLE_UART_TX_GPIO`/`DONGLE_UART_RX_GPIO` (`GPIO4`/`GPIO5`, `firmware/main/dongle_uart.c`). ESP32-C6's strapping pins are commonly cited as GPIO4, GPIO5, GPIO8, GPIO9, and GPIO15 — if that's accurate for the DevKitC-1, GPIO4/GPIO5 in particular could interfere with boot-mode selection if something (the LED, or a UART adapter on UART1) is actively driving them at power-on. Confirm against the board's actual schematic before wiring; if you see erratic boot behavior, move the affected signal to a different free GPIO and update the corresponding `#define` in `pairing_mode.c`/`dongle_uart.c`. `FACTORY_RESET_BUTTON_GPIO` (`GPIO9`, `firmware/main/factory_reset_button.c`, reusing the board's own BOOT button) has the same open question, though it not being newly wired makes an actual conflict less likely — the board's designers presumably already accounted for BOOT's dual use.
