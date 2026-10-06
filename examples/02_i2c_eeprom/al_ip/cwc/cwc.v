/************************************************************\
**	Copyright (c) 2012-2026 Anlogic Inc.
**	All Right Reserved.
\************************************************************/
/************************************************************\
**	Gen time	:	Jun 15 2026 16:33:52
**	IpTool version	:	2026.01(189136 2026/01/26)
**	App version	:	6.2.2(build number:190657)
**	Ip Version	:	1.0
\************************************************************/
module cwc
(
  input   [7:0]                 probe0,
  input   [7:0]                 probe1,
  input   [2:0]                 probe2,
  input   [0:0]                 probe3,
  input   [0:0]                 probe4,
  input   [0:0]                 probe5,
  input   [0:0]                 probe6,
  input                         clk
);

  ChipWatcher_cwc  ChipWatcher_Inst
  (
      .probe0(probe0),
      .probe1(probe1),
      .probe2(probe2),
      .probe3(probe3),
      .probe4(probe4),
      .probe5(probe5),
      .probe6(probe6),
      .clk(clk)
  );
endmodule
