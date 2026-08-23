#ifndef PAIRING_MODE_H
#define PAIRING_MODE_H

/* Runs the pairing-mode loop for a factory-unclaimed node: periodically
 * announces itself, listens frequently for BLINK/CLAIM frames (per the M4
 * plan's "wakes frequently... e.g. 500ms every 2s" pairing-mode behavior),
 * blinks an LED on a BLINK targeting this node's factory ID, and persists
 * identity + returns on a valid CLAIM.
 *
 * Returns once claimed (caller should then run the normal scheduled
 * cycle); loops forever otherwise. */
void pairing_mode_run(void);

#endif
