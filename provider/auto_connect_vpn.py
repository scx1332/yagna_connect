import os
import time

import subprocess

test = True


def get_default_interface_info():
    res = "default via 172.18.0.1 dev eth0"
    if not test:
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


def search_for_interface(search_name):
    interfaces = """
        1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
            link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
        2: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN mode DEFAULT group default qlen 1000
            link/ipip 0.0.0.0 brd 0.0.0.0
        3: sit0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN mode DEFAULT group default qlen 1000
            link/sit 0.0.0.0 brd 0.0.0.0
        12: vpn0: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UNKNOWN mode DEFAULT group default qlen 500
            link/none
        59: eth0@if60: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default
            link/ether 02:42:ac:12:00:03 brd ff:ff:ff:ff:ff:ff link-netnsid 0
            """
    if not test:
        command = "ip link show"
        result = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = result.communicate()
        interfaces = out.decode('ascii')

    if not interfaces:
        raise Exception("Failed to get interfaces")

    interfaces = interfaces.split("\n")

    for interface in interfaces:
        split_1 = interface.split(":")
        if len(split_1) >= 2:
            interface_name = split_1[1].strip()
            if interface_name == search_name:
                print(f"Found vpn interface {interface_name}")
                return interface_name
    return None


gateway, main_interface = get_default_interface_info()

while True:
    child_interface = search_for_interface("vpn0")
    if child_interface == "vpn0":
        break

ip_table_rules = [f"-A FORWARD -i {child_interface} -o eth0 -j ACCEPT",
                  f"-A FORWARD -i {main_interface} -o {child_interface} -m state --state ESTABLISHED,RELATED -j ACCEPT",
                  f"-A POSTROUTING -t nat -o {main_interface} -j MASQUERADE"]

command = "iptables -S"
result = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = result.communicate()
existing_ip_tables = out.decode('ascii')
existing_ip_tables.split("\n")

for rule in ip_table_rules:
    if rule in existing_ip_tables:
        print(f"Rule {rule} already exists")
    else:
        print(f"Rule {rule} does not exist, adding")
        os.system(f"iptables {rule}")
