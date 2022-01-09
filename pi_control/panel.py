print("Loaded pi_control panel module")

import os
import threading
import time
import yaml

import pi_control.__init__
import pi_control.device

"""
2022-01-01 Added option to read from a config file.
2022-01-02 Added monitoring for devices without events.
2022-01-08 Separated expanders, outputs, and inputs in the config.

To do:
  Separate actions into class
  Should take_action() run in a thread?
"""

"""
import pi_control.panel
"""

debug = False

class Panel:
	"""
	panel = pi_control.panel.Panel(name, config_filename || devices_dict)
	"""
	def __init__(self, panel_name, devices={}, debug_pref=False):
		global debug
		if debug_pref:
			debug = True
		
		self._name = str(panel_name)
		if type(devices) is str:
			devices = self.read_conf(devices)
		if type(devices) is not dict:
			raise TypeError("Invalid devices dictionary")
		
		self._polling_interval = 2.5
		
		if debug:
			print("devices:", devices)
		self._expanders = {}
		self._outputs = {}
		self._inputs = {}
		
		# Init expanders
		if 'expanders' in devices:
			for name, device_info in devices['expanders'].items():
				if 'type' not in device_info or type(device_info['type']) is not str:
					raise AttributeError("Expander {} is missing a valid type".format(name))
				device_info['panel'] = self
				
				self._expanders[name] = pi_control.device.ExpanderDevice(name, device_info, debug)
		
		# Fill source_devices and init outputs
		if 'outputs' in devices:
			for name, device_info in devices['outputs'].items():
				if 'type' not in device_info or type(device_info['type']) is not str:
					raise AttributeError("Output {} is missing a valid type".format(name))
				device_info['panel'] = self
				
				if 'source_device' in device_info:
					if device_info['source_device'] not in self._expanders:
						raise AttributeError("Source device {} for {} not found".format(device_info['source_device'], name))
					if not self._expanders[device_info['source_device']]._chip:
						raise AttributeError("Source device {} for {} must be an expander device".format(device_info['source_device'], name))
					device_info['source_device'] = self._expanders[device_info['source_device']]
				
				if device_info['type'] == 'led':
					self._outputs[name] = pi_control.device.LED(name, device_info, debug)
				elif device_info['type'] == 'haptic':
					self._outputs[name] = pi_control.device.Haptic(name, device_info, debug)
				elif device_info['type'] == 'http':
					self._outputs[name] = pi_control.device.HTTP(name, device_info, debug)
				elif device_info['type'] == 'message':
					self._outputs[name] = pi_control.device.Message(name, device_info, debug)
				elif device_info['type'] == 'sound':
					self._outputs[name] = pi_control.device.Sound(name, device_info, debug)
				else:
					raise ValueError("Device type {} not found".format(device_info['type']))
		
		# Fill actions and init inputs
		needs_monitoring = False
		if 'inputs' in devices:
			for name, device_info in devices['inputs'].items():
				if 'type' not in device_info or type(device_info['type']) is not str:
					raise AttributeError("Input {} is missing a valid type".format(name))
				device_info['panel'] = self
				
				if 'source_device' in device_info:
					if device_info['source_device'] not in self._expanders:
						raise AttributeError("Source device {} for {} not found".format(device_info['source_device'], name))
					if not self._expanders[device_info['source_device']]._chip:
						raise AttributeError("Source device {} for {} must be an expander device".format(device_info['source_device'], name))
					device_info['source_device'] = self._expanders[device_info['source_device']]
				
				# Process actions
				device = None
				if device_info['type'] == 'button':
					device = pi_control.device.Button(name, device_info, debug)
				elif device_info['type'] == 'potentiometer':
					device = pi_control.device.Potentiometer(name, device_info, debug)
				elif device_info['type'] == 'rotary_encoder':
					device = pi_control.device.RotaryEncoder(name, device_info, debug)
				else:
					raise ValueError("Device type {} not found".format(device_info['type']))
				
				if device._needs_monitoring:
					needs_monitoring = True
				if pi_control.is_method(device, 'update_status'):
					device.update_status(True)
				self._inputs[name] = device
		
		# Set monitoring thread
		if needs_monitoring:
			if debug:
				print("Starting monitoring")
			self._monitor_stop = False
			self._monitor_thread = threading.Thread(target=self.monitor_devices, args=(lambda : self._monitor_stop, ))
			self._monitor_thread.start()

	@property
	def name(self):
		return self._name
	
	@property
	def expanders(self):
		return self._expanders
	
	@property
	def outputs(self):
		return self._outputs
	
	@property
	def inputs(self):
		return self._inputs
	
	def get_expander(self, device_name):
		if device_name in self.expanders:
			return self.expanders[device_name]
		return None
	
	def get_output(self, device_name):
		if device_name in self.outputs:
			return self.outputs[device_name]
		return None
	
	def get_input(self, device_name):
		if device_name in self.inputs:
			return self.inputs[device_name]
		return None
	
	def take_action(self, input_device, action_name, startup=False):
# 		print(input_device.name + ": Take action")
		actions = input_device.get_actions(action_name)
		cnt = 0
		for action in actions:
			if 'name' not in action:
				raise KeyError("Name is required in action {} in action for {}.{}".format(cnt, device_name, action_name))
			cnt += 1
			
			# On init, skip non-init actions
			if startup and ('init' not in action or not action['init']):
				continue
			
			# Defined actions
			if 'name' in action:
				if action['name'] not in self._outputs:
					raise ValueError("Output {} in action for {}.{} not found".format(action['name'], device_name, action_name))
# 				print("  action()")
				device = self._outputs[action['name']]
				if pi_control.is_method(device, 'action'):
					device.action(action)
	
	def monitor_devices(self, stop_function=lambda:True):
		while 42:
			for name, device in self._inputs.items():
				if not device._needs_monitoring:
					continue
				if pi_control.is_method(device, 'update_status'):
					device.update_status()
# 					action_key = device.monitor()
# 					if action_key:
# 						device.change_status(action_key)
				if stop_function():
					break
			if stop_function():
				return
			time.sleep(self._polling_interval)
		return True
	
	def read_conf(self, path):
		if os.path.exists(path):
			with open(path) as file:
				data = yaml.load(file, Loader=yaml.FullLoader)
				if not len(data):
					print("Config file is empty.")
					raise ValueError;
				return data
		else:
			print("Config file not found at '{}'".format(path))
			raise FileNotFoundError;
	
		
