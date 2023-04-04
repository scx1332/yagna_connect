#!/bin/bash
set -ex
mkdir tmp
cd tmp
wget -O- https://github.com/golemfactory/ya-runtime-outbound/releases/download/$1/ya-runtime-outbound-linux-x86_64.gz | gunzip > ya-runtime-outbound
wget https://github.com/golemfactory/ya-runtime-outbound/releases/download/$1/ya-runtime-outbound.json
mkdir -p ~/.local/lib/yagna/plugins
mkdir -p ~/.local/lib/yagna/plugins/ya-runtime-outbound
mv ya-runtime-outbound.json ~/.local/lib/yagna/plugins/ya-runtime-outbound.json
mv ya-runtime-outbound ~/.local/lib/yagna/plugins/ya-runtime-outbound/ya-runtime-outbound
chmod +x ~/.local/lib/yagna/plugins/ya-runtime-outbound/ya-runtime-outbound
cd ..
rm tmp -r