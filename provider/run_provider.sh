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
ya-provider preset remove default
if [ "$PROVIDER_ENABLE_VM" == "true" ]; then
  ya-provider preset create --no-interactive --preset-name vm --exe-unit vm --pricing linear --price golem.usage.cpu_sec=1E-12 --price golem.usage.duration_sec=1E-12
  ya-provider preset activate vm
fi
if [ "$PROVIDER_ENABLE_OUTBOUND" == "true" ]; then
  ya-provider preset create --no-interactive --preset-name outbound --exe-unit outbound --pricing linear --price golem.usage.duration_sec=1E-12 --price golem.usage.network.in-mib=1E-12 --price golem.usage.network.out-mib=1E-12
  ya-provider preset activate outbound
fi
ya-provider run --max-simultaneous-agreements $MAX_AGREEMENTS --min-agreement-expiration $MIN_AGREEMENT_EXPIRATION

echo "Waiting for 30 seconds before leaving the container..."
sleep 30
echo "Leaving the container..."

