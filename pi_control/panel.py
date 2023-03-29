print("Loaded pi_control panel module")

import inspect
import os
import re
import threading
import time
import yaml

import pi_control.__init__
import pi_control.device

"""
2022-01-01 Added option to read from a config file.
2022-01-02 Added monitoring for devices without events.
2022-01-08 Separated expanders, outputs, and inputs in the config.
2023-03-29 Improved logging.

To do:
  Separate actions into class
  Should take_action() run in a thread?
"""

"""
import pi_control.panel
"""

class Panel:
	"""
	panel = pi_control.panel.Panel(name, config_filename || devices_dict)
	"""
	def __init__(self, panel_name, devices={}, dry_run=False, log_level=4):
		self._dry_run = dry_run
		self._log_level = log_level
		
		self._name = str(panel_name)
		if type(devices) is str:
			devices = self.read_conf(devices)
		if type(devices) is not dict:
			raise TypeError("Invalid devices dictionary")
		
		self._polling_interval = 2.5
		
		if self._log_level >= 6:
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
				
				self._expanders[name] = pi_control.device.ExpanderDevice(name, device_info, dry_run=self._dry_run, log_level=self._log_level)
		
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
					self._outputs[name] = pi_control.device.LED(name, device_info, dry_run=self._dry_run, log_level=self._log_level)
				elif device_info['type'] == 'haptic':
					self._outputs[name] = pi_control.device.Haptic(name, device_info, dry_run=self._dry_run, log_level=self._log_level)
				elif device_info['type'] == 'http':
					self._outputs[name] = pi_control.device.HTTP(name, device_info, dry_run=self._dry_run, log_level=self._log_level)
				elif device_info['type'] == 'message':
					self._outputs[name] = pi_control.device.Message(name, device_info, dry_run=self._dry_run, log_level=self._log_level)
				elif device_info['type'] == 'sound':
					self._outputs[name] = pi_control.device.Sound(name, device_info, dry_run=self._dry_run, log_level=self._log_level)
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
					device = pi_control.device.Button(name, device_info, dry_run=self._dry_run, log_level=self._log_level)
				elif device_info['type'] == 'potentiometer':
					device = pi_control.device.Potentiometer(name, device_info, dry_run=self._dry_run, log_level=self._log_level)
				elif device_info['type'] == 'rotary_encoder':
					device = pi_control.device.RotaryEncoder(name, device_info, dry_run=self._dry_run, log_level=self._log_level)
				elif device_info['type'] == 'selector_switch':
					device = pi_control.device.SelectorSwitch(name, device_info, dry_run=self._dry_run, log_level=self._log_level)
				else:
					raise ValueError("Device type {} not found".format(device_info['type']))
				
				if device._needs_monitoring:
					needs_monitoring = True
				if pi_control.is_method(device, 'update_status'):
					device.update_status(True)
				self._inputs[name] = device
		
		# Set monitoring thread
		if needs_monitoring:
			if self._log_level >= 6:
				print("Starting monitoring")
			self._monitor_stop = False
			self._monitor_thread = threading.Thread(target=self.monitor_devices, args=(lambda : self._monitor_stop, ))
			self._monitor_thread.start()

	def convert_log_level(self, name):
		if name in ['debug', 'start', 'end']:
			return 7
		elif name == 'info':
			return 6
		elif name == 'notice':
			return 5
		elif name == 'warn':
			return 4
		elif name == 'error':
			return 3
		elif name == 'crit':
			return 2
		elif name == 'alert':
			return 1
		elif name == 'emerg':
			return 0
	
	def log(self, message, level='debug'):
		log_level = self.convert_log_level(level)
		if log_level > self._log_level:
			return
		cnt = 0
		for i in range(len(inspect.stack())):
			function = inspect.stack()[i].function
			if function not in ('<module>', '__init__', 'inner'):
				cnt += 1
		indent = '  ' * cnt
		if level not in ['start', 'end']:
			indent = '  ' + indent
		function = inspect.stack()[1].function
		filename = re.sub(r'^.*\/', '', inspect.stack()[1].filename)
		line = inspect.stack()[1].lineno
		if log_level < 7:
			print("  {}:{}() {}: {}".format(filename, function, line, message))
		else:
			print("{}{}:{}() {}: {}".format(indent, filename, function, line, message))
	
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
		self.log(input_device.name, 'start')
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
# 				self.log("  action()")
				device = self._outputs[action['name']]
				if pi_control.is_method(device, 'action'):
					device.action(action)
		self.log(input_device.name, 'end')
	
	# Main monitoring loop
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
					self.log("Config file is empty.", 'error')
					raise ValueError;
				return data
		else:
			self.log("Config file not found at '{}'".format(path), 'error')
			raise FileNotFoundError;
	
		
