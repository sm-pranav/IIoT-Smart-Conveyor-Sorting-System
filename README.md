# IIoT Smart Conveyor Sorting System

A size-based conveyor sorter running on real Siemens S7-1200 PLC code (simulated in PLCSIM), with a Python gateway that reads the PLC over the S7 protocol and streams live production data to a browser dashboard over MQTT. The whole thing runs on one laptop, no physical hardware required.

## Overview

Sorting parts by size is a routine job on a packaging or logistics line, and the thing plant managers increasingly ask for on top of it is live visibility: how many parts went where, how fast, and whether anything is jammed. This project does both. Three photoelectric sensors classify each box as small, medium, or large; a pneumatic diverter pushes it into the matching lane; and the PLC keeps the production counts, works out an OEE figure, and handles faults. A small edge gateway then publishes that data to a web dashboard and accepts a few control commands back.

I built it to show the full control-to-cloud path the way it is actually wired in industry, with the control logic living on the PLC (not faked in a script) and the monitoring layer sitting on top of it.

## What it does

- Runs the belt motor from a latching start/stop circuit. The E-Stop is wired normally closed, so a pressed button or a cut wire both drop the belt.
- Sorts into three lanes by size. Each diverter fires for a fixed two seconds using a pulse timer, which is enough to push a box off the belt even though the size sensor only sees it for an instant.
- Counts parts per lane and in total, and flags a reject when a box trips the entry sensor but no diverter fires within three seconds (an unrecognized part).
- Calculates live KPIs written into a shared data block: OEE (availability x performance x quality), throughput in parts per minute, belt speed as a percentage, and motor uptime in seconds.
- Handles three alarms: a jam (the sort-junction photo-eye blocked for more than five seconds), E-Stop, and a sensor-conflict fault (two size sensors on at once, which is physically impossible for one box). The beacon flashes at 1 Hz on any fault and the belt stops while an alarm is active.
- Drives an analog belt-speed reference to a VFD, scaled from a 0-10 V setpoint.
- Serves a browser dashboard that shows the counts, mode, OEE, throughput, uptime, alarms, and a live throughput trend, and can send Start, Stop, Reset, and mode commands back to the PLC.

## How it works

The system is split into three layers, which is how a real Industry 4.0 setup is organized:

```
   TIA Portal (laptop)
     PLC program (Ladder + SCL)  -->  PLCSIM (simulator)      control logic runs here
     WinCC HMI (optional)                                      operator screen
                    |  S7 protocol (TCP 102)
            iot_gateway.py (python-snap7)                       reads DB1, builds JSON
                    |  MQTT
            broker.hivemq.com                                   public MQTT broker
                    |  MQTT over WebSocket (wss 8884)
            dashboard.html (browser)                            live dashboard
```

Telemetry flows up: the PLC writes everything into one data block (DB1), the gateway reads that block by byte offset every two seconds, converts it to JSON, and publishes it. Control flows down: dashboard buttons publish a small JSON command, the gateway receives it and pulses the matching command bit inside DB1, and the ladder logic acts on it.

The PLC program is deliberately split by language. The discrete control (motor latch, diverting) is Ladder, because relay-style interlocks read naturally there. The arithmetic (counting, OEE, throughput, alarm evaluation) is Structured Text, because doing that math with ladder boxes is painful. Two design choices are worth calling out because they are easy to miss:

- DB1 is set to non-optimized (standard) access. snap7 reads it by byte offset, and only the classic memory layout gives fixed, predictable offsets. The variable order in DB1 is therefore fixed and documented below, and it has to match the gateway.
- Lane counting uses rising-edge detection plus an increment rather than an IEC counter block. It gives the same result and avoids depending on the exact counter instance type across TIA versions.

## Tech stack

| Component | Detail |
|:--|:--|
| PLC | Siemens S7-1200, CPU 1214C DC/DC/DC (`6ES7 214-1AG40-0XB0`) |
| Analog output | SB 1232 AQ signal board (`6ES7 232-4HA30-0XB0`), provides `QW80` |
| Engineering software | TIA Portal V18 (STEP 7 Professional, optional WinCC Basic) |
| Simulator | S7-PLCSIM V18 |
| PLC languages | Ladder (LAD) and Structured Text (SCL), IEC 61131-3 |
| Gateway | Python 3.10+, `python-snap7`, `paho-mqtt` |
| Messaging | MQTT via public broker `broker.hivemq.com` (TCP 1883 for Python, WSS 8884 for the browser) |
| Dashboard | Single HTML file, plain HTML/CSS/JS, `mqtt.js` from a CDN |

## Repository structure

```
01_Conveyor_Sorting/
├── README.md
└── code/
    ├── conveyor_plc_structured_text.st   # SCL source: DB1 + FB3 (counters/KPIs) + FB4 (alarms)
    ├── iot_gateway.py                     # reads DB1 over S7, bridges to MQTT
    └── dashboard.html                     # browser dashboard (open directly, no server)
```

The SCL file carries DB1 and the two Structured Text blocks. The two Ladder blocks (FB1, FB2), the OB1 calls, and the tag table are built in TIA Portal by hand; everything you need to recreate them is written out below.

## What you need

Software:

- TIA Portal V18 with STEP 7 Professional and S7-PLCSIM. WinCC Basic is optional (only if you want the operator panel; the dashboard does not need it).
- Python 3.10 or newer.

Python packages:

```powershell
pip install python-snap7 paho-mqtt
```

On Windows, `python-snap7` needs the native `snap7.dll`. Recent wheels bundle it. If you get a "snap7 library not found" error, download snap7 from sourceforge, take the 64-bit `snap7.dll` from `release\Windows\Win64\`, and put it next to `iot_gateway.py` or in `C:\Windows\System32`. Match the DLL bitness to your Python (64-bit with 64-bit).

No physical hardware is used. Field sensors and actuators are represented by forcing PLC inputs in PLCSIM.

## The PLC program

### I/O and memory

| Address | Tag | Meaning |
|:--|:--|:--|
| I0.0 | Start_Button | Start pushbutton |
| I0.1 | Stop_Button | Stop pushbutton |
| I0.2 | E_Stop | Emergency stop, wired normally closed (1 = healthy) |
| I0.3 | Sensor_Entry | Object entering the belt |
| I0.4 | Sensor_Small | Small-size photo-eye |
| I0.5 | Sensor_Medium | Medium-size photo-eye |
| I0.6 | Sensor_Large | Large-size photo-eye |
| I0.7 | Jam_Sensor | Photo-eye at the sort junction |
| Q0.0 | Conveyor_Motor | Belt motor |
| Q0.1 | Diverter_Lane1 | Diverter, small lane |
| Q0.2 | Diverter_Lane2 | Diverter, medium lane |
| Q0.3 | Diverter_Lane3 | Diverter, large lane |
| Q0.4 | Alarm_Beacon | Fault beacon (flashes) |
| Q0.5 | Alarm_Horn | Fault horn |
| IW64 | Speed_Setpoint | Speed pot, 0-27648 = 0-10 V |
| QW80 | VFD_Speed_Ref | VFD reference, 0-27648 = 0-10 V |
| M0.0 | Mode_Auto | AUTO mode bit |
| M0.1 | Mode_Manual | MANUAL mode bit |
| M0.2 | Mode_Fault | FAULT mode bit |
| M10.5 | Clock_1Hz | 1 Hz clock (from clock memory byte MB10) |

### Blocks

| Block | Language | Role |
|:--|:--|:--|
| OB1 (Main) | LAD | Calls FB1, FB2, FB3, FB4 every scan |
| FB1 ConveyorControl | LAD | Motor latch, mode bits, speed reference, alarm outputs |
| FB2 SortingLogic | LAD | Two-second diverter pulse per size sensor |
| FB3 ProductionCounter | SCL | Counts, rejects, OEE, throughput, speed %, uptime, mode integer |
| FB4 AlarmHandler | SCL | E-Stop, jam timer, sensor-conflict fault, alarm code |
| DB1 ConveyorData | data | Shared data block, non-optimized |

FB3 and FB4 are in `conveyor_plc_structured_text.st`. The two ladder blocks are short enough to describe in full.

FB1 ConveyorControl:

- Network 1, motor latch. `Conveyor_Motor` turns on if `Start_Button` or `Cmd_Start` or `Conveyor_Motor` (the seal-in contact) is true, and stays on only while `Stop_Button`, `E_Stop`, `Alarm_Active`, and `Cmd_Stop` are all clear (four normally-closed contacts in series). Releasing Start leaves the motor running through its own contact; any stop condition breaks the rung.

```
   Start_Button      Stop_Button  E_Stop  Alarm_Active  Cmd_Stop   Conveyor_Motor
 +----| |----+----------|/|--------|/|-------|/|----------|/|---------( )--
 |           |
 +--| |------+   Conveyor_Motor (seal-in)
 +--| |------+   Cmd_Start (remote)
```

- Network 2, mode bits. `Cmd_Mode_Auto` sets `Mode_Auto` and resets `Mode_Manual`; `Cmd_Mode_Manual` does the reverse; `Alarm_Active` drives `Mode_Fault`.
- Network 3, speed. When `Conveyor_Motor` is on, MOVE `Speed_Setpoint` into `VFD_Speed_Ref`. When it is off, MOVE 0 into `VFD_Speed_Ref`.
- Network 4, alarm outputs. `Alarm_Beacon` = `Alarm_Active` AND `Clock_1Hz` (so it flashes once a second). `Alarm_Horn` = `Alarm_Active` (steady).

FB2 SortingLogic:

- Network 1. `Object_Present` (a DB1 bit) follows `Sensor_Entry`.
- Networks 2 to 4. For each size sensor in series with `Conveyor_Motor`, a TP (pulse) timer with a preset of `T#2s` drives the matching diverter for two seconds: `Sensor_Small` to `Diverter_Lane1`, `Sensor_Medium` to `Diverter_Lane2`, `Sensor_Large` to `Diverter_Lane3`.

OB1 calls all four blocks each scan. FB1 and FB2 read tags and DB1 directly, so they need no parameters. FB3 and FB4 take these inputs:

- FB3: `Enable`=TRUE, `Reset`=`ConveyorData.Cmd_Reset`, `Divert1/2/3`=`Q0.1/Q0.2/Q0.3`, `Entry_Sensor`=`I0.3`, `Motor_On`=`Q0.0`, `Speed_Raw`=`IW64`, `OneSec_Clock`=`M10.5`, `Auto_Mode`=`M0.0`, `Manual_Mode`=`M0.1`, `Alarm`=`ConveyorData.Alarm_Active`.
- FB4: `EStop_NC`=`I0.2`, `Jam_Sensor`=`I0.7`, `Small_Sensor`=`I0.4`, `Medium_Sensor`=`I0.5`, `Large_Sensor`=`I0.6`.

### DB1 data layout

DB1 is 32 bytes and must be non-optimized. The gateway reads these exact offsets, so keep the variable order as shown.

| Offset | Name | Type | Offset | Name | Type |
|:--|:--|:--|:--|:--|:--|
| 0 | Total_Count | Int | 24 | Mode | Int |
| 2 | Lane1_Count | Int | 26.0 | Motor_Running | Bool |
| 4 | Lane2_Count | Int | 26.1 | Alarm_Active | Bool |
| 6 | Lane3_Count | Int | 26.2 | Jam_Detected | Bool |
| 8 | Reject_Count | Int | 26.3 | System_Running | Bool |
| 10 | OEE | Real | 26.4 | Sorting_Small | Bool |
| 14 | Throughput | Real | 26.5 | Sorting_Medium | Bool |
| 18 | Uptime_Seconds | DInt | 26.6 | Sorting_Large | Bool |
| 22 | Speed_Actual | Int | 26.7 | EStop_Active | Bool |
| 27.0 | Object_Present | Bool | 28 | Active_Alarm_Code | Int |
| 30.0 | Cmd_Start | Bool | 30.1 | Cmd_Stop | Bool |
| 30.2 | Cmd_Reset | Bool | 30.3 | Cmd_Mode_Auto | Bool |
| 30.4 | Cmd_Mode_Manual | Bool | | | |

Mode is 0 STOP, 1 AUTO, 2 MANUAL, 3 FAULT. Active_Alarm_Code is 0 none, 1 E-Stop, 2 jam, 3 sensor fault.

## Setup and run

### 1. Build the PLC program in TIA Portal

1. Create a new project and add the CPU 1214C DC/DC/DC (`6ES7 214-1AG40-0XB0`).
2. Add the SB 1232 AQ signal board to the CPU. It provides the analog output `QW80`.
3. In the CPU properties, enable the clock memory byte and leave it at MB10. This gives you the 1 Hz bit `M10.5`.
4. Create a tag table with all the tags in the I/O and memory table above.
5. Add a global data block named `ConveyorData` (DB1). Enter the variables in the order in the DB1 table. Open its properties and turn off "Optimized block access". This step is required for the gateway to read it correctly.
6. Add FB3 (`ProductionCounter`) and FB4 (`AlarmHandler`) as SCL blocks. Paste each block's code from `code/conveyor_plc_structured_text.st` (the file also contains the DB1 definition for reference).
7. Add FB1 (`ConveyorControl`) and FB2 (`SortingLogic`) as Ladder blocks and build the networks described in "The PLC program".
8. In OB1, call FB1, FB2, FB3, FB4 (accept an instance DB for each), and wire the FB3 and FB4 inputs as listed above.
9. Compile the whole program.

### 2. Start the simulation

1. Start S7-PLCSIM, download the program to it, and set the CPU to RUN.
2. Confirm there are no compile or download errors and the CPU shows RUN.

### 3. Run the gateway

```powershell
pip install python-snap7 paho-mqtt
python code/iot_gateway.py
```

The gateway connects to PLCSIM at `127.0.0.1`, rack 0, slot 1, reads 32 bytes from DB1, and publishes JSON to `iiot/conveyor/demo01/telemetry` every two seconds. It also subscribes to `iiot/conveyor/demo01/cmd` for commands. The session id `demo01` keeps the topic private on the shared broker; change `SESSION_ID` near the top of the file if you want a different one.

### 4. Open the dashboard

Open `code/dashboard.html` in a browser by double-clicking it. Set the Session field to the same id as the gateway (`demo01` by default) and click Connect. The status dot turns green when it is connected to the broker.

## How to verify it works

With PLCSIM in RUN, open a watch table in TIA Portal and add the tags below. Modify inputs and watch the outputs and DB values react. The gateway terminal and the dashboard should mirror everything.

1. Enable the safety input. Set `E_Stop` to 1 (normally closed means 1 is healthy). The belt cannot start while it is 0.
2. Start the belt. Set `Start_Button` to 1, then back to 0. `Conveyor_Motor` turns on and stays on, which confirms the latch.
3. Set the speed. Set `Speed_Setpoint` to 13824. `ConveyorData.Speed_Actual` should read about 50 (percent), and `VFD_Speed_Ref` should follow the setpoint while the motor runs.
4. Sort a box. Set `Sensor_Small` to 1, then back to 0. `Diverter_Lane1` pulses on for about two seconds, and `Lane1_Count` and `Total_Count` each increase by one. Repeat with `Sensor_Medium` (lane 2) and `Sensor_Large` (lane 3).
5. Make a reject. Set `Sensor_Entry` to 1 and leave it for more than three seconds without triggering a size sensor. `Reject_Count` increases by one.
6. Trigger a jam. Set `Jam_Sensor` to 1 and leave it for more than five seconds. `Jam_Detected` and `Alarm_Active` go true, `Mode` becomes 3, `Alarm_Beacon` flashes, and the motor stops. Set it back to 0 and the alarm clears on its own.
7. Test the E-Stop. Set `E_Stop` to 0. The motor stops immediately and `EStop_Active` goes true. Set it back to 1 to release.

On the dashboard you should see the lane cards and total climb as you sort, the mode and speed update, OEE and throughput move, the alarm panel turn red during a fault, and the throughput trend fill in over time. The Start, Stop, Reset, AUTO, and MANUAL buttons should drive the PLC (the gateway prints each command it forwards). The gateway prints a status line every cycle showing mode, counts, OEE, and throughput.

## Troubleshooting

| Symptom | Cause and fix |
|:--|:--|
| Dashboard and gateway show only zeros or nonsense | DB1 is still optimized. Turn off "Optimized block access" on DB1, recompile, and download again. |
| Gateway cannot connect or reports an unreachable peer | PLCSIM is not in RUN, or the address is wrong. Use `127.0.0.1`, rack 0, slot 1, and set the CPU to RUN. |
| Gateway raises "snap7 library not found" on Windows | Place the 64-bit `snap7.dll` next to `iot_gateway.py` or in `C:\Windows\System32`, matching your Python bitness. |
| A diverter never fires | Sorting only runs while the belt is on. Start the motor first. |
| Motor will not start | `E_Stop` must read 1 (normally closed healthy) and no alarm may be active. |
| Dashboard status dot stays red | The session id must match the gateway, and the browser needs to reach `broker.hivemq.com` on WebSocket port 8884. |

## Limitations and scope

This is a prototype that runs entirely in PLCSIM. Sensors are simulated by forcing inputs, so it demonstrates the control logic and the data path but not physical wiring or commissioning. The MQTT link uses a public broker with no authentication or encryption, which is fine for a demo but not for production; a real deployment would use a private broker with TLS, or OPC UA straight to the PLC. The OEE and throughput formulas are simplified, the counters are 16-bit and reset on a power cycle, and there is no historical logging. Reasonable next steps would be adding a database for trends, moving the PLC link to OPC UA, and extending the sort to barcode or destination-based routing.

## Author

Pranav S M

