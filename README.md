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

## Tech stack

| Component | Detail |
|:--|:--|
| PLC | Siemens S7-1200, CPU 1214C DC/DC/DC (`6ES7 214-1AG40-0XB0`) |
| Engineering software | TIA Portal V18 (STEP 7 Professional) |
| Simulator | S7-PLCSIM V18 |
| PLC languages | Ladder (LAD) and Structured Text (SCL), IEC 61131-3 |

## Author

Pranav S M
