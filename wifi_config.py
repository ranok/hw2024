#!/usr/bin/env python3

import nmcli
from flask import Flask, request

app = Flask(__name__)

ENV_FILE = '/opt/cg/.env'

def wifi_connected() -> bool:
    return any(w.in_use for w in nmcli.device.wifi())

def setup_hotspot(ssid : str = 'canarygotchi', password : str = 'canarygotchi'):
    return nmcli.device.wifi_hotspot(ssid = ssid, password = password)

def wifi_connect(ssid : str, password : str):
    nmcli.device.wifi_connect(ssid, password)

def get_nearby_aps() -> list[str]:
    ssids = [w.ssid for w in nmcli.device.wifi()]
    ssids.remove('')
    return ssids

@app.route('/')
def show_wifi_config():
    '''
    Hosts the Flask-based captive portal to configure the device
    '''
    ssids = get_nearby_aps()
    ssid_list = '\n'.join([f'<option value="{ssid}">{ssid}</option>' for ssid in ssids])
    config_html = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>Connect your Canarygotchi</title>
        </head>
        <body>
            <h1>Select a network</h1>
            <p>Choose from the detected networks:</p>
            <form action="/submit" method="post">
                <label for="ssid">SSID:</label>
                <select name="ssid" id="ssid">
                    {ssid_list}
                </select>
                <br />
                <label for="password">Password for selected SSID:</label>
                <input type="password" name="password" />
                <br />
                <label for="consolehash">Console hash:</label>
                <input type="text" name="consolehash" />
                <br />
                <label for="consolekey">Console read-only API key:</label>
                <input type="text" name="consolekey" />
                <br />
                <input type="submit" value="Connect" />
            </form>
        </body>
    </html>
    """
    return config_html

@app.route('/submit', methods=['POST'])
def handle_wifi_config():
    ssid = request.form['ssid']
    password = request.form['password']

    # TODO Save the API information
    console_hash = request.form['consolehash']
    console_key = request.form['consolekey']
    with open(ENV_FILE, 'w') as fp:
        efc = f"CONSOLE_HASH={console_hash}\nAPI_KEY={console_key}\n"
        fp.write(efc)

    try:
        wifi_connect(ssid, password)
    except Exception as e:
        return f'Error: {e}'
    return f'Success! Connected to {ssid}!'

if __name__ == '__main__':
    if not wifi_connected():
        print("No WiFi detected, setting up hotspot")
        setup_hotspot()
        app.run(debug=True, host='0.0.0.0', port=80)