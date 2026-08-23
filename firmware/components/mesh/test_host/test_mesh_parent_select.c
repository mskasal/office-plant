#include <stdio.h>
#include "mesh_parent_select.h"

static int failures = 0;

#define CHECK(cond) do { \
    if (!(cond)) { \
        printf("FAIL: %s (line %d)\n", #cond, __LINE__); \
        failures++; \
    } \
} while (0)

/* Mirrors tests/test_protocol_parent_selection.py's three cases exactly. */

static void test_no_candidates_returns_negative_one(void) {
    CHECK(select_parent(NULL, 0) == -1);
}

static void test_lowest_hop_count_wins(void) {
    parent_candidate_t candidates[] = {
        { .sender_id = 1, .hop_count = 2, .rssi = -1 },
        { .sender_id = 2, .hop_count = 1, .rssi = -9 },
    };
    CHECK(select_parent(candidates, 2) == 2);
}

static void test_tie_broken_by_best_rssi(void) {
    parent_candidate_t candidates[] = {
        { .sender_id = 1, .hop_count = 1, .rssi = -9 },
        { .sender_id = 2, .hop_count = 1, .rssi = -1 },
    };
    CHECK(select_parent(candidates, 2) == 2);
}

int main(void) {
    test_no_candidates_returns_negative_one();
    test_lowest_hop_count_wins();
    test_tie_broken_by_best_rssi();

    if (failures == 0) {
        printf("All tests passed.\n");
        return 0;
    }
    printf("%d check(s) failed.\n", failures);
    return 1;
}
