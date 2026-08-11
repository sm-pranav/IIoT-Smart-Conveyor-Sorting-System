# =============================================================
#  IIoT Smart Conveyor Sorting System - IoT Gateway
#
#  Reads DB1 from the Siemens PLC (PLCSIM) over S7 protocol,
#  publishes telemetry as JSON to MQTT.
#
#  Requires: pip install python-snap7 paho-mqtt
# =============================================================

import json
import time
import uuid

import snap7
from snap7.client import Client
from snap7.util import get_int, get_dint, get_real, get_bool
import paho.mqtt.client as mqtt

PLC_IP   = "127.0.0.1"
PLC_RACK = 0
PLC_SLOT = 1
DB_NUMBER = 1
DB_SIZE   = 32

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT   = 1883
PUBLISH_PERIOD = 2.0

SESSION_ID = "demo01"
TOPIC_TELEMETRY = f"iiot/conveyor/{SESSION_ID}/telemetry"

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
        "session":        SESSION_ID,
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
        "ts":             int(time.time()),
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


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_BROKER}")
    else:
        print(f"[MQTT] Connect failed (rc={rc})")


def main():
    print("=" * 55)
    print("  IIoT Conveyor Gateway  (S7 -> MQTT)")
    print("=" * 55)

    plc = connect_plc()

    client_id = f"conveyor-gw-{uuid.uuid4().hex[:6]}"
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        mq = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION1,
                         client_id=client_id)
    except ImportError:
        mq = mqtt.Client(client_id=client_id)

    mq.on_connect = on_connect
    mq.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
    mq.loop_start()

    try:
        while True:
            try:
                sample = read_plc(plc)
                sample["activity"] = build_activity(sample)
                mq.publish(TOPIC_TELEMETRY, json.dumps(sample))

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
            time.sleep(PUBLISH_PERIOD)
    except KeyboardInterrupt:
        print("\n[EXIT] Stopping ...")
    finally:
        mq.loop_stop()
        mq.disconnect()
        try: plc.disconnect()
        except: pass
        print("[EXIT] Done.")


if __name__ == "__main__":
    main()
