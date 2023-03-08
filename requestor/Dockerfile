FROM python:3.11
RUN apt-get update
# install common helpful tools
RUN apt-get install -y curl vim jq net-tools htop iptables build-essential iputils-ping iproute2 dnsutils ncat
# install python requirements for yagna_mon.py
RUN pip install quart requests


WORKDIR /yagna
RUN wget https://github.com/golemfactory/yagna/releases/download/pre-rel-v0.13.0-raw-rc1/golem-provider-linux-pre-rel-v0.13.0-raw-rc1.tar.gz -O - | tar -xz && mv golem-provider-linux-pre-rel-v0.13.0-raw-rc1 golem-binaries

RUN mv golem-binaries/yagna /usr/bin

COPY *.py ./
COPY *.sh ./
RUN chmod +x *.sh


