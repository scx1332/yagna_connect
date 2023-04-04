ARG YAGNA_RELEASE_TAG=pre-rel-v0.13.0-raw-rc4
ARG RUNTIME_OUTBOUND_RELEASE_TAG=v0.3.0

FROM python:3.11
RUN apt-get update
# install common helpful tools
RUN apt-get install -y curl vim jq net-tools htop iptables build-essential iputils-ping iproute2 dnsutils ncat tcpdump
# install helpful python libraries
RUN pip install quart requests websockets scapy aiohttp

ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /yagna_install
COPY install_provider_from_release_tag.sh .
ARG YAGNA_RELEASE_TAG
RUN /bin/bash install_provider_from_release_tag.sh ${YAGNA_RELEASE_TAG}

COPY install_outbound_from_release_tag.sh .
ARG RUNTIME_OUTBOUND_RELEASE_TAG
RUN /bin/bash install_outbound_from_release_tag.sh ${RUNTIME_OUTBOUND_RELEASE_TAG}

COPY ya-provider /root/.local/share/ya-provider
COPY ya-runtime-outbound /root/.local/share/ya-runtime-outbound

COPY *.py .
COPY *.sh .
RUN chmod +x *.sh
