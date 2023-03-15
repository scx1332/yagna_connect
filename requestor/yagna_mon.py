import asyncio
import logging
import os
import json
import time
import quart
from quart import request
from quart import g
import subprocess
import requests

app = quart.Quart(__name__)

yagna_initialized = False
payment_initialized = False

yagna_app_key = os.getenv("YAGNA_APPKEY") or "q-24538-4939"


def check_me():
    endpoint = "http://127.0.0.1:7465/me"
    # data = {"ip": "1.1.2.3"}
    headers = {"Authorization": f"Bearer {yagna_app_key}"}

    identity = requests.get(endpoint, headers=headers).json()
    return identity


def init_sender():
    command = "yagna payment init --sender"
    print(f"Executing command {command}")
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()
    if err:
        raise Exception(err)
    return True


def testnet_fund():
    command = "yagna payment fund"
    print(f"Executing command {command}")
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()
    if err:
        raise Exception(err)
    return True


def check_payments():
    command = f"yagna payment status --json"
    print(f"Executing command {command}")
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()
    payments = json.loads(out)
    print(payments)
    return payments


vpn_proc = None
vpn_conn_res = None


async def attach_vpn(websocket_addr):
    command = f"ya-vpn-connector --websocket-address {websocket_addr}"
    print(f"Attaching VPN: {command}")

    global vpn_conn_res
    vpn_conn_res = None

    async def spawn_vpn_process_and_wait():
        global vpn_proc
        if vpn_proc:
            vpn_proc.kill()
            await asyncio.sleep(1.0)
        vpn_proc = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = await vpn_proc.communicate()
        vpn_proc = None
        if err:
            print(f"Error when leaving process vpn connector {err}")
        global vpn_conn_res
        vpn_conn_res = err.decode('ascii')
        print(err)

    asyncio.create_task(spawn_vpn_process_and_wait())

    await asyncio.sleep(3.0)
    if vpn_conn_res:
        raise Exception(f"{vpn_conn_res}")





@app.route('/')
async def index():
    identity_info = check_me() if yagna_initialized else {}
    payment_details = check_payments() if payment_initialized else {}

    info = {
        "yagna_initialized": yagna_initialized,
        "payment_initialized": payment_initialized,
        "payment_details": payment_details,
        "identity_info": identity_info
    }
    return quart.jsonify(info)


@app.route('/payment_init')
async def payment_init():
    try:
        init_sender()
    except Exception as ex1:
        return quart.jsonify({"result": str(ex1)})
    return quart.jsonify({"result": "success"})


@app.route('/payment_fund')
async def payment_fund():
    try:
        testnet_fund()
    except Exception as ex1:
        return quart.jsonify({"result": str(ex1)})
    return quart.jsonify({"result": "success"})


@app.route('/attach_vpn')
async def attach_vpn_endpoint():
    try:
        websocket_addr = request.args.get('websocket_address')
        await attach_vpn(websocket_addr)
    except Exception as ex1:
        return str(ex1)
    return quart.jsonify({"result": "success"})


@app.route('/check_vpn')
async def check_vpn_endpoint():
    try:
        global vpn_proc
        if vpn_proc:
            return quart.jsonify({"result": "running"})
        else:
            return quart.jsonify({"result": "stopped"})
    except Exception as ex1:
        return str(ex1)
    return quart.jsonify({"result": "success"})


def run() -> None:
    app.run(host="0.0.0.0", port=3333, use_reloader=False)


def check_for_yagna_startup(max_tries: int):
    for tries in range(0, max_tries):
        try:
            time.sleep(1.0)
            print(f"Calling yagna identity... (try no: {tries + 1})")
            check_me()
            return True
        except Exception as ex:
            print(ex)
    return False


def initialize_payments(max_tries: int):
    for tries in range(0, max_tries):
        try:
            time.sleep(1.0)
            print(f"Initializing payments... (try no: {tries + 1})")
            init_sender()
            return True
            break
        except Exception as ex:
            print(ex)
    return False


if __name__ == '__main__':
    os.unsetenv("RUST_LOG")
    yagna_initialized = check_for_yagna_startup(10)
    if yagna_initialized:
        payment_initialized = initialize_payments(5)

    run()
