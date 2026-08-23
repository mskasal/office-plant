#ifndef LEAF_MAIN_H
#define LEAF_MAIN_H

/* Runs one leaf wake cycle: wake, listen briefly for BEACONs, select a
 * parent, JOIN it (if one was found), sense+send DATA, sleep. Always ends
 * in sleep_wake_go_to_sleep(), which does not return. */
void leaf_main_run(void);

#endif
