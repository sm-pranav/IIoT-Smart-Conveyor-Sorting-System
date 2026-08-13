# =============================================================
#  IIoT Smart Conveyor Sorting System - IoT Gateway
#
#  Reads DB1 from the Siemens PLC (PLCSIM) over S7 protocol,
#  publishes telemetry as JSON to MQTT, and forwards dashboard
#  commands back to the PLC.
#
#  Requires: pip install python-snap7 paho-mqtt
# =============================================================

import json
import time
import uuid

import snap7
from snap7.client import Client
from snap7.util import get_int, get_dint, get_real, get_bool, set_bool
import paho.mqtt.client as mqtt

# -------------------------------------------------------------
#  CONFIGURATION  (edit these if needed)
# -------------------------------------------------------------
PLC_IP   = "127.0.0.1"     # PLCSIM on this machine
PLC_RACK = 0
PLC_SLOT = 1
DB_NUMBER = 1              # "ConveyorData"
DB_SIZE   = 32             # bytes - matches the DB1 layout

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT   = 1883
PUBLISH_PERIOD = 2.0       # seconds between publishes

# A short session id keeps our topics private on the public broker.
# The web dashboard must use the SAME id. Change "demo01" to your own.
SESSION_ID = "demo01"
TOPIC_TELEMETRY = f"iiot/conveyor/{SESSION_ID}/telemetry"
TOPIC_COMMAND   = f"iiot/conveyor/{SESSION_ID}/cmd"

# Text lookups so the dashboard receives friendly labels
MODE_TEXT  = {0: "STOP", 1: "AUTO", 2: "MANUAL", 3: "FAULT"}
ALARM_TEXT = {
    0: "No active alarms",
    1: "EMERGENCY STOP pressed",
    2: "CONVEYOR JAM at sorting junction",
    3: "SENSOR FAULT (multiple size sensors active)",
}

# Byte offset inside DB1 where the command bits live (see the .st file)
CMD_BYTE = 30
CMD_BITS = {          # command name -> bit position in byte 30
    "start":       0,
    "stop":        1,
    "reset":       2,
    "mode_auto":   3,
    "mode_manual": 4,
}


# -------------------------------------------------------------
#  PLC HELPERS
# -------------------------------------------------------------
def connect_plc():
    """Keep trying until PLCSIM answers. Returns a connected client."""
    client = Client()
    while True:
        try:
            print(f"[PLC ] Connecting to {PLC_IP} rack {PLC_RACK} slot {PLC_SLOT} ...")
            client.connect(PLC_IP, PLC_RACK, PLC_SLOT)
            if client.get_connected():
                print("[PLC ] Connected.")
                return client
        except Exception as exc:
            print(f"[PLC ] Not ready yet ({exc}). Retrying in 3 s. "
                  f"Is PLCSIM in RUN?")
        time.sleep(3)


def read_plc(client):
    """Read DB1 and unpack the bytes into a Python dictionary.

    The offsets below MUST match the DB1 layout in
    conveyor_plc_structured_text.st.
    """
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
    """Turn the live sorting bits into one human-readable line."""
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


def pulse_command(client, name):
    """Write a short TRUE pulse to one command bit, then clear it.

    Only the command byte (30) is touched, so this never disturbs
    the rest of DB1.
    """
    bit = CMD_BITS.get(name)
    if bit is None:
        print(f"[CMD ] Ignored unknown command '{name}'")
        return

    buf = bytearray(1)
    set_bool(buf, 0, bit, True)
    client.db_write(DB_NUMBER, CMD_BYTE, buf)   # set the bit
    time.sleep(0.3)                             # hold long enough for the PLC scan
    set_bool(buf, 0, bit, False)
    client.db_write(DB_NUMBER, CMD_BYTE, buf)   # clear it
    print(f"[CMD ] Sent '{name}' to PLC.")


# -------------------------------------------------------------
#  MQTT CALLBACKS
# -------------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_BROKER}. Session id = '{SESSION_ID}'")
        client.subscribe(TOPIC_COMMAND)
        print(f"[MQTT] Listening for commands on: {TOPIC_COMMAND}")
    else:
        print(f"[MQTT] Connect failed with code {rc}")


def on_message(client, userdata, msg):
    """A command arrived from the dashboard. Forward it to the PLC."""
    plc_client = userdata["plc"]
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        command = str(payload.get("cmd", "")).lower()
        pulse_command(plc_client, command)
    except Exception as exc:
        print(f"[MQTT] Bad command message: {exc}")


# -------------------------------------------------------------
#  MAIN
# -------------------------------------------------------------
def main():
    print("=" * 55)
    print("  IIoT Conveyor Gateway  (S7 -> MQTT)")
    print("=" * 55)

    plc = connect_plc()

    # A unique MQTT client id avoids clashes on the public broker.
    client_id = f"conveyor-gw-{uuid.uuid4().hex[:6]}"

    # paho-mqtt 2.x requires a callback API version; 1.x has no such argument.
    # Importing from paho.mqtt.enums (which only exists in 2.x) lets us support BOTH.
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION1,
                                  client_id=client_id, userdata={"plc": plc})
    except ImportError:
        # paho-mqtt 1.x
        mqtt_client = mqtt.Client(client_id=client_id, userdata={"plc": plc})

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
    mqtt_client.loop_start()          # handle MQTT traffic in the background

    try:
        while True:
            try:
                sample = read_plc(plc)
                sample["activity"] = build_activity(sample)
                mqtt_client.publish(TOPIC_TELEMETRY, json.dumps(sample))

                flag = "ALARM" if sample["alarm_active"] else "ok   "
                print(f"[DATA] {flag} mode={sample['mode']:<6} "
                      f"total={sample['total']:<4} "
                      f"L1={sample['lane1']} L2={sample['lane2']} "
                      f"L3={sample['lane3']} rej={sample['reject']} "
                      f"oee={sample['oee']}% tp={sample['throughput']}ppm")
            except Exception as exc:
                # Lost the PLC (e.g. PLCSIM stopped). Reconnect and continue.
                print(f"[PLC ] Read error: {exc}. Reconnecting ...")
                try:
                    plc.disconnect()
                except Exception:
                    pass
                plc = connect_plc()
                mqtt_client.user_data_set({"plc": plc})

            time.sleep(PUBLISH_PERIOD)

    except KeyboardInterrupt:
        print("\n[EXIT] Stopping gateway ...")
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        try:
            plc.disconnect()
        except Exception:
            pass
        print("[EXIT] Clean shutdown. Bye.")


if __name__ == "__main__":
    main()
