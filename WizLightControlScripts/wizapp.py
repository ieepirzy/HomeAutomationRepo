from flask import Flask, jsonify
from pywizlight import wizlight, PilotBuilder
import asyncio
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()
light_IP1 = os.getenv("lightIP1")
light_IP2 = os.getenv("lightIP2")

try:
    if not light_IP1 or not light_IP2:
        raise ValueError("Light IP addresses not found in environment variables.")

except Exception as light_exception:
    print(f"error occurred: {light_exception}")


@app.route('/api/wizlights', methods=['POST', 'GET'])
def main():
    
    try:
       asyncio.run(turnOnLights())
       return jsonify({
            "status": "success",
            "message": "Sequence started successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to start script: {e}"
        }), 500


async def turnOnLights():
    light1 = wizlight(light_IP1)
    light2 = wizlight(light_IP2)
    pilot = PilotBuilder(brightness=255, warm_white=255)
    await asyncio.gather(
        light1.turn_on(pilot),
        light2.turn_on(pilot)
        )

if __name__ == '__main__':
    # Run this file to start the API server
    app.run(debug=True, host='0.0.0.0')


