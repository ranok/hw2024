#!/usr/bin/env python3

import spidev as SPI
import logging, qrcode
import ST7789, wifi_config
from dotenv import load_dotenv
import time
import threading
import requests
import os
from PIL import Image, ImageSequence, ImageDraw
import canarystate
from canarystate import save_state, canarygotchi_state, console_state, console
from psd import PSD, PSDEvent
import queue
import canarytools
from copy import deepcopy
import gpiozero
import random
from datetime import datetime, timedelta
import uuid
from functools import reduce

load_dotenv()

# Logging configuration
logging.basicConfig(level=logging.DEBUG)

# Initialize the display
disp = ST7789.ST7789()
disp.Init()
disp.clear()
disp.bl_DutyCycle(50)


# Global variables
bright_green = (0, 255, 0)

last_portscan_src = ""
ENV_FILE = '/opt/cg/.env'
current_screen = "home"  # Default screen is home
polling_interval = 20  # Polling interval in seconds
selected_menu_index = 0
animation_running = False
animation_thread = None
base_animation = "media/gifs/meander_laser.gif"
base_animation_2 = "media/gifs/meander_pulse.gif"
sad_animation = "media/gifs/sad.gif"
incident_animation = "media/gifs/alert_incident.gif"
attack_animation = "media/gifs/freakout.gif"
pet_animation = "pet_animation.gif"
feed_animation = "feed_animation.gif"
current_animation = base_animation
unacked_incidents = 0
cg_uuid = ""
reg_seq = []

KEY_UP_PIN     = 6
KEY_DOWN_PIN   = 19
KEY_LEFT_PIN   = 5
KEY_RIGHT_PIN  = 26
KEY_PRESS_PIN  = 13

KEY1_PIN       = 21
KEY2_PIN       = 20
KEY3_PIN       = 16

# Screen Manager
class ScreenManager:
    def __init__(self, display):
        self.display = display
        self.font_size = 20
        self.text_y_space = 30
        self.screens = {
            "home": self.home_screen,
            "menu": self.menu_screen,
            "stats": self.stats_screen,
            "alerts": self.alerts_screen,
            "wifi": self.wifi_screen,
            "interact": self.interact_screen,
            "registration": self.registration_screen,
            "alert_qrcode": self.alert_qrcode_screen
        }

    def show_screen(self, screen_name):
        global animation_running, animation_thread
        if screen_name in self.screens:
            logging.info(f"Switching to screen: {screen_name}")
            if animation_running:
                animation_running = False  # Stop any ongoing animations when switching screens
                if animation_thread is not None:
                    animation_thread.join()  # Ensure the animation thread has stopped
            self.screens[screen_name]()
        else:
            logging.error(f"Unknown screen: {screen_name}")

    def home_screen(self):
        # Display the Tamagotchi animations in a separate thread
        def play_animation():
            global last_portscan_src, incident_animation, attack_animation, sad_animation, animation_running, current_animation, console_state, base_animation, base_animation_2

            animation_running = True

            icon_attack = Image.open("media/icons/attack.png").convert("RGBA")  # Load the icon image
            icon_attack = icon_attack.resize((30, 30))  # Resize the icon if

            icon_alert = Image.open("media/icons/alert.png").convert("RGBA")  # Load the icon image
            icon_alert = icon_alert.resize((30, 30))  # Resize the icon if needed

            icon_sad = Image.open("media/icons/sad.png").convert("RGBA")  # Load the icon image
            icon_sad = icon_sad.resize((30, 30))  # Resize the icon if needed

            try:
                gif = Image.open(current_animation)
                resized_width = disp.width - 50
                resized_height = disp.height - 50
                frames = [frame.resize((resized_height, resized_width)).rotate(0) for frame in ImageSequence.Iterator(gif)]
                base_animation_repeats = 0

                last_incident_count = len(console_state['unacked_incidents'])

                last_attack_count = len(console_state['attacks'])
                playAttackAnimation = False
                while current_screen == "home" and animation_running:
                    playIncidentAnimation = False
                    playAttackAnimation = False
                    current_incident_count = len(console_state['unacked_incidents'])
                    current_attack_count = len(console_state['attacks'])
                    print("Attack count")
                    print(current_attack_count)
                    attackSource = ""

                    if last_attack_count > current_attack_count:
                        last_attack_count = current_attack_count

                    if last_incident_count < current_incident_count:
                        last_incident_count = current_incident_count
                        playIncidentAnimation = True
                        print("PLAY ALERT/INCIDENT ANIMATION")
                    if last_attack_count < current_attack_count:
                        last_attack_count = current_attack_count
                        playAttackAnimation = True
                        last_attack_index = current_attack_count -1
                        attackSource = console_state['attacks'][last_attack_index]
                        last_portscan_src = console_state['attacks'][last_attack_index].src_ip
                        print("PLAY ATTACK ANIMATION")
                    #else:
                    #    last_incident_count = len(console_state['unacked_incidents'])

                    base_animation_repeats += 1

                    #print(base_animation_repeats)
                    if base_animation_repeats > 2 or playIncidentAnimation or playAttackAnimation:
                        base_animation_repeats = 0

                        chance = 0
                        #print(canarygotchi_state["happiness"])
                        if canarygotchi_state["happiness"] < 11:
                            chance = 0
                        elif canarygotchi_state["happiness"] < 31:
                            chance = random.randint(0,2)
                        elif canarygotchi_state["happiness"] < 61:
                            chance = random.randint(0,4)
                        else:
                            #print("happy")
                            chance = 1


                        if chance == 0:
                            #print(chance)
                            current_animation = sad_animation
                        elif current_animation != base_animation: # pulse.gif
                            current_animation = base_animation
                        else:
                            current_animation = base_animation_2


                        resized_width = disp.width - 50
                        resized_height = disp.height - 50

                        if playAttackAnimation:
                            current_animation = attack_animation
                            resized_width = disp.width - 80
                            resized_height = disp.height - 80
                        elif playIncidentAnimation:
                            current_animation = incident_animation
                        #print(current_animation)
                        gif = Image.open(current_animation)




                        frames = [frame.resize((resized_height, resized_width)).rotate(0) for frame in ImageSequence.Iterator(gif)]

                    for frame in frames[1:]:
                        if not animation_running:
                            return


                        canvas = Image.new("RGB", (disp.width, disp.height), "BLACK")
                        draw = ImageDraw.Draw(canvas)


                        if len(console_state['unacked_incidents']) > 0:
                            icon_alert_text = str(len(console_state['unacked_incidents']))
                            icon_alert_x = 5  # Left margin for the icon
                            icon_alert_y = 5  # Top margin for the icon
                            icon_alert_text_x = icon_alert_x + icon_alert.width + 5  # Position text to the right of the icon
                            icon_alert_text_y = icon_alert_y + (icon_alert.height // 2) - 12  # Vertically align text with the icon


                            draw.text((icon_alert_text_x, icon_alert_text_y), icon_alert_text, fill="WHITE", font_size=20)
                            canvas.paste(icon_alert, (icon_alert_x, icon_alert_y), icon_alert)  # Use the alpha channel for transparency

                        # FIX when we have counts for attacks (portscan against Canarygotchi)
                        # if len(console_state['attacks']) > 0:
                        #
                        if len(console_state['attacks']) > 0:
                            icon_attack_text = str(len(console_state['attacks']))
                            icon_attack_x = 140  # Left margin for the icon
                            icon_attack_y = 5  # Top margin for the icon
                            icon_attack_text_x = icon_attack_x + icon_attack.width + 5  # Position text to the right of the icon
                            icon_attack_text_y = icon_attack_y + (icon_attack.height // 2) - 12  # Vertically align text with the icon

                            draw.text((icon_attack_text_x, icon_attack_text_y), icon_attack_text, fill="WHITE", font_size=20)

                            draw.text((50,210), f'Portscan {last_portscan_src}', fill="WHITE", font_size=20)
                            canvas.paste(icon_attack, (icon_attack_x, icon_attack_y), icon_attack)  # Use the alpha channel for transparency

                        if canarygotchi_state["happiness"] < 61:

                            icon_sad_x = 205  # Left margin for the icon
                            icon_sad_y = 5  # Top margin for the icon

                            canvas.paste(icon_sad, (icon_sad_x, icon_sad_y), icon_sad)  # Use the alpha channel for transparency

                        # Paste the resized frame below the text and icon
                        gif_x = (disp.width - resized_width) // 2  # Center horizontally
                        gif_y = 50
                        #gif_y = 50  # Leave space for the text and icon
                        canvas.paste(frame, (gif_x, gif_y))

                        disp.ShowImage(canvas)
                        time.sleep(0.05)
                        if current_screen != "home":
                            return
            except KeyboardInterrupt:
                disp.clear()
                logging.info("Exited Home Screen")

        global animation_thread
        animation_thread = threading.Thread(target=play_animation, daemon=True)
        animation_thread.start()

    def interact_screen(self):
        '''Screen that lets you play with/feed the bird'''
        image = Image.new("RGB", (disp.width, disp.height), "BLACK")
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), f"Food: {canarygotchi_state['food_available']}" , fill="WHITE", font_size=self.font_size)
        draw.text((10, 10+self.text_y_space), f"1: Pet 2: Feed 3: Back" , fill="WHITE", font_size=self.font_size)
        disp.ShowImage(image)

        def play_interact_animation():
            global animation_running, current_animation
            #animation_running = True
            try:
                while not animation_running:
                    pass
            except KeyboardInterrupt:
                disp.clear()
            gif = Image.open(current_animation)
            if current_animation == feed_animation and canarygotchi_state['food_available'] < 1:
                image = Image.new("RGB", (disp.width, disp.height), "BLACK")
                draw = ImageDraw.Draw(image)
                draw.text((10, 10), f"No food available!" , fill="RED", font_size=self.font_size)
                draw.text((10, 10+self.text_y_space), f"Deploy a Canarytoken" , fill="WHITE", font_size=self.font_size)
                disp.ShowImage(image)
                return
            if current_animation == feed_animation:
                canarygotchi_state['food_available'] -= 1
                canarygotchi_state['hunger'] = 0
                canarygotchi_state['happiness'] += 10
            elif current_animation == pet_animation:
                canarygotchi_state['happiness'] += 10
            canarystate.save_state(canarygotchi_state, console_state)
            try:
                while current_screen == "interact" and animation_running:
                    for frame in ImageSequence.Iterator(gif):
                        if not animation_running:
                            return
                        frame = frame.resize((disp.width, disp.height))
                        frame = frame.rotate(0)
                        disp.ShowImage(frame)
                        time.sleep(0.05)
                        if current_screen != "interact":
                            return
            except KeyboardInterrupt:
                disp.clear()
                logging.info("Exited interact Screen")

        global animation_thread
        animation_thread = threading.Thread(target=play_interact_animation, daemon=True)
        animation_thread.start()

    def menu_screen(self):
        # Display the menu options
        image = Image.new("RGB", (disp.width, disp.height), "BLACK")
        draw = ImageDraw.Draw(image)
        menu_items = ["1. Stats", "2. Interact", "3. Alerts", "4. WiFI Settings", "5. Console Link"]
        y = 10
        for i, item in enumerate(menu_items):
            if i == selected_menu_index:
                draw.text((10, y), item, fill=bright_green, font_size=self.font_size)  # Highlight selected item
            else:
                draw.text((10, y), item, fill="WHITE", font_size=self.font_size)
            y += self.text_y_space
        disp.ShowImage(image)

    def registration_screen(self):

        def play_registration_animation():
            global cg_uuid, reg_seq, ENV_FILE
            # Display the menu options
            #image = Image.new("RGB", (disp.width, disp.height), "BLACK")
            #draw = ImageDraw.Draw(image)
            qrimage = generate_qrcode(f'https://canarygotchi.com/enrollment/?id={cg_uuid}')
            qrimage = qrimage.resize((200, 200))
            canvas = Image.new("RGB", (disp.width, disp.height), "BLACK")
            draw = ImageDraw.Draw(canvas)
            draw.text((5,5), "Enter sequence: ", fill="WHITE", font_size=16)

            canvas.paste(qrimage, (20,40), qrimage)
            disp.ShowImage(canvas)

            reg_seq = []
            len_last_reg_seq = 0
            while True:
                if len_last_reg_seq != len(reg_seq):
                    print(reg_seq)
                    len_last_reg_seq = len(reg_seq)

                if len(reg_seq) == 5:
                    print(reg_seq)
                    #seq = "sequence=" + ",".join(reg_seq)
                    seq = {
                        "sequence": ",".join(reg_seq)
                    }
                    print(seq)
                    r = requests.post(f'http://canarygotchi.com/api/validate-sequence/{cg_uuid}', json=seq)

                    try:
                        response_data = r.json()

                        print("\nResponse Body:")
                        print(response_data)

                        # Extract the values for name, hash, and auth_token
                        name = response_data['data']['name']
                        hash_value = response_data['data']['hash']
                        auth_token = response_data['data']['auth_token']
                        if name != "" and hash_value != "" and auth_token != "":
                            env_vars = {}
                            if os.path.exists(ENV_FILE):
                                with open(ENV_FILE, 'r') as file:
                                    for line in file.readlines():
                                        # Strip any whitespace/newlines and split on '=' to get key-value pairs
                                        if '=' in line:
                                            key, value = line.strip().split('=', 1)
                                            env_vars[key] = value

                            # Update or add the required values
                            env_vars['CONSOLE_HASH'] = hash_value
                            env_vars['API_KEY'] = auth_token
                            env_vars['NAME'] = name

                            # Write the updated values back to the .env file
                            with open(ENV_FILE, 'w') as file:
                                for key, value in env_vars.items():
                                    file.write(f"{key}={value}\n")

                    except:
                        print("Sequence validation failed")
                    break
                time.sleep(0.5)

        global animation_thread
        animation_thread = threading.Thread(target=play_registration_animation, daemon=True)
        animation_thread.start()

    def stats_screen(self):
        # Display the stats
        image = Image.new("RGB", (disp.width, disp.height), "BLACK")
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), f"Happiness: {canarygotchi_state['happiness']}", fill="WHITE", font_size=self.font_size)
        draw.text((10, 10+self.text_y_space), f"XP: {canarygotchi_state['xp']}", fill="WHITE", font_size=self.font_size)
        draw.text((10, 10+self.text_y_space*2), f"Hunger: {canarygotchi_state['hunger']}", fill="WHITE", font_size=self.font_size)
        draw.text((10, 10+self.text_y_space*3), f"Food available: {canarygotchi_state['food_available']}", fill="WHITE", font_size=self.font_size)

        disp.ShowImage(image)

    def alerts_screen(self):
        global console_state
        '''Display the alerts'''
        image = Image.new("RGB", (disp.width, disp.height), "BLACK")
        draw = ImageDraw.Draw(image)
        y = 10
        if len(console_state['unacked_incidents']) > 0:
            #print(console_state['unacked_incidents'])
            #for k in console_state['unacked_incidents']:
            #    print(k.events)
            #    for s in k.events:
            #        print(s)
            #        print(vars(s))


            for i, alert in enumerate(console_state['unacked_incidents']):


                #repls = { "Canarytoken triggered:": "tkn"}


                #for key, value in repls.items():
                #    title = title.replace(key, value)
                #print(title)

                if i == selected_menu_index:
                    draw.text((10, y), f"{i+1}. {alert['title']}", fill=bright_green, font_size=self.font_size)
                else:
                    draw.text((10, y), f"{i+1}. {alert['title']}", fill="WHITE", font_size=self.font_size)
                y += self.text_y_space
        else:
            draw.text((10, y), "No alerts", fill="WHITE", font_size=self.font_size)
        disp.ShowImage(image)

    def alert_qrcode_screen(self):
        alert = console_state['unacked_incidents'][selected_menu_index]
        logging.info(f"Showing QR for alert: {alert}")
        image = Image.new("RGB", (disp.width, disp.height), "BLACK")
        qrimage = generate_qrcode(f'https://{canarystate.console_hash}.canary.tools/nest/incident/{alert["hash"]}')
        qrimage = qrimage.resize((240, 240))
        canvas = Image.new("RGB", (disp.width, disp.height), "BLACK")
        canvas.paste(qrimage, (0,0), qrimage)
        disp.ShowImage(canvas)

    def wifi_screen(self):
        '''Shows WiFi information'''
        image = Image.new("RGB", (disp.width, disp.height), "BLACK")
        draw = ImageDraw.Draw(image)
        y = 10
        ssid = 'canarygotchi'
        cssid = wifi_config.active_ssid()
        msgs = []
        if cssid is None or cssid == ssid:
            # Hotspot
            msgs.append('Running hotspot:')
            msgs.append('SSID: ' + ssid)
            msgs.append('PW: canarygotchi')
            msgs.append('URL: canarygotchi.local:8080')
        else:
            msgs.append('Connected to WiFi')
            msgs.append(f'SSID: {cssid}')
        for msg in msgs:
            draw.text((10, y), msg, fill='WHITE', font_size=self.font_size)
            y += self.text_y_space
        disp.ShowImage(image)


# Button Handling
class ButtonHandler:
    def __init__(self, display, screen_manager):
        self.display = display
        self.screen_manager = screen_manager

    def setup_buttons(self):
        button_pins = [
            KEY1_PIN, KEY2_PIN, KEY3_PIN, KEY_PRESS_PIN,
            KEY_UP_PIN, KEY_DOWN_PIN, KEY_LEFT_PIN, KEY_RIGHT_PIN
            ]

        buttons = [gpiozero.Button(b) for b in button_pins]
        for button in buttons:
            button.when_pressed = self.handle_buttons

    def handle_buttons(self, button):
        gpio = button.pin.info.name
        pin_num = int(gpio[4:])
        global current_screen, selected_menu_index, current_animation, animation_running, reg_seq
        try:
            if pin_num == KEY1_PIN:  # Key 1 pressed
                logging.info("Key 1 pressed")
                if current_screen == "home":
                    current_screen = "menu"
                    self.screen_manager.show_screen(current_screen)
                if current_screen == "interact":
                    current_animation = pet_animation
                    animation_running = True

            elif pin_num == KEY2_PIN:  # Key 2 pressed
                logging.info("Key 2 pressed")
                if current_screen == "home":
                    current_screen = "alerts"
                    self.screen_manager.show_screen(current_screen)
                elif current_screen == "interact":
                    current_animation = feed_animation
                    animation_running = True

            elif pin_num == KEY3_PIN:  # Key 3 pressed
                logging.info("Key 3 pressed")
                #if current_screen == "home":
                current_screen = "home"
                self.screen_manager.show_screen(current_screen)
                #if current_screen == "interact":
                #    current_screen = "home"
                #    self.screen_manager.show_screen(current_screen)

            elif pin_num == KEY_UP_PIN:  # Up button pressed
                logging.info("Up button pressed")
                if current_screen == "menu":
                    selected_menu_index = (selected_menu_index - 1) % 5 # TODO: fix so that menu item count is not hardcoded
                    self.screen_manager.show_screen(current_screen)
                if current_screen == "alerts":
                    selected_menu_index = (selected_menu_index - 1) % 9 # TODO: fix so that menu item count is not hardcoded
                    self.screen_manager.show_screen(current_screen)
                if current_screen == "registration":
                    reg_seq.append("up")
                    #self.screen_manager.show_screen(current_screen)


            elif pin_num == KEY_DOWN_PIN:  # Down button pressed
                logging.info("Down button pressed")
                if current_screen == "menu":
                    selected_menu_index = (selected_menu_index + 1) % 5 # TODO: fix so that menu item count is not hardcoded
                    self.screen_manager.show_screen(current_screen)
                if current_screen == "alerts":
                    selected_menu_index = (selected_menu_index + 1) % 9 # TODO: fix so that menu item count is not hardcoded
                    self.screen_manager.show_screen(current_screen)
                if current_screen == "registration":
                    reg_seq.append("down")
                    # self.screen_manager.show_screen(current_screen)

            elif pin_num == KEY_LEFT_PIN:  # Left button pressed
                logging.info("Left button pressed")
                if current_screen == "menu":
                    current_screen = "home"
                    current_animation = base_animation  # Reset to base animation
                    self.screen_manager.show_screen(current_screen)
                elif current_screen in ["stats", "alerts", "interact", "wifi", "alerts", "alert_qrcode"]:
                    current_screen = "menu"
                    self.screen_manager.show_screen(current_screen)
                if current_screen == "registration":
                    reg_seq.append("left")


            elif pin_num == KEY_RIGHT_PIN:  # Right button pressed
                logging.info("Right button pressed")
                if current_screen == "menu":
                    if selected_menu_index == 0:
                        current_screen = "stats"
                        self.screen_manager.show_screen(current_screen)
                    elif selected_menu_index == 1:
                        current_screen = "interact"
                        self.screen_manager.show_screen(current_screen)
                    elif selected_menu_index == 2:
                        current_screen = "alerts"
                        self.screen_manager.show_screen(current_screen)
                    elif selected_menu_index == 3:
                        current_screen = "wifi"
                        self.screen_manager.show_screen(current_screen)
                    elif selected_menu_index == 4:
                        current_screen = "registration"
                        self.screen_manager.show_screen(current_screen)
                    # Add more cases as needed for other menu items
                elif current_screen == "alerts":
                    # An alert selected with right key, show QR code:
                    current_screen = "alert_qrcode"
                    self.screen_manager.show_screen(current_screen)

                if current_screen == "registration":
                    reg_seq.append("right")


        except KeyboardInterrupt:
            self.display.module_exit()

# Background API Polling
def poll_api():
    global console_state
    while True:
        try:
            logging.info("Polling console...")
            cs_new = canarystate.get_console_state(console_state)

            new_things = lambda k: cs_new[k] > console_state[k]

            if cs_new['num_deployed_tokens'] > console_state['num_deployed_tokens']:
                canarygotchi_state['happiness'] += 1
                canarygotchi_state['xp'] += 5
                canarygotchi_state['food_available'] += 1

            if new_things('live_devices'):
                canarygotchi_state['happiness'] += 1
                canarygotchi_state['xp'] += 5

            if new_things('dead_devices'):
                canarygotchi_state['happiness'] -= 1

            if len(cs_new['unacked_incidents']) != len(console_state['unacked_incidents']):
                unacked_difference = len(cs_new['unacked_incidents']) - len(console_state['unacked_incidents'])
                canarygotchi_state['happiness'] -= unacked_difference
                logging.info(f"Unack'd delta: {unacked_difference}")

            #response = requests.get(f"{console_hash}/api/v1/ping", params=payload)
            #if response.status_code == 200:
                # Trigger event-based animations if needed
                #if "event_animation" in data:
                #    global current_animation
                #    current_animation = "some other animation"
                #    logging.info(f"Switching to event animation: {current_animation}")
                #    if current_screen == "home":
                        # Restart the animation thread to play the new animation
                #        screen_manager.show_screen(current_screen)
            logging.warn(f"console_state: {console_state} cs_new: {cs_new}")
            console_state = deepcopy(console_state | cs_new)
            canarystate.save_state(canarygotchi_state, console_state)
        except canarytools.ConsoleError:
            logging.exception(f"API request failed")

        time.sleep(polling_interval)

def generate_qrcode(url : str) -> Image:
    return qrcode.make(url)

# Main Function
def main():
    global cg_uuid, ENV_FILE
    try:
        tmp_uuid = os.environ['UUID']
        cg_uuid = str(tmp_uuid)
        print("UUID exists")
    except:
        print("generating UUID")
        tmp_uuid = uuid.uuid4()

        with open(ENV_FILE, 'a') as fp:
            efc = f"UUID={str(tmp_uuid)}\n"
            fp.write(efc)
        cg_uuid = str(tmp_uuid)

    # Grabbing first 10 incidents at start, this should be moved to a function as part of the polling/heartbeat
    # 1. Get unacknowledged incidents, limit 1
    # 2. if 0 or incident == last incident ID STOP
    # 3. Else: get incidents - paginated - until we have the same state localy as we do on the console
    new_alerts = []

    for incident in console.incidents.unacknowledged():
        # Extract necessary fields
        incident_summary = incident.summary
        incident_description = incident.description if incident.description != "" else "No memo available"  # Default if "memo" key doesn't exist
        incident_id = incident.id

        # Determine the title based on the incident_name
        # Super limited space on the screen, so we need to shorten stuff
        if incident_description == "N/A": # incident from canarytoken
            incident_title = f"Token: {incident_description}" # [:20]
        else: #incident from Canary
            incident_title = f"{incident_description}: {incident_summary}" #:20

        # Create the incident dictionary
        new_alerts.append({
            "title": incident_title,
            "id": incident_id
        })
    global canarygotchi_state
    canarygotchi_state['alerts'] = new_alerts


    global screen_manager
    screen_manager = ScreenManager(disp)
    button_handler = ButtonHandler(disp, screen_manager)

    # Start API polling in a separate thread
    api_thread = threading.Thread(target=poll_api, daemon=True)
    api_thread.start()

    # Show the home screen initially
    screen_manager.show_screen(current_screen)

    # Start button handling
    button_handler.setup_buttons()

    psd_queue = queue.Queue()
    psd = PSD(psd_queue)
    psd.start()
    portscan_expire = timedelta(seconds=20)
    while True:
        try:
            psd_event = psd_queue.get(timeout=5)
            console_state['attacks'].append(psd_event)
            canarystate.save_state(canarygotchi_state, console_state)
        except queue.Empty:
            attacks_after_expiry = [p for p in console_state['attacks'] if p.timestamp > (datetime.now() - portscan_expire)]
            # attacks_after_expiry has to be <= existing console_state['attacks'] as its a filtered (sub)set thereof.
            attacks_delta = len(console_state['attacks']) - len(attacks_after_expiry)
            console_state['attacks'] = attacks_after_expiry
            logging.warn(f"Attacks: {console_state['attacks']}")
            if attacks_delta > 0:
                logging.info(f"Expired {attacks_delta} attacks")


if __name__ == "__main__":
    main()
