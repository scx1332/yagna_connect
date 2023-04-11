#!/bin/bash
if [ -z ${1+x} ]; then
  echo "Need argument with release tag or NO_INSTALL";
  exit 0
fi
if [ "$1" == "NO_INSTALL" ]; then
  echo "Skipping installation of outbound runtime"
  exit 0
fi
set -ex
mkdir tmp
cd tmp
wget -O- https://github.com/golemfactory/ya-runtime-outbound/releases/download/$1/ya-runtime-outbound-linux-x86_64.tar.xz | xz --decompress | tar -xf -
wget https://github.com/golemfactory/ya-runtime-outbound/releases/download/$1/ya-runtime-outbound.json
mkdir -p ~/.local/lib/yagna/plugins
mkdir -p ~/.local/lib/yagna/plugins/ya-runtime-outbound
mv ya-runtime-outbound.json ~/.local/lib/yagna/plugins/ya-runtime-outbound.json
mv ya-runtime-outbound ~/.local/lib/yagna/plugins/ya-runtime-outbound/ya-runtime-outbound
chmod +x ~/.local/lib/yagna/plugins/ya-runtime-outbound/ya-runtime-outbound
cd ..
rm tmp -r