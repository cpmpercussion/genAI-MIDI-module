# GenAI MIDI Module

The generative AI MIDI module lets you add generative AI capability to electronic musical instruments over a MIDI interface. This system runs on a Raspberry Pi Zero 2 W. 

This program doesn't make any sounds, it just sends generated MIDI messages over a Raspberry Pi's serial port.

## Making

### Prepare Raspberry Pi OS

You'll need:

- an SD card
- a Raspberry Pi Zero 2 W
- an internet connection

1. Flash an SD card with "Raspberry Pi OS Lite 64-bit" using the [Raspberry Pi Imager](https://www.raspberrypi.com/software/). These instructions work with Kernel 6.1, Debian 12 Bookworm.

2. Make sure that SSH is enabled and that you know the username and password. The username should be `pi`.

3. If needed, set up USB ethernet by following the instructions [here](https://forums.raspberrypi.com/viewtopic.php?p=2184846), adding `dtoverlay=dwc2` to `config.txt` and `modules-load=dwc2,g_ether` to `cmdline.txt` in the boot partition.

3. SSH into the Pi and run:

```
sudo apt update && sudo apt upgrade
sudo apt install git
```

4. clone this repository: `git clone https://github.com/cpmpercussion/genAI-MIDI-module.git`

## Install

## Using

