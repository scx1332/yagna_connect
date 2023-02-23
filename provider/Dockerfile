# change token to bypass docker caching system
ARG YA_RUNTIME_OUTBOUND_GIT_CLONE_CACHE_TOKEN=3a826a24-3ada-4c48-bfaa-58d2714ba66e

FROM rust as ya-runtime-outbound-gateway
RUN apt-get update
RUN apt-get install cmake openssl musl-tools -y
ARG YA_RUNTIME_OUTBOUND_GIT_CLONE_CACHE_TOKEN
RUN echo ${YA_RUNTIME_OUTBOUND_GIT_CLONE_CACHE_TOKEN} && git clone --single-branch --branch master https://github.com/golemfactory/ya-runtime-outbound-gateway.git ya-runtime-outbound-gateway
WORKDIR /ya-runtime-outbound-gateway
RUN cargo build --release -p ya-runtime-outbound-gateway


FROM python:3.11
RUN apt-get update
# install common helpful tools
RUN apt-get install -y curl vim jq net-tools htop
# install python requirements for yagna_mon.py
RUN pip install quart requests


WORKDIR /yagna
RUN wget https://github.com/golemfactory/yagna/releases/download/pre-rel-v0.13.0-raw-rc1/golem-provider-linux-pre-rel-v0.13.0-raw-rc1.tar.gz -O - | tar -xz && mv golem-provider-linux-pre-rel-v0.13.0-raw-rc1 golem-binaries

RUN mv golem-binaries/yagna /usr/bin
RUN mv golem-binaries/ya-provider /usr/bin
RUN mv golem-binaries/golemsp /usr/bin
RUN mkdir -p /root/.local/lib/yagna
RUN mv golem-binaries/plugins /root/.local/lib/yagna

# COPY plugins /root/.local/lib/yagna/plugins
COPY ya-provider /root/.local/share/ya-provider

COPY --from=ya-runtime-outbound-gateway /ya-runtime-outbound-gateway/target/release/ya-runtime-outbound-gateway /root/.local/lib/yagna/plugins/ya-runtime-outbound-gateway/ya-runtime-outbound-gateway
COPY --from=ya-runtime-outbound-gateway /ya-runtime-outbound-gateway/conf/ya-runtime-outbound-gateway.json /root/.local/lib/yagna/plugins/ya-runtime-outbound-gateway.json

COPY *.py .
COPY *.sh .
RUN chmod +x *.sh


