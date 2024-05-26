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

There are three install scripts. You'll need to have an internet connection to get these to work:

- `install_hardware.sh`: sets up ethernet-over-USB and enables the UART for MIDI in/out.
- `install_software.sh`: installs Python and other packages needed for the genAI program.
- `install_start_on_boot.sh`: installs a systemd service that runs the genAI program when the Raspberry Pi boots

Once you have run these scripts (and they were successful), you can test the genAI MIDI module works by running: `start.sh`.

N.B.: The `genai_midi_module.py` program takes a long time to start (~90s).

You can stop the `genai_midi_module.py` program by typing Ctrl-C.

## Using

- Config is in `config.toml`

- `start.sh` starts the main python file

# Poetry Install

This project also works with poetry for defining dependencies and setting up a virtualenv for you (yay).

_this replaces the software install step..._

1. install poetry.
2. if on Raspberry Pi, use [this workaround](https://github.com/python-poetry/poetry/issues/8623) to stop poetry failing: `export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`
3. run `poetry install`

N.B.: working towards making this the default on all platforms.
