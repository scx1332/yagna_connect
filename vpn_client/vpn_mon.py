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

yagna_app_key = os.getenv("YAGNA_APPKEY") or "q-24538-4939"
vpn_proc = None
vpn_conn_res = None


async def attach_vpn(websocket_addr):
    command = f"ya-vpn-connector --websocket-address {websocket_addr}"
    print(f"Attaching VPN: {command}")

    global vpn_conn_res
    vpn_conn_res = None

    async def spawn_vpn_process_and_wait():
        global vpn_proc
        os.system("pkill -f ya-vpn-connector")
        await asyncio.sleep(0.2)
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
    # add route via VPN connection
    comm = f"ip route add default via 192.168.8.7"
    print(f"Adding route: {comm}")
    os.system(comm)


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
    app.run(host="0.0.0.0", port=3336, use_reloader=False)


def get_default_interface_info():
    command = "ip route show default"
    result = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = result.communicate()
    res = out.decode('ascii')

    if not res:
        raise Exception("Failed to get default interface")

    interface = res.split(" ")
    if interface[0] != "default":
        raise Exception(f"Invalid interface {interface[0]}")
    if interface[1] != "via":
        raise Exception(f"Invalid via {interface[1]}")
    if interface[3] != "dev":
        raise Exception(f"Invalid dev {interface[3]}")

    gateway = interface[2]
    interface_main = interface[4]

    print(f"Default gateway: {gateway}, main interface: {interface_main}")

    return gateway, interface_main


if __name__ == '__main__':
    # get default gateway
    gateway, interface_main = get_default_interface_info()
    print(f"Default gateway: {gateway}, main interface: {interface_main}")

    command = "dig +short host.docker.internal"
    result = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = result.communicate()
    res = out.decode('ascii')
    host_internal_ip = res.strip()

    print(f"Host docker internal: {host_internal_ip}")

    # add route to host internal

    command = f"ip route add {host_internal_ip} via {gateway} dev {interface_main}"
    os.system(command)

    # delete default route
    command = f"ip route del default"
    os.system(command)

    run()
