#!/bin/bash
# This AFC03 RK3576 configuration uses PCIe1 and disables the USB1 hub.
# Never patches boot/DT or toggles manually exported regulator/reset GPIOs.
set -euo pipefail
TASK_DEPLOY=$(cd -- "$(dirname -- "$0")" && pwd)
[[ $(id -u) == 0 ]] || { echo 'Run as root'; exit 1; }
tr '\0' '\n' < /proc/device-tree/compatible | grep -q rk3576 || { echo 'This setup targets the tested RK3576 board'; exit 1; }
[[ $(tr -d '\0' < /sys/firmware/devicetree/base/pcie@2a210000/status) == okay ]] || { echo 'PCIe1 DT disabled; install the verified boot separately'; exit 1; }
[[ $(tr -d '\0' < /sys/firmware/devicetree/base/usb@23400000/status) == disabled ]] || { echo 'USB1 must be disabled for PCIe1; refusing incompatible DT'; exit 1; }
TASK_CMA=$(awk '/CmaTotal:/ {print $2}' /proc/meminfo)
[[ $TASK_CMA -ge 65536 ]] || { echo "CMA ${TASK_CMA}KB insufficient for the validated four-buffer capture"; exit 1; }
for ko in "$TASK_DEPLOY/sgdma_drv/anlogic_pci.ko" "$TASK_DEPLOY/v4l2_drv/milianke_v4l2.ko"; do
    [[ -f $ko && $(modinfo -F vermagic "$ko" | awk '{print $1}') == $(uname -r) ]] || { echo "Missing/mismatched module: $ko"; exit 1; }
done
if [[ -d /sys/module/milianke_v4l2 ]]; then rmmod milianke_v4l2; fi
if [[ -d /sys/module/anlogic_pci ]]; then rmmod anlogic_pci; fi
find_endpoint() {
    local d
    for d in /sys/bus/pci/devices/*; do
        [[ -f $d/vendor && -f $d/device ]] || continue
        if [[ $(cat "$d/vendor") == 0x1edb && $(cat "$d/device") == 0xabcd ]]; then echo "$d"; fi
    done
}
TASK_EP=$(find_endpoint)
TASK_CTRL=/sys/bus/platform/drivers/rk-pcie
if [[ -z $TASK_EP ]]; then
    if [[ -d $TASK_CTRL/2a210000.pcie ]]; then echo 2a210000.pcie > "$TASK_CTRL/unbind"; fi
    # Only release the known legacy PERST sysfs ownership; the DT driver drives it.
    if [[ -d /sys/class/gpio/gpio48 ]]; then echo 48 > /sys/class/gpio/unexport; fi
    echo 2a210000.pcie > "$TASK_CTRL/bind"
    sleep 1
    TASK_EP=$(find_endpoint)
fi
[[ -n $TASK_EP && $(printf '%s\n' "$TASK_EP" | wc -l) == 1 ]] || { echo 'Expected exactly one 1edb:abcd endpoint; check FPGA SRAM programming'; exit 1; }
insmod "$TASK_DEPLOY/sgdma_drv/anlogic_pci.ko" poll_mode=1 enable_st_c2h_credit=1 desc_blen_max=1048576 poll_idle_us=30
python3 - "$TASK_EP/resource0" <<'PY'
import mmap,os,struct,sys,subprocess
fd=os.open(sys.argv[1],os.O_RDWR|os.O_SYNC)
with mmap.mmap(fd,4096) as m:
    for reg,value in [(0x60,0),(0xA4,0),(0x20,0),(0x90,0),(0x98,32)]:
        subprocess.run(['/home/linaro/pcie_fix_20261003/tools/bar_store32_native37',hex(reg),str(value)],check=True)
    print({hex(r):hex(struct.unpack_from('<I',m,r)[0]) for r in [0x5c,0x60,0x84,0x90,0x98,0xA4]})
os.close(fd)
PY
# Initialize FPGA mode before V4L2 caches the negotiated format.
insmod "$TASK_DEPLOY/v4l2_drv/milianke_v4l2.ko"
TASK_VIDEO=''
for name in /sys/class/video4linux/video*/name; do
    if grep -q 'Milianke PCIe Capture' "$name"; then TASK_VIDEO=/dev/$(basename "$(dirname "$name")"); fi
done
[[ -n $TASK_VIDEO ]] || { echo 'Capture node not created'; exit 1; }
echo "READY endpoint=$(basename "$TASK_EP") camera=$TASK_VIDEO CMA=${TASK_CMA}KB; camera is enabled by STREAMON"
