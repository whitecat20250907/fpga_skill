<?xml version="1.0" encoding="UTF-8"?>
<Project Version="3" Minor="2" Path="E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/evidence/skill_helper_uart_clone_20261004">
    <Project_Created_Time></Project_Created_Time>
    <TD_Encoding>UTF-8</TD_Encoding>
    <TD_Version>6.2.200067</TD_Version>
    <Name>fpga_prj</Name>
    <HardWare>
        <Family>PH1</Family>
        <Device>PH1A90SEG324</Device>
        <Speed>-2</Speed>
    </HardWare>
    <Source_Files>
        <Verilog>
            <File Path="uisrc/01_rtl/uart_top.v">
                <FileInfo>
                    <Attr Name="UsedInSyn" Val="true"/>
                    <Attr Name="UsedInP&R" Val="true"/>
                    <Attr Name="BelongTo" Val="design_1"/>
                    <Attr Name="CompileOrder" Val="1"/>
                </FileInfo>
            </File>
            <File Path="uisrc/03_ip/uiuart_rx.v">
                <FileInfo>
                    <Attr Name="UsedInSyn" Val="true"/>
                    <Attr Name="UsedInP&R" Val="true"/>
                    <Attr Name="BelongTo" Val="design_1"/>
                    <Attr Name="CompileOrder" Val="2"/>
                </FileInfo>
            </File>
            <File Path="uisrc/03_ip/uiuart_tx.v">
                <FileInfo>
                    <Attr Name="UsedInSyn" Val="true"/>
                    <Attr Name="UsedInP&R" Val="true"/>
                    <Attr Name="BelongTo" Val="design_1"/>
                    <Attr Name="CompileOrder" Val="3"/>
                </FileInfo>
            </File>
        </Verilog>
        <ADC_FILE>
            <File Path="uisrc/04_pin/fpga_pin.adc">
                <FileInfo>
                    <Attr Name="UsedInSyn" Val="true"/>
                    <Attr Name="UsedInP&R" Val="true"/>
                    <Attr Name="BelongTo" Val="constraint_1"/>
                    <Attr Name="CompileOrder" Val="2"/>
                </FileInfo>
            </File>
        </ADC_FILE>
        <SDC_FILE>
            <File Path="uisrc/04_pin/timing.sdc">
                <FileInfo>
                    <Attr Name="UsedInSyn" Val="true"/>
                    <Attr Name="UsedInP&R" Val="true"/>
                    <Attr Name="BelongTo" Val="constraint_1"/>
                    <Attr Name="CompileOrder" Val="1"/>
                </FileInfo>
            </File>
        </SDC_FILE>
    </Source_Files>
    <FileSets>
        <FileSet Name="design_1" Type="DesignFiles">
        </FileSet>
        <FileSet Name="constraint_1" Type="ConstrainFiles">
        </FileSet>
    </FileSets>
    <TOP_MODULE>
        <LABEL>uart_top</LABEL>
        <MODULE>uart_top</MODULE>
        <CREATEINDEX>user</CREATEINDEX>
    </TOP_MODULE>
    <Property>
        <SimProperty>
            <lib>E:/modelsim/modelsim/anlogic/PH1</lib>
        </SimProperty>
    </Property>
    <Device_Settings>
    </Device_Settings>
    <Configurations>
    </Configurations>
    <Runs>
        <Run Name="syn_1" Type="Synthesis" ConstraintSet="constraint_1" Description="" Active="true">
            <Strategy Name="Default_Synthesis_Strategy">
            </Strategy>
            <UserParams>
            </UserParams>
        </Run>
        <Run Name="phy_1" Type="PhysicalDesign" ConstraintSet="constraint_1" Description="" SynRun="syn_1" Active="true">
            <Strategy Name="Default_PhysicalDesign_Strategy">
                <BitgenProperty::GeneralOption>
                    <compress>on</compress>
                </BitgenProperty::GeneralOption>
            </Strategy>
            <UserParams>
            </UserParams>
        </Run>
    </Runs>
    <Project_Settings>
    </Project_Settings>
</Project>
