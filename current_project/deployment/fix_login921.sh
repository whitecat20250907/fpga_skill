set -eu
install -d /etc/lightdm/lightdm.conf.d /etc/systemd/system/getty@.service.d
cat > /etc/lightdm/lightdm.conf.d/90-hmi-autologin.conf <<'EOF'
[Seat:*]
autologin-user=linaro
autologin-user-timeout=0
autologin-session=xfce
user-session=xfce
EOF
cat > /etc/systemd/system/getty@.service.d/90-hmi-autologin.conf <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin linaro --noclear %I $TERM
EOF
install -d -o linaro -g linaro /home/linaro/.config/autostart
for app in light-locker xscreensaver xfce4-screensaver; do
cat > /home/linaro/.config/autostart/$app.desktop <<EOF
[Desktop Entry]
Type=Application
Name=$app
Hidden=true
EOF
chown linaro:linaro /home/linaro/.config/autostart/$app.desktop
done
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET,shutil,os
base=Path('/home/linaro/.config/xfce4/xfconf/xfce-perchannel-xml')
backup=Path('/userdata/hmi_v2/backups/access921');backup.mkdir(parents=True,exist_ok=True)
changes={'xfce4-power-manager':{'xfce4-power-manager/lock-screen-suspend-hibernate':False},
 'xfce4-session':{'shutdown/LockScreen':False},
 'xfce4-screensaver':{'lock/enabled':False,'saver/enabled':False}}
for channel,settings in changes.items():
 p=base/(channel+'.xml')
 if p.exists():
  if not (backup/p.name).exists():shutil.copy2(p,backup/p.name)
  root=ET.parse(p).getroot()
 else:root=ET.Element('channel',name=channel,version='1.0')
 for name,value in settings.items():
  node=root
  for part in name.split('/'):
   found=next((q for q in node.findall('property') if q.get('name')==part),None)
   if found is None:found=ET.SubElement(node,'property',name=part,type='empty')
   node=found
  node.set('type','bool');node.set('value','false')
 ET.ElementTree(root).write(p,encoding='UTF-8',xml_declaration=True);os.chown(p,1000,1000)
PY
systemctl daemon-reload
systemctl restart lightdm
systemctl reset-failed hmi-autostart920
systemctl start --no-block hmi-autostart920
echo AUTOLOGIN921_CONFIGURED
