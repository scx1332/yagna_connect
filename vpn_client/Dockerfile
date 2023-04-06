ARG CONNECTOR_RELEASE_TAG=v0.2.6

FROM python:3.11
RUN apt-get update
# install common helpful tools
RUN apt-get install -y curl vim jq net-tools htop iptables build-essential iputils-ping iproute2 dnsutils ncat tcpdump
# install helpful python libraries
RUN pip install quart requests websockets scapy aiohttp

WORKDIR /connector_install
COPY install_connector_from_release_tag.sh .
ARG CONNECTOR_RELEASE_TAG
RUN /bin/bash install_connector_from_release_tag.sh ${CONNECTOR_RELEASE_TAG}

COPY *.py ./
COPY *.sh ./
RUN chmod +x *.sh
