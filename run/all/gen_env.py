# Script for create .env file with random accounts
# Look at README.md for more details

import random
import secrets
import string
from eth_account import Account

for env_files in ["prov1.env", "prov2.env", "prov3.env"]:
    with open(env_files, "w") as f:
        random_name = ''.join(random.choice(string.ascii_lowercase + string.ascii_uppercase) for _ in range(10))
        f.write(f"# Yagna node name, don't have to be unique but it is nice to have\n")
        f.write(f"NODE_NAME={random_name}\n")
        private_key = secrets.token_hex(32)
        private_key_with0x = "0x" + private_key

        f.write(f"# Yagna private account\n")
        f.write(f"YAGNA_AUTOCONF_ID_SECRET={private_key}\n")
        f.write(f"# This one not needed, added for convenience\n")
        f.write(f"YAGNA_AUTOCONF_PUBLIC_ADDRESS={Account.from_key(private_key_with0x).address}\n")

        random_app_key = ''.join(random.choice(string.digits) for _ in range(20))
        f.write(f"YAGNA_AUTOCONF_APPKEY={random_app_key}\n")
        f.write(f"YAGNA_APPKEY={random_app_key}\n")


with open(".env", "w") as f:
    random_name = ''.join(random.choice(string.ascii_lowercase + string.ascii_uppercase) for _ in range(10))
    f.write(f"# Yagna node name, don't have to be unique but it is nice to have\n")
    f.write(f"NODE_NAME={random_name}\n")
    private_key = secrets.token_hex(32)
    private_key_with0x = "0x" + private_key

    f.write(f"# Yagna private account\n")
    f.write(f"YAGNA_AUTOCONF_ID_SECRET={private_key}\n")
    f.write(f"# This one not needed, added for convenience\n")
    f.write(f"YAGNA_AUTOCONF_PUBLIC_ADDRESS={Account.from_key(private_key_with0x).address}\n")

    random_app_key = ''.join(random.choice(string.digits) for _ in range(20))
    f.write(f"YAGNA_AUTOCONF_APPKEY={random_app_key}\n")
    f.write(f"YAGNA_APPKEY={random_app_key}\n")

