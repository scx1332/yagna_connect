import argparse
import asyncio
import logging
import shutil
import sys
import traceback
import urllib
from datetime import datetime, timedelta, timezone

import requests
import websockets

import aiohttp
import platform
import time
import json
import os
import scapy
from scapy.all import Raw
from scapy.layers.dns import DNS
from scapy.layers.inet import IP, in4_chksum, UDP
from scapy.layers.l2 import Ether

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BEARER_TOKEN = ""
SUBNET = "vpn"
API_URL = "http://127.0.0.1:7465"
API_URL_WEBSOCKETS = "ws://127.0.0.1:7465"
YAGNA_INTERNAL_WEBSOCKETS = "ws://192.168.65.2:7465"


def string_unescape(s, encoding='utf-8'):
    try:
        if s is None:
            return ""
        return (s.encode('latin1')  # To bytes, required by 'unicode-escape'
                .decode('unicode-escape')  # Perform the actual octal-escaping decode
                .encode('latin1')  # 1:1 mapping back to bytes
                .decode(encoding))  # Decode original encoding
    except Exception as ex:
        logger.error(f"Error decoding string {s}: {ex}")
        return s


class PostException(Exception):
    pass


async def send_request(url, method="get", data=None):
    headers = [
        ('Content-Type', 'application/json'),
        ('Accept', 'application/json'),
        ('Authorization', f'Bearer {bearer_token}')
    ]
    if data:
        data_bytes = data.encode('utf-8')  # needs to be bytes
        headers.append(('Content-Length', str(len(data_bytes))))
    else:
        data_bytes = None

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.request(method, url, data=data_bytes) as result:
                if result.status == 413:
                    logger.error(
                        f"Data exceeded RPC limit, data size {len(data_bytes)} try lowering batch size")
                    raise PostException("Data too big")
                if result.status == 400:
                    logger.error(
                        f"Error 400")
                    logger.error(await result.json())
                    raise PostException("Error 400 received")
                if result.status == 404:
                    logger.error(
                        f"Error 404")
                    logger.error(await result.text())
                    raise PostException("Error 404 received")
                if result.status == 500:
                    logger.error(
                        f"Error 500")
                    logger.error(await result.text())
                    raise PostException("Error 500 received")
                if result.status == 401:
                    logger.error(
                        f"Unauthorized, check your API key, data size")
                    raise PostException("Unauthorized")
                if result.status != 200 and result.status != 201 and result.status != 204:
                    logger.error(f"RPC call failed with status code {result.status}")
                    raise PostException(f"Other error {result.status}")
                try:
                    content = await result.text()
                    return content
                except Exception as ex:
                    logger.error(f"Error reading result {ex}")
                    raise PostException(f"Error reading result {ex}")
    except aiohttp.ClientConnectorError as ex:
        logger.error(f"aiohttp.ClientConnectorError: {ex}")
        raise PostException(f"aiohttp.ClientConnectorError: {ex}")


demand_template = """{
   "properties":{
      "golem.com.payment.debit-notes.accept-timeout?": 240,
      "golem.node.debug.subnet": "%%SUBNET%%",
      "golem.com.payment.chosen-platform": "erc20-rinkeby-tglm",
      "golem.com.payment.platform.erc20-rinkeby-tglm.address": "%%SENDER_ADDRESS%%",
      "golem.srv.comp.expiration": %%EXPIRATION%%
   },
   "constraints":"(&(golem.node.debug.subnet=%%SUBNET%%)(golem.com.payment.platform.erc20-rinkeby-tglm.address=*)(golem.com.pricing.model=linear)(golem.runtime.name=outbound-gateway)(golem.runtime.capabilities=gateway))"
}
"""

next_info = 1


async def prepare_tmp_directory():
    if os.path.exists("tmp"):
        shutil.rmtree("tmp")
    await asyncio.sleep(1.0)
    os.mkdir("tmp")


def dump_next_info(file_name, text):
    global next_info
    with open(f"tmp/{next_info:03}_{file_name}", "w") as f:
        f.write(text)
    next_info += 1


async def create_demand(sender_address):
    now_datetime = datetime.now(timezone.utc)
    agreement_validity_timedelta = timedelta(minutes=30)
    demand_expiration_datetime = now_datetime + agreement_validity_timedelta
    demand_expiration_timestamp = str(int(demand_expiration_datetime.timestamp() * 1000))
    demand_expiration_formatted = now_datetime.astimezone().isoformat()
    logger.info(f"Setting demand expiration to {demand_expiration_formatted} timestamp {demand_expiration_timestamp}")

    demand = json.loads(demand_template
                        .replace("%%EXPIRATION%%", demand_expiration_timestamp)
                        .replace("%%SENDER_ADDRESS%%", sender_address)
                        .replace("%%SUBNET%%", SUBNET))

    dump_next_info("demand.json", json.dumps(demand, indent=4))

    # Yagna daemon is automatically collecting Offers propagated by Providers.
    # To find matching Providers we need to publish Demand on market, which will describe
    # our needs. Market will later return events related to all Offers matching our Demand.
    #
    # Note: In opposition to Offers, our Demand is not propagated to other Nodes and will be visible
    # only to those Nodes, that we start negotiations with.
    demand_id = await send_request(f"{API_URL}/market-api/v1/demands", method="post", data=json.dumps(demand, indent=4))
    demand_id = demand_id.replace('"', '')

    logger.info(f"Demands information: {demand_id}")
    return demand_id, demand


# This function will negotiate single Agreement with the first Provider that will respond
# to us. In normal use cases probably we would like to have more advanced market strategy
# which scores different Proposals based on the price requested in relation to resources offered.
async def negotiate_agreement(sender_address):
    demand_id, demand = await create_demand(sender_address)

    while True:
        max_events = 5
        poll_timeout = 3000

        # Query market for new events (we are interested in new Proposals).
        # Events are incoming asynchronously, since Providers' Offers are broadcasted through
        # the network and aren't available immediately after we publish our Demand.
        events = await send_request(
            f"{API_URL}/market-api/v1/demands/{demand_id}/events?maxEvents={max_events}&pollTimeout={poll_timeout}")
        logger.info(f"Query result: {len(events)} event(s)")
        events = json.loads(events)

        for event in events:
            try:
                # We can get here other events like ProposalRejected, so filtering them out
                if event['eventType'] != 'ProposalEvent':
                    continue

                dump_next_info("event.json", json.dumps(event, indent=4))

                proposal_id = event['proposal']['proposalId']
                logger.info(f"Proposal id: {proposal_id}")

                # Getting full Proposal content from market API
                received_proposal = await send_request(
                    f"{API_URL}/market-api/v1/demands/{demand_id}/proposals/{proposal_id}")
                received_proposal = json.loads(received_proposal)

                dump_next_info("received_proposal.json", json.dumps(received_proposal, indent=4))

                if received_proposal["state"] == "Initial":
                    # In this case we got Proposal from the market, but we didn't talk
                    # with this Provider yet, so we should send counter Proposal.
                    # We just send the same properties and constraints as we sent in Demand before,
                    # because we don't use more advanced negotiations here.
                    proposal_id = received_proposal['proposalId']

                    logger.info(f"Sending counter proposal for {proposal_id}")

                    dump_next_info("counter_proposal.json", json.dumps(demand, indent=4))

                    counter_proposal = await send_request(
                        f"{API_URL}/market-api/v1/demands/{demand_id}/proposals/{proposal_id}",
                        method='post',
                        data=json.dumps(demand))
                    counter_proposal_id = counter_proposal.replace('"', '')
                    logger.info(f"Counter proposal: {counter_proposal_id}")
                elif received_proposal["state"] == "Draft":
                    # In this case Provider responded to our first counter Proposal.
                    # We could try to propose Agreement.
                    proposal_id = received_proposal['proposalId']

                    # `validTo` field specifies, how long will we wait for Agreement proposal acceptance.
                    valid_to = datetime.now(timezone.utc) + timedelta(seconds=30)
                    valid_to_formatted = valid_to.isoformat().replace("+00:00", "Z")
                    agreement_proposal = {
                        "proposalId": proposal_id,
                        "validTo": valid_to_formatted
                    }

                    logger.info(f"Creating Agreement for: {proposal_id}")
                    create_agreement = await send_request(f"{API_URL}/market-api/v1/agreements", method="post",
                                                          data=json.dumps(agreement_proposal))
                    agreement_id = create_agreement.replace('"', '')
                    logger.info(f"agreement_id: {agreement_id}")

                    logger.info(f"Sending Agreement: {agreement_id} to Provider")
                    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/confirm", method="post",
                                       data=None)

                    # We are waiting until Provide will accept our Agreement proposal.
                    # Since Providers can negotiate with multiple Requestors and can implement different
                    # market strategies, we can't be sure if our Agreement will be accepted.
                    # This endpoint will return 410 (Gone) if Provider rejected Agreement proposal
                    # and we need to go back to negotiations with other Providers.
                    logger.info(f"Waiting for Agreement: {agreement_id} Approval")
                    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/wait",
                                       method="post", data=None)
                    logger.info(f"Agreement {agreement_id} approved")

                    # We have signed Agreement and we are returning, without notifying other Providers
                    # that we were negotiating with. It is correct behavior, but to be more gentle, we could
                    # reject all other Proposals.
                    return agreement_id
                else:
                    # Other states are unexpected, so continue the loop
                    continue
            except PostException as ex:
                logger.error(f"Send exception when processing event: {event}")
                pass
            except Exception as ex:
                logger.error(f"Error while processing event: {event}")
                raise ex


async def create_network():
    # Here we will create new virtual network. Thanks to this Requestor and Providers
    # will be able to communicate with each other using standard networking protocols (UDP, TCP).
    # This step doesn't require signed Agreement, so it could be done anywhere in the code.
    ip_remote = "192.168.8.7"
    new_network = {
        "ip": "192.168.8.0/24",
        "mask": "255.255.255.0",
        "gateway": ip_remote
    }
    # This call creates virtual network.
    net_response = await send_request(f"{API_URL}/net-api/v2/vpn/net", method="post", data=json.dumps(new_network))
    net_response = json.loads(net_response)
    net_id = net_response["id"]

    dump_next_info("net_response.json", json.dumps(net_response, indent=4))

    # Assign Requestor ip address in created network.
    ip_addr_resp = await send_request(f"{API_URL}/net-api/v2/vpn/net/{net_id}/addresses")
    ip_local = json.loads(ip_addr_resp)
    if ip_local[0]['ip'] != "192.168.8.1/24":
        logger.error(f"Unexpected local ip {ip_local}")
        raise Exception("Unexpected local ip {ip_local}")

    # Check if local IP is assigned as expected to 192.168.8.1
    ip_addr_resp = await send_request(f"{API_URL}/net-api/v2/vpn/net/{net_id}/addresses")
    ip_local = json.loads(ip_addr_resp)
    if ip_local[0]['ip'] != "192.168.8.1/24":
        logger.error(f"Unexpected local ip {ip_local}")
        raise Exception("Unexpected local ip {ip_local}")

    return net_response, ip_local, ip_remote


async def remove_network(network_id):
    logger.info(f"Removing network: {network_id}")
    await send_request(f"{API_URL}/net-api/v2/vpn/net/{network_id}", method="delete")
    logger.info(f"Network: {network_id} removed")


async def wait_for_batch_finish(activity_id, batch_id):
    current_time = time.time()
    while True:
        # Query batch results until it will be finished.
        response_output = await send_request(
            f"{API_URL}/activity-api/v1/activity/{activity_id}/exec/{batch_id}")
        response_exec_json = json.loads(response_output)
        wait = True
        for batch in response_exec_json:
            if batch['isBatchFinished']:
                wait = False
                break
        if not wait:
            logger.info(f"Batch execution finished")
            break
        logger.info(f"Waiting for batch to finish")
        await asyncio.sleep(1)
        dump_next_info("exec_output.json", json.dumps(response_exec_json, indent=4))
        if time.time() - current_time > 20:
            raise Exception("Timeout waiting for batch to finish")

    dump_next_info("exec_output.json", json.dumps(response_exec_json, indent=4))

    for batch in response_exec_json:
        stdout = batch["stdout"]
        stderr = batch["stderr"]
        batch_id = batch["index"]
        if batch["result"] != "Ok":
            raise Exception(f"Batch {batch_id} failed")

        dump_next_info(f"exec_output_{batch_id}_stdout.log", string_unescape(stdout))
        dump_next_info(f"exec_output_{batch_id}_stderr.log", string_unescape(stderr))


async def create_allocation(platform, wallet, amount):
    # Allocation will be freed after this time and all reserved money
    # will be available for new Agreements.
    valid_to = datetime.now(timezone.utc) + timedelta(hours=24)
    valid_to = valid_to.isoformat().replace("+00:00", "Z")

    allocation = {
        "totalAmount": amount,
        "makeDeposit": False,
        "timeout": valid_to,
        "paymentPlatform": platform,
        "address": wallet
    }
    allocation = await send_request(
        f"{API_URL}/payment-api/v1/allocations", method="post", data=json.dumps(allocation))
    allocation = json.loads(allocation)
    allocation_id = allocation["allocationId"]

    dump_next_info("allocation.json", json.dumps(allocation, indent=4))
    logger.info(f"Created allocation: {allocation_id} for platform: {platform} and wallet: {wallet}")

    return allocation_id


async def release_allocation(allocation_id):
    logger.info(f"Releasing allocation: {allocation_id}")

    await send_request(
        f"{API_URL}/payment-api/v1/allocations/{allocation_id}", method="delete")

    logger.info(f"Allocation: {allocation_id} released")


async def accept_debit_notes(agreement, activity, allocation_id):
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    logger.info("Listening for debit note events")

    while True:
        try:
            # Provider will send DebitNotes in intervals specified in Agreement.
            # We are expected to accept payments for these DebitNotes, otherwise
            # Provider might break Agreement with us.
            logger.info(f"Query debit note events after: {ts}")
            events = await send_request(
                f"{API_URL}/payment-api/v1/debitNoteEvents?afterTimestamp={ts}&timeout=15")
            events = json.loads(events)

            dump_next_info("debit_note_event.json", json.dumps(events, indent=4))
        except Exception as e:
            logger.error("Failed to fetch debit note events: %s", e)
            events = []

        for event in events:
            debit_note_id = event.get("debitNoteId")
            event_date = event.get("eventDate")
            event_type = event.get("eventType")

            # When we query events next time, we want to ignore events, that we
            # already processed. Events are expected to come ordered by timestamps.
            ts = event_date

            if event_type != "DebitNoteReceivedEvent":
                logger.warning("Ignoring DebitNote event type: %s", event_type)
                continue
            if not (debit_note_id and event_date):
                logger.warning("Empty DebitNote event: %r", event)
                continue

            # Event contains limited amount of information. We might need more to verify
            # DebitNote, so let's query full DebitNote content.
            debit_note = await send_request(f"{API_URL}/payment-api/v1/debitNotes/{debit_note_id}")
            debit_note = json.loads(debit_note)
            amount_exact_str = debit_note["totalAmountDue"]

            dump_next_info("debit_note.json", json.dumps(debit_note, indent=4))

            # Check if DebitNote is for Agreement and Activity that we created.
            # On this endpoint we could get DebitNotes for all Agreements created using
            # the same identity.
            if debit_note["agreementId"] != agreement:
                continue
            if debit_note["activityId"] != activity:
                continue

            logger.info(f"Received DebitNote to amount: {float(amount_exact_str)} - exact value {amount_exact_str}")

            # In production code we should validate the amount requested here.
            acceptance = {
                "totalAmountAccepted": amount_exact_str,
                "allocationId": allocation_id,
            }

            # Accepting DebitNotes means, that we agree to pay amount specified in this DebitNote.
            # If we don't agree to pay, we should immediately reject DebitNote and break Agreement.
            # Anyway if we don't accept DebitNotes, then Provider will break Agreement himself.
            # In general, it is better to accept DebitNotes, otherwise Providers may not want to
            # cooperate with us.
            await send_request(f"{API_URL}/payment-api/v1/debitNotes/{debit_note_id}/accept", method="post",
                               data=json.dumps(acceptance))

            logger.info(
                "Debit note %s (amount: %s) accepted",
                debit_note_id,
                amount_exact_str,
            )


async def pay_invoices(agreement, allocation_id, timeout):
    logger.info("Waiting for Invoices to pay..")

    start_ts = datetime.now(timezone.utc)
    ts = start_ts.isoformat().replace("+00:00", "Z")
    while True:
        try:
            # Provider will send Invoice after Agreement will be terminated.
            # Due to problems on Provider side, Invoice might not come, so we wait
            # only for specific time.
            timeout_left = (timedelta(seconds=timeout) - (datetime.now(timezone.utc) - start_ts)).total_seconds()

            if timeout_left < 0.0:
                logger.warning(f"Invoice didn't received in timeout: {timeout}")
                return

            logger.info(f"Query Invoice events after: {ts}, timeout: {timeout_left}")
            events = await send_request(
                f"{API_URL}/payment-api/v1/invoiceEvents?afterTimestamp={ts}&timeout={timeout_left}")
            events = json.loads(events)

            dump_next_info("invoice_event.json", json.dumps(events, indent=4))
        except Exception as e:
            logger.error("Failed to fetch Invoice events: %s", e)
            events = []

        for event in events:
            invoice_id = event.get("invoiceId")
            event_date = event.get("eventDate")
            event_type = event.get("eventType")

            # When we query events next time, we want to ignore events, that we
            # already processed. Events are expected to come ordered by timestamps.
            ts = event_date

            if event_type != "InvoiceReceivedEvent":
                logger.warning("Ignoring invoice event type: %s", event_type)
                continue
            if not (invoice_id and event_date):
                logger.warning("Empty Invoice event: %r", event)
                continue

            # Event contains limited amount of information. We might need more to verify
            # DebitNote, so let's query full DebitNote content.
            invoice = await send_request(f"{API_URL}/payment-api/v1/invoices/{invoice_id}")
            invoice = json.loads(invoice)
            amount_exact_str = invoice["amount"]

            dump_next_info("invoice.json", json.dumps(invoice, indent=4))

            # Check if Invoice is for Agreement and Activity that we created.
            # On this endpoint we could get Invoices for all Agreements created using
            # the same identity.
            if invoice["agreementId"] != agreement:
                continue

            logger.info(f"Received Invoice to amount: {float(amount_exact_str)} - exact value {amount_exact_str}")

            # In production code we should validate the amount requested here.
            acceptance = {
                "totalAmountAccepted": amount_exact_str,
                "allocationId": allocation_id,
            }

            await send_request(f"{API_URL}/payment-api/v1/invoices/{invoice_id}/accept", method="post",
                               data=json.dumps(acceptance))

            logger.info(
                "Invoice %s (amount: %s) accepted",
                invoice_id,
                amount_exact_str,
            )
            return


async def main():
    parser = argparse.ArgumentParser(
        prog='ConnectVPN',
        description='Simple demo script for outbound VPN activity')
    parser.add_argument('--key', help='API key', required=True)
    parser.add_argument('--debug-ignore-payments', help='Ignore payments', action='store_true')
    global bearer_token
    bearer_token = parser.parse_args().key
    ignore_payments = parser.parse_args().debug_ignore_payments
    if ignore_payments:
        logger.warning(f"Payments ignored: {ignore_payments}. This is not proper way to use yagna, only for DEBUGGING.")

    await prepare_tmp_directory()

    me_data = await send_request(f"{API_URL}/me")
    logger.info(f"Identity information: {me_data}")
    me_data = json.loads(me_data)
    sender_address = me_data["identity"]

    # We need to reserve money for future payments.
    if not ignore_payments:
        allocation_id = await create_allocation("erc20-rinkeby-tglm", sender_address, 10)

    # To compute anything, we need to sign Agreement with at least one Provider.
    # This function implements whole negotiations process and returns negotiated Agreement.
    agreement_id = await negotiate_agreement(sender_address)
    logger.info(f"Agreement id successfully negotiated: {agreement_id}")

    try:
        # Get content of the negotiated Agreement. This step is not required, since Agreement
        # consists of final Proposals (Demand and Offer) from negotiation stage and we could
        # already keep track of these information.
        # Showing this method just for convenience.
        aggreement_resp = await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}")
        aggreement = json.loads(aggreement_resp)
        provider_id = aggreement['offer']['providerId']

        # Computations are done in the context of Activity, so we need to create one.
        # Single Agreement can have multiple activities created after each other.
        # Creating new activity will give you clear state of the ExeUnit Runtime.
        # In most cases one activity will be enough to suite your needs.
        activity_request = {
            "agreementId": agreement_id,
            "requestorPubKey": None
        }
        activity = await send_request(f"{API_URL}/activity-api/v1/activity", method="post",
                                      data=json.dumps(activity_request))
        activity = json.loads(activity)
        activity_id = activity['activityId']
        logger.info(f"Activity id: {activity_id}")

        # Provider will start sending DebitNotes in intervals.
        # We need background task, that will validate and accept them to sustain the Agreement.
        if not ignore_payments:
            asyncio.create_task(accept_debit_notes(agreement_id, activity_id, allocation_id))

        (network, local_ip, ip_remote) = await create_network()
        net_id = network["id"]

        # Activity is created, now we need to start ExeUnit Runtime and initialize it.
        # We do this by sending `Deploy` and `Start` commands. In `Deploy` command we specify
        # network configuration.
        commands = [
            {
                "deploy": {
                    "net": [
                        {
                            "id": network["id"],
                            "ip": network["ip"],
                            "mask": network["mask"],
                            # Since we are initializing outbound gateway runtime we assign it
                            # the same address as for default network gateway.
                            "nodeIp": network["gateway"]
                        }
                    ]
                }
            },
            {
                "start": {}
            }
        ]

        str = json.dumps(commands)
        exec_command = {
            "text": str
        }
        logger.info(f"Deploying network on provider {net_id}")
        dump_next_info("exec_command.json", json.dumps(exec_command, indent=4))

        # Execute commands in the context of created activity.
        response_exec = await send_request(f"{API_URL}/activity-api/v1/activity/{activity_id}/exec", method="post",
                                           data=json.dumps(exec_command))
        response_batch_id = response_exec.replace('"', '')
        logger.info(f"Exec batch id: {response_batch_id}")

        # Let's wait until initialization of ExeUnit will be finished.
        await wait_for_batch_finish(activity_id, response_batch_id)

        # To use VPN on our Provider we have to assign IP address to it.

        assign_output = {
            "id": provider_id,
            "ip": ip_remote
        }
        logger.info(f"Assigning output to {net_id}")
        await send_request(f"{API_URL}/net-api/v2/vpn/net/{net_id}/nodes", method="post",
                           data=json.dumps(assign_output))

        nodes = await send_request(f"{API_URL}/net-api/v2/vpn/net/{net_id}/nodes")
        nodes = json.loads(nodes)
        logger.info(f"Nodes: {nodes}")

        remote_port = 22

        headers = {
            "Content-Type": "application/json",
        }
        # wait
        # print("Waiting for 50 seconds")
        # await asyncio.sleep(50)
        if 1:

            ip_local = local_ip[0]["ip"].split("/")[0]
            ws_url = f"{API_URL_WEBSOCKETS}/net-api/v2/vpn/net/{net_id}/raw/from/{ip_local}/to/{ip_remote}"
            logger.info(ws_url)

            ws_url_internal = f"{YAGNA_INTERNAL_WEBSOCKETS}/net-api/v2/vpn/net/{net_id}/raw/from/{ip_local}/to/{ip_remote}"
            ws_url_quoted = urllib.parse.quote(ws_url_internal, safe='')
            logger.info(ws_url_quoted)

            resp = requests.get(f"http://127.0.0.1:3336/attach_vpn?websocket_address={ws_url_quoted}")
            logger.info(resp.text)
            for i in range(0, 10000000):
                resp = requests.get(f"http://127.0.0.1:3336/check_vpn")
                logger.info(f"VPN res: {resp.text}")
                await asyncio.sleep(1)

            # async with websockets.connect(ws_url,
            #                               extra_headers=[('Authorization', f'Bearer {bearer_token}')]) as websocket:
            #     logger.info(f"Connected to websocket")
            #     while True:
            #         packet = Ether(dst=100000, src=2332)/IP(src=ip_local, dst=ip_remote)/UDP(sport=1000,
            #               dport=5000)/Raw(load="Hello World")
            #         packet_raw = scapy.compat.raw(packet)
            #         packet.show()
            #         packet_hex = packet_raw.hex()
            #         logger.info(f"Sending packet {packet_hex}")
            #         await websocket.send(packet_raw)
            #         logger.info(f"Packet sent, waiting for response")
            #         packet_back = await asyncio.wait_for(websocket.recv(), 10)
            #         Ether(packet_back).show()
            #         packet_back_hex = packet_back.hex()
            #         logger.info(f"Got packet back: {packet_back_hex}")
            #         await asyncio.sleep(1)

        # todo websocket
        # aiohttp.ClientSession()


    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        logger.error(f"Error while sending activity events: {e}")
    finally:
        # We should pay for computations here.
        # Invoice will be sent by Provider, after Agreement is terminated, so we spawn
        # task to listen to Invoices asynchronously and terminate Agreement.
        # This way we won't miss incoming event.
        if not ignore_payments:
            payments = asyncio.create_task(pay_invoices(agreement_id, allocation_id, 15))

        # We should always free Provider, by terminating the Agreement.
        terminate_reason = {
            "message": "Finishing agreement",
            "extra": {}
        }
        terminate_agreement = await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/terminate",
                                                 method="post", data=json.dumps(terminate_reason))
        logger.info(f"Agreement terminated: {terminate_agreement}")

        # Release allocation made on the beginning, for funds to be available in other application runs.
        # Allocation will be release automatically after timeout, if we forget about this.
        await remove_network(net_id)
        if not ignore_payments:
            await payments

        if not ignore_payments:
            await release_allocation(allocation_id)


if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
