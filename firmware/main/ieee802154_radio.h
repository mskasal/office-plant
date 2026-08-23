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
