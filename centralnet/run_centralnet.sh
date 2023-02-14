#! /bin/bash

ya-sb-router -l tcp://0.0.0.0:15758

echo "Waiting for 30 seconds before leaving the container..."
sleep 30
echo "Leaving the container..."

