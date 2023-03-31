#! /bin/bash

export MAX_AGREEMENTS=${MAX_AGREEMENTS:-1}
export MIN_AGREEMENT_EXPIRATION=${MIN_AGREEMENT_EXPIRATION:-5s}
export YA_PAYMENT_NETWORK=${YA_PAYMENT_NETWORK:-rinkeby}

echo "Waiting for 1 seconds before starting yagna"
sleep 1
yagna service run &
sleep 5
yagna id list
yagna payment init --receiver --driver erc20 --network $YA_PAYMENT_NETWORK
ya-provider run --max-simultaneous-agreements $MAX_AGREEMENTS --min-agreement-expiration $MIN_AGREEMENT_EXPIRATION

echo "Waiting for 30 seconds before leaving the container..."
sleep 30
echo "Leaving the container..."

