#! /bin/bash

export YAGNA_AUTOCONF_APPKEY=${YAGNA_AUTOCONF_APPKEY-q$RANDOM$RANDOM}
export YAGNA_APPKEY=${YAGNA_AUTOCONF_APPKEY}
export NETWORK=${NETWORK:-rinkeby}
export SUBNET=${SUBNET:-payment_testing_subnet}
export NODE_NAME=${NODE_NAME:-polygon_proxy}
export YA_PAYMENT_NETWORK=${NETWORK:-rinkeby}

export MAX_AGREEMENTS=${MAX_AGREEMENTS:-1}
export MIN_AGREEMENT_EXPIRATION=${MIN_AGREEMENT_EXPIRATION:-5s}

echo "Waiting for 5 seconds before starting yagna"
sleep 5
yagna service run &
sleep 5
yagna id list
yagna payment init --receiver --driver erc20 --network $NETWORK
ya-provider run --max-simultaneous-agreements $MAX_AGREEMENTS --min-agreement-expiration $MIN_AGREEMENT_EXPIRATION

echo "Waiting for 30 seconds before leaving the container..."
sleep 30
echo "Leaving the container..."

