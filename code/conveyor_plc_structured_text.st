// ============================================================
// IIoT Smart Conveyor Sorting System
// Siemens S7-1200 (CPU 1214C) - TIA Portal V18
// SCL source: DB1 (ConveyorData), FB3 (ProductionCounter), FB4 (AlarmHandler)
//
// NOTE: DB1 must be NON-OPTIMIZED for snap7 byte-offset reads.
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
