#!/bin/sh

# This script installs the Python and apt packages needed for the genAI program on a Raspberry Pi.
# For installing on Raspberry Pi OS -- use this, for other systems, use `poetry install`

# Setup Tensorflow
sudo apt update && sudo apt upgrade -y && \
sudo apt install -y \
    libhdf5-dev \
    unzip \
    pkg-config \
    python3-pip \
    cmake \
    make \
    git \
    python-is-python3 \
    wget \
    patchelf && \
pip install -U pip --break-system-packages && \
pip install numpy==1.26.2 --break-system-packages && \
pip install keras_applications==1.0.8 --no-deps --break-system-packages && \
pip install keras_preprocessing==1.1.2 --no-deps --break-system-packages && \
pip install h5py==3.10.0 --break-system-packages && \
pip install pybind11==2.9.2 --break-system-packages && \
pip install packaging --break-system-packages && \
pip install protobuf==3.20.3 --break-system-packages && \
pip install six wheel mock gdown --break-system-packages
pip uninstall tensorflow
TFVER=2.15.0.post1
PYVER=311
ARCH=`python -c 'import platform; print(platform.machine())'`
echo CPU ARCH: ${ARCH}

pip install \
--no-cache-dir \
--break-system-packages \
https://github.com/PINTO0309/Tensorflow-bin/releases/download/v${TFVER}/tensorflow-${TFVER}-cp${PYVER}-none-linux_${ARCH}.whl

# Setup other python packages.
pip install -U tensorflow-probability==0.23.0 --break-system-packages && \
pip install -U python-osc --break-system-packages && \
pip install -U keras-mdn-layer --break-system-packages && \
pip install -U pyserial --break-system-packages && \
pip install -U websockets --break-system-packages && \
pip install -U mido --break-system-packages && \
pip install -U python-rtmidi --break-system-packages && \
pip install -U click --break-system-packages
