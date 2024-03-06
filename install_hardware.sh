# Setup Ethernet gadget according to: https://forums.raspberrypi.com/viewtopic.php?p=2184846
cat >/etc/network/interfaces.d/g_ether <<'EOF'
auto usb0
allow-hotplug usb0
iface usb0 inet static
        address 169.254.1.107
        netmask 255.255.0.0

auto usb0.1
allow-hotplug usb0.1
iface usb0.1 inet dhcp

EOF
