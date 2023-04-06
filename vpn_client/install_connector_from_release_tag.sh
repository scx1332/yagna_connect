#!/bin/bash
set -ex
mkdir tmp
cd tmp
wget -O- https://github.com/golemfactory/ya-vpn-connector/releases/download/$1/ya-vpn-connector-linux-x86_64.tar.xz | xz --decompress | tar -xf -
mv `find -name ya-vpn-connector` /usr/bin
cd ..
rm tmp -r