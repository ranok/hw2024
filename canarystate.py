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
    'dead_devices': 0,
    'bare_devices': 0, # no services enabled
    'unacked_incidents': []
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
    with open(STATE_FILE, 'wb') as fp:
        pickle.dump(state, fp)

def capi(uri):
    try:
        res = requests.get(f"https://{console_hash}.canary.tools/api/v1/{uri}', data={'auth_token': auth_token}")
        if not res.ok:
            logger.error(f"Failed call api: {res.reason}: {res.content}")
            return None
        return res.json()
    except:
        logger.exception("Failed to call console API")
        return None



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

    if not new_state['unacked_incidents']:
        unacknowledged = console.incidents.unacknowledged()
        new_state['unacked_incidents'] = unacknowledged
    else:
        # We have some already cached, just get newer ones:
        latest = sorted(console_state['unacked_incidents'], key=lambda d: d.created_std)[-1]
        new_unacked = console.incidents.unacknowledged(newer_than=latest.created_std.strftime("%Y-%m-%d-%H:%M:%S"))
        new_state['unacked_incidents'].extend([na for na in new_unacked if not na.id in [i.id for i in console_state['unacked_incidents']]])
        logger.info(f"Latest incident: {latest.created_std} All: {[i.created_std for i in console_state['unacked_incidents']]}")

    for u in new_state['unacked_incidents']:
        logger.info(f"Unacknowledged: {str(u.created_std)}: {type(u.created_std)}")

    return new_state



