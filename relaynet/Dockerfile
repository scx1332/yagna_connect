

FROM python:3.11
RUN apt-get update
# install common helpful tools
RUN apt-get install -y curl vim jq net-tools htop
# install python requirements for yagna_mon.py
RUN pip install quart requests

WORKDIR /ya-relay
RUN wget https://github.com/golemfactory/ya-relay/releases/download/v0.2.2/ya-relay-server
RUN chmod +x ya-relay-server
RUN mv /ya-relay/ya-relay-server /usr/bin

COPY *.sh .
RUN chmod +x *.sh

