#!/usr/bin/env python3
import os
import time
import sys
import RPi.GPIO as GPIO
import json
import traceback

from lib_oled96 import ssd1306
from smbus import SMBus
from PIL import ImageFont, Image

I2CBUS = SMBus(1)

############### Uncomment this for the ToF sensor ##################
# imports for ToF Sensor
# import board
# import busio
# import adafruit_vl53l0x

# I2C = busio.I2C(board.SCL, board.SDA)

# set speed and accuracy of sensor (measuring time in nanoseconds)
# SENSOR_ACCURACY = 200000	# =200ms
# set threshold for maximum distance to detect a glass (distance from sensor in mm)
# SENSOR_THRESHOLD = 100	# =10cm
####################################################################

from menu import MenuItem, Menu, Back, MenuContext, MenuDelegate
from drinks import drink_list, drink_options

GPIO.setmode(GPIO.BCM)

SCREEN_WIDTH = 128
SCREEN_HEIGHT = 64

LEFT_BTN_PIN = 16
LEFT_PIN_BOUNCE = 200

RIGHT_BTN_PIN = 12
RIGHT_PIN_BOUNCE = 800

### use / change these for a dedicated shutdown button ###
SHUTDOWN_BTN_PIN = 26
SHUTDOWN_PIN_BOUNCE = 400

FLOW_RATE = 60.0 / 100.0

FONT = ImageFont.truetype("FreeSans.ttf", 15)

class Bartender(MenuDelegate):
    def __init__(self):

        # set the oled screen height
        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT

        self.btn1Pin = LEFT_BTN_PIN
        self.btn2Pin = RIGHT_BTN_PIN

        ### only use with dedicated shutdown button ###
        self.btnShutdownPin = SHUTDOWN_BTN_PIN

        ############### Uncomment this for the ToF sensor ##################
        # self.sensor = adafruit_vl53l0x.VL53L0X(I2C)

        # set speed and accuracy of sensor
        # self.sensor.measurement_timing_budget = SENSOR_ACCURACY
        # self.sensorThreshold = SENSOR_THRESHOLD
        ####################################################################

        # configure inputs
        GPIO.setup(self.btn1Pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.btn2Pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        ### only use with dedicated shutdown button ###
        GPIO.setup(self.btnShutdownPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # configure screen and show boot logo
        self.led = ssd1306(I2CBUS)
        logo = Image.open('logo.png')
        self.led.canvas.bitmap((0, 0), logo, fill=1)
        self.led.display()
        # sleep to show boot logo for 4 seconds
        time.sleep(4)

        # load the pump configuration from file
        self.pump_configuration = Bartender.readPumpConfiguration()
        for pump in self.pump_configuration.keys():
            GPIO.setup(self.pump_configuration[pump]["pin"], GPIO.OUT, initial=GPIO.HIGH)

        print("Done initializing")

    @staticmethod
    def readPumpConfiguration():
        return json.load(open('pump_config.json'))

    @staticmethod
    def writePumpConfiguration(configuration):
        with open("pump_config.json", "w") as jsonFile:
            json.dump(configuration, jsonFile)

    def startInterrupts(self):
        GPIO.add_event_detect(self.btn1Pin, GPIO.FALLING, callback=self.left_btn, bouncetime=LEFT_PIN_BOUNCE)
        GPIO.add_event_detect(self.btn2Pin, GPIO.FALLING, callback=self.right_btn, bouncetime=RIGHT_PIN_BOUNCE)

        ### only use with dedicated shutdown button ###
        GPIO.add_event_detect(self.btnShutdownPin, GPIO.FALLING, callback=self.shutdown, bouncetime=SHUTDOWN_PIN_BOUNCE)

    def stopInterrupts(self):
        GPIO.remove_event_detect(self.btn1Pin)
        GPIO.remove_event_detect(self.btn2Pin)

        #### only use with dedicated shutdown button ###
        GPIO.remove_event_detect(self.btnShutdownPin)

    def buildMenu(self, drink_list, drink_options):
        # create a new main menu
        m = Menu("Main Menu")

        # add drink options
        drink_opts = []
        for d in drink_list:
            drink_opts.append(MenuItem('drink', d["name"], {"ingredients": d["ingredients"]}))

        configuration_menu = Menu("Configure")

        # add pump configuration options
        pump_opts = []
        for p in sorted(self.pump_configuration.keys()):
            config = Menu(self.pump_configuration[p]["name"])
            # add fluid options for each pump
            for opt in drink_options:
                # star the selected option
                selected = "*" if opt["value"] == self.pump_configuration[p]["value"] else ""
                config.addOption(
                    MenuItem('pump_selection', opt["name"], {"key": p, "value": opt["value"], "name": opt["name"]}))
            # add a back button so the user can return without modifying
            config.addOption(Back("Back"))
            config.setParent(configuration_menu)
            pump_opts.append(config)

        # add a back button to the configuration menu
        configuration_menu.addOption(Back("Back"))

        # adds an option that cleans all pumps to the configuration menu
        configuration_menu.addOption(MenuItem('clean', 'Clean'))

        # adds an option to cleanly shut down the raspberry pi
        configuration_menu.addOption(MenuItem('shutdown', 'Shutdown'))

        # add pump menus to the configuration menu
        configuration_menu.addOptions(pump_opts)

        configuration_menu.setParent(m)

        m.addOptions(drink_opts)
        m.addOption(configuration_menu)

        # create a menu context
        self.menuContext = MenuContext(m, self)

    def filterDrinks(self, menu):
        """
		Removes any drinks that can't be handled by the pump configuration
		"""
        for i in menu.options:
            if (i.type == "drink"):
                i.visible = False
                ingredients = i.attributes["ingredients"]
                presentIng = 0
                for ing in ingredients.keys():
                    for p in self.pump_configuration.keys():
                        if (ing == self.pump_configuration[p]["value"]):
                            presentIng += 1
                if (presentIng == len(ingredients.keys())):
                    i.visible = True
            elif (i.type == "menu"):
                self.filterDrinks(i)

    def selectConfigurations(self, menu):
        """
		Adds a selection star to the pump configuration option
		"""
        for i in menu.options:
            if (i.type == "pump_selection"):
                key = i.attributes["key"]
                if (self.pump_configuration[key]["value"] == i.attributes["value"]):
                    i.name = "%s %s" % (i.attributes["name"], "*")
                else:
                    i.name = i.attributes["name"]
            elif (i.type == "menu"):
                self.selectConfigurations(i)

    def prepareForRender(self, menu):
        self.filterDrinks(menu)
        self.selectConfigurations(menu)
        return True

    def menuItemClicked(self, menuItem):
        if (menuItem.type == "drink"):
            self.makeDrink(menuItem.name, menuItem.attributes["ingredients"])
            return True
        elif (menuItem.type == "pump_selection"):
            self.pump_configuration[menuItem.attributes["key"]]["value"] = menuItem.attributes["value"]
            Bartender.writePumpConfiguration(self.pump_configuration)
            return True
        elif (menuItem.type == "clean"):
            self.clean()
            return True
        elif (menuItem.type == "shutdown"):
            self.shutdown()
            return True
        return False

    def clean(self):

        ##################### Uncomment this for the ToF sensor #####################
        # distance = sensor.range
        #
        # if distance > self.sensorThreshold:
        #	self.led.cls()
        #	self.led.canvas.text((10, 20), "Glas missing", font=FONT, fill=1)
        #	self.led.display()
        #
        #	time.sleep(2)
        #	return
        ############################################################################

        pins = []

        for pump in self.pump_configuration.keys():
            pins.append(self.pump_configuration[pump]["pin"])

        self.startProgressBar()
        GPIO.output(pins, GPIO.LOW)
        self.sleepAndProgress(time.time(), 10, 10)
        GPIO.output(pins, GPIO.HIGH)

    def displayMenuItem(self, menuItem):
        print(menuItem.name)
        self.led.cls()
        self.led.canvas.text((10, 20), menuItem.name, font=FONT, fill=1)
        self.led.display()

    def startProgressBar(self, x=15, y=20):
        start_time = time.time()
        self.led.cls()
        self.led.canvas.text((22, 15), "Dispensing...", font=FONT, fill=1)

    def sleepAndProgress(self, startTime, waitTime, totalTime, x=20, y=37):
        localStartTime = time.time()
        height = 10
        width = self.screen_width - 2 * x

        while time.time() - localStartTime < waitTime:
            progress = (time.time() - startTime) / totalTime
            p_loc = int(progress * width)
            self.led.canvas.rectangle((x, y, x + width, y + height), outline=255, fill=0)
            self.led.canvas.rectangle((x + 1, y + 1, x + p_loc, y + height - 1), outline=255, fill=1)
            try:
                self.led.display()
            except IOError:
                print("Failed to talk to screen")
            time.sleep(0.2)

    def makeDrink(self, drink, ingredients):

        ##################### Uncomment this for the ToF sensor #####################
        # distance = sensor.range
        #
        # if distance > self.sensorThreshold:
        #	self.led.cls()
        #	self.led.canvas.text((22, 20), "Glas missing", font=FONT, fill=1)
        #	self.led.display()
        #
        #	time.sleep(2)
        #	return
        ############################################################################

        # Parse the drink ingredients and create pouring data
        pumpTimes = []
        for ing in ingredients.keys():
            for pump in self.pump_configuration.keys():
                if ing == self.pump_configuration[pump]["value"]:
                    waitTime = ingredients[ing] * FLOW_RATE
                    pumpTimes.append([self.pump_configuration[pump]["pin"], waitTime])

        # Put the drinks in the order they'll stop pouring
        pumpTimes.sort(key=lambda x: x[1])

        # Note the total time required to pour the drink
        totalTime = pumpTimes[-1][1]

        # Change the times to be relative to the previous not absolute
        for i in range(len(pumpTimes) - 1, 0, -1):
            pumpTimes[i][1] -= pumpTimes[i - 1][1]

        print(pumpTimes)

        self.startProgressBar()
        startTime = time.time()
        print("starting all")
        GPIO.output([p[0] for p in pumpTimes], GPIO.LOW)
        for p in pumpTimes:
            pin, delay = p
            if delay > 0:
                self.sleepAndProgress(startTime, delay, totalTime)
            GPIO.output(pin, GPIO.HIGH)
            print("stopping {}".format(pin))

    def left_btn(self, ctx):
        print("LEFT_BTN pressed")
        self.stopInterrupts()
        self.menuContext.advance()
        self.startInterrupts()

    def right_btn(self, ctx):
        print("RIGHT_BTN pressed")
        self.stopInterrupts()
        self.menuContext.select()
        self.startInterrupts()

    def shutdown(self):
        print("SHUTDOWN_BTN pressed")
        self.stopInterrupts()
        GPIO.cleanup()
        self.led.cls()
        self.led.canvas.text((5, 20), "Shutting down", font=FONT, fill=1)
        self.led.display()
        os.system("sudo shutdown -h now")

    def run(self):
        self.startInterrupts()

        # main loop
        try:
            while True:
                time.sleep(0.1)

        except KeyboardInterrupt:
            GPIO.cleanup()  # clean up GPIO on CTRL+C exit
        GPIO.cleanup()  # clean up GPIO on normal exit

        traceback.print_exc()


def main():
    bartender = Bartender()
    bartender.buildMenu(drink_list, drink_options)
    bartender.run()


if __name__ == "__main__":
    main()
