from flask import Flask, jsonify
import subprocess
import sys
import os

app = Flask(__name__)

# Full path to your light script, relative to the current directory
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'wizlightcontrolscript-turnon.py')

@app.route('/api/turn_on', methods=['POST', 'GET'])
def trigger_lights():
    
    # 1. Start the subprocess
    # sys.executable is the path to the python.exe in your active .venv
    # We detach the process using subprocess.Popen so the HTTP request returns quickly
    try:
        process = subprocess.Popen([sys.executable, SCRIPT_PATH])
        
        # 2. Immediately return success to n8n
        return jsonify({
            "status": "triggered",
            "message": "Light script initiated successfully.",
            "process_id": process.pid
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to start script: {e}"
        }), 500

if __name__ == '__main__':
    # Run this file to start the API server
    app.run(debug=True, host='0.0.0.0')