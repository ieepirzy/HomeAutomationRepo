import asyncio
from dotenv import load_dotenv
from aiowebostv import WebOsClient
import os
from pprint import pprint

async def main():
    load_dotenv()

    tv_ip = os.getenv("Tv_IP")
    clientKey = os.getenv("CLIENT_KEY")

    if not tv_ip or not clientKey:
        raise ValueError("failed to load 1 or more variables from environment.")

    client = WebOsClient(tv_ip, clientKey)
    await client.connect()

if __name__ == "__main__":
    asyncio.run(main())

