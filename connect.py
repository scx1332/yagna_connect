import asyncio
import logging
from datetime import datetime

import aiohttp
import platform
import time
import json
import os

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


BEARER_TOKEN = "71028674574053709964"
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


demand_template = """
{
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

proposal_template = """
{
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
async def main():
    me_data = await send_request(f"{API_URL}/me")
    print(f"Identity information: {me_data}")
    # load json
    me_data = json.loads(me_data)
    sender_address = me_data["identity"]

    demand_json = demand_template\
        .replace("%%EXPIRATION%%", str(int(time.time() * 1000 + 3600 * 1000)))\
        .replace("%%SENDER_ADDRESS%%", sender_address)\
        .replace("%%SUBNET%%", SUBNET)

    if not os.path.exists("tmp"):
        os.mkdir("tmp")

    # validate json
    json.loads(demand_json)
    print(f"Writting demand to tmp/demand.json")
    with open("tmp/demand.json", "w") as f:
        f.write(demand_json)

    # Create Demand on Market
    demand_id = await send_request(f"{API_URL}/market-api/v1/demands", "post", data=demand_json)
    demand_id = demand_id.replace('"', '')
    print(f"Demands information: {demand_id}")

    while True:
        max_events = 5
        poll_timeout = 3000
        poll = await send_request(f"{API_URL}/market-api/v1/demands/{demand_id}/events?maxEvents={max_events}&pollTimeout={poll_timeout}")
        print(f"Poll result: {poll}")
        poll_json = json.loads(poll)

        if len(poll_json) > 0:
            for poll_res in poll_json:
                if poll_res['eventType'] != 'ProposalEvent':
                    continue
                print(f"Proposal: {poll_res['proposal']}")
                with open("tmp/event.json", "w") as f:
                    f.write(json.dumps(poll_res, indent=4))
                proposal_id = poll_res['proposal']['proposalId']
                print(f"Proposal id: {proposal_id}")
                send_proposal = await send_request(f"{API_URL}/market-api/v1/demands/{demand_id}/proposals/{proposal_id}")
                print(f"Writing proposal to file tmp/proposal.json")
                send_proposal_json = json.loads(send_proposal)
                with open("tmp/proposal.json", "w") as f:
                    f.write(json.dumps(send_proposal_json, indent=4))

                if proposal_id != send_proposal_json['proposalId']:
                    raise Exception("Proposal id mismatch")
                proposal_id = send_proposal_json['proposalId']
                print(f"{API_URL}/market-api/v1/demands/{demand_id}/proposals/{proposal_id}")
                counter_proposal = await send_request(f"{API_URL}/market-api/v1/demands/{demand_id}/proposals/{proposal_id}", 'post', demand_json)
                counter_proposal = counter_proposal.replace('"', '')
                print(f"Counter proposal: {counter_proposal}")


                #confirm_agreement = await send_request(f"http://127.0.0.1:7465/market-api/v1/agreements", 'post', send_proposal)
                #print(f"Confirm agreement: {confirm_agreement}")

                while True:
                    max_events = 5
                    poll_timeout = 3000
                    print(f"Polling for events: {max_events} {poll_timeout}")
                    poll = await send_request(f"{API_URL}/market-api/v1/demands/{demand_id}/events?maxEvents={max_events}&pollTimeout={poll_timeout}")
                    poll_json = json.loads(poll)
                    for poll_res in poll_json:
                        print(f"Poll result: {json.dumps(poll_res, indent=4)}")
                        if poll_res['eventType'] != 'ProposalEvent':
                            continue
                        if "prevProposalId" not in poll_res['proposal']:
                            continue
                        if poll_res['proposal']["prevProposalId"] != counter_proposal:
                            continue
                        print(f"Proposal: {poll_res['proposal']}")
                        proposal_id = poll_res['proposal']['proposalId']
                        agreement_proposal = {
                            "proposalId": proposal_id,
                            "validTo": datetime.now().isoformat() + "Z"
                        }
                        agreement_proposal = json.dumps(agreement_proposal)
                        print(f"Agreement proposal: {agreement_proposal}")
                        create_agreement = await send_request(f"{API_URL}/market-api/v1/agreements", "post", data=agreement_proposal)
                        print(f"Create agreement: {create_agreement}")
                        agreement_id = create_agreement.replace('"', '')
                        print(f"Agreement id: {agreement_id}")

                        confirm_agreement = await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/confirm", "post", data=None)
                        print(f"Confirm agreement: {confirm_agreement}")

                        wait_for_agreement = await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/wait", "post", data=None)
                        print(f"Wait for agreement: {wait_for_agreement}")


                    await asyncio.sleep(10)

    await asyncio.sleep(10)









if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
