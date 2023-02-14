

FROM python:3.11
RUN apt-get update
# install common helpful tools
RUN apt-get install -y curl vim jq net-tools htop
# install python requirements for yagna_mon.py
RUN pip install quart requests

WORKDIR /ya-service-bus
RUN wget https://github.com/golemfactory/ya-service-bus/releases/download/v0.6.1/ya-sb-router-linux-v0.6.1.tar.gz -O - | tar -xz && mv ya-sb-router-linux-v0.6.1 golemsp-binaries
RUN mv golemsp-binaries/ya-sb-router /usr/bin

COPY *.sh .
RUN chmod +x *.sh

