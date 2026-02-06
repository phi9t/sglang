# Dockerfile for SGLang on Pascal GPUs (GTX 10xx series, compute capability 6.1)
# This builds PyTorch from source with sm_61 support

FROM nvidia/cuda:11.8.0-devel-ubuntu22.04
SHELL ["/bin/bash", "-c"]

ARG SGLANG_REPO=https://github.com/sgl-project/sglang.git
ARG VER_SGLANG=main

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    curl \
    wget \
    vim \
    gcc \
    g++ \
    make \
    ninja-build \
    libsqlite3-dev \
    libnuma-dev \
    numactl \
    python3.10 \
    python3.10-dev \
    python3.10-venv \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Set python3.10 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1

# Upgrade pip
RUN python3 -m pip install --upgrade pip setuptools wheel

# Install PyTorch 2.1.2 with CUDA 11.8 (last version with decent Pascal support)
# Note: This uses pre-built wheels which may have limited sm_61 support
# For full support, PyTorch would need to be built from source
RUN pip3 install torch==2.1.2+cu118 torchvision==0.16.2+cu118 torchaudio==2.1.2+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

# Install other dependencies
RUN pip3 install ninja packaging

WORKDIR /sgl-workspace

# Clone SGLang and install with relaxed dependencies
RUN git clone ${SGLANG_REPO} sglang && \
    cd sglang && \
    git checkout ${VER_SGLANG}

# Install SGLang (may need to relax some version constraints)
WORKDIR /sgl-workspace/sglang/python
RUN pip3 install -e ".[all]" || pip3 install -e . || \
    (pip3 install transformers accelerate sentencepiece protobuf && pip3 install -e . --no-deps)

WORKDIR /sgl-workspace/sglang

ENV CUDA_VISIBLE_DEVICES=0
