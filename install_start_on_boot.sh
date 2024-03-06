#!/bin/sh

# This script installs a systemd service to start the genAI program on boot.

cd /home/pi/genai-midi-module
sudo cp /home/pi/genai-midi-module/genaimodule.service /etc/systemd/system/genaimodule.service
sudo chmod 644 /etc/systemd/system/genaimodule.service
# sudo systemctl start genaimodule.service
# sudo systemctl stop genaimodule.service
sudo systemctl enable genaimodule.service
