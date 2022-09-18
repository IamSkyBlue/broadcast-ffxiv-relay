import os
import asyncio
from datetime import datetime
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


async def get_info():
    servers = {
        "1042": ("陆行鸟区", "拉诺西亚"),
        "1043": ("猫小胖区", "紫水栈桥"),
        "1044": ("陆行鸟区", "幻影群岛"),
        "1045": ("猫小胖区", "摩杜纳"),
        "1060": ("陆行鸟区", "萌芽池"),
        "1076": ("莫古力区", "白金幻象"),
        "1081": ("陆行鸟区", "神意之地"),
        "1106": ("猫小胖区", "静语庄园"),
        "1113": ("莫古力区", "旅人栈桥"),
        "1121": ("莫古力区", "拂晓之间"),
        "1166": ("莫古力区", "龙巢神殿"),
        "1167": ("陆行鸟区", "红玉海"),
        "1169": ("猫小胖区", "延夏"),
        "1170": ("莫古力区", "潮风亭"),
        "1171": ("莫古力区", "神拳痕"),
        "1172": ("莫古力区", "白银乡"),
        "1173": ("陆行鸟区", "宇宙和音"),
        "1174": ("陆行鸟区", "沃仙曦染"),
        "1175": ("陆行鸟区", "晨曦王座"),
        "1176": ("莫古力区", "梦羽宝境"),
        "1177": ("猫小胖区", "海猫茶屋"),
        "1178": ("猫小胖区", "柔风海湾"),
        "1179": ("猫小胖区", "琥珀原"),
        "1180": ("豆豆柴区", "太阳海岸"),
        "1183": ("豆豆柴区", "银泪湖"),
        "1186": ("豆豆柴区", "伊修加德"),
        "1192": ("豆豆柴区", "水晶塔"),
        "1201": ("豆豆柴区", "红茶川"),
    }
    async with aiohttp.ClientSession() as client:
        async with client.get(huntAssetUrl) as r:
            r = await r.json()
            ShuntNames = {
                key: item["Name"]["ChineseSimplified"]
                for key, item in r.items()
                if item["Name"] and (item["Rank"] in [3, 4, 5])
            }
        async with client.get(zoneAssetUrl) as r:
            r = await r.json()
            zoneNames = {
                key: item["Name"]["ChineseSimplified"]
                for key, item in r.items()
                if item["Name"] and "ChineseSimplified" in item["Name"]
            }
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
            zoneName = zoneNames[str(relayObj["ZoneId"])]
            if relayObj["InstanceId"] != 0:
                zoneName += str(relayObj["InstanceId"] + 1)
            info.append(zoneName)
            info.append(ShuntNames[str(relayObj["Id"])])
            raw = relayObj.pop("ActorId")

            if relayObj["ActorId"] in actorBuffer:
                if relayObj["CurrentHp"] == 0:
                    actorBuffer.remove(relayObj["ActorId"])
                    info.append("掛了")
                    await send_webhook(info, raw)
                continue

            actorBuffer.append(relayObj["ActorId"])
            await send_webhook(info, raw)


async def send_webhook(info, raw):
    async with aiohttp.ClientSession() as client:
        async with client.get(csvUrl) as r:
            raw = await r.text(encoding="utf-8")
            rows = csv.DictReader(raw.splitlines(), delimiter=",")
            for row in rows:
                if info[0] in row["datacenter "]:
                    now = datetime.now().strftime("%m/%d %H:%M ")
                    info[1] = "[" + info[1] + "]"
                    string = " ".join(info[1::])
                    string = now + string
                    data = {"content": string, "raw": raw}
                    await client.post(row["url "], json=data)
                    print(row["nickname "], info, raw)


async def main():
    servers, ShuntNames, zoneNames = await get_info()
    print("setup done.")
    await loop(servers, ShuntNames, zoneNames)


if __name__ == "__main__":
    asyncio.run(main())