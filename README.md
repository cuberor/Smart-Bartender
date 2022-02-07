# Smart Bartender
## Changes made in this fork compared to original (HackerShack)
* changed the screen and it's library from SPI to I2C
* removed multithreading for pumping
* changed the way the progress bar is animated

## Changes made in this fork compared to original (HackerShack)
* fixed false button triggers using interupts
* added an option to safely shut down the Pi
* added optional ToF sensor to detect the presence of a glass

## Prerequisites for the Raspberry Pi
You will need to SSH into the Pi or have otherwise access to the console.

Make sure the following are installed:
* Python 3 (should already be installed on most Raspberry Pi). Check your version with `python -V`

* [pip](https://www.raspberrypi.com/documentation/computers/os.html#pip) for Python 3
  `sudo apt install python3-pip`

### Enable I2C
You'll need to enable I2C for the OLED screen to work properly. Typing the following command in the terminal will bring you to a configuration menu.

```
sudo raspi-config 
```

Then navigate to `Interfacing Options` and select `I2C`. Make sure it's turned on and reboot.


Now let's make sure i2c is also configured properly. Type

```
sudo nano /etc/modules
```

in the terminal,

then make sure to paste the following two lines in the file:

```
i2c-bcm2708
i2c-dev
```

press `CRTL+X`, then `y`, followed by `Enter` to save and exit.

Now, let's reboot the Pi to apply those changes:
```
sudo reboot
```

## Installing the Software

First, make sure to download this repository on your raspberry pi.
```
sudo apt install git
git clone https://github.com/R0BATZEN/Smart-Bartender.git
```

Once you do, navigate to the downloaded folder in the terminal:

```
cd Smart-Bartender
```

and install the dependencies

```
sudo apt install libopenjp2-7-dev python3-smbus
sudo pip3 install -r requirements.txt
```

## Starting the software

You can start the bartender by running

```
python3 bartender.py
```
### Running at Startup
You can configure the bartender to run at startup by starting the program from the `rc.local` file. First, make sure to get the path to the current directory by running

```
pwd
```

from the repository folder. Copy this to your clipboard.

Next, type

```
sudo nano /etc/rc.local
```

to open the rc.local file. Before the last line (`exit 0`), add the following two lines:

```
cd <your/pwd/path/here>       #e.g. cd /home/pi/Smart-Bartender
sudo python bartender.py &
```

`your/pwd/path/here` should be replaced with the path you copied above. `sudo python bartender.py &` starts the bartender program in the background. Finally, press `CRTL+X` then `y` followed by `Enter` to save and exit. 

If that doesn't work, you can consult this [guide](https://www.dexterindustries.com/howto/run-a-program-on-your-raspberry-pi-at-startup/) for more options.

## Configuring Drinks and Recipes
There are two files that support the bartender.py file:

#### drinks.py
Holds all of the possible drink options. Drinks are filtered by the values in the pump configuration. If you want to add more drinks, add more entries to `drinks_list`. If you want to add more pump beverage options, add more entries to the `drink_options`.

`drinks_list` entries have the following format:

```
{
		"name": "Gin & Tonic",
		"ingredients": {
			"gin": 50,
			"tonic": 150
		}
	}
```

`name` specifies a name that will be displayed on the OLED menu. This name doesn't have to be unique, but it will help the user identify which drink has been selected. `ingredients` contains a map of beverage options that are available in `drink_options`. Each key represents a possible drink option. The value is the amount of liquid in mL. *Note: you might need a higher value for carbonated beverages since some of the CO2 might come out of solution while pumping the liquid.*

`drink_options` entries have the following format:

```
{"name": "Gin", "value": "gin"}
```

The `name` will be displayed on the pump configuration menu and the `value` will be assigned to the pump. The pump values will filter out drinks that the user can't make with the current pump configuration. 

### pump_config.json
The pump configuration persists information about pumps and the liquids that they are assigned to. An pump entry looks like this:

```
"pump_1": {
		"name": "Pump 1",
		"pin": 17, 
		"value": "gin"
	}
```

Each pump key needs to be unique. It is comprised of `name`, `pin`, and `value`. `name` is the display name shown to the user on the pump configuration menu, `pin` is the GPIO pin attached to the relay for that particular pump, and `value` is the current selected drink. `value` doesn't need to be set initially, but it will be changed once you select an option from the configuration menu.

My bartender only has 8 pumps, but you could easily use more by adding more pump config entries.

## A Note on Cleaning
After you use the bartender, you'll want to flush out the pump tubes in order to avoid bacteria growth.
There is an easy way to do this in the configuration menu.
Hook all the tubes up to a water source, then navigate to `configure`->`clean` and press the select button.
All pumps will turn on to flush the existing liquid from the tubes.

I take the tubes out of the water source halfway through to remove all liquid from the pumps.

*Note: make sure you have a glass under the funnel to catch the flushed out liquid.*
