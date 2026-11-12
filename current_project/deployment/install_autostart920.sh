set -eu
install -m 755 /home/linaro/pcie_fix_20261003/autostart920.py /userdata/hmi_v2/tools/autostart920.py
install -m 644 /home/linaro/pcie_fix_20261003/hmi-autostart920.service /etc/systemd/system/hmi-autostart920.service
systemd-analyze verify /etc/systemd/system/hmi-autostart920.service
systemctl daemon-reload
systemctl enable hmi-autostart920.service
systemctl is-enabled hmi-autostart920.service lightdm
systemctl get-default
