本文档用于rk3576端的部署
首次部署：rk3576烧写固件为mlk-rk03-debian.img。这里使用了rk03的debian固件，同时还需要升级boot.img。也可以使用新的设备树文件构建update.img
1、将本文件夹下所有文件拷贝到rk3576，/root/deploy/目录下。
2、执行命令进入文件夹，修改权限，执行配置脚本。注意，这里需要fpga端已经烧写好bit或者固件启动。
	cd /root/deploy
	chmod +x *.sh
	./pcie_setup.sh   
脚本实际完成了驱动编译，安装，pcie链路绑定。这里我们默认使用1080p60格式。
 gst-launch-1.0 v4l2src device=/dev/video73 ! 'video/x-raw,width=1920,height=1080,format=RGB' ! videoconvert ! kmssink 
或者使用debian自带茄子显示。