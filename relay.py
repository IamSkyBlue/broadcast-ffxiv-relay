import os
import copy
import asyncio
import datetime
import aiohttp
import websockets
import json
import csv
from dotenv import load_dotenv

load_dotenv()
feedUrl = os.getenv("feedUrl")
csvUrl = os.getenv("csvUrl")
huntAssetUrl = os.getenv("huntAssetUrl")
zoneAssetUrl = os.getenv("zoneAssetUrl")
serversAsstUrl = "https://raw.githubusercontent.com/IamSkyBlue/broadcast-ffxiv-relay/master/serversDict.json"


async def get_info():
    async with aiohttp.ClientSession() as client:
        async with client.get(serversAsstUrl) as r:
            servers = await r.json(content_type="text/plain")
        async with client.get(huntAssetUrl) as r:
            r = await r.json()
            ShuntNames = {
                key: item["Name"]
                for key, item in r.items()
                if item["Name"] and (item["Rank"] in [3, 4, 5])
            }
        async with client.get(zoneAssetUrl) as r:
            r = await r.json()
            zoneNames = {key: item["Name"] for key, item in r.items() if item["Name"]}
    return servers, ShuntNames, zoneNames


async def loop(servers, ShuntNames, zoneNames):
    async with websockets.connect(feedUrl) as websocket:
        actorBuffer = []
        while True:
            msg = await websocket.recv()
            relayObj = json.loads(msg)

            if relayObj["Type"] != "Hunt":
                continue

            if str(relayObj["Id"]) not in ShuntNames.keys():
                continue

            if str(relayObj["WorldId"]) not in servers.keys():
                continue

            info = []
            info.extend(servers[str(relayObj["WorldId"])])
            zoneName = copy.deepcopy(zoneNames[str(relayObj["ZoneId"])])
            if relayObj["InstanceId"] != 0:
                for zoneNamelan in zoneName:
                    zoneName[zoneNamelan] += str(relayObj["InstanceId"])
            info.append(zoneName)
            info.append(ShuntNames[str(relayObj["Id"])])
            info.extend(
                [
                    "X:" + "{:2.1f}".format(RawToFlagCoord(relayObj["Coords"]["X"])),
                    "Y:" + "{:2.1f}".format(RawToFlagCoord(relayObj["Coords"]["Y"])),
                ]
            )
            rawinfo = {key: item for key, item in relayObj.items() if key != "ActorId"}

            if relayObj["ActorId"] in actorBuffer:
                if relayObj["CurrentHp"] == 0:
                    actorBuffer.remove(relayObj["ActorId"])
                    await send_webhook(info, rawinfo, True)
                continue

            if relayObj["CurrentHp"] == 0:
                continue

            actorBuffer.append(relayObj["ActorId"])
            await send_webhook(info, rawinfo, False)


async def send_webhook(info, rawinfo, isDead):
    async with aiohttp.ClientSession() as client:
        async with client.get(csvUrl) as r:
            raw = await r.text(encoding="utf-8")
            raw.replace(' "', '"')
            rows = csv.DictReader(raw.splitlines(), delimiter=",")
            info[1] = "[" + info[1] + "]"
            for row in rows:
                if info[0] in row["datacenter"]:
                    now = datetime.datetime.utcnow() + datetime.timedelta(
                        hours=int(row["timezone"])
                    )
                    now = now.strftime("%m/%d %H:%M ")
                    language = row["language"]
                    string1 = " ".join([str[language] for str in info[2:4]])
                    string2 = " ".join(info[4::])
                    if row["language"] == "English":
                        isDeadstr = "is dead"
                    else:
                        isDeadstr = "掛了"
                    string = now + " " + info[1] + " " + string1 + " " + string2
                    if isDead:
                        string += " " + isDeadstr
                    data = {"content": string, "raw": rawinfo}
                    try:
                        await client.post(row["url"], json=data)
                    except Exception as e:
                        print(f"An unexpected error occurred: {e}")
                    print(row["nickname"], info, rawinfo)


async def main():
    servers, ShuntNames, zoneNames = await get_info()
    print("setup done.")
    await loop(servers, ShuntNames, zoneNames)


def RawToFlagCoord(raw):
    return (41 * ((raw + 1024) / 2048)) + 1


if __name__ == "__main__":
    asyncio.run(main())
