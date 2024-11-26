#!/usr/bin/env python3

import os
import pickle
from pathlib import Path
import requests
from dotenv import load_dotenv
import logging
import canarytools
from copy import deepcopy


load_dotenv()

logger = logging.getLogger(__name__)

console_hash = os.environ['CONSOLE_HASH']
auth_token = os.environ['API_KEY']

console = canarytools.Console(console_hash, auth_token)

STATE_FILE = 'cgstate.dat'

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
    'dead_devices': 0
}

sf = Path(STATE_FILE)
if sf.is_file():
    with open(STATE_FILE, 'rb') as fp:
        state = pickle.load(fp)
        canarygotchi_state = state['cgs']
        console_state = state['cs']

def save_state(cgs = canarygotchi_state, cs = console_state):
    state = {
        'cgs': cgs,
        'cs': cs
    }
    with open(STATE_FILE, 'wb') as fp:
        pickle.dump(state, fp)

def get_console_state() -> dict:
    url = f"https://{console_hash}.canary.tools"
    res = requests.get(url + '/api/v1/license/detailed/info', data={'auth_token': auth_token})
    if res.status_code != 200:
        print("Error fetching console state! " + res.text)
        return {}
    new_state = deepcopy(console_state)
    new_state['num_unused_licenses'] = res.json().get('canaryvm_remaining_licenses', 0)
    res = requests.get(url + '/api/v1/canarytokens/fetch', data={'auth_token': auth_token})
    if res.status_code != 200:
        print("Error fetching console state! " + res.text)
        return {}
    try:
        new_state['num_deployed_canarytokens'] = len(console.tokens.all())
    except canarytools.CanaryTokenError:
        logger.exception("Failed to get canarytokens from console")

    try:
        new_state.update({
            "live_devices": len(console.devices.live()),
            "dead_devices": len(console.devices.dead())
        })
    except Exception:
        logger.exception("Failed to live/dead device counts")

    return new_state



