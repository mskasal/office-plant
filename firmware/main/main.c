#include "esp_system.h"
#include "root_main.h"
#include "leaf_main.h"
#include "pairing_mode.h"
#include "node_identity.h"
#include "factory_reset_button.h"

/* NODE_IS_ROOT is injected as a compile definition by
 * firmware/main/CMakeLists.txt from the NODE_IS_ROOT CMake cache variable
 * (idf.py build -DNODE_IS_ROOT=1 for the root board, omitted/0 for leaf —
 * see firmware/main/CMakeLists.txt and the M2 plan's "Role selection"
 * section). This bench-only flag is scoped to M2's two-board test; M5's
 * real multi-node deployment uses real addressing throughout. */
void app_main(void) {
    node_identity_init();
    factory_reset_button_enable_wakeup();

    /* A press-triggered wake (the leaf's deep-sleep cycle, not pairing
     * mode's continuous loop — see pairing_mode.c) needs its hold
     * re-confirmed before acting, so a brief bump that merely woke the
     * radio doesn't wipe a real claim. */
    if (factory_reset_button_caused_wakeup() && factory_reset_button_confirm_long_press()) {
        node_identity_factory_reset();
        esp_restart();
    }

#if NODE_IS_ROOT
    root_main_run();
#else
    if (!node_identity_is_claimed()) {
        pairing_mode_run();
    }
    leaf_main_run();
#endif
}
