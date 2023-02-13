import asyncio
import logging
import aiohttp
import platform
import time
import json
import os

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


BEARER_TOKEN = "12909321636293016160"


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
                    raise PostException("Unauthorized")
                if result.status == 401:
                    logger.error(
                        f"Unauthorized, check your API key, data size")
                    raise PostException("Unauthorized")
                if result.status != 200 and result.status != 201:
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
      "golem.node.debug.subnet": "vpn",
      "golem.com.payment.chosen-platform": "erc20-rinkeby-tglm",
      "golem.com.payment.platform.erc20-rinkeby-tglm.address": "%%SENDER_ADDRESS%%",
      "golem.srv.comp.expiration": %%EXPIRATION%%
   },
   "constraints":"(&(golem.node.debug.subnet=vpn)(golem.com.payment.platform.erc20-rinkeby-tglm.address=*)(golem.com.pricing.model=linear)(golem.runtime.name=outbound-gateway)(golem.runtime.capabilities=net-gateway))"
}
"""
async def main():
    me_data = await send_request("http://127.0.0.1:7465/me")
    print(f"Identity information: {me_data}")
    # load json
    me_data = json.loads(me_data)
    sender_address = me_data["identity"]

    demand_json = demand_template\
        .replace("%%EXPIRATION%%", str(int(time.time() * 1000 + 200 * 1000)))\
        .replace("%%SENDER_ADDRESS%%", sender_address)

    if not os.path.exists("tmp"):
        os.mkdir("tmp")

    # validate json
    json.loads(demand_json)
    print(f"Demands information: {demand_json}")
    demand_id = await send_request("http://127.0.0.1:7465/market-api/v1/demands", "post", data=demand_json)
    demand_id = demand_id.replace('"', '')
    print(f"Demands information: {demand_id}")

    while True:
        max_events = 5
        poll_timeout = 3000
        poll = await send_request(f"http://127.0.0.1:7465/market-api/v1/demands/{demand_id}/events?maxEvents={max_events}&pollTimeout={poll_timeout}")
        # print(f"Poll result: {poll}")
        poll_json = json.loads(poll)

        if len(poll_json) > 0:
            for poll_res in poll_json:
                print(f"Proposal: {poll_res['proposal']}")
                proposal_id = poll_res['proposal']['proposalId']
                print(f"Proposal id: {proposal_id}")
                send_proposal = await send_request(f"http://127.0.0.1:7465/market-api/v1/demands/{demand_id}/proposals/{proposal_id}")
                print(f"Send proposal: {send_proposal}")
                send_proposal_json = json.loads(send_proposal)
                print(f"Send proposal json: {json.dumps(send_proposal_json, indent=4)}")
                with open("tmp/proposal.json", "w") as f:
                    f.write(json.dumps(send_proposal_json, indent=4))






if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
