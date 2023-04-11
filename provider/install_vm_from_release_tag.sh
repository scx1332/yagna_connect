#!/bin/bash
set -ex
mkdir tmp
cd tmp
wget -O- https://github.com/golemfactory/ya-runtime-vm/releases/download/$1/ya-runtime-vm-linux-$1.tar.gz | gunzip | tar -xf -
mkdir -p ~/.local/lib/yagna/plugins
mv ya-runtime-vm-linux-$1/ya-runtime-vm.json ~/.local/lib/yagna/plugins/ya-runtime-vm.json
mv ya-runtime-vm-linux-$1/ya-runtime-vm ~/.local/lib/yagna/plugins/ya-runtime-vm
cd ..
rm tmp -r