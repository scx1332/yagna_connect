ARG YAGNA_RELEASE_TAG=pre-rel-v0.13.0-raw-rc4
ARG YAGNA_OUTBOUND_TAG=v0.2.5

FROM python:3.11
RUN apt-get update
# install common helpful tools
RUN apt-get install -y curl vim jq net-tools htop
# install python requirements for yagna_mon.py
RUN pip install quart requests

WORKDIR /yagna_install
COPY install_provider_from_release_tag.sh .
RUN /bin/bash install_provider_from_release_tag.sh ${YAGNA_RELEASE_TAG}

COPY install_outbound_from_release_tag.sh .
RUN /bin/bash install_outbound_from_release_tag.sh ${YAGNA_OUTBOUND_TAG}

COPY *.py .
COPY *.sh .
RUN chmod +x *.sh
