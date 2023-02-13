FROM python:3.11
RUN apt-get update
# install common helpful tools
RUN apt-get install -y curl vim jq net-tools htop
# install python requirements for yagna_mon.py
RUN pip install quart requests


WORKDIR /yagna
RUN wget https://github.com/golemfactory/yagna/releases/download/v0.12.0/golem-requestor-linux-v0.12.0.tar.gz -O - | tar -xz && mv golem-requestor-linux-v0.12.0 golem-binaries

RUN mv golem-binaries/yagna /usr/bin

COPY *.py .
COPY *.sh .
RUN chmod +x *.sh


