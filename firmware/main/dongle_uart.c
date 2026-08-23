#include "dongle_uart.h"
#include <stdio.h>
#include "driver/uart.h"
#include "protocol_frame.h"

#define DONGLE_UART_PORT UART_NUM_1
/* Bench-only pin choice, not yet verified against a specific Pi wiring —
 * whoever wires the physical dongle<->Pi link (M3 Task 5's bench test)
 * should confirm/adjust these against the real board, same status as M1's
 * GPIO0 boot-strap caveat (see developer-setup.md Section 6). */
#define DONGLE_UART_TX_GPIO 4
#define DONGLE_UART_RX_GPIO 5
#define DONGLE_UART_BAUD_RATE 115200
#define DONGLE_UART_DRIVER_RX_BUF_SIZE 256
#define DONGLE_UART_LINE_MAX_LEN 64

static char s_line_buf[DONGLE_UART_LINE_MAX_LEN];
static size_t s_line_len = 0;

void dongle_uart_init(void) {
    uart_config_t uart_config = {
        .baud_rate = DONGLE_UART_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(DONGLE_UART_PORT, DONGLE_UART_DRIVER_RX_BUF_SIZE, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(DONGLE_UART_PORT, &uart_config));
    ESP_ERROR_CHECK(uart_set_pin(DONGLE_UART_PORT, DONGLE_UART_TX_GPIO, DONGLE_UART_RX_GPIO,
                                  UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
}

static void hex_encode(const uint8_t *data, uint8_t len, char *out) {
    static const char digits[] = "0123456789abcdef";
    for (uint8_t i = 0; i < len; i++) {
        out[i * 2] = digits[(data[i] >> 4) & 0xF];
        out[i * 2 + 1] = digits[data[i] & 0xF];
    }
    out[len * 2] = '\0';
}

static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int hex_decode(const char *hex, size_t hex_len, uint8_t *out, size_t out_max) {
    if (hex_len == 0 || hex_len % 2 != 0) {
        return -1;
    }
    size_t out_len = hex_len / 2;
    if (out_len > out_max) {
        return -1;
    }
    for (size_t i = 0; i < out_len; i++) {
        int hi = hex_nibble(hex[i * 2]);
        int lo = hex_nibble(hex[i * 2 + 1]);
        if (hi < 0 || lo < 0) {
            return -1;
        }
        out[i] = (uint8_t)((hi << 4) | lo);
    }
    return (int)out_len;
}

void dongle_uart_send_rx_line(const uint8_t *frame, uint8_t frame_len, int8_t rssi) {
    char hex[PROTOCOL_FRAME_MAX_LEN * 2 + 1];
    hex_encode(frame, frame_len, hex);

    char line[16 + sizeof(hex)];
    int n = snprintf(line, sizeof(line), "RX %s %d\n", hex, rssi);
    uart_write_bytes(DONGLE_UART_PORT, line, n);
}

/* Parses one complete line (without the trailing '\n') already assembled in
 * s_line_buf. Only "TX <hex>" is recognized — the dongle has no opinion
 * about frame semantics, per the M3 plan's protocol decision; anything else
 * is silently dropped. */
static bool parse_tx_line(const char *line, size_t len, uint8_t *out_buf, uint8_t *out_len) {
    if (len < 4 || line[0] != 'T' || line[1] != 'X' || line[2] != ' ') {
        return false;
    }
    int decoded_len = hex_decode(line + 3, len - 3, out_buf, PROTOCOL_FRAME_MAX_LEN);
    if (decoded_len <= 0) {
        return false;
    }
    *out_len = (uint8_t)decoded_len;
    return true;
}

bool dongle_uart_poll_tx_frame(uint8_t *out_buf, uint8_t *out_len) {
    uint8_t byte;
    while (uart_read_bytes(DONGLE_UART_PORT, &byte, 1, 0) == 1) {
        if (byte == '\n') {
            bool got_frame = parse_tx_line(s_line_buf, s_line_len, out_buf, out_len);
            s_line_len = 0;
            if (got_frame) {
                return true;
            }
            continue;
        }
        if (s_line_len < sizeof(s_line_buf) - 1) {
            s_line_buf[s_line_len++] = (char)byte;
        }
        /* else: line too long — drop the excess byte; the line is discarded
         * as garbage once '\n' finally arrives (parse_tx_line's prefix/
         * length checks reject it). */
    }
    return false;
}
