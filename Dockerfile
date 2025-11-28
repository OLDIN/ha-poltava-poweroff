FROM mcr.microsoft.com/devcontainers/python:1-3.13

RUN \
    apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        git \
        cmake \
        libturbojpeg0-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .pre-commit-config.yaml ./
RUN pip install --no-cache-dir -r requirements.txt

ENV SHELL=/bin/bash
