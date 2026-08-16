# M1 Single-Node Firmware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ESP-IDF firmware for a single ESP32-C6 node — deep sleep with RTC-timer wake, a moisture-sensor ADC read, and 802.15.4 radio init/send — as a hardware proof-of-life, and confirm measured power draw against the solar/battery budget assumption in the spec.

**Architecture:** A hardware-independent `protocol` component (frame encode/decode) that is testable on the host with plain `gcc`, plus three hardware-facing modules in `main/` (`sleep_wake`, `moisture_sensor`, `ieee802154_radio`) that wrap ESP-IDF APIs, wired together in `app_main()`. The protocol component is deliberately free of ESP-IDF headers so it can be reused unchanged by M2 (two-node link) and M3 (hub-radio dongle firmware).

**Tech Stack:** ESP-IDF (C), target chip `esp32c6`. Host-side tests use plain `gcc`, no ESP-IDF toolchain required for Task 1.

**Spec:** `docs/superpowers/specs/2026-08-16-office-plant-swarm-design.md` (Section 3: Tech Stack, Section 4: Protocol Design, Section 8: M1 deliverable)

## ⚠️ Verification limits in this environment

This plan was written with no ESP-IDF toolchain and no physical ESP32-C6 installed in the authoring environment. What that means per task:

- **Task 1** (protocol frame encode/decode) has **zero ESP-IDF dependencies** and was actually compiled and run with `gcc` while writing this plan — all 6 checks passed. Treat it as verified, same standard as the M0 plan.
- **Tasks 2–6** use real ESP-IDF APIs — function names, header paths, struct fields, and the event-callback-registration pattern were pulled directly from `github.com/espressif/esp-idf` source (the `esp_sleep.h`, `esp_adc/adc_oneshot.h`, `esp_ieee802154.h`/`esp_ieee802154_types.h` headers, the `ieee802154` component's `Kconfig`, and the real usage pattern in `components/openthread/src/port/esp_openthread_radio.c`) — not from memory. They were **not compiled or flashed** here. The implementer must have ESP-IDF installed and a real ESP32-C6 board; if `idf.py build` fails, treat it as ESP-IDF-version drift to resolve against the cited source files (linked in each task), not as evidence the plan's design is wrong.

## Global Constraints

- Firmware lives under `firmware/` at repo root; target chip is `esp32c6` (`idf.py set-target esp32c6`).
- `firmware/components/protocol/` holds hardware-independent code only — no ESP-IDF includes, ever. Anything that needs an ESP-IDF header belongs in `firmware/main/`.
- Wire frame format (fixed by Task 1, must not change in later tasks): byte 0 = frame type (`FRAME_TYPE_BEACON`/`JOIN`/`DATA`), bytes 1-2 = `sender_id` (uint16, little-endian), then type-specific fields. This is the payload that goes into `esp_ieee802154_transmit`'s buffer starting at index 1 — index 0 of *that* buffer is the separate PHY length prefix required by the radio driver (payload length + 2 for the hardware-appended FCS), not part of our frame format.
- Radio must call `esp_ieee802154_set_promiscuous(true)` during init. Our frames don't use standard 802.15.4 MAC addressing, so without promiscuous mode the hardware's address/FCF filter would silently drop them — this was confirmed by checking the driver header; there's no separate "accept non-standard frames" flag, promiscuous mode is the documented lever.
- Event callbacks are registered via `esp_ieee802154_event_callback_list_register()` with our own function names (matching the real pattern used by ESP-IDF's own OpenThread radio port) — not by defining functions literally named `esp_ieee802154_receive_done` etc. (that's a different, legacy mechanism this plan does not use).
- Radio defaults for M1 (single node, no link partner yet — range/power tuning is M2's job): channel 25, PAN ID `0x4F50`, TX power 0 dBm, short address `0x0001` (hardcoded test value; real per-node addressing arrives with M4 provisioning).
- Moisture sensor uses ADC1 channel 0, which is GPIO0 on ESP32-C6 (confirmed against `soc/esp32c6/include/soc/adc_channel.h`).

---

### Task 1: Protocol frame encode/decode (host-testable)

**Files:**
- Create: `firmware/components/protocol/include/protocol_frame.h`
- Create: `firmware/components/protocol/protocol_frame.c`
- Create: `firmware/components/protocol/CMakeLists.txt`
- Test: `firmware/components/protocol/test_host/test_protocol_frame.c`

**Interfaces:**
- Produces: `FRAME_TYPE_BEACON`/`FRAME_TYPE_JOIN`/`FRAME_TYPE_DATA` (uint8 constants), `BEACON_FRAME_LEN`=4, `JOIN_FRAME_LEN`=5, `DATA_FRAME_LEN`=9, `PROTOCOL_FRAME_MAX_LEN`=9
- Produces: `beacon_frame_t { uint16_t sender_id; uint8_t hop_count; }`
- Produces: `join_frame_t { uint16_t sender_id; uint16_t target_parent_id; }`
- Produces: `needs_water_t { NEEDS_WATER_FALSE=0, NEEDS_WATER_TRUE=1, NEEDS_WATER_NONE=2 }`
- Produces: `data_frame_t { uint16_t sender_id; needs_water_t needs_water; uint8_t battery_pct; uint32_t timestamp; }`
- Produces: `size_t encode_beacon_frame(const beacon_frame_t*, uint8_t *out_buf)`, `encode_join_frame`, `encode_data_frame` (same shape) — each writes to `out_buf` and returns bytes written
- Produces: `int decode_frame_type(const uint8_t *buf, size_t len)` (returns `buf[0]`, or -1 if `len==0`), `int decode_beacon_frame(const uint8_t*, size_t, beacon_frame_t*)`, `decode_join_frame`, `decode_data_frame` (each returns 0 on success, -1 on length/type mismatch)

- [ ] **Step 1: Write the header**

```c
// firmware/components/protocol/include/protocol_frame.h
#ifndef PROTOCOL_FRAME_H
#define PROTOCOL_FRAME_H

#include <stdint.h>
#include <stddef.h>

#define FRAME_TYPE_BEACON 0x01
#define FRAME_TYPE_JOIN   0x02
#define FRAME_TYPE_DATA   0x03

#define BEACON_FRAME_LEN 4
#define JOIN_FRAME_LEN   5
#define DATA_FRAME_LEN   9
#define PROTOCOL_FRAME_MAX_LEN DATA_FRAME_LEN

typedef struct {
    uint16_t sender_id;
    uint8_t hop_count;
} beacon_frame_t;

typedef struct {
    uint16_t sender_id;
    uint16_t target_parent_id;
} join_frame_t;

typedef enum {
    NEEDS_WATER_FALSE = 0,
    NEEDS_WATER_TRUE = 1,
    NEEDS_WATER_NONE = 2,
} needs_water_t;

typedef struct {
    uint16_t sender_id;
    needs_water_t needs_water;
    uint8_t battery_pct;
    uint32_t timestamp;
} data_frame_t;

size_t encode_beacon_frame(const beacon_frame_t *in, uint8_t *out_buf);
size_t encode_join_frame(const join_frame_t *in, uint8_t *out_buf);
size_t encode_data_frame(const data_frame_t *in, uint8_t *out_buf);

int decode_frame_type(const uint8_t *buf, size_t len);
int decode_beacon_frame(const uint8_t *buf, size_t len, beacon_frame_t *out);
int decode_join_frame(const uint8_t *buf, size_t len, join_frame_t *out);
int decode_data_frame(const uint8_t *buf, size_t len, data_frame_t *out);

#endif
```

- [ ] **Step 2: Write the failing test**

```c
// firmware/components/protocol/test_host/test_protocol_frame.c
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "protocol_frame.h"

static int failures = 0;

#define CHECK(cond) do { \
    if (!(cond)) { \
        printf("FAIL: %s (line %d)\n", #cond, __LINE__); \
        failures++; \
    } \
} while (0)

static void test_beacon_roundtrip(void) {
    beacon_frame_t in = { .sender_id = 42, .hop_count = 3 };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t n = encode_beacon_frame(&in, buf);
    CHECK(n == BEACON_FRAME_LEN);
    CHECK(decode_frame_type(buf, n) == FRAME_TYPE_BEACON);

    beacon_frame_t out;
    CHECK(decode_beacon_frame(buf, n, &out) == 0);
    CHECK(out.sender_id == 42);
    CHECK(out.hop_count == 3);
}

static void test_join_roundtrip(void) {
    join_frame_t in = { .sender_id = 1000, .target_parent_id = 7 };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t n = encode_join_frame(&in, buf);
    CHECK(n == JOIN_FRAME_LEN);

    join_frame_t out;
    CHECK(decode_join_frame(buf, n, &out) == 0);
    CHECK(out.sender_id == 1000);
    CHECK(out.target_parent_id == 7);
}

static void test_data_roundtrip(void) {
    data_frame_t in = {
        .sender_id = 65535,
        .needs_water = NEEDS_WATER_TRUE,
        .battery_pct = 87,
        .timestamp = 0x01020304,
    };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t n = encode_data_frame(&in, buf);
    CHECK(n == DATA_FRAME_LEN);

    data_frame_t out;
    CHECK(decode_data_frame(buf, n, &out) == 0);
    CHECK(out.sender_id == 65535);
    CHECK(out.needs_water == NEEDS_WATER_TRUE);
    CHECK(out.battery_pct == 87);
    CHECK(out.timestamp == 0x01020304u);
}

static void test_wrong_type_rejected(void) {
    beacon_frame_t beacon_in = { .sender_id = 1, .hop_count = 0 };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t n = encode_beacon_frame(&beacon_in, buf);

    data_frame_t data_out;
    CHECK(decode_data_frame(buf, n, &data_out) == -1);
}

static void test_wrong_length_rejected(void) {
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN] = { FRAME_TYPE_DATA, 0, 0, 0 };
    data_frame_t out;
    CHECK(decode_data_frame(buf, 4, &out) == -1);
}

static void test_max_len_fits_all_frame_types(void) {
    CHECK(PROTOCOL_FRAME_MAX_LEN >= BEACON_FRAME_LEN);
    CHECK(PROTOCOL_FRAME_MAX_LEN >= JOIN_FRAME_LEN);
    CHECK(PROTOCOL_FRAME_MAX_LEN >= DATA_FRAME_LEN);
    /* 802.15.4 aMaxPHYPacketSize is 127 bytes, including the 2-byte
     * hardware-appended FCS and our own header; our largest frame must
     * leave comfortable headroom. */
    CHECK(PROTOCOL_FRAME_MAX_LEN < 127 - 2);
}

int main(void) {
    test_beacon_roundtrip();
    test_join_roundtrip();
    test_data_roundtrip();
    test_wrong_type_rejected();
    test_wrong_length_rejected();
    test_max_len_fits_all_frame_types();

    if (failures == 0) {
        printf("All tests passed.\n");
        return 0;
    }
    printf("%d check(s) failed.\n", failures);
    return 1;
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `gcc -Wall -Wextra -std=c11 -Ifirmware/components/protocol/include -o /tmp/test_protocol_frame firmware/components/protocol/test_host/test_protocol_frame.c`
Expected: FAIL to link/compile — `protocol_frame.c` doesn't exist yet, undefined reference errors for every `encode_*`/`decode_*` function.

- [ ] **Step 4: Implement protocol_frame.c**

```c
// firmware/components/protocol/protocol_frame.c
#include "protocol_frame.h"

static void write_u16le(uint8_t *buf, uint16_t v) {
    buf[0] = (uint8_t)(v & 0xFF);
    buf[1] = (uint8_t)((v >> 8) & 0xFF);
}

static uint16_t read_u16le(const uint8_t *buf) {
    return (uint16_t)(buf[0] | ((uint16_t)buf[1] << 8));
}

static void write_u32le(uint8_t *buf, uint32_t v) {
    buf[0] = (uint8_t)(v & 0xFF);
    buf[1] = (uint8_t)((v >> 8) & 0xFF);
    buf[2] = (uint8_t)((v >> 16) & 0xFF);
    buf[3] = (uint8_t)((v >> 24) & 0xFF);
}

static uint32_t read_u32le(const uint8_t *buf) {
    return (uint32_t)buf[0] | ((uint32_t)buf[1] << 8) |
           ((uint32_t)buf[2] << 16) | ((uint32_t)buf[3] << 24);
}

size_t encode_beacon_frame(const beacon_frame_t *in, uint8_t *out_buf) {
    out_buf[0] = FRAME_TYPE_BEACON;
    write_u16le(out_buf + 1, in->sender_id);
    out_buf[3] = in->hop_count;
    return BEACON_FRAME_LEN;
}

size_t encode_join_frame(const join_frame_t *in, uint8_t *out_buf) {
    out_buf[0] = FRAME_TYPE_JOIN;
    write_u16le(out_buf + 1, in->sender_id);
    write_u16le(out_buf + 3, in->target_parent_id);
    return JOIN_FRAME_LEN;
}

size_t encode_data_frame(const data_frame_t *in, uint8_t *out_buf) {
    out_buf[0] = FRAME_TYPE_DATA;
    write_u16le(out_buf + 1, in->sender_id);
    out_buf[3] = (uint8_t)in->needs_water;
    out_buf[4] = in->battery_pct;
    write_u32le(out_buf + 5, in->timestamp);
    return DATA_FRAME_LEN;
}

int decode_frame_type(const uint8_t *buf, size_t len) {
    if (len == 0) {
        return -1;
    }
    return buf[0];
}

int decode_beacon_frame(const uint8_t *buf, size_t len, beacon_frame_t *out) {
    if (len != BEACON_FRAME_LEN || buf[0] != FRAME_TYPE_BEACON) {
        return -1;
    }
    out->sender_id = read_u16le(buf + 1);
    out->hop_count = buf[3];
    return 0;
}

int decode_join_frame(const uint8_t *buf, size_t len, join_frame_t *out) {
    if (len != JOIN_FRAME_LEN || buf[0] != FRAME_TYPE_JOIN) {
        return -1;
    }
    out->sender_id = read_u16le(buf + 1);
    out->target_parent_id = read_u16le(buf + 3);
    return 0;
}

int decode_data_frame(const uint8_t *buf, size_t len, data_frame_t *out) {
    if (len != DATA_FRAME_LEN || buf[0] != FRAME_TYPE_DATA) {
        return -1;
    }
    out->sender_id = read_u16le(buf + 1);
    out->needs_water = (needs_water_t)buf[3];
    out->battery_pct = buf[4];
    out->timestamp = read_u32le(buf + 5);
    return 0;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `gcc -Wall -Wextra -std=c11 -Ifirmware/components/protocol/include -o /tmp/test_protocol_frame firmware/components/protocol/protocol_frame.c firmware/components/protocol/test_host/test_protocol_frame.c && /tmp/test_protocol_frame`
Expected: `All tests passed.` (this exact command was run during plan authoring — 6/6 checks passed, 0 compiler warnings under `-Wall -Wextra`)

- [ ] **Step 6: Add the ESP-IDF component registration (build-system only, not exercised by the host test)**

```cmake
# firmware/components/protocol/CMakeLists.txt
idf_component_register(
    SRCS "protocol_frame.c"
    INCLUDE_DIRS "include"
)
```

- [ ] **Step 7: Commit**

```bash
git add firmware/components/protocol/
git commit -m "feat(firmware): add host-testable protocol frame encode/decode"
```

---

### Task 2: ESP-IDF project scaffolding

**Files:**
- Create: `firmware/CMakeLists.txt`
- Create: `firmware/sdkconfig.defaults`
- Create: `firmware/main/CMakeLists.txt`
- Create: `firmware/main/main.c`

**Interfaces:**
- Consumes: nothing yet (this task only proves the project builds and boots)
- Produces: a buildable, flashable ESP-IDF project skeleton that later tasks add to

- [ ] **Step 1: Create the top-level project file**

```cmake
# firmware/CMakeLists.txt
cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(office_plant_node)
```

- [ ] **Step 2: Create sdkconfig defaults**

```
# firmware/sdkconfig.defaults
CONFIG_IDF_TARGET="esp32c6"
CONFIG_IEEE802154_ENABLED=y
```

- [ ] **Step 3: Create the main component registration**

```cmake
# firmware/main/CMakeLists.txt
idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    REQUIRES protocol
)
```

- [ ] **Step 4: Create a minimal main.c**

```c
// firmware/main/main.c
#include "esp_log.h"

static const char *TAG = "main";

void app_main(void) {
    ESP_LOGI(TAG, "M1 firmware boot");
}
```

- [ ] **Step 5: Build (requires ESP-IDF installed — not run in this authoring environment)**

Run: `cd firmware && idf.py set-target esp32c6 && idf.py build`
Expected: build succeeds with no errors. If `idf.py` is not found, install ESP-IDF first (`https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/get-started/`) — that installation step is a one-time environment prerequisite, not part of this plan.

- [ ] **Step 6: Commit**

```bash
git add firmware/CMakeLists.txt firmware/sdkconfig.defaults firmware/main/
git commit -m "feat(firmware): add ESP-IDF project scaffolding for esp32c6"
```

---

### Task 3: Deep sleep and RTC-timer wake

**Files:**
- Create: `firmware/main/sleep_wake.h`
- Create: `firmware/main/sleep_wake.c`
- Modify: `firmware/main/main.c`

**Interfaces:**
- Produces: `void sleep_wake_log_boot(void)` — logs the wakeup cause and an RTC-persisted boot counter
- Produces: `void sleep_wake_go_to_sleep(uint32_t seconds)` — enters deep sleep for `seconds`; does not return

- [ ] **Step 1: Write sleep_wake.h**

```c
// firmware/main/sleep_wake.h
#ifndef SLEEP_WAKE_H
#define SLEEP_WAKE_H

#include <stdint.h>

void sleep_wake_log_boot(void);
void sleep_wake_go_to_sleep(uint32_t seconds);

#endif
```

- [ ] **Step 2: Implement sleep_wake.c**

```c
// firmware/main/sleep_wake.c
#include "sleep_wake.h"
#include <inttypes.h>
#include "esp_sleep.h"
#include "esp_log.h"

static const char *TAG = "sleep_wake";

/* ESP32-C6 only has RTC FAST memory, so RTC_DATA_ATTR is the correct
 * attribute to persist this counter across deep sleep (confirmed against
 * esp_sleep.h's ESP32-C6-specific documentation). */
RTC_DATA_ATTR static uint32_t s_boot_count = 0;

void sleep_wake_log_boot(void) {
    s_boot_count++;
    esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
    ESP_LOGI(TAG, "boot #%" PRIu32 ", wakeup cause = %d", s_boot_count, (int)cause);
}

void sleep_wake_go_to_sleep(uint32_t seconds) {
    ESP_LOGI(TAG, "sleeping for %" PRIu32 " seconds", seconds);
    esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
    esp_deep_sleep_start();
}
```

- [ ] **Step 3: Wire into main.c**

```c
// firmware/main/main.c — replace the body of app_main
#include "esp_log.h"
#include "sleep_wake.h"

static const char *TAG = "main";

#define TEST_WAKE_INTERVAL_SEC 30  /* short interval for M1 bench observation;
                                       production interval is set by the hub
                                       at pairing time (M4), not hardcoded. */

void app_main(void) {
    sleep_wake_log_boot();
    ESP_LOGI(TAG, "M1 firmware boot");
    sleep_wake_go_to_sleep(TEST_WAKE_INTERVAL_SEC);
}
```

- [ ] **Step 4: Flash and observe (requires real hardware — not run in this authoring environment)**

Run: `cd firmware && idf.py -p <PORT> flash monitor`
Expected: log line `boot #1, wakeup cause = 0` (cause 0 = `ESP_SLEEP_WAKEUP_UNDEFINED`, i.e. power-on reset) on first boot, then the device sleeps; after ~30s it wakes again and logs `boot #2, wakeup cause = <timer-wakeup-value>`, confirming the RTC-persisted counter survives deep sleep and the timer wakeup fires. Press Ctrl+] to exit the monitor.

- [ ] **Step 5: Commit**

```bash
git add firmware/main/sleep_wake.h firmware/main/sleep_wake.c firmware/main/main.c
git commit -m "feat(firmware): add deep sleep and RTC timer wake"
```

---

### Task 4: Moisture sensor ADC read

**Files:**
- Create: `firmware/main/moisture_sensor.h`
- Create: `firmware/main/moisture_sensor.c`
- Modify: `firmware/main/main.c`

**Interfaces:**
- Produces: `void moisture_sensor_init(void)`
- Produces: `int moisture_sensor_read_raw(void)` — returns the raw ADC count (0-4095 at 12-bit default width)
- Produces: `void moisture_sensor_deinit(void)`

- [ ] **Step 1: Write moisture_sensor.h**

```c
// firmware/main/moisture_sensor.h
#ifndef MOISTURE_SENSOR_H
#define MOISTURE_SENSOR_H

#include "hal/adc_types.h"

/* ADC1 channel 0 is GPIO0 on ESP32-C6 (confirmed against
 * soc/esp32c6/include/soc/adc_channel.h). */
#define MOISTURE_SENSOR_ADC_CHANNEL ADC_CHANNEL_0

void moisture_sensor_init(void);
int moisture_sensor_read_raw(void);
void moisture_sensor_deinit(void);

#endif
```

- [ ] **Step 2: Implement moisture_sensor.c**

```c
// firmware/main/moisture_sensor.c
#include "moisture_sensor.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_err.h"
#include "esp_log.h"

static const char *TAG = "moisture_sensor";
static adc_oneshot_unit_handle_t s_adc_handle = NULL;

void moisture_sensor_init(void) {
    adc_oneshot_unit_init_cfg_t init_config = {
        .unit_id = ADC_UNIT_1,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&init_config, &s_adc_handle));

    adc_oneshot_chan_cfg_t chan_config = {
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .atten = ADC_ATTEN_DB_12,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(s_adc_handle, MOISTURE_SENSOR_ADC_CHANNEL, &chan_config));
}

int moisture_sensor_read_raw(void) {
    int raw = 0;
    ESP_ERROR_CHECK(adc_oneshot_read(s_adc_handle, MOISTURE_SENSOR_ADC_CHANNEL, &raw));
    ESP_LOGI(TAG, "raw ADC reading: %d", raw);
    return raw;
}

void moisture_sensor_deinit(void) {
    adc_oneshot_del_unit(s_adc_handle);
    s_adc_handle = NULL;
}
```

- [ ] **Step 3: Wire into main.c**

```c
// firmware/main/main.c — add sensor read before sleeping
#include "esp_log.h"
#include "sleep_wake.h"
#include "moisture_sensor.h"

static const char *TAG = "main";

#define TEST_WAKE_INTERVAL_SEC 30

void app_main(void) {
    sleep_wake_log_boot();

    moisture_sensor_init();
    int raw = moisture_sensor_read_raw();
    moisture_sensor_deinit();
    ESP_LOGI(TAG, "moisture raw = %d", raw);

    sleep_wake_go_to_sleep(TEST_WAKE_INTERVAL_SEC);
}
```

- [ ] **Step 4: Flash and observe with the sensor in open air, then in water (requires real hardware)**

Run: `cd firmware && idf.py -p <PORT> flash monitor`
Expected: `moisture raw = <value>` logs each wake cycle. Note the raw value with the sensor in open air (dry baseline) and with the sensing tip in a glass of water (wet baseline) — these two numbers are the calibration input for the `needs_water` threshold used in Task 6; there is no way to know them in advance of the actual sensor hardware, so this step's output is a required input to Task 6, not a gap in this plan.

- [ ] **Step 5: Commit**

```bash
git add firmware/main/moisture_sensor.h firmware/main/moisture_sensor.c firmware/main/main.c
git commit -m "feat(firmware): add moisture sensor ADC read"
```

---

### Task 5: 802.15.4 radio init, send, and receive

**Files:**
- Create: `firmware/main/ieee802154_radio.h`
- Create: `firmware/main/ieee802154_radio.c`

**Interfaces:**
- Consumes: `PROTOCOL_FRAME_MAX_LEN` from `protocol_frame.h`
- Produces: `RADIO_CHANNEL`=25, `RADIO_PAN_ID`=0x4F50, `RADIO_TX_POWER_DBM`=0 (constants)
- Produces: `void ieee802154_radio_init(uint16_t short_address)`
- Produces: `void ieee802154_radio_send(const uint8_t *frame, uint8_t frame_len)` — `frame`/`frame_len` are a pre-encoded buffer from `encode_*_frame`
- Produces: `bool ieee802154_radio_receive(uint8_t *out_buf, uint8_t *out_len, int8_t *out_rssi, uint32_t timeout_ms)` — polls a queue fed by the receive-done callback; returns `false` on timeout

- [ ] **Step 1: Write ieee802154_radio.h**

```c
// firmware/main/ieee802154_radio.h
#ifndef IEEE802154_RADIO_H
#define IEEE802154_RADIO_H

#include <stdint.h>
#include <stdbool.h>

#define RADIO_CHANNEL      25
#define RADIO_PAN_ID       0x4F50
#define RADIO_TX_POWER_DBM 0

/* Enables the radio, sets channel/PAN ID/short address/tx power, enables
 * promiscuous mode (required — our frames don't use standard 802.15.4
 * addressing, which the hardware filter would otherwise drop), registers
 * callbacks, and starts listening. */
void ieee802154_radio_init(uint16_t short_address);

/* Transmits a pre-encoded protocol frame (from encode_*_frame in
 * protocol_frame.h). */
void ieee802154_radio_send(const uint8_t *frame, uint8_t frame_len);

/* Polls for a received frame. Returns true and fills out_buf/out_len/out_rssi
 * if one arrived within timeout_ms, false on timeout. */
bool ieee802154_radio_receive(uint8_t *out_buf, uint8_t *out_len, int8_t *out_rssi, uint32_t timeout_ms);

#endif
```

- [ ] **Step 2: Implement ieee802154_radio.c**

```c
// firmware/main/ieee802154_radio.c
#include "ieee802154_radio.h"
#include <string.h>
#include "protocol_frame.h"
#include "esp_ieee802154.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

static const char *TAG = "ieee802154_radio";

typedef struct {
    uint8_t len;
    uint8_t data[PROTOCOL_FRAME_MAX_LEN];
    int8_t rssi;
} radio_rx_item_t;

static QueueHandle_t s_rx_queue = NULL;

/* Registered via esp_ieee802154_event_callback_list_register — this is the
 * pattern ESP-IDF's own OpenThread radio port uses (confirmed by reading
 * components/openthread/src/port/esp_openthread_radio.c). We do NOT define a
 * function literally named esp_ieee802154_receive_done; that's a separate,
 * legacy weak-symbol mechanism this plan does not use. */
static void radio_on_receive_done(uint8_t *frame, esp_ieee802154_frame_info_t *frame_info) {
    /* frame[0] is the PHY length byte (payload + 2-byte hw-appended FCS);
     * frame[1..] is our protocol payload. */
    uint8_t payload_len = frame[0] - 2;
    if (payload_len > PROTOCOL_FRAME_MAX_LEN) {
        payload_len = PROTOCOL_FRAME_MAX_LEN;
    }
    radio_rx_item_t item;
    item.len = payload_len;
    memcpy(item.data, frame + 1, payload_len);
    item.rssi = frame_info->rssi;

    BaseType_t higher_priority_task_woken = pdFALSE;
    xQueueSendFromISR(s_rx_queue, &item, &higher_priority_task_woken);
    if (higher_priority_task_woken) {
        portYIELD_FROM_ISR();
    }
}

static void radio_on_transmit_done(const uint8_t *frame, const uint8_t *ack, esp_ieee802154_frame_info_t *ack_frame_info) {
    (void)frame; (void)ack; (void)ack_frame_info;
    ESP_LOGD(TAG, "transmit done");
}

static void radio_on_transmit_failed(const uint8_t *frame, esp_ieee802154_tx_error_t error) {
    (void)frame;
    ESP_LOGW(TAG, "transmit failed, error=%d", (int)error);
}

void ieee802154_radio_init(uint16_t short_address) {
    s_rx_queue = xQueueCreate(8, sizeof(radio_rx_item_t));

    esp_ieee802154_event_cb_list_t cb_list = {
        .rx_done_cb = radio_on_receive_done,
        .tx_done_cb = radio_on_transmit_done,
        .tx_failed_cb = radio_on_transmit_failed,
    };
    ESP_ERROR_CHECK(esp_ieee802154_event_callback_list_register(cb_list));

    ESP_ERROR_CHECK(esp_ieee802154_enable());
    ESP_ERROR_CHECK(esp_ieee802154_set_promiscuous(true));
    ESP_ERROR_CHECK(esp_ieee802154_set_channel(RADIO_CHANNEL));
    ESP_ERROR_CHECK(esp_ieee802154_set_panid(RADIO_PAN_ID));
    ESP_ERROR_CHECK(esp_ieee802154_set_short_address(short_address));
    ESP_ERROR_CHECK(esp_ieee802154_set_txpower(RADIO_TX_POWER_DBM));
    ESP_ERROR_CHECK(esp_ieee802154_receive());

    ESP_LOGI(TAG, "radio ready: channel=%d panid=0x%04x addr=0x%04x",
             RADIO_CHANNEL, RADIO_PAN_ID, short_address);
}

void ieee802154_radio_send(const uint8_t *frame, uint8_t frame_len) {
    uint8_t tx_buf[1 + PROTOCOL_FRAME_MAX_LEN];
    tx_buf[0] = frame_len + 2; /* PHY length: payload + 2-byte hw-appended FCS */
    memcpy(tx_buf + 1, frame, frame_len);
    esp_err_t err = esp_ieee802154_transmit(tx_buf, false);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "transmit request failed: %d", (int)err);
    }
}

bool ieee802154_radio_receive(uint8_t *out_buf, uint8_t *out_len, int8_t *out_rssi, uint32_t timeout_ms) {
    radio_rx_item_t item;
    if (xQueueReceive(s_rx_queue, &item, pdMS_TO_TICKS(timeout_ms)) != pdTRUE) {
        return false;
    }
    memcpy(out_buf, item.data, item.len);
    *out_len = item.len;
    *out_rssi = item.rssi;
    return true;
}
```

- [ ] **Step 3: Update main component's CMakeLists to require the freertos queue headers (already part of ESP-IDF's default `freertos` component — no new REQUIRES needed) — no file change needed, this step is a no-op confirmation**

Verify `firmware/main/CMakeLists.txt` still reads exactly as Task 2 left it (`REQUIRES protocol`) — FreeRTOS is a default dependency of every ESP-IDF component and needs no explicit `REQUIRES` entry.

- [ ] **Step 4: Note for M2 — do not wire this into main.c yet**

M1's stated goal (spec Section 8) is "radio init/send" as a proof-of-life, not a two-way exchange — that's M2's job once a second physical node exists to receive. Task 6 sends one `DATA` frame per wake cycle using this module; receiving is exercised for real starting in M2.

- [ ] **Step 5: Commit**

```bash
git add firmware/main/ieee802154_radio.h firmware/main/ieee802154_radio.c
git commit -m "feat(firmware): add 802.15.4 raw radio init/send/receive module"
```

---

### Task 6: Full integration and power measurement

**Files:**
- Modify: `firmware/main/main.c`

**Interfaces:**
- Consumes: everything produced by Tasks 1, 3, 4, 5

- [ ] **Step 1: Wire the full wake → sense → send → sleep cycle**

```c
// firmware/main/main.c — final version
#include "esp_log.h"
#include "sleep_wake.h"
#include "moisture_sensor.h"
#include "ieee802154_radio.h"
#include "protocol_frame.h"

static const char *TAG = "main";

#define TEST_NODE_SHORT_ADDRESS 0x0001
#define TEST_WAKE_INTERVAL_SEC  30

/* Placeholder threshold: roughly the midpoint of the 12-bit ADC range
 * (0-4095). Task 4, Step 4 logs real dry/wet raw values from the actual
 * sensor hardware — replace this constant with the midpoint between those
 * two measured values once available. This is a calibration input from
 * real hardware, not an unresolved design decision: the code path, the
 * logging, and the comparison are all fully specified now. */
#define MOISTURE_DRY_THRESHOLD_RAW 2000

void app_main(void) {
    sleep_wake_log_boot();

    moisture_sensor_init();
    int raw = moisture_sensor_read_raw();
    moisture_sensor_deinit();

    ieee802154_radio_init(TEST_NODE_SHORT_ADDRESS);

    data_frame_t reading = {
        .sender_id = TEST_NODE_SHORT_ADDRESS,
        .needs_water = (raw < MOISTURE_DRY_THRESHOLD_RAW) ? NEEDS_WATER_TRUE : NEEDS_WATER_FALSE,
        .battery_pct = 100, /* battery-voltage ADC channel is out of scope for M1 */
        .timestamp = 0,     /* real clock sync arrives with the hub in M3/M4 */
    };
    uint8_t buf[PROTOCOL_FRAME_MAX_LEN];
    size_t len = encode_data_frame(&reading, buf);
    ieee802154_radio_send(buf, (uint8_t)len);
    ESP_LOGI(TAG, "sent DATA frame: raw=%d needs_water=%d", raw, reading.needs_water);

    sleep_wake_go_to_sleep(TEST_WAKE_INTERVAL_SEC);
}
```

- [ ] **Step 2: Flash and confirm the full cycle logs correctly (requires real hardware)**

Run: `cd firmware && idf.py -p <PORT> flash monitor`
Expected: each ~30s cycle logs boot count, raw moisture, the DATA frame being sent, then re-enters deep sleep. Confirms Tasks 3-5 integrate without conflicting over shared resources (radio + ADC + sleep).

- [ ] **Step 3: Measure real power draw (physical multimeter procedure — this is M1's stated acceptance test per spec Section 8)**

1. Put a multimeter in series between the battery and the board (current/µA range).
2. Record the current during deep sleep (expect single-digit-to-low-double-digit µA per the ESP32-C6 datasheet; if measured draw is far higher, check that no peripheral is left enabled before `esp_deep_sleep_start()` — the ADC and radio are explicitly deinitialized/left idle by this task's code before sleep).
3. Record the peak current during the active phase (moisture read + radio transmit), which will be on the order of tens of mA for a fraction of a second.
4. Using the two numbers and the wake frequency the spec assumes (1-2x/day, Section 4.1), compute average daily energy draw and compare it against the solar/battery sizing assumption in spec Section 3. Record the result — this is the real-world input that Task M6 (hardware finalization) needs and cannot fabricate today.

- [ ] **Step 4: Commit**

```bash
git add firmware/main/main.c
git commit -m "feat(firmware): integrate sleep/sensor/radio into full M1 wake cycle"
```
