import asyncio
import logging
import shutil
from datetime import datetime, timedelta, timezone
import websockets

import aiohttp
import platform
import time
import json
import os

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BEARER_TOKEN = "65742089207217182944"
SUBNET = "vpn"
API_URL = "http://127.0.0.1:7465"
API_URL_WEBSOCKETS = "ws://127.0.0.1:7465"


def string_unescape(s, encoding='utf-8'):
    return (s.encode('latin1')  # To bytes, required by 'unicode-escape'
            .decode('unicode-escape')  # Perform the actual octal-escaping decode
            .encode('latin1')  # 1:1 mapping back to bytes
            .decode(encoding))  # Decode original encoding


class PostException(Exception):
    pass


async def send_request(url, method="get", data=None):
    headers = [
        ('Content-Type', 'application/json'),
        ('Accept', 'application/json'),
        ('Authorization', f'Bearer {BEARER_TOKEN}')
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
                    logger.error(await result.text())
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


async def get_proposal_event(demand_id, prev_proposal_id=None, max_events=5, poll_timeout=3000):
    while True:
        poll = await send_request(
            f"{API_URL}/market-api/v1/demands/{demand_id}/events?maxEvents={max_events}&pollTimeout={poll_timeout}")
        poll_json = json.loads(poll)
        for poll_res in poll_json:
            if poll_res['eventType'] != 'ProposalEvent':
                continue
            if prev_proposal_id and "prevProposalId" not in poll_res['proposal']:
                continue
            if prev_proposal_id and poll_res['proposal']["prevProposalId"] != prev_proposal_id:
                continue

            return poll_res
        await asyncio.sleep(10)


async def negotiate_agreement(sender_address):
    now_datetime = datetime.now(timezone.utc)
    agreement_validity_timedelta = timedelta(minutes=30)
    demand_expiration_datetime = now_datetime + agreement_validity_timedelta
    demand_expiration_timestamp = str(int(demand_expiration_datetime.timestamp() * 1000))
    demand_expiration_formatted = now_datetime.astimezone().isoformat()
    demand_expiration_formatted_z = demand_expiration_datetime.isoformat().replace("+00:00", "Z")
    logger.info(f"Setting demand expiration to {demand_expiration_formatted}")
    logger.info(f"  Formatted for demand (timestamp microseconds): {demand_expiration_timestamp}")
    logger.info(f"  Formatted for json post (ISO format with Z at the end): {demand_expiration_formatted_z}")

    demand = json.loads(demand_template \
                        .replace("%%EXPIRATION%%", demand_expiration_timestamp) \
                        .replace("%%SENDER_ADDRESS%%", sender_address) \
                        .replace("%%SUBNET%%", SUBNET))

    dump_next_info("demand.json", json.dumps(demand, indent=4))
    demand_id = await send_request(f"{API_URL}/market-api/v1/demands", method="post", data=json.dumps(demand, indent=4))
    demand_id = demand_id.replace('"', '')
    logger.info(f"Demands information: {demand_id}")

    while True:
        max_events = 5
        poll_timeout = 3000

        # Query market for new events (we are interested in new Proposals)
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
                    agreement_proposal = {
                        "proposalId": proposal_id,
                        "validTo": demand_expiration_formatted_z
                    }

                    logger.info(f"Creating Agreement for: {proposal_id}")
                    create_agreement = await send_request(f"{API_URL}/market-api/v1/agreements", method="post",
                                                          data=json.dumps(agreement_proposal))
                    agreement_id = create_agreement.replace('"', '')
                    logger.info(f"agreement_id: {agreement_id}")

                    logger.info(f"Sending Agreement: {agreement_id} to Provider")
                    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/confirm", method="post",
                                       data=None)

                    logger.info(f"Waiting for Agreement: {agreement_id} Approval")
                    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/wait",
                                       method="post", data=None)
                    logger.info(f"Agreement {agreement_id} approved")
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


async def main():
    await prepare_tmp_directory()

    me_data = await send_request(f"{API_URL}/me")
    logger.info(f"Identity information: {me_data}")
    me_data = json.loads(me_data)
    sender_address = me_data["identity"]

    agreement_id = await negotiate_agreement(sender_address)
    logger.info(f"Agreement id successfully negotiated: {agreement_id}")

    aggreement_resp = await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}")
    aggreement = json.loads(aggreement_resp)
    provider_id = aggreement['offer']['providerId']
    activity_request = {
        "agreementId": agreement_id,
        "requestorPubKey": None
    }
    activity = await send_request(f"{API_URL}/activity-api/v1/activity", method="post",
                                  data=json.dumps(activity_request))
    activity = json.loads(activity)
    activity_id = activity['activityId']
    logger.info(f"Activity id: {activity_id}")

    try:
        ip_remote = "192.168.8.7"
        new_network = {
            "ip": "192.168.8.0/24",
            "mask": "255.255.255.0",
            "gateway": ip_remote
        }
        net_response = await send_request(f"{API_URL}/net-api/v2/vpn/net", method="post", data=json.dumps(new_network))
        net_response = json.loads(net_response)
        net_id = net_response["id"]

        dump_next_info("net_response.json", json.dumps(net_response, indent=4))

        ip_addr_resp = await send_request(f"{API_URL}/net-api/v2/vpn/net/{net_id}/addresses")
        ip_local = json.loads(ip_addr_resp)
        if ip_local[0]['ip'] != "192.168.8.1/24":
            logger.error(f"Unexpected local ip {ip_local}")
            raise Exception("Unexpected local ip {ip_local}")
        ip_local = "192.168.8.1"

        commands = [
            {
                "deploy": {
                    "net": [
                        {
                            "id": net_id,
                            "ip": net_response["ip"],
                            "mask": net_response["mask"],
                            "nodeIp": ip_remote
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

        response_exec = await send_request(f"{API_URL}/activity-api/v1/activity/{activity_id}/exec", method="post",
                                           data=json.dumps(exec_command))
        response_batch_id = response_exec.replace('"', '')
        logger.info(f"Exec batch id: {response_batch_id}")

        current_time = time.time()
        while True:
            response_output = await send_request(
                f"{API_URL}/activity-api/v1/activity/{activity_id}/exec/{response_batch_id}")
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
            if stderr:
                dump_next_info(f"exec_output_{batch_id}_stderr.log", string_unescape(stderr))

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
        if 1:
            async with websockets.connect(f"{API_URL_WEBSOCKETS}/net-api/v2/vpn/net/{net_id}/tcp/{ip_remote}/50671",
                                          extra_headers=[('Authorization', f'Bearer {BEARER_TOKEN}')]) as websocket:
                logger.info(f"Connected to websocket")
                while True:
                    await websocket.send("Hello")
                    logger.info(f"Sent message")
                    break

        # todo websocket
        # aiohttp.ClientSession()


    except Exception as e:
        logger.error(f"Error while sending activity events: {e}")
    finally:
        terminate_reason = {
            "message": "Finishing agreement",
            "extra": {}
        }
        terminate_agreement = await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/terminate",
                                                 method="post", data=json.dumps(terminate_reason))
        logger.info(f"Agreement terminated: {terminate_agreement}")


if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
