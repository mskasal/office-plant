#include "root_main.h"
#include "leaf_main.h"

/* NODE_IS_ROOT is injected as a compile definition by
 * firmware/main/CMakeLists.txt from the NODE_IS_ROOT CMake cache variable
 * (idf.py build -DNODE_IS_ROOT=1 for the root board, omitted/0 for leaf —
 * see firmware/main/CMakeLists.txt and the M2 plan's "Role selection"
 * section). This bench-only flag is scoped to M2's two-board test; M5's
 * real deployment uses M4's provisioning-assigned addressing instead. */
void app_main(void) {
#if NODE_IS_ROOT
    root_main_run();
#else
    leaf_main_run();
#endif
}
