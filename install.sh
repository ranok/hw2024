#!/bin/bash

sudo apt-get update && sudo apt-get upgrade -y
sudo apt install python3-pip libfreetype-dev libjpeg-dev -y
sudo apt-get install libopenblas*dev -y
sudo apt-get -y install xtables-addons-common build-essential python3-dev libnetfilter-queue-dev netfilter-persistent
sudo cp -f dist/rules.v4 /etc/iptables/rules.v4 && sudo iptables-restore /etc/iptables/rules.v4
sudo mkdir -p /opt/cg
sudo chown $(whoami):$(whoami) /opt/cg
cd /opt/cg && git clone https://github.com/ranok/hw2024.git .
cd /opt/cg && sudo ln -s /opt/cg/wificonfig.service /etc/systemd/system/wificonfig.service
sudo systemctl enable --now wificonfig.service
cd /opt/cg && python3 -m venv venv
sudo setcap CAP_NET_ADMIN=+eip "$(readlink -f venv/bin/python)" # Persists, The file capability sets are stored in an extended attribute (see setxattr(2)) named security.capability.
cd /opt/cg && source venv/bin/activate && pip install pillow numpy lgpio spidev gpiozero flask python-dotenv qrcode nmcli canarytools scapy netfilterqueue
