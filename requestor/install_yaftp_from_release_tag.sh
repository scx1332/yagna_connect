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
wget -O- https://github.com/scx1332/yaftp/releases/download/$1/yaftp-linux-x86_64.tar.xz | xz --decompress | tar -xf -
mkdir -p ~/.local/bin
mv yaftp ~/.local/bin/yaftp
chmod +x ~/.local/bin/yaftp
cd ..
rm tmp -r