from pywizlight import wizlight, PilotBuilder
import asyncio
import os
from dotenv import load_dotenv


async def main():
    load_dotenv()
    light_IP1 = os.getenv("lightIP1")
    light_IP2 = os.getenv("lightIP2")

    if not light_IP1 or not light_IP2:
        raise ValueError("Light IP addresses not found in environment variables.")
    light1 = wizlight(light_IP1)
    light2 = wizlight(light_IP2)

    pilot = PilotBuilder(brightness=256, warm_white=255)
    await light1.turn_on(pilot)
    await light2.turn_on(pilot)

asyncio.run(main())

