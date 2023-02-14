import asyncio
import logging
import shutil
from datetime import datetime

import aiohttp
import platform
import time
import json
import os

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BEARER_TOKEN = "12909321636293016160"
SUBNET = "vpn"
API_URL = "http://127.0.0.1:7465"


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


async def main():
    me_data = await send_request(f"{API_URL}/me")
    logger.info(f"Identity information: {me_data}")
    # load json
    next_info = 1
    me_data = json.loads(me_data)
    sender_address = me_data["identity"]

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
    agreement_response = await send_request(f"{API_URL}/market-api/v1/agreements", method="post", data=agreement_proposal)
    agreement_id = agreement_response.replace('"', '')
    logger.info(f"Created agreement id: {agreement_id}")

    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/confirm", method="post", data=None)
    logger.info(f"Agreement confirmed")

    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/wait", method="post", data=None)
    logger.info(f"Agreement approved")


if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
