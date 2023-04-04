#!/bin/bash
set -ex
mkdir tmp
cd tmp
wget -O- https://github.com/golemfactory/yagna/releases/download/$1/golem-requestor-linux-$1.tar.gz | tar -xzf -
mkdir -p ~/.local/bin
mv `find -name yagna` ~/.local/bin/yagna
mv `find -name gftp` ~/.local/bin/gftp
cd ..
rm tmp -r