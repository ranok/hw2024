#!/bin/bash

sudo apt-get update && sudo apt-get upgrade -y
sudo apt install python3-pip libfreetype-dev libjpeg-dev -y
sudo apt-get install libopenblas*dev -y
sudo mkdir -p /opt/cg
sudo chown $(whoami):$(whoami) /opt/cg
cd /opt/cg && python3 -m venv venv
cd /opt/cg && source venv/bin/activate && pip install pillow numpy lgpio spidev gpiozero 