import asyncio
import logging
import shutil
from datetime import datetime
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
    return (s.encode('latin1')         # To bytes, required by 'unicode-escape'
            .decode('unicode-escape') # Perform the actual octal-escaping decode
            .encode('latin1')         # 1:1 mapping back to bytes
            .decode(encoding))        # Decode original encoding


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


async def negotiate_aggreement(sender_address):
    demand_json = demand_template \
        .replace("%%EXPIRATION%%", str(int(time.time() * 1000 + 3600 * 1000))) \
        .replace("%%SENDER_ADDRESS%%", sender_address) \
        .replace("%%SUBNET%%", SUBNET)

    if os.path.exists("tmp"):
        shutil.rmtree("tmp")
        await asyncio.sleep(1.0)
    os.mkdir("tmp")

    # validate json
    json.loads(demand_json)
    global next_info
    with open(f"tmp/{next_info:03}_demand.json", "w") as f:
        f.write(demand_json)
    next_info += 1

    # Create Demand on Market
    demand_id = await send_request(f"{API_URL}/market-api/v1/demands", method="post", data=demand_json)
    demand_id = demand_id.replace('"', '')
    logger.info(f"Demands information: {demand_id}")

    poll_event = await get_proposal_event(demand_id)

    with open(f"tmp/{next_info:03}_event.json", "w") as f:
        f.write(json.dumps(poll_event, indent=4))
        next_info += 1

    proposal = poll_event['proposal']
    proposal_id = proposal['proposalId']

    counter_proposal = await send_request(f"{API_URL}/market-api/v1/demands/{demand_id}/proposals/{proposal_id}",
                                          method='post', data=demand_json)
    counter_proposal_id = counter_proposal.replace('"', '')
    logger.info(f"Counter proposal: {counter_proposal_id}")
    poll_event = await get_proposal_event(demand_id, counter_proposal_id)
    logger.info(f"Received second proposal event after counter proposal")

    with open(f"tmp/{next_info:03}_proposal_event.json", "w") as f:
        f.write(json.dumps(poll_event, indent=4))
        next_info += 1

    proposal_id = poll_event['proposal']['proposalId']
    agreement_proposal = {
        "proposalId": proposal_id,
        "validTo": datetime.now().isoformat() + "Z"
    }
    agreement_proposal = json.dumps(agreement_proposal)
    with open(f"tmp/{next_info:03}_agreement_proposal.json", "w") as f:
        f.write(json.dumps(agreement_proposal, indent=4))
        next_info += 1
    logger.info(f"Agreement proposal: {agreement_proposal}")
    agreement_response = await send_request(f"{API_URL}/market-api/v1/agreements", method="post",
                                            data=agreement_proposal)
    agreement_id = agreement_response.replace('"', '')
    logger.info(f"Created agreement id: {agreement_id}")

    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/confirm", method="post", data=None)
    logger.info(f"Agreement confirmed")

    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/wait", method="post", data=None)
    logger.info(f"Agreement approved")
    return agreement_id


async def main():
    me_data = await send_request(f"{API_URL}/me")
    logger.info(f"Identity information: {me_data}")
    me_data = json.loads(me_data)
    sender_address = me_data["identity"]

    agreement_id = await negotiate_aggreement(sender_address)
    logger.info(f"Agreement id successfully negotiated: {agreement_id}")

    aggreement_resp = await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}")
    aggreement = json.loads(aggreement_resp)

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
        new_network = {
            "ip": "192.168.8.0",
            "mask": "255.255.255.0",
            "gateway": None
        }
        net_response = await send_request(f"{API_URL}/net-api/v2/vpn/net", method="post", data=json.dumps(new_network))
        net_response = json.loads(net_response)
        net_id = net_response["id"]
        global next_info
        with open(f"tmp/{next_info:03}_net_response.json", "w") as f:
            f.write(json.dumps(net_response, indent=4))
            next_info += 1

        ip_remote = "192.168.8.7"
        ip_local = "192.168.8.12"

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
        print(f"Deploying network on provider {net_id}")
        with open(f"tmp/{next_info:03}_exec_command.json", "w") as f:
            f.write(json.dumps(commands, indent=4))
            next_info += 1

        response_exec = await send_request(f"{API_URL}/activity-api/v1/activity/{activity_id}/exec", method="post",
                                           data=json.dumps(exec_command))
        response_batch_id = response_exec.replace('"', '')
        print(f"Exec batch id: {response_batch_id}")

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
                print(f"Batch execution finished")
                break
            print(f"Waiting for batch to finish")
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
            "id": sender_address,
            "ip": ip_local
        }
        print(f"Assigning output to {net_id}")
        await send_request(f"{API_URL}/net-api/v2/vpn/net/{net_id}/nodes", method="post",
                           data=json.dumps(assign_output))

        nodes = await send_request(f"{API_URL}/net-api/v2/vpn/net/{net_id}/nodes")
        nodes = json.loads(nodes)
        print(f"Nodes: {nodes}")

        remote_port = 22

        headers = {
            "Content-Type": "application/json",
        }
        if 1:
            async with websockets.connect(f"{API_URL_WEBSOCKETS}/net-api/v2/vpn/net/{net_id}/tcp/{ip_remote}/50671", extra_headers=[('Authorization', f'Bearer {BEARER_TOKEN}')]) as websocket:
                print(f"Connected to websocket")
                while True:
                    await websocket.send("Hello")
                    print(f"Sent message")
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
