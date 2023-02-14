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

BEARER_TOKEN = "12909321636293016160"
SUBNET = "vpn"
API_URL = "http://127.0.0.1:74651


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


async def negotiate_agreement(demand, demand_id):
    while True:
        max_events = 5
        poll_timeout = 3000

        # Query market for new events (we are interested in new Proposals)
        events = await send_request(
            f"{API_URL}/market-api/v1/demands/{demand_id}/events?maxEvents={max_events}&pollTimeout={poll_timeout}")
        print(f"Query result: {len(events)} event(s)")
        events = json.loads(events)

        for event in events:
            try:
                # We can get here other events like ProposalRejected, so filtering them out
                if event['eventType'] != 'ProposalEvent':
                    continue

                with open("tmp/event.json", "w") as f:
                    f.write(json.dumps(event, indent=4))

                proposal_id = event['proposal']['proposalId']
                print(f"Proposal id: {proposal_id}")

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

                    print(f"Sending counter proposal for {proposal_id}")
                    counter_proposal = await send_request(
                        f"{API_URL}/market-api/v1/demands/{demand_id}/proposals/{proposal_id}", 'post', demand)
                    counter_proposal_id = counter_proposal.replace('"', '')
                    print(f"Counter proposal: {counter_proposal_id}")
                elif received_proposal["state"] == "Draft":
                    # In this case Provider responded to our first counter Proposal.
                    # We could try to propose Agreement.
                    proposal_id = received_proposal['proposalId']
                    agreement_proposal = {
                        "proposalId": proposal_id,
                        "validTo": datetime.now().isoformat() + "Z"
                    }

                    print(f"Creating Agreement for: {proposal_id}")
                    create_agreement = await send_request(f"{API_URL}/market-api/v1/agreements", "post",
                                                       data=json.dumps(agreement_proposal))
                    agreement_id = create_agreement.replace('"', '')
                    print(f"agreement_id: {agreement_id}")

                    print(f"Agreement id: {agreement_id}")
                    print(f"Sending Agreement: {agreement_id} to Provider")
                    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/confirm", "post", data=None)

                    print(f"Waiting for Agreement: {agreement_id} Approval")
                    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/wait",
                                                            "post", data=None)
                    print(f"Agreement {agreement_id} approved")
                    return agreement_id
                else:
                    # Other states are unexpected, so continue the loop
                    continue
            except:
                pass


async def main():
    me_data = await send_request(f"{API_URL}/me")
    print(f"Identity information: {me_data}")
    # load json
    me_data = json.loads(me_data)
    sender_address = me_data["identity"]

    demand_json = demand_template \
        .replace("%%EXPIRATION%%", str(int(time.time() * 1000 + 3600 * 1000))) \
        .replace("%%SENDER_ADDRESS%%", sender_address) \
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

    agreement_id = await negotiate_agreement(demand_json, demand_id)

    # Here should you should:
    # - Assign address to Provider Node
    # - Connect with websocket
    # - Handle packets forwarding

    print(f"Terminating Agreement {agreement_id}")
    reason = {
        "message": "Work finished"
    }

    await send_request(f"{API_URL}/market-api/v1/agreements/{agreement_id}/terminate",
                       "post", data=json.dumps(reason))

    print(f"Agreement {agreement_id} terminated")


if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
