#!/usr/bin/env python3

import spidev as SPI
import logging
import ST7789
from dotenv import load_dotenv
import time
import threading
import requests
import os
from PIL import Image, ImageSequence, ImageDraw
import pickle
import canarystate
from canarystate import save_state, canarygotchi_state, console_state

load_dotenv()

console_hash = os.environ['CONSOLE_HASH']
auth_token = os.environ['API_KEY']

payload = {
  'auth_token': 'abcdefg',
  'limit':'10'
}

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
current_animation = base_animation

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
            "alerts": self.alerts_screen
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
                while current_screen == "home" and animation_running:
                    for frame in ImageSequence.Iterator(gif):
                        if not animation_running:
                            return
                        frame = frame.resize((disp.width, disp.height))
                        frame = frame.rotate(0)
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

    def menu_screen(self):
        # Display the menu options
        image = Image.new("RGB", (disp.width, disp.height), "BLACK")
        draw = ImageDraw.Draw(image)
        menu_items = ["1. Stats", "2. Alerts", "3. Timeline", "4. Settings"]
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
        disp.ShowImage(image)

    def alerts_screen(self):

        # Display the alerts
        image = Image.new("RGB", (disp.width, disp.height), "BLACK")
        draw = ImageDraw.Draw(image)
        y = 10
        for i, alert in enumerate(canarygotchi_state['alerts']):
            if i == selected_menu_index:
                draw.text((10, y), f"{i+1}. {alert['title']}", fill=bright_green, font_size=self.font_size)
            else:
                draw.text((10, y), f"{i+1}. {alert['title']}", fill="WHITE", font_size=self.font_size)
            y += self.text_y_space
        disp.ShowImage(image)

# Button Handling
class ButtonHandler:
    def __init__(self, display, screen_manager):
        self.display = display
        self.screen_manager = screen_manager

    def handle_buttons(self):
        global current_screen, selected_menu_index, current_animation
        try:
            while True:
                if self.display.digital_read(self.display.GPIO_KEY1_PIN) == 1:  # Key 1 pressed
                    logging.info("Key 1 pressed")
                    if current_screen == "home":
                        current_screen = "alerts"
                        self.screen_manager.show_screen(current_screen)
                    time.sleep(0.2)

                elif self.display.digital_read(self.display.GPIO_KEY2_PIN) == 1:  # Key 2 pressed
                    logging.info("Key 2 pressed")
                    if current_screen == "home":
                        current_screen = "menu"
                        self.screen_manager.show_screen(current_screen)
                    time.sleep(0.2)

                elif self.display.digital_read(self.display.GPIO_KEY3_PIN) == 1:  # Key 3 pressed
                    logging.info("Key 3 pressed")
                    if current_screen == "home":
                        current_screen = "menu"
                        self.screen_manager.show_screen(current_screen)
                    time.sleep(0.2)

                elif self.display.digital_read(self.display.GPIO_KEY_UP_PIN) == 1:  # Up button pressed
                    logging.info("Up button pressed")
                    if current_screen == "menu":
                        selected_menu_index = (selected_menu_index - 1) % 4 # TODO: fix so that menu item count is not hardcoded
                        self.screen_manager.show_screen(current_screen)
                    if current_screen == "alerts":
                        selected_menu_index = (selected_menu_index - 1) % 10 # TODO: fix so that menu item count is not hardcoded
                        self.screen_manager.show_screen(current_screen)
                    time.sleep(0.2)

                elif self.display.digital_read(self.display.GPIO_KEY_DOWN_PIN) == 1:  # Down button pressed
                    logging.info("Down button pressed")
                    if current_screen == "menu":
                        selected_menu_index = (selected_menu_index + 1) % 4 # TODO: fix so that menu item count is not hardcoded
                        self.screen_manager.show_screen(current_screen)
                    if current_screen == "alerts":
                        selected_menu_index = (selected_menu_index + 1) % 10 # TODO: fix so that menu item count is not hardcoded
                        self.screen_manager.show_screen(current_screen)
                    time.sleep(0.2)

                elif self.display.digital_read(self.display.GPIO_KEY_LEFT_PIN) == 1:  # Left button pressed
                    logging.info("Left button pressed")
                    if current_screen == "menu":
                        current_screen = "home"
                        current_animation = base_animation  # Reset to base animation
                    elif current_screen in ["stats", "alerts"]:
                        current_screen = "menu"
                    self.screen_manager.show_screen(current_screen)
                    time.sleep(0.2)

                elif self.display.digital_read(self.display.GPIO_KEY_RIGHT_PIN) == 1:  # Right button pressed
                    logging.info("Right button pressed")
                    if current_screen == "menu":
                        if selected_menu_index == 0:
                            current_screen = "stats"
                        elif selected_menu_index == 1:
                            current_screen = "alerts"
                        # Add more cases as needed for other menu items
                        self.screen_manager.show_screen(current_screen)
                    time.sleep(0.2)
        except KeyboardInterrupt:
            self.display.module_exit()

# Background API Polling
def poll_api():
    while True:
        try:
            print("dummy poll")
            if not 'CONSOLEHASH' in console_hash:
                cs_new = canarystate.get_console_state(console_hash, api_key)
                #if console_state['num_deployed_canarytokens'] != cs_new['num_deployed_canarytokens']:

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
        except requests.RequestException as e:
            logging.error(f"API request failed: {e}")
        time.sleep(polling_interval)

# Main Function
def main():

    # Grabbing first 10 incidents at start, this should be moved to a function as part of the polling/heartbeat
    # 1. Get unacknowledged incidents, limit 1
    # 2. if 0 or incident == last incident ID STOP
    # 3. Else: get incidents - paginated - until we have the same state localy as we do on the console
    data = {'incidents': []}
    if not "CONSOLEHASH" in console_hash:
        r = requests.get(f"{console_hash}/api/v1/incidents/unacknowledged", params=payload)
        data = r.json()
    new_alerts = []
    for incident in data["incidents"]:
        # Extract necessary fields
        incident_summary = incident["summary"]
        incident_name = incident["description"]["name"]
        incident_memo = incident["description"].get("memo", "No memo available")  # Default if "memo" key doesn't exist
        incident_id = incident["id"]
        
        # Determine the title based on the incident_name
        # Super limited space on the screen, so we need to shorten stuff
        if incident_name == "N/A": # incident from canarytoken
            incident_title = f"Token: {incident_memo[:20]}"
        else: #incident from Canary
            incident_title = f"{incident_name}: {incident_summary[:20]}"
        
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
    button_handler.handle_buttons()

if __name__ == "__main__":
    main()
