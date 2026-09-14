# Magrathea lemma gate. Runtime: docker run --network=none (rc gate).
# Lean pin: leanprover/lean4:v4.33.0. No mathlib.
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git gcc g++ make xz-utils libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

ARG ELAN_VERSION=v4.2.4
ARG ELAN_ASSET=elan-x86_64-unknown-linux-gnu.tar.gz
ARG ELAN_SHA256=42b94d4244e8353142c456ec0e4ca6528fd898a6c604d4059f494e706e431f63

ENV ELAN_HOME=/usr/local/elan
ENV PATH=/usr/local/elan/bin:$PATH

RUN curl -fsSL -o /tmp/elan.tgz \
      "https://github.com/leanprover/elan/releases/download/${ELAN_VERSION}/${ELAN_ASSET}" \
    && echo "${ELAN_SHA256}  /tmp/elan.tgz" | sha256sum -c - \
    && tar -xzf /tmp/elan.tgz -C /tmp \
    && chmod +x /tmp/elan-init \
    && /tmp/elan-init -y --no-modify-path --default-toolchain leanprover/lean4:v4.33.0 \
    && rm -f /tmp/elan.tgz /tmp/elan-init \
    && lean --version

WORKDIR /src
CMD ["lake", "build"]
