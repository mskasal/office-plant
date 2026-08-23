#ifndef MESH_PARENT_SELECT_H
#define MESH_PARENT_SELECT_H

#include <stdint.h>
#include <stddef.h>

typedef struct {
    uint16_t sender_id;
    uint8_t hop_count;
    int8_t rssi;
} parent_candidate_t;

/* Mirrors sim/protocol.py's select_parent: lowest hop_count wins, ties
 * broken by highest rssi. Returns the winning candidate's sender_id, or -1
 * if candidates is empty. */
int select_parent(const parent_candidate_t *candidates, size_t count);

#endif
