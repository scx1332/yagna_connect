#!/bin/bash
set -x
mkdir tmp
cd tmp
wget https://github.com/golemfactory/yagna/releases/download/$1/golem-provider-linux-$1.tar.gz
tar -xzvf golem-provider-linux-$1.tar.gz
rm golem-provider-linux-$1.tar.gz
mkdir -p ~/.local/bin
cp `find -name yagna` ~/.local/bin/yagna
cp `find -name ya-provider` ~/.local/bin/ya-provider
cp `find -name golemsp` ~/.local/bin/golemsp
mkdir -p ~/.local/lib/yagna/plugins
cp `find -name exe-unit` ~/.local/lib/yagna/plugins/exe-unit
wget https://github.com/golemfactory/yagna/releases/download/$1/golem-requestor-linux-$1.tar.gz
tar -xzvf golem-requestor-linux-$1.tar.gz
rm golem-requestor-linux-$1.tar.gz
cp `find -name gftp` ~/.local/bin/gftp
cd ..
rm tmp -r