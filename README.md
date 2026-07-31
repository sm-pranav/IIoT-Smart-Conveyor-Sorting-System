# IIoT Smart Conveyor Sorting System

A size-based conveyor sorter on a Siemens S7-1200 PLC, with a Python gateway that reads production data over S7 and streams it to a browser dashboard via MQTT. Runs on one laptop using PLCSIM.

## Architecture

```
   TIA Portal -> PLCSIM (PLC simulator)
        | S7 protocol (TCP 102)
   iot_gateway.py (python-snap7)
        | MQTT
   broker.hivemq.com
        | WebSocket (WSS 8884)
   dashboard.html (browser)
```

## What it does

- Latching start/stop motor control with E-Stop
- Three-lane size-based sorting with pulse timers
- Live KPIs: OEE, throughput, belt speed, uptime
- Alarms: jam detection, E-Stop, sensor fault
- Analog belt-speed output to VFD (0-10V)

## Tech stack

| Component | Detail |
|:--|:--|
| PLC | Siemens S7-1200, CPU 1214C DC/DC/DC |
| Software | TIA Portal V18, S7-PLCSIM V18 |
| PLC languages | Ladder + Structured Text (IEC 61131-3) |
| Gateway | Python 3.10+, python-snap7, paho-mqtt |
| Dashboard | HTML/CSS/JS, mqtt.js CDN |

## Author
Pranav S M
