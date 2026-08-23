#include "mesh_parent_select.h"

int select_parent(const parent_candidate_t *candidates, size_t count) {
    if (count == 0) {
        return -1;
    }

    const parent_candidate_t *best = &candidates[0];
    for (size_t i = 1; i < count; i++) {
        const parent_candidate_t *c = &candidates[i];
        if (c->hop_count < best->hop_count ||
            (c->hop_count == best->hop_count && c->rssi > best->rssi)) {
            best = c;
        }
    }
    return best->sender_id;
}
