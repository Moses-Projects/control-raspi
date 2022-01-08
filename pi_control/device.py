print("Loaded pi_control device module")

import adafruit_drv2605
import board
import busio
# from gpiozero import Button, LED, MCP3008
import gpiozero
import json
import os
import random
import re
import threading
import time

import pi_control.__init__

"""
2021-12-30 Added debounce, timed checks after debounce, threading on output, canceling threads, init devices.
2022-01-01 Added MCP3*** ADC support and potentiometers.
2022-01-04 Added expander devices for ADCs and port expanders.
2022-01-04 Added update_status for potentiometers.
2022-01-04 Added actions based on value ranges.
2022-01-05 Added GPIO rotary encoder.
2022-01-08 Added HTTP and Sound outputs.

To do:
	Add I2C haptic driver
	Add I2C MCP23xxx expander
	Add rotary encoder w/ MCP23xxx
	Consolidate last_status and last_action?
	Add cooldown on actions
	Add outputs
		wait
		print
		sns
		mqtt
"""

"""
import pi_control.device
"""

debug = False

class Device:
	"""
	device = pi_control.device.Device(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		global debug
		self._debug = False
		if debug_pref:
			self._debug = True
		
		self._name = str(name)
		self._type = 'device'
		self._needs_monitoring = False
		self.last_status = None
		self._connection = None
		self._connections = {}
		
		self._panel = None
		if 'panel' in args:
			self._panel = args['panel']
		
		self._gpio_pin = None
		if 'gpio_pin' in args:
			self.gpio_pin = args['gpio_pin']
		
		self._gpio_pins = {}
		if 'gpio_pins' in args:
			self.gpio_pins = args['gpio_pins']
		
		self._source_bus = None
		self._i2c = None
		if 'source_bus' in args:
			self.source_bus = args['source_bus']
		
		self._source_channel = None
		if 'source_channel' in args:
			self.source_channel = args['source_channel']
	
	@property
	def name(self):
		return self._name
	
	@property
	def type(self):
		return self._type
	
	@property
	def last_status(self):
		return self._last_status
	
	@last_status.setter
	def last_status(self, last_status):
		self._last_status = last_status
	
	@property
	def panel(self):
		return self._panel
	
	@property
	def gpio_pin(self):
		return self._gpio_pin
	
	@gpio_pin.setter
	def gpio_pin(self, gpio_pin):
		if type(gpio_pin) is not str and type(gpio_pin) is not int and type(gpio_pin) is not float:
			raise TypeError("Invalid GPIO pin type {}".format(type(gpio_pin)))
		pin = int(gpio_pin)
		if pin < 0 or pin > 27:
			raise ValueError("Invalid GPIO pin value {}".format(gpio_pin))
		self._gpio_pin = pin
	
	@property
	def gpio_pins(self):
		return self._gpio_pins
	
	@gpio_pins.setter
	def gpio_pins(self, gpio_pins):
		if type(gpio_pins) is not dict:
			raise TypeError("Invalid GPIO pins type in {}".format(self.name))
		for label, gpio_pin in gpio_pins.items():
			if type(gpio_pin) is not str and type(gpio_pin) is not int and type(gpio_pin) is not float:
				raise TypeError("Invalid GPIO pin type for {} in {}".format(label, self.name))
			pin = int(gpio_pin)
			if pin < 0 or pin > 27:
				raise ValueError("Invalid GPIO pin value for {} in {}".format(label, self.name))
			self._gpio_pins[label] = pin
	
	@property
	def source_bus(self):
		return self._source_bus
	
	@source_bus.setter
	def source_bus(self, source_bus):
		if type(source_bus) is not str:
			raise TypeError("Invalid source bus type {}".format(type(source_bus)))
		if source_bus != 'i2c':
			raise TypeError("Invalid source bus {}".format(source_bus))
		self._source_bus = source_bus
		self._i2c = busio.I2C(board.SCL, board.SDA)
	
	@property
	def source_channel(self):
		return self._source_channel
	
	@source_channel.setter
	def source_channel(self, source_channel):
		if type(source_channel) is not str and type(source_channel) is not int and type(source_channel) is not float:
			raise TypeError("Invalid ADC channel type {}".format(type(source_channel)))
		channel = int(source_channel)
		self._source_channel = channel
	

"""
Expander Devices
"""

class ExpanderDevice(Device):
	"""
	device = pi_control.device.ExpanderDevice(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		super().__init__(name, args, debug_pref)
		self._type = 'expander'
		
		# Properties
		if 'chip' not in args:
			raise AttributeError("chip is required for {} {}".format(self.type, self.name))
		self.chip = args['chip']
	
	@property
	def parent(self):
		return 'expander'
	
	@property
	def chip(self):
		return self._chip
	
	@chip.setter
	def chip(self, chip):
		if type(chip) is not str:
			raise TypeError("Invalid chip type for {} {}".format(self.type, self.name))
		chip_info = self.get_chip_info(chip)
		if not chip_info:
			raise ValueError("Invalid or unsupported chip for {} {}".format(self.type, self.name))
		
		self._chip = chip
		self._type = chip_info['type']
		self._bus = chip_info['bus']
		self._channels = chip_info['channels']
	
	def get_chip_info(self, chip):
		chips = {
			"ads1015": { "type": "adc", "bus": "i2c", "channels": 4 },
			"ads1115": { "type": "adc", "bus": "i2c", "channels": 4 },
			"mcp3001": { "type": "adc", "bus": "spi", "channels": 1 },
			"mcp3002": { "type": "adc", "bus": "spi", "channels": 2 },
			"mcp3004": { "type": "adc", "bus": "spi", "channels": 4 },
			"mcp3008": { "type": "adc", "bus": "spi", "channels": 8 },
			"mcp3201": { "type": "adc", "bus": "spi", "channels": 1 },
			"mcp3202": { "type": "adc", "bus": "spi", "channels": 2 },
			"mcp3204": { "type": "adc", "bus": "spi", "channels": 4 },
			"mcp3208": { "type": "adc", "bus": "spi", "channels": 8 },
			"mcp3301": { "type": "adc", "bus": "spi", "channels": 1 },
			"mcp3302": { "type": "adc", "bus": "spi", "channels": 2 },
			"mcp3304": { "type": "adc", "bus": "spi", "channels": 4 },
			"mcp23008": { "type": "expander", "bus": "i2c", "channels": 8 },
			"mcp23017": { "type": "expander", "bus": "i2c", "channels": 16 }
		}
		if chip in chips:
			return chips[chip]
		return None
	
	def get_connection(self, chnl=None):
		if chnl < 0 or chnl >= self._channels:
			raise ValueError("Invalid channel value {} for expander {} {}".format(chnl, self._chip, self._name))
		chip = self._chip
		if chip == 'mcp3001':
			return gpiozero.MCP3001(channel=chnl)
		elif chip == 'mcp3002':
			return gpiozero.MCP3002(channel=chnl)
		elif chip == 'mcp3004':
			return gpiozero.MCP3004(channel=chnl)
		elif chip == 'mcp3008':
			return gpiozero.MCP3008(channel=chnl)
		elif chip == 'mcp3201':
			return gpiozero.MCP3201(channel=chnl)
		elif chip == 'mcp3202':
			return gpiozero.MCP3202(channel=chnl)
		elif chip == 'mcp3204':
			return gpiozero.MCP3204(channel=chnl)
		elif chip == 'mcp3208':
			return gpiozero.MCP3208(channel=chnl)
		elif chip == 'mcp3301':
			return gpiozero.MCP3301(channel=chnl)
		elif chip == 'mcp3302':
			return gpiozero.MCP3302(channel=chnl)
		elif chip == 'mcp3304':
			return gpiozero.MCP3304(channel=chnl)
		return None
	
	

"""
Input Devices
"""

class InputDevice(Device):
	"""
	device = pi_control.device.InputDevice(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		super().__init__(name, args, debug_pref)
		self._type = 'input'
		self._update_timer = None
		
		# Properties
		self.debounce = 0.5
		if 'debounce' in args:
			self.debounce = args['debounce']
		
		# Actions
		self._actions = {}
		if 'actions' in args:
			if type(args['actions']) is not dict:
				raise TypeError("Invalid actions type for {}".format(name))
			self._actions = args['actions']
		
		self.last_changed_ts = None
	
	@property
	def parent(self):
		return 'input'
	
	@property
	def last_changed_ts(self):
		return self._last_changed_ts
	
	@last_changed_ts.setter
	def last_changed_ts(self, ts):
		self._last_changed_ts = ts
	
	
	
	@property
	def on_hold(self):
		time_now = time.time()
		if self.last_changed_ts and (time_now - self.last_changed_ts) <= self.debounce:
			return True
		return False
	
	@property
	def debounce(self):
		return self._debounce
	
	@debounce.setter
	def debounce(self, debounce):
		if type(debounce) is int or type(debounce) is str:
			debounce = float(debounce)
		elif type(debounce) is not float:
			raise TypeError("Invalid debounce type for {} {}".format(self.type, self.name))
		self._debounce = debounce
	
	def get_actions(self, action_name):
		if action_name not in self._actions:
			return []
		return self._actions[action_name]
	
	def process_analog_actions(self):
		self._action_keys = list(self._actions.keys())
		self._action_keys.sort()
	
	def change_status(self, status, startup=False):
# 		print(self.name + ": Change status")
		
		# No change, skip
		if self.last_status == status:
			print('  ' + self.name + ' no change')
			return False
		
		# Wait for debounce time to finish, skip
		if self.on_hold:
			print('  ' + self.name + ' skipping')
			return False
		
		# A change has occurred!
		self.cancel_update_timer()
		self.last_changed_ts = time.time()
		self.last_status = status
		print('  ' + self.name + ' ' + str(status))
		
# 		print("  take action")
		self.panel.take_action(self, status, startup)
		
		if not startup:
			self.start_update_timer()
		return True
	
	def start_update_timer(self):
# 		print(self.name + ": Start update timer")
		if not pi_control.is_method(self, 'update_status'):
			return
		
		duration = self.debounce + .1
		self._update_timer = threading.Timer(duration, self.update_status)
# 		print("{}: Starting {} - {}".format(self.name, self._update_timer, duration))
		self._update_timer.start()
	
	def cancel_update_timer(self):
# 		print(self.name + ": Cancel update timer")
		if not self._update_timer:
			return
		self._update_timer.cancel()
		self._update_timer = None
		

class Button(InputDevice):
	"""
	button = pi_control.device.Button(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		super().__init__(name, args, debug_pref)
		self._type = 'button'
		
		# Properties
		if 'gpio_pin' not in args:
			raise AttributeError("GPIO pin required for {} {}".format(self.type, self.name))
		
		# Internal args
		pull_up_value = True
		if 'pull_up' in args:
			if type(args['pull_up']) is not type(True):
				raise ValueError("Invalid pull_up type for {}".format(self._name))
			if not args['pull_up']:
				pull_up_value = False
		
		# Init
		self._connection = gpiozero.Button(self._gpio_pin, pull_up=pull_up_value)
		self._connection.when_pressed = self.event_pressed
		self._connection.when_released = self.event_released
	
	
	@property
	def pressed(self):
		if self._connection.is_pressed:
			return True
		return False
	
	def event_pressed(self):
		print(self.name + ": Pressed")
		self.change_status('pressed')
	
	def event_released(self):
		print(self.name + ": Released")
		self.change_status('released')
	
	def update_status(self, startup=False):
		if self.pressed:
			print(self.name + ": Update status - pressed")
			self.change_status('pressed', startup)
		else:
			print(self.name + ": Update status - released")
			self.change_status('released', startup)
	
class Potentiometer(InputDevice):
	"""
	button = pi_control.device.Potentiometer(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		super().__init__(name, args, debug_pref)
		self._type = 'potentiometer'
		self._needs_monitoring = True
		self._last_value = 0
		self._last_action_key = 100000
		
		# Properties
		if 'source_device' not in args:
			raise AttributeError("Source device is required for {} {}".format(self.type, self.name))
		self._source_device = args['source_device']
		if type(self.source_channel) is not int:
			raise AttributeError("Channel is required for {} {}".format(self.type, self.name))
		
		self.process_analog_actions()
		
		# Init
		self._connection = self._source_device.get_connection(self.source_channel)
	
	
	@property
	def value(self):
		self._last_value = int(self._connection.value * 100)
		return self._last_value
	
	def update_status(self, startup=False):
		value = self.value
		action_key = None
		for key in self._action_keys:
			if value < int(key):
				action_key = key
				break
		if type(action_key) is type(None):
			return None
		if action_key == self._last_action_key:
			return None
		print("{}: {} - {}".format(value, self._last_action_key, action_key))
		self._last_action_key = action_key
		self.change_status(action_key, startup)
		
class RotaryEncoder(InputDevice):
	"""
	button = pi_control.device.RotaryEncoder(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		super().__init__(name, args, debug_pref)
		self._type = 'button'
		
		# Properties
		if 'gpio_pins' not in args:
			raise AttributeError("GPIO pins required for {} {}".format(self.type, self.name))
		
		# Internal args
		pull_up_value = True
		if 'pull_up' in args:
			if type(args['pull_up']) is not type(True):
				raise ValueError("Invalid pull_up type for {}".format(self._name))
			if not args['pull_up']:
				pull_up_value = False
		
		# Init
		for label, gpio_pin in self.gpio_pins.items():
			self._connections[label] = gpiozero.Button(gpio_pin, pull_up=pull_up_value)
			self._connections[label].when_pressed = self.event_selected
	
	
	@property
	def selection(self):
		for label, connection in self._connections.items():
			if connection.is_pressed:
				return label
		return None
	
	def event_selected(self):
		label = self.selection
		if not label:
			return
		print(self.name + ": " + label)
		self.change_status(label)
	
	def update_status(self, startup=False):
		label = self.selection
		if not label:
			return
		print(self.name + ": Update status - " + label)
		self.change_status(label, startup)
	


"""
Output Devices
"""

class OutputDevice(Device):
	"""
	device = pi_control.device.OutputDevice(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		super().__init__(name, args, debug_pref)
		self._type = 'output'
		self._threads = []
		
		self.last_action = None
		self.last_action_ts = None
	
	@property
	def parent(self):
		return 'output'
	
	@property
	def last_action(self):
		return self._last_action
	
	@last_action.setter
	def last_action(self, action):
		self._last_action = action
	
	@property
	def last_action_ts(self):
		return self._last_action_ts
	
	@last_action_ts.setter
	def last_action_ts(self, ts):
		self._last_action_ts = ts
	
	def action(self, action_info):
		if 'action' not in action_info:
			raise AttributeError("action empty when calling {}".format(self.name))
		
		# Stop running threads
		if len(self._threads):
			for th in self._threads:
				th['stop'] = True
		
		self.last_action_ts = time.time()
		self.last_action = action_info['action']
	
	def start_thread(self, target_method, method_args):
		thread = { "stop": False, "id": random.randint(1000000, 10000000) }
		method_args = method_args + (thread['id'], lambda : thread['stop'], )
		thread['thread'] = threading.Thread(target=target_method, args=method_args)
		thread['thread'].start()
		self._threads.append(thread)
	
	def finish_thread(self, id=None):
		if not id:
			return True
		for i in range(len(self._threads)):
			if self._threads[i]['id'] == id:
				del self._threads[i]
				break
		return True
	

class LED(OutputDevice):
	"""
	led = pi_control.device.LED(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		super().__init__(name, args, debug_pref)
		self._type = 'led'
		if 'gpio_pin' not in args:
			raise AttributeError("GPIO pin required for {} {}".format(self.type, self.name))
		self._connection = gpiozero.PWMLED(self._gpio_pin)
		self.off()
		
	
	"""
	led.action()
	"""
	def action(self, action_info):
		super().action(action_info)
		action = action_info['action']
		
		# No change, skip
		on_actions = ['on', 'flicker_on']
		off_actions = ['off', 'flicker_off']
		
		if self.last_status == 'on' and action in on_actions:
			print('  ' + self.name + ' no change')
			return False
		if self.last_status == 'off' and action in off_actions:
			print('  ' + self.name + ' no change')
			return False
		
		value = None
		if 'value' in action_info:
			value = float(action_info['value'])
		duration = None
		if 'duration' in action_info:
			duration = float(action_info['duration'])
		iterations = None
		if 'iterations' in action_info:
			iterations = int(action_info['iterations'])
		
		if action == 'on':
			return self.on()
		elif action == 'off':
			return self.off()
		elif action == 'value':
			return self.on(value)
		elif action == 'blink':
			self.start_thread(self.blink, (iterations, duration))
			return True
		elif action == 'flicker_on':
			self.start_thread(self.flicker_on, (duration,))
			return True
		elif action == 'flicker_off':
			self.start_thread(self.flicker_off, (duration,))
			return True
		elif action == 'fade_on':
			self.start_thread(self.fade_on, (duration,))
			return True
		elif action == 'fade_off':
			self.start_thread(self.fade_off, (duration,))
			return True
		return False
	
	"""
	led.on()
	"""
	def on(self, value=1.0):
		self._connection.value = value
		self.last_status = 'on'
		return True
	
	"""
	led.off()
	"""
	def off(self):
		self._connection.value = 0.0
		self.last_status = 'off'
		return True
	
	"""
	led.blink(iterations, duration)
	"""
	def blink(self, iterations=3, duration=3, id=None, stop_function=lambda:True):
		for i in range(iterations):
			off_duration =  duration / (iterations*2 - 1)
			on_duration = off_duration
			
			# Off
			if i != 0:
				self._connection.value = 0.0
				if stop_function():
					break
				time.sleep(off_duration)
			
			# On
			self._connection.value = 1.0
			if stop_function():
				break
			time.sleep(on_duration)
		
		if stop_function():
			print("  STOP")
		self.off()
		return self.finish_thread(id)
	
	"""
	led.flicker_on(duration)
	"""
	def flicker_on(self, duration=.5, id=None, stop_function=lambda:True):
		for i in range(8):
			off_duration = (8-i) * float(duration) / 45
			on_duration = i * float(duration) / 45
			brightness = (i+1) / 8
			
			# Off
			if i != 0:
				self._connection.value = 0.0
				if stop_function():
					break
				time.sleep(off_duration)
			
			# On
			self._connection.value = brightness
			if stop_function():
				break
			time.sleep(on_duration)
		
		if stop_function():
			print("  STOP")
			self.off()
		else:
			self.on()
		return self.finish_thread(id)
	
	"""
	led.flicker_off(duration)
	"""
	def flicker_off(self, duration=.5, id=None, stop_function=lambda:True):
		for i in range(8):
			on_duration = (8-i) * float(duration) / 45
			off_duration = i * float(duration) / 45
			brightness = (8-i) / 8
			
			# On
			if i != 0:
				self._connection.value = brightness
				if stop_function():
					break
				time.sleep(on_duration)
			
			# Off
			self._connection.value = 0.0
			if stop_function():
				break
			time.sleep(off_duration)
		
		if stop_function():
			print("  STOP")
			self.on()
		self.off()
		return self.finish_thread(id)
	
	"""
	led.fade_on(duration)
	"""
	def fade_on(self, duration=.5, id=None, stop_function=lambda:True):
		increment = 32
		on_duration = float(duration) / increment
		for i in range(increment):
			brightness = (i+1) / increment
			
			# On
			self._connection.value = brightness
			if stop_function():
				break
			time.sleep(on_duration)
		
		if stop_function():
			print("  STOP")
			self.off()
		else:
			self.on()
		return self.finish_thread(id)
	
	"""
	led.fade_off(duration)
	"""
	def fade_off(self, duration=.5, id=None, stop_function=lambda:True):
		increment = 32
		on_duration = float(duration) / increment
		for i in range(increment):
			brightness = (increment-i) / increment
			
			# On
			self._connection.value = brightness
			if stop_function():
				break
			time.sleep(on_duration)
		
		if stop_function():
			print("  STOP")
			self.on()
		self.off()
		return self.finish_thread(id)
	

class Haptic(OutputDevice):
	"""
	haptic = pi_control.device.Haptic(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		super().__init__(name, args, debug_pref)
		self._type = 'haptic'
		if 'source_bus' not in args:
			raise AttributeError("Source bus required for {} {}".format(self.type, self.name))
		self._connection = adafruit_drv2605.DRV2605(self._i2c)
		
		self._motor = 'erm'
		if 'motor' in args:
			if type(args['motor']) is not str:
				raise TypeError("motor in output {} must be type str".format(self.name))
			args['motor'] = args['motor'].lower()
			if args['motor'] not in ['erm', 'lra']:
				raise AttributeError("Invalid motor in output {}".format(self.name))
			self._motor = args['motor']
			if self._motor == 'lra':
				self._connection.use_LRM()
		
		self._effect = None
		if 'effect' in args:
			if type(args['effect']) is not str and type(args['effect']) is not int and type(args['effect']) is not float:
				raise TypeError("effect in output {} must be type int".format(self.name))
			effect = int(args['effect'])
			if effect < 1 or effect > 123:
				raise ValueError("Invalid effect value for {}".format(self.name))
			self._effect = effect
	
	"""
	haptic.action()
	"""
	def action(self, action_info):
		if 'action' not in action_info:
			action_info['action'] = self._effect
		super().action(action_info)
		action = action_info['action']
		
		# Set variables
		effect = self._effect
		if 'effect' in action_info:
			if type(action_info['effect']) is not str and type(action_info['effect']) is not int and type(action_info['effect']) is not float:
				raise TypeError("effect in output {} must be type int".format(self.name))
			effect = int(action_info['effect'])
			if effect < 1 or effect > 123:
				raise ValueError("Invalid effect value for {}".format(self.name))
			self._effect = effect
		if not effect:
			raise KeyError("effect is required for {} action {}".format(self.type, self.name))
		
		self._connection.sequence[0] = adafruit_drv2605.Effect(effect)
		self._connection.play()
	

class HTTP(OutputDevice):
	"""
	http = pi_control.device.HTTP(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		super().__init__(name, args, debug_pref)
		self._type = 'http'
		self._method = 'get'
		if 'method' in args:
			if type(args['method']) is not str:
				raise TypeError("method in output {} must be type str".format(self.name))
			self._method = args['method']
		self._url = None
		if 'url' in args:
			if type(args['url']) is not str:
				raise TypeError("url in output {} must be type str".format(self.name))
			self._url = args['url']
		self._bearer_token = None
		if 'bearer_token' in args:
			if type(args['bearer_token']) is not str:
				raise TypeError("bearer_token in output {} must be type str".format(self.name))
			self._bearer_token = args['bearer_token']
		self._post_data = {}
		if 'post_data' in args:
			if type(args['post_data']) is not dict:
				raise TypeError("post_data in output {} must be type dict".format(self.name))
			self._method = 'post'
			self._post_data = args['post_data']
		
	
	"""
	http.action()
	"""
	def action(self, action_info):
		if 'action' not in action_info:
			action_info['action'] = self._method
		super().action(action_info)
		action = action_info['action']
		
		# Set variables
		method = self._method
		if 'method' in action_info:
			if type(action_info['method']) is not str:
				raise TypeError("method in action {} must be type str".format(self.name))
			method = action_info['method']
		
		url = self._url
		if 'url' in action_info:
			if type(action_info['url']) is not str:
				raise TypeError("url in action {} must be type str".format(self.name))
			url = action_info['url']
		if not url:
			raise KeyError("url is required for {} action {}".format(self.type, self.name))
		
		bearer_token = self._bearer_token
		if 'bearer_token' in action_info:
			if type(action_info['bearer_token']) is not str:
				raise TypeError("bearer_token in action {} must be type str".format(self.name))
			bearer_token = action_info['bearer_token']
		
		post_data = self._post_data.copy()
		if 'post_data' in action_info:
			if type(action_info['post_data']) is not dict:
				raise TypeError("post_data in action {} must be type str".format(self.name))
			for key, value in action_info['post_data'].items():
				post_data[key] = value
		
		auth_string = ''
		if bearer_token:
			auth_string = ' -H "Authorization: Bearer {}"'.format(bearer_token)
		
		post_string = ''
		if len(post_data):
			data_string = json.dumps(post_data)
			post_string = ' -X POST -H "Content-Type: application/json" -d \'{}\''.format(data_string)
		
		cmd = 'curl -s{}{} {} &'.format(auth_string, post_string, url)
		if self._debug:
			print("cmd:", cmd)
		os.system(cmd)
		
	
class Sound(OutputDevice):
	"""
	sound = pi_control.device.Sound(name, args)
	"""
	def __init__(self, name, args={}, debug_pref=False):
		super().__init__(name, args, debug_pref)
		self._type = 'sound'
		self._file = None
		if 'file' in args:
			if type(args['file']) is not str:
				raise TypeError("file in output {} must be type str".format(self.name))
			self._file = args['file']
		
	
	"""
	sound.action()
	"""
	def action(self, action_info):
		if 'action' not in action_info:
			action_info['action'] = self._file
		super().action(action_info)
		action = action_info['action']
		
		# Set variables
		file = self._file
		if 'file' in action_info:
			if type(action_info['file']) is not str:
				raise TypeError("file in action {} must be type str".format(self.name))
			file = action_info['file']
		if not file:
			raise KeyError("file is required for {} action {}".format(self.type, self.name))
		
		if re.search(r'\.mp3', file):
			os.system('mpg123 -q -m /opt/control/sounds/{} &'.format(file))
		elif re.search(r'\.wav', file):
			os.system('aplay -q /opt/control/sounds/{} &'.format(file))
