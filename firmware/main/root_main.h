#ifndef ROOT_MAIN_H
#define ROOT_MAIN_H

/* Runs the root role forever: continuous radio (no deep-sleep cycling —
 * this bench role previews M3's mains-powered hub-radio dongle), beaconing
 * hop_count=0 on a fixed interval and logging every received frame. Does
 * not return. */
void root_main_run(void);

#endif
