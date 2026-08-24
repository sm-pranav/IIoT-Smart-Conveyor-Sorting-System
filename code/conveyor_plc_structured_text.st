// ============================================================
// IIoT Smart Conveyor Sorting System
// Siemens S7-1200 (CPU 1214C) - TIA Portal V18
// SCL source: DB1 (ConveyorData), FB3 (ProductionCounter), FB4 (AlarmHandler)
//
// DB1 must use non-optimized (standard) access for snap7 byte-offset reads.
// ============================================================


// ============================================================
// DB1 : "ConveyorData"  (Global Data Block, STANDARD access)
// ------------------------------------------------------------
// This is the single "shared memory" for the whole system.
// The HMI reads it, and the Python gateway reads it over S7.
//
// The BYTE OFFSET column is critical - the Python gateway reads
// these exact offsets. Do not reorder the variables.
//
//  OFFSET  NAME               TYPE   NOTES
//  ------  -----------------  -----  ---------------------------
//   0.0    Total_Count        Int    All sorted parts
//   2.0    Lane1_Count        Int    Small parts  -> Lane 1
//   4.0    Lane2_Count        Int    Medium parts -> Lane 2
//   6.0    Lane3_Count        Int    Large parts  -> Lane 3
//   8.0    Reject_Count       Int    Unrecognized parts
//  10.0    OEE                Real   Overall Equipment Effectiveness %
//  14.0    Throughput         Real   Parts per minute
//  18.0    Uptime_Seconds     DInt   Seconds the motor has run
//  22.0    Speed_Actual       Int    Belt speed as % (0..100)
//  24.0    Mode               Int    0=STOP 1=AUTO 2=MANUAL 3=FAULT
//  26.0    Motor_Running      Bool
//  26.1    Alarm_Active       Bool
//  26.2    Jam_Detected       Bool
//  26.3    System_Running     Bool
//  26.4    Sorting_Small      Bool
//  26.5    Sorting_Medium     Bool
//  26.6    Sorting_Large      Bool
//  26.7    EStop_Active       Bool
//  27.0    Object_Present     Bool
//  28.0    Active_Alarm_Code  Int    0=none 1=EStop 2=Jam 3=SensorFault
//  30.0    Cmd_Start          Bool   Remote start  (written by gateway)
//  30.1    Cmd_Stop           Bool   Remote stop
//  30.2    Cmd_Reset          Bool   Remote counter reset
//  30.3    Cmd_Mode_Auto      Bool   Remote select AUTO
//  30.4    Cmd_Mode_Manual    Bool   Remote select MANUAL
//
//  TOTAL SIZE = 32 bytes  (gateway reads 32 bytes from DB1)
// ------------------------------------------------------------

DATA_BLOCK "ConveyorData"
{ S7_Optimized_Access := 'FALSE' }   // <-- MUST be FALSE for snap7
VERSION : 0.1
   VAR
      Total_Count : Int := 0;
      Lane1_Count : Int := 0;
      Lane2_Count : Int := 0;
      Lane3_Count : Int := 0;
      Reject_Count : Int := 0;
      OEE : Real := 0.0;
      Throughput : Real := 0.0;
      Uptime_Seconds : DInt := 0;
      Speed_Actual : Int := 0;
      Mode : Int := 0;
      Motor_Running : Bool := FALSE;
      Alarm_Active : Bool := FALSE;
      Jam_Detected : Bool := FALSE;
      System_Running : Bool := FALSE;
      Sorting_Small : Bool := FALSE;
      Sorting_Medium : Bool := FALSE;
      Sorting_Large : Bool := FALSE;
      EStop_Active : Bool := FALSE;
      Object_Present : Bool := FALSE;
      Active_Alarm_Code : Int := 0;
      Cmd_Start : Bool := FALSE;
      Cmd_Stop : Bool := FALSE;
      Cmd_Reset : Bool := FALSE;
      Cmd_Mode_Auto : Bool := FALSE;
      Cmd_Mode_Manual : Bool := FALSE;
   END_VAR
BEGIN
END_DATA_BLOCK


// ============================================================
// FB3 : "ProductionCounter"  (Structured Text / SCL)
// ------------------------------------------------------------
// Counts parts per lane, totals, rejects, and calculates the
// live production KPIs (OEE, throughput, uptime, speed %).
// Call this every scan from OB1.
// ============================================================

FUNCTION_BLOCK "ProductionCounter"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1

   VAR_INPUT
      Enable : Bool;                 // Master enable (usually TRUE)
      Reset : Bool;                  // Reset all counters to zero
      Divert1 : Bool;                // Diverter 1 pulse (small)  Q0.1
      Divert2 : Bool;                // Diverter 2 pulse (medium) Q0.2
      Divert3 : Bool;                // Diverter 3 pulse (large)  Q0.3
      Entry_Sensor : Bool;           // Object entering conveyor  I0.3
      Motor_On : Bool;               // Conveyor motor running    Q0.0
      Speed_Raw : Int;               // Raw setpoint 0..27648 (IW64)
      OneSec_Clock : Bool;           // 1 Hz clock bit (M10.5)
      Auto_Mode : Bool;              // AUTO memory bit  (M0.0)
      Manual_Mode : Bool;            // MANUAL memory bit (M0.1)
      Alarm : Bool;                  // Any alarm active (from FB4)
   END_VAR

   VAR
      Small_Edge : R_TRIG;           // rising edge of diverter 1 pulse
      Medium_Edge : R_TRIG;          // rising edge of diverter 2 pulse
      Large_Edge : R_TRIG;           // rising edge of diverter 3 pulse
      SecEdge : R_TRIG;              // 1 Hz rising edge
      RejectTimer : TON_TIME;        // Entry with no sort -> reject
      RejectEdge : R_TRIG;
      RunSeconds : DInt := 0;        // Time motor has been running
      PlannedSeconds : DInt := 0;    // Time system has been enabled
      AnyDivert : Bool;
      Availability : Real;
      Performance : Real;
      Quality : Real;
   END_VAR

BEGIN

   // --- Reset all counters on command ---
   IF #Reset THEN
      "ConveyorData".Total_Count := 0;
      "ConveyorData".Lane1_Count := 0;
      "ConveyorData".Lane2_Count := 0;
      "ConveyorData".Lane3_Count := 0;
      "ConveyorData".Reject_Count := 0;
      #RunSeconds := 0;
      #PlannedSeconds := 0;
   END_IF;

   // --- Count each lane on the RISING EDGE of its diverter pulse.
   //     R_TRIG gives a one-scan pulse per box, so we add exactly 1.
   //     (Simple, always-compiles equivalent of an IEC CTU counter.) ---
   #Small_Edge(CLK := #Divert1);
   #Medium_Edge(CLK := #Divert2);
   #Large_Edge(CLK := #Divert3);

   IF #Small_Edge.Q AND NOT #Reset THEN
      "ConveyorData".Lane1_Count := "ConveyorData".Lane1_Count + 1;
   END_IF;
   IF #Medium_Edge.Q AND NOT #Reset THEN
      "ConveyorData".Lane2_Count := "ConveyorData".Lane2_Count + 1;
   END_IF;
   IF #Large_Edge.Q AND NOT #Reset THEN
      "ConveyorData".Lane3_Count := "ConveyorData".Lane3_Count + 1;
   END_IF;

   "ConveyorData".Total_Count := "ConveyorData".Lane1_Count
                               + "ConveyorData".Lane2_Count
                               + "ConveyorData".Lane3_Count;

   // --- Reject: object entered but no diverter fired within 3 s ---
   #AnyDivert := #Divert1 OR #Divert2 OR #Divert3;
   #RejectTimer(IN := #Entry_Sensor AND NOT #AnyDivert, PT := T#3S);
   #RejectEdge(CLK := #RejectTimer.Q);
   IF #RejectEdge.Q AND NOT #Reset THEN
      "ConveyorData".Reject_Count := "ConveyorData".Reject_Count + 1;
   END_IF;

   // --- Mirror live sorting + status bits for HMI / dashboard ---
   //     (Object_Present is written by FB2 Network 1, so not repeated here.)
   "ConveyorData".Sorting_Small := #Divert1;
   "ConveyorData".Sorting_Medium := #Divert2;
   "ConveyorData".Sorting_Large := #Divert3;
   "ConveyorData".Motor_Running := #Motor_On;
   "ConveyorData".System_Running := #Motor_On;

   // --- One-second time keeping (driven by 1 Hz clock bit) ---
   #SecEdge(CLK := #OneSec_Clock);
   IF #SecEdge.Q AND #Enable THEN
      #PlannedSeconds := #PlannedSeconds + 1;
      IF #Motor_On THEN
         #RunSeconds := #RunSeconds + 1;
      END_IF;
   END_IF;
   "ConveyorData".Uptime_Seconds := #RunSeconds;

   // --- Speed as a percentage (0..27648 raw -> 0..100 %) ---
   "ConveyorData".Speed_Actual :=
      REAL_TO_INT(INT_TO_REAL(#Speed_Raw) * 100.0 / 27648.0);

   // --- Throughput (parts per minute since motor started) ---
   IF #RunSeconds > 0 THEN
      "ConveyorData".Throughput :=
         INT_TO_REAL("ConveyorData".Total_Count) / DINT_TO_REAL(#RunSeconds) * 60.0;
   ELSE
      "ConveyorData".Throughput := 0.0;
   END_IF;

   // --- OEE = Availability x Performance x Quality (as a percentage) ---
   // Availability: how much of enabled time the belt actually ran
   IF #PlannedSeconds > 0 THEN
      #Availability := DINT_TO_REAL(#RunSeconds) / DINT_TO_REAL(#PlannedSeconds);
   ELSE
      #Availability := 0.0;
   END_IF;

   // Performance: actual rate vs ideal rate
   // Ideal rate = 0.5 parts/second (one part every 2 s = 30 parts/min)
   IF #RunSeconds > 0 THEN
      #Performance := (INT_TO_REAL("ConveyorData".Total_Count)
                       / DINT_TO_REAL(#RunSeconds)) / 0.5;
   ELSE
      #Performance := 0.0;
   END_IF;
   IF #Performance > 1.0 THEN
      #Performance := 1.0;           // cannot exceed 100 %
   END_IF;

   // Quality: good parts vs all parts that were handled
   IF ("ConveyorData".Total_Count + "ConveyorData".Reject_Count) > 0 THEN
      #Quality := INT_TO_REAL("ConveyorData".Total_Count)
                  / INT_TO_REAL("ConveyorData".Total_Count + "ConveyorData".Reject_Count);
   ELSE
      #Quality := 1.0;
   END_IF;

   "ConveyorData".OEE := #Availability * #Performance * #Quality * 100.0;

   // --- Translate the mode memory bits into the DB Mode integer ---
   IF #Alarm THEN
      "ConveyorData".Mode := 3;      // FAULT overrides everything
   ELSIF #Auto_Mode THEN
      "ConveyorData".Mode := 1;      // AUTO
   ELSIF #Manual_Mode THEN
      "ConveyorData".Mode := 2;      // MANUAL
   ELSE
      "ConveyorData".Mode := 0;      // STOP
   END_IF;

END_FUNCTION_BLOCK


// ============================================================
// FB4 : "AlarmHandler"  (Structured Text / SCL)
// ------------------------------------------------------------
// Watches for fault conditions, builds the active alarm code,
// and drives the master Alarm_Active flag. Call every scan.
//
// Alarms are self-clearing: when the physical condition goes
// away, the alarm clears by itself. Cmd_Reset clears counters
// (handled in FB3), not the live alarm state.
// ============================================================

FUNCTION_BLOCK "AlarmHandler"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1

   VAR_INPUT
      EStop_NC : Bool;               // Raw E-Stop input I0.2 (1 = healthy)
      Jam_Sensor : Bool;             // Jam photo-eye I0.7
      Small_Sensor : Bool;           // I0.4
      Medium_Sensor : Bool;          // I0.5
      Large_Sensor : Bool;           // I0.6
   END_VAR

   VAR
      JamTimer : TON_TIME;           // Jam sensor blocked > 5 s
      SensorSum : Int;
      SensorFault : Bool;
      EStop_Pressed : Bool;
   END_VAR

BEGIN

   // --- E-Stop is wired Normally Closed (fail-safe).
   //     Input reads TRUE when healthy, FALSE when pressed or wire broken.
   #EStop_Pressed := NOT #EStop_NC;
   "ConveyorData".EStop_Active := #EStop_Pressed;

   // --- Jam: sorting-junction photo-eye blocked longer than 5 s ---
   #JamTimer(IN := #Jam_Sensor, PT := T#5S);
   "ConveyorData".Jam_Detected := #JamTimer.Q;

   // --- Sensor fault: two or more size sensors ON at once is impossible ---
   //     (BOOL cannot be added directly in SCL, so we count with IFs.)
   #SensorSum := 0;
   IF #Small_Sensor THEN
      #SensorSum := #SensorSum + 1;
   END_IF;
   IF #Medium_Sensor THEN
      #SensorSum := #SensorSum + 1;
   END_IF;
   IF #Large_Sensor THEN
      #SensorSum := #SensorSum + 1;
   END_IF;
   #SensorFault := (#SensorSum >= 2);

   // --- Master alarm flag ---
   "ConveyorData".Alarm_Active :=
      #EStop_Pressed OR "ConveyorData".Jam_Detected OR #SensorFault;

   // --- Active alarm code (priority order) ---
   IF #EStop_Pressed THEN
      "ConveyorData".Active_Alarm_Code := 1;
   ELSIF "ConveyorData".Jam_Detected THEN
      "ConveyorData".Active_Alarm_Code := 2;
   ELSIF #SensorFault THEN
      "ConveyorData".Active_Alarm_Code := 3;
   ELSE
      "ConveyorData".Active_Alarm_Code := 0;
   END_IF;

END_FUNCTION_BLOCK

