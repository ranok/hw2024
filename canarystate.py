#!/usr/bin/env python3

import os
import pickle
from pathlib import Path
import requests
from dotenv import load_dotenv
import logging
import canarytools
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

load_dotenv()

logger = logging.getLogger(__name__)

console_hash = os.environ['CONSOLE_HASH']
auth_token = os.environ['API_KEY']

console = canarytools.Console(console_hash, auth_token)

STATE_FILE = 'cgstate.dat'

state_lock = Lock()

canarygotchi_state = {
    "happiness": 100,
    "xp": 0,
    "hunger": 0,
    "food_available": 1,
    "alerts": []
}

console_state = {
    'num_unused_licenses': 0,
    'num_deployed_tokens': 0,
    'live_devices': 0,
    'dead_devices': 0,
    'bare_devices': 0, # no services enabled
    'unacked_incidents': [],
    'attacks': []
}

sf = Path(STATE_FILE)
if sf.is_file():
    with open(STATE_FILE, 'rb') as fp:
        state = pickle.load(fp)
        # OR the dicts below so we update structure on save if we ever change them.
        canarygotchi_state = canarygotchi_state | state['cgs']
        console_state = console_state | state['cs']

def save_state(cgs = canarygotchi_state, cs = console_state):
    state = {
        'cgs': cgs,
        'cs': cs
    }
    state_lock.acquire()
    with open(STATE_FILE, 'wb') as fp:
        pickle.dump(state, fp)
    state_lock.release()

def capi(uri):

    try:
        res = requests.get(f'https://{console_hash}.canary.tools/api/v1/{uri}', data={'auth_token': auth_token})
        if not res.ok:
            logger.error(f"Failed call api: {res.reason}: {res.content}")
            return None
        return res.json()
    except:
        logger.exception("Failed to call console API")
        return None



def get_console_state(previous_state = console_state) -> dict:
    global console_state
    url = f"https://{console_hash}.canary.tools"
    res = requests.get(url + '/api/v1/license/detailed/info', data={'auth_token': auth_token})
    if res.status_code != 200:
        print("Error fetching console state! " + res.text)
        return {}
    new_state = deepcopy(previous_state)
    new_state['num_unused_licenses'] = res.json().get('canaryvm_remaining_licenses', 0)
    res = requests.get(url + '/api/v1/canarytokens/fetch', data={'auth_token': auth_token})
    if res.status_code != 200:
        print("Error fetching console state! " + res.text)
        return {}
    try:
        new_state['num_deployed_tokens'] = len(console.tokens.all())
    except canarytools.CanaryTokenError:
        logger.exception("Failed to get canarytokens from console")

    try:
        all_devices = console.devices.all()
        new_state.update({
            "live_devices": len([d for d in all_devices if d.live]),
            "dead_devices": len([d for d in all_devices if not d.live]),
            "bare_devices": len([d for d in all_devices if d.service_count == 0])
        })
    except Exception:
        logger.exception("Failed to live/dead device counts")

    #unacknowledged = console.incidents.unacknowledged()
    #last_ten_unacked = sorted(unacknowledged, key=lambda d: d.created_std)[-10:]
    #new_state['unacked_incidents'] = last_ten_unacked[::-1] # Newest first
    data = capi("incidents/unacknowledged")
    new_alerts = []
    for incident in data["incidents"]:
        # Extract necessary fields
        incident_summary = incident["summary"]
        incident_name = incident["description"]["name"]
        incident_memo = incident["description"].get("memo", "No memo available")  # Default if "memo" key doesn't exist
        incident_id = incident["id"]
        incident_hash = incident["hash_id"]

        # Determine the title based on the incident_name
        # Super limited space on the screen, so we need to shorten stuff
        if incident_name == "N/A": # incident from canarytoken
            incident_title = f"Token: {incident_memo[:20]}"
        else: #incident from Canary
            incident_title = f"{incident_name}: {incident_summary[:20]}"

        # Create the incident dictionary
        new_alerts.append({
            "title": incident_title,
            "id": incident_id,
            "hash": incident_hash
        })
    new_state['unacked_incidents'] = new_alerts[::-1]

    for u in new_state['unacked_incidents']:
        #logger.info(f"Unacknowledged: {u.summary} @ {u.created_std}")
        logger.info(f"Unacknowledged: {u['id']} @ {u['title']}")

    return new_state



