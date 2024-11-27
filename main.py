#!/usr/bin/env python3

import spidev as SPI
import logging, qrcode
import ST7789
from dotenv import load_dotenv
import time
import threading
import requests
import os
from PIL import Image, ImageSequence, ImageDraw
import pickle
import canarystate
from canarystate import save_state, canarygotchi_state, console_state, console
import canarytools
from copy import deepcopy
import gpiozero

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

current_screen = "home"  # Default screen is home
polling_interval = 20  # Polling interval in seconds
selected_menu_index = 0
animation_running = False
animation_thread = None
base_animation = "base_animation.gif"
pet_animation = "pet_animation.gif"
feed_animation = "feed_animation.gif"
current_animation = base_animation


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
            "interact": self.interact_screen
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
            global animation_running, current_animation
            gif = Image.open(current_animation)
            animation_running = True
            try:
                frames = [frame.resize((240, 240)).rotate(0) for frame in ImageSequence.Iterator(gif)]
                while current_screen == "home" and animation_running:
                    for frame in frames[1:]:
                        if not animation_running:
                            return

                        disp.ShowImage(frame)
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
        menu_items = ["1. Stats", "2. Interact with Canary", "3. Alerts", "4. Timeline", "5. Settings"]
        y = 10
        for i, item in enumerate(menu_items):
            if i == selected_menu_index:
                draw.text((10, y), item, fill=bright_green, font_size=self.font_size)  # Highlight selected item
            else:
                draw.text((10, y), item, fill="WHITE", font_size=self.font_size)
            y += self.text_y_space
        disp.ShowImage(image)

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
        '''Display the alerts'''
        image = Image.new("RGB", (disp.width, disp.height), "BLACK")
        draw = ImageDraw.Draw(image)
        y = 10
        if len(canarygotchi_state['alerts']) > 0:
            for i, alert in enumerate(canarygotchi_state['alerts']):
                if i == selected_menu_index:
                    draw.text((10, y), f"{i+1}. {alert['title']}", fill=bright_green, font_size=self.font_size)
                else:
                    draw.text((10, y), f"{i+1}. {alert['title']}", fill="WHITE", font_size=self.font_size)
                y += self.text_y_space
        else:
            draw.text((10, y), "No alerts", fill="WHITE", font_size=self.font_size)
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
        global current_screen, selected_menu_index, current_animation, animation_running
        try:
            if pin_num == KEY1_PIN:  # Key 1 pressed
                logging.info("Key 1 pressed")
                if current_screen == "home":
                    current_screen = "alerts"
                    self.screen_manager.show_screen(current_screen)
                if current_screen == "interact":
                    current_animation = pet_animation
                    animation_running = True

            elif pin_num == KEY2_PIN:  # Key 2 pressed
                logging.info("Key 2 pressed")
                if current_screen == "home":
                    current_screen = "interact"
                    self.screen_manager.show_screen(current_screen)
                elif current_screen == "interact":
                    current_animation = feed_animation
                    animation_running = True

            elif pin_num == KEY3_PIN:  # Key 3 pressed
                logging.info("Key 3 pressed")
                if current_screen == "home":
                    current_screen = "menu"
                    self.screen_manager.show_screen(current_screen)
                if current_screen == "interact":
                    current_screen = "home"
                    self.screen_manager.show_screen(current_screen)

            elif pin_num == KEY_UP_PIN:  # Up button pressed
                logging.info("Up button pressed")
                if current_screen == "menu":
                    selected_menu_index = (selected_menu_index - 1) % 4 # TODO: fix so that menu item count is not hardcoded
                    self.screen_manager.show_screen(current_screen)
                if current_screen == "alerts":
                    selected_menu_index = (selected_menu_index - 1) % 10 # TODO: fix so that menu item count is not hardcoded
                    self.screen_manager.show_screen(current_screen)

            elif pin_num == KEY_DOWN_PIN:  # Down button pressed
                logging.info("Down button pressed")
                if current_screen == "menu":
                    selected_menu_index = (selected_menu_index + 1) % 4 # TODO: fix so that menu item count is not hardcoded
                    self.screen_manager.show_screen(current_screen)
                if current_screen == "alerts":
                    selected_menu_index = (selected_menu_index + 1) % 10 # TODO: fix so that menu item count is not hardcoded
                    self.screen_manager.show_screen(current_screen)

            elif pin_num == KEY_LEFT_PIN:  # Left button pressed
                logging.info("Left button pressed")
                if current_screen == "menu":
                    current_screen = "home"
                    current_animation = base_animation  # Reset to base animation
                elif current_screen in ["stats", "alerts"]:
                    current_screen = "menu"
                self.screen_manager.show_screen(current_screen)

            elif pin_num == KEY_RIGHT_PIN:  # Right button pressed
                logging.info("Right button pressed")
                if current_screen == "menu":
                    if selected_menu_index == 0:
                        current_screen = "stats"
                    elif selected_menu_index == 1:
                        current_screen = "interact"
                    elif selected_menu_index == 2:
                        current_screen = "alerts"
                    # Add more cases as needed for other menu items
                    self.screen_manager.show_screen(current_screen)

        except KeyboardInterrupt:
            self.display.module_exit()

# Background API Polling
def poll_api():
    global console_state
    while True:
        try:
            logging.info("Polling console...")
            cs_new = canarystate.get_console_state()

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

            if len(cs_new['unacked_incidents']) > len(console_state['unacked_incidents']):
                logging.info("New unack'd incidents discovered")

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

            console_state = deepcopy(cs_new)
            canarystate.save_state(canarygotchi_state, console_state)
        except canarytools.ConsoleError:
            logging.exception(f"API request failed")

        time.sleep(polling_interval)

def generate_qrcode(url : str) -> Image:
    return qrcode.make(url)

# Main Function
def main():

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
            incident_title = f"Token: {incident_description[:20]}"
        else: #incident from Canary
            incident_title = f"{incident_description}: {incident_summary[:20]}"

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
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
