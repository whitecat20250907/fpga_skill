"""Apply two final audit corrections to the task-owned driver copy only."""
import hashlib,sys
from pathlib import Path
p=Path(sys.argv[1])
v=p/'deploy/v4l2_drv/milianke_v4l2_zerocopy.c'
s=v.read_bytes().replace(b'\r\n',b'\n')
old=b'        if (best != mdev->cam_mode) {'
new=b'        if (best != mdev->cam_mode ||\n            (ioread32(mdev->user_bar + REG_CAM_MODE) & 0x3) != best) {'
assert s.count(old)==1
v.write_bytes(s.replace(old,new))
f=p/'deploy/sgdma_drv/anlogic_pci_lib.c'
s=f.read_bytes().replace(b'\r\n',b'\n')
old=b'\t/* dummy read of status register to flush all previous writes */\n\tdbg_tfr("%s(%s) done\\n", __func__, engine->name);'
new=b'\t/* Complete the posted control write before recycling descriptors.\n\t * This read is a bus flush, not proof that hardware BUSY is clear. */\n\t(void)read_register(&engine->regs->status);\n\tdbg_tfr("%s(%s) done\\n", __func__, engine->name);'
assert s.count(old)==1
f.write_bytes(s.replace(old,new))
for target in (v,f): print(hashlib.sha256(target.read_bytes()).hexdigest(),target.name)
