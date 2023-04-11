#!/bin/bash
if [ -z ${1+x} ]; then
  echo "Need argument with release tag or NO_INSTALL";
  exit 0
fi
if [ "$1" == "NO_INSTALL" ]; then
  echo "Skipping installation of VM runtime"
  exit 0
fi
set -ex
mkdir tmp
cd tmp
wget -O- https://github.com/golemfactory/ya-runtime-vm/releases/download/$1/ya-runtime-vm-linux-$1.tar.gz | gunzip | tar -xf -
mkdir -p ~/.local/lib/yagna/plugins
mv ya-runtime-vm-linux-$1/ya-runtime-vm.json ~/.local/lib/yagna/plugins/ya-runtime-vm.json
mv ya-runtime-vm-linux-$1/ya-runtime-vm ~/.local/lib/yagna/plugins/ya-runtime-vm
cd ..
rm tmp -r