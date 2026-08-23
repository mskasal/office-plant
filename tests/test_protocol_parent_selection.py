from sim.protocol import BeaconReceived, select_parent


def test_no_beacons_returns_none():
    assert select_parent([]) is None


def test_lowest_hop_count_wins():
    beacons = [
        BeaconReceived(sender_id=1, hop_count=2, rssi=-1.0),
        BeaconReceived(sender_id=2, hop_count=1, rssi=-9.0),
    ]
    assert select_parent(beacons) == 2


def test_tie_broken_by_best_rssi():
    beacons = [
        BeaconReceived(sender_id=1, hop_count=1, rssi=-9.0),
        BeaconReceived(sender_id=2, hop_count=1, rssi=-1.0),
    ]
    assert select_parent(beacons) == 2
