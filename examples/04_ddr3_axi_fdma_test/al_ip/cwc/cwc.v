/************************************************************\
**	Copyright (c) 2012-2026 Anlogic Inc.
**	All Right Reserved.
\************************************************************/
/************************************************************\
**	Gen time	:	Apr 16 2026 08:47:37
**	IpTool version	:	2026.01(189136 2026/01/26)
**	App version	:	6.2.2(build number:190657)
**	Ip Version	:	1.0
\************************************************************/
module cwc
(
  input   [15:0]                probe0,
  input   [0:0]                 probe1,
  input   [0:0]                 probe2,
  input   [0:0]                 probe3,
  input   [0:0]                 probe4,
  input   [15:0]                probe5,
  input   [15:0]                probe6,
  input   [0:0]                 probe7,
  input   [0:0]                 probe8,
  input   [0:0]                 probe9,
  input   [0:0]                 probe10,
  input   [2:0]                 probe11,
  input   [0:0]                 probe12,
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
      .probe7(probe7),
      .probe8(probe8),
      .probe9(probe9),
      .probe10(probe10),
      .probe11(probe11),
      .probe12(probe12),
      .clk(clk)
  );
endmodule
