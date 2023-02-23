# yagna_connect


Make sure you are familiar with basic yagna usage:

https://handbook.golem.network/introduction/requestor

https://handbook.golem.network/introduction/provider

Outbound VPN documentation

https://github.com/golemfactory/ya-runtime-outbound-gateway


### 1. [Optional - only for local debugging] Spinup central net in the folder centralnet #### ###

```
docker-compose up -d
```

yagna will communicate with the central net through the port 15758

### 2. Spinup provider in the folder provider ###

Prepare environment variables if not done yet
```
pip install web3
python3 gen_env.py
```

or

```
poetry run python3 gen_env.py
```

### 3. Spinup requestor in the folder requestor ###

Prepare environment variables if not done yet
```
pip install web3
python3 gen_env.py
```

```
docker-compose up -d
```

Fund payment for requestor
```
http://127.0.0.1:3333/payment_fund
```

Modify docker-compose.yml and common_config.env to your own needs

Check status of the requestor
```
http://127.0.0.1:3333/
```

### 4. To communicate with yagna using commands: ###

Optionally find your container with 
```
docker ps
```
or
```
docker-compose ps
```

Go inside container:
```
docker exec -it /requestor-yagna_requestor_node-1 /bin/bash
```
```
yagna id list
yagna payments status
yagna app-key list
yagna app-key create MyKey
yagna app-key list
```

To extract outbound or exe-unit logs from provider:

```
docker ps
docker exec -it provider-prov1-1 /bin/bash
python print_exe_unit_logs.py
python print_outbound_logs.py
```

or from outside the docker:

```
docker exec -t all-prov1-1 python print_outbound_logs.py
```

These scripts are looking for newest activity logs in the container and printing them

### Running ###

You can run using poetry or installed python (which needs some pip installs) as you prefer.

```poetry run python3 connect.py --key <app-key>```

