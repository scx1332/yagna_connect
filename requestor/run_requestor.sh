#! /bin/bash
python -u yagna_mon.py&
yagna service run
#sleep 5
#python -u connect.py --key ${YAGNA_APPKEY}

