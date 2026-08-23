#ifndef DONGLE_UART_H
#define DONGLE_UART_H

#include <stdint.h>
#include <stdbool.h>

/* Configures a secondary UART for the dongle<->Pi line protocol (M3 plan,
 * "Decision: dongle <-> Pi serial protocol"). Deliberately not UART0/the
 * console — that stays free for idf.py flash/monitor and ESP_LOG output,
 * separate from the application data link to the Pi. */
void dongle_uart_init(void);

/* Writes "RX <hex-encoded frame> <rssi>\n" for one received mesh frame. */
void dongle_uart_send_rx_line(const uint8_t *frame, uint8_t frame_len, int8_t rssi);

/* Non-blocking: drains any bytes currently buffered on the UART, assembling
 * '\n'-terminated lines. If a complete "TX <hex>" line was parsed on this
 * call, decodes it into out_buf/out_len and returns true; otherwise returns
 * false without blocking. Call once per root_main_run loop iteration. */
bool dongle_uart_poll_tx_frame(uint8_t *out_buf, uint8_t *out_len);

#endif
