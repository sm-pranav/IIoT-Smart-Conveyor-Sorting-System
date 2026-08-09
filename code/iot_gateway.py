# =============================================================
#  IIoT Smart Conveyor Sorting System - IoT Gateway
#
#  Reads DB1 from the Siemens PLC (PLCSIM) over S7 protocol.
#
#  Requires: pip install python-snap7
# =============================================================

import json
import time

import snap7
from snap7.client import Client
from snap7.util import get_int, get_dint, get_real, get_bool

PLC_IP   = "127.0.0.1"
PLC_RACK = 0
PLC_SLOT = 1
DB_NUMBER = 1
DB_SIZE   = 32

POLL_PERIOD = 2.0

MODE_TEXT  = {0: "STOP", 1: "AUTO", 2: "MANUAL", 3: "FAULT"}
ALARM_TEXT = {
    0: "No active alarms",
    1: "EMERGENCY STOP pressed",
    2: "CONVEYOR JAM at sorting junction",
    3: "SENSOR FAULT (multiple size sensors active)",
}


def connect_plc():
    client = Client()
    while True:
        try:
            print(f"[PLC ] Connecting to {PLC_IP} rack {PLC_RACK} slot {PLC_SLOT} ...")
            client.connect(PLC_IP, PLC_RACK, PLC_SLOT)
            if client.get_connected():
                print("[PLC ] Connected.")
                return client
        except Exception as exc:
            print(f"[PLC ] Not ready ({exc}). Retry in 3s ...")
        time.sleep(3)


def read_plc(client):
    data = client.db_read(DB_NUMBER, 0, DB_SIZE)
    mode_val  = get_int(data, 24)
    alarm_val = get_int(data, 28)
    return {
        "total":          get_int(data, 0),
        "lane1":          get_int(data, 2),
        "lane2":          get_int(data, 4),
        "lane3":          get_int(data, 6),
        "reject":         get_int(data, 8),
        "oee":            round(get_real(data, 10), 1),
        "throughput":     round(get_real(data, 14), 1),
        "uptime":         get_dint(data, 18),
        "speed":          get_int(data, 22),
        "mode":           MODE_TEXT.get(mode_val, "?"),
        "motor_running":  get_bool(data, 26, 0),
        "alarm_active":   get_bool(data, 26, 1),
        "jam":            get_bool(data, 26, 2),
        "sorting_small":  get_bool(data, 26, 4),
        "sorting_medium": get_bool(data, 26, 5),
        "sorting_large":  get_bool(data, 26, 6),
        "estop":          get_bool(data, 26, 7),
        "object_present": get_bool(data, 27, 0),
        "alarm_code":     alarm_val,
        "alarm_text":     ALARM_TEXT.get(alarm_val, "Unknown alarm"),
    }


def build_activity(sample):
    if sample["sorting_small"]:
        return "Sorting SMALL -> Lane 1"
    if sample["sorting_medium"]:
        return "Sorting MEDIUM -> Lane 2"
    if sample["sorting_large"]:
        return "Sorting LARGE -> Lane 3"
    if sample["object_present"]:
        return "Object detected at entry"
    if sample["motor_running"]:
        return "Conveyor running - waiting for parts"
    return "Conveyor stopped"


def main():
    plc = connect_plc()
    try:
        while True:
            try:
                sample = read_plc(plc)
                sample["activity"] = build_activity(sample)
                flag = "ALARM" if sample["alarm_active"] else "ok   "
                print(f"[DATA] {flag} mode={sample['mode']:<6} "
                      f"total={sample['total']:<4} "
                      f"L1={sample['lane1']} L2={sample['lane2']} "
                      f"L3={sample['lane3']} rej={sample['reject']} "
                      f"oee={sample['oee']}% tp={sample['throughput']}ppm")
            except Exception as exc:
                print(f"[PLC ] Read error: {exc}. Reconnecting ...")
                try: plc.disconnect()
                except: pass
                plc = connect_plc()
            time.sleep(POLL_PERIOD)
    except KeyboardInterrupt:
        print("\nStopping ...")
    finally:
        try: plc.disconnect()
        except: pass


if __name__ == "__main__":
    main()
