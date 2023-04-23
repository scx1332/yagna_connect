#!/bin/bash

ya-relay-server -a udp://127.0.0.1:7464 --ip-checker-port 7465

echo "Waiting for 30 seconds before leaving the container..."
sleep 30
echo "Leaving the container..."

