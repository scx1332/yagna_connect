ARG YAGNA_RELEASE_TAG=pre-rel-v0.13.0-raw-rc4
ARG YAFTP_RELEASE_TAG=v0.3.10

FROM python:3.11
RUN apt-get update
# install common helpful tools
RUN apt-get install -y curl vim jq net-tools htop iptables build-essential iputils-ping iproute2 dnsutils ncat tcpdump
# install helpful python libraries
RUN pip install quart requests websockets scapy aiohttp

ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /yagna_install
COPY install_requestor_from_release_tag.sh .
ARG YAGNA_RELEASE_TAG
RUN /bin/bash install_requestor_from_release_tag.sh ${YAGNA_RELEASE_TAG}

COPY install_yaftp_from_release_tag.sh .
ARG YAFTP_RELEASE_TAG
RUN /bin/bash install_yaftp_from_release_tag.sh ${YAFTP_RELEASE_TAG}

COPY *.py ./
COPY *.sh ./
RUN chmod +x *.sh


