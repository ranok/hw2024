#!/usr/bin/env python3

import pickle
from pathlib import Path
import requests

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
    'num_deployed_tokens': 0
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

def get_console_state(ch : str, api_key : str) -> dict:
    res = requests.get(ch + '/api/v1/license/detailed/info', headers={'auth_token': api_key})
    if res.status_code != 200:
        print("Error fetching console state! " + res.text)
        return {}
    state = {}
    state['num_unused_licenses'] = res.json().get('canaryvm_remaining_licenses')
        res = requests.get(ch + '/api/v1/canarytokens/fetch', headers={'auth_token': api_key})
    if res.status_code != 200:
        print("Error fetching console state! " + res.text)
        return {}
    state['num_deployed_canarytokens'] = len(res.json().get('tokens'))

