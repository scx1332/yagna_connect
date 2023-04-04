#!/bin/bash
set -x
mkdir tmp
cd tmp
wget https://github.com/golemfactory/ya-runtime-outbound/releases/download/$1/ya-runtime-outbound-linux-x86_64
wget https://github.com/golemfactory/ya-runtime-outbound/releases/download/$1/ya-runtime-outbound.json
mkdir -p ~/.local/lib/yagna/plugins
mkdir -p ~/.local/lib/yagna/plugins/ya-runtime-outbound
cp ya-runtime-outbound.json ~/.local/lib/yagna/plugins/ya-runtime-outbound.json
cp ya-runtime-outbound ~/.local/lib/yagna/plugins/ya-runtime-outbound/ya-runtime-outbound
cd ..
rm tmp -r