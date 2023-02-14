# yagna_connect


1. Spinup central net in the folder centralnet

```
docker-compose up -d
```

yagna will communicate with the central net through the port 15758


2. Spinup provider in the folder provider

Prepare environment variables if not done yet
```
pip install web3
python gen_env.py
```

3. Spinup requestor in the folder requestor

Prepare environment variables if not done yet
```
pip install web3
python gen_env.py
```

```
docker-compose up -d
```

Fund payment for requestor
```
http://127.0.0.1:3333/payment_fund
```

Modify docker-compose.yml and common_config.env to your own needs

http://127.0.0.1:3333/

