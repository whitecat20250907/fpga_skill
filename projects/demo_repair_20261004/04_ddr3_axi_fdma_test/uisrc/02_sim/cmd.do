## part 1: create lib
vlib work
vmap work work

## part 2: load rtl
vlog -timescale 1ps/1ps -sv -f   compile.f                        \
 +define+PH1_DDR_SIM                                              \
 +define+SIMULATION                                               \
 +define+den4096Mb                                                \
 +define+sg125                                                    \
 +define+x16                                                       \
 +define+DRAM_BYTE_NUM=4                                          \
 +define+MC_AXI     

## part 3: sim
vsim -voptargs=+acc work.sim_tb_top        \
+define+PH1_DDRPHY_SIM
+define+PH1_MIS_SIM
+define+MC0_DDRPHY_CFG_ROM=../../uisrc/03_ip/ui_ddr/ui_ddr_cfg_rom.txt   \
+define+MC0_DDRPHY_MCU_ROM=../../uisrc/03_ip/ui_ddr/ui_ddr_mcu_rom.txt


## part 4: add wave
do my_wave.do


## part 5: show ui
view wave
view structure
view signals

## part 6: run sim
run -all



