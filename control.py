#!/usr/bin/env python3.7

from gpiozero import Button, LED
import json
import os
import paho.mqtt.publish as publish
import re
from signal import pause
import time
import yaml
import boto3
from botocore.exceptions import ClientError

sns = boto3.client('sns')
sns.set_sms_attributes(attributes = { 'DefaultSMSType': 'Transactional' })

conf = []


import board
import busio
import adafruit_drv2605

def main():
	global conf
	conf = read_conf()
	
# 	device = {}
# 	i2c = busio.I2C(board.SCL, board.SDA)
# 	device = adafruit_drv2605.DRV2605(i2c)
# 	device.use_LRM()
# 	device.sequence[0] = adafruit_drv2605.Effect(47)
# 	print("haptic")
# 	device.play()
	
	initialize_pins()
	
	button_handler(True)
	while 42:
		time.sleep(1)
		button_handler()
	
def read_conf():
	path = '/opt/control/control.yml'
	if os.path.exists(path):
		with open(path) as file:
			data = yaml.load(file, Loader=yaml.FullLoader)
			if type(data) is not list:
				print("Config file should be a list.")
				raise ValueError;
			if not len(data):
				print("Config file is empty.")
				raise ValueError;
			return data
	else:
		print("Config file not found at '/opt/control.yml'.")
		raise FileNotFoundError;
	

def initialize_pins():
	global conf
	i2c = None
	for device in conf:
		if 'type' not in device or 'pin' not in device:
			continue
		
		if device['type'] == 'led':
			device['gpio'] = LED(int(device['pin']))
		elif device['type'] == 'button':
			device['gpio'] = Button(int(device['pin']))
			device['last_status'] = False
			device['gpio'].when_pressed = button_handler
			device['gpio'].when_released = button_handler
		elif device['type'] == 'haptic_erm':
			if not i2c:
				i2c = busio.I2C(board.SCL, board.SDA)
			device['gpio'] = adafruit_drv2605.DRV2605(i2c)
		elif device['type'] == 'haptic_lra':
			if not i2c:
				i2c = busio.I2C(board.SCL, board.SDA)
			device['gpio'] = adafruit_drv2605.DRV2605(i2c)
			device['gpio'].use_LRM()
		
		if 'mqtt_id' in device and 'mqtt_broker' in device:
			device['mqtt'] = {
				'id': device['mqtt_id'],
				'broker': device['mqtt_broker'],
				'name': re.sub(r'^.*\/', '', device['mqtt_id']),
				'title': re.sub(r'^.*\/', '', device['mqtt_id']),
				'port': 1883
			}
			if 'mqtt_username' in device and 'mqtt_password' in device:
				device['mqtt']['auth'] = {
					"username": device['mqtt_username'],
					"password": device['mqtt_password']
				}
			if 'mqtt_port' in device:
				device['mqtt']['port'] = int(device['mqtt_port'])
			if 'title' in device:
				device['mqtt']['title'] = device['title']
			device['mqtt']['payload'] = {
				'unique_id': device['mqtt']['name'],
				'name': device['mqtt']['title'],
				'state_topic': "{}/state".format(device['mqtt_id']),
				'command_topic': "{}/set".format(device['mqtt_id']),
				'availability': {'topic': "{}/available".format(device['mqtt_id'])},
				'payload_on': "ON",
				'payload_off': "OFF",
				'state_on': "ON",
				'state_off': "OFF",
				'optimistic': False,
				'qos': 0,
				'retain': True,
			}
# 			print("Discover MQTT")
# 			print("mqtt_payload:", device['mqtt']['payload'])
			publish.single(
				device['mqtt_id'] + '/config',
				payload = json.dumps(device['mqtt']['payload']),
				qos = 1,
				retain = True,
				hostname = device['mqtt']['broker'],
				port = device['mqtt']['port'],
				client_id = "",
				keepalive = 60,
				will = None,
				auth = device['mqtt']['auth'],
				tls = None,
				transport = "tcp"
			)
			publish.single(
				device['mqtt']['payload']['availability']['topic'],
				payload = 'online',
				qos = 1,
				retain = True,
				hostname = device['mqtt']['broker'],
				port = device['mqtt']['port'],
				client_id = "",
				keepalive = 60,
				will = None,
				auth = device['mqtt']['auth'],
				tls = None,
				transport = "tcp"
			)


def button_handler(is_startup=False):
	global conf
	for device in conf:
		if 'type' not in device or device['type'] != 'button':
			continue
		
		# Pressed
		if device['gpio'].is_pressed and not device['last_status']:
			print("press", device['name'])
			device['last_status'] = True
			if 'on_actions' in device:
				action_handler(device, device['on_actions'], is_startup)
		# Released
		elif not device['gpio'].is_pressed and device['last_status']:
			print("release", device['name'])
			device['last_status'] = False
			if 'off_actions' in device:
				action_handler(device, device['off_actions'], is_startup)
		

def action_handler(device, actions, is_startup=False):
	global conf
	devices = {}
	for item in conf:
		devices[item['name']] = item['gpio']
	
	for action in actions:
		if 'delay' in action:
			time_now = time.time()
			if 'timestamp' not in action:
				action['timestamp'] = time_now
			elif (time_now - action['timestamp']) <= action['delay']:
				print('  delay {}'.format(int(action['delay'] - (time_now - action['timestamp']))))
				continue
			action['timestamp'] = time_now
		
		if 'action' not in action:
			continue
		if action['action'] == 'led' and 'device' in action and 'value' in action:
			if action['value'] == 'on':
				devices[action['device']].on()
			elif action['value'] == 'off':
				devices[action['device']].off()
		elif is_startup:
			continue
		elif action['action'] == 'haptic':
			if 'effect' in action:
				devices[action['device']].sequence[0] = adafruit_drv2605.Effect(action['effect'])
			time.sleep(.2)
			devices[action['device']].play()
		elif action['action'] == 'http' and 'url' in action:
			auth_string = ''
			if 'bearer_token' in action:
				auth_string = ' -H "Authorization: Bearer {}"'.format(action['bearer_token'])
			
			post_string = ''
			if 'post_data' in action and type(action['post_data']) is dict:
				data_string = json.dumps(action['post_data'])
				post_string = ' -X POST -H "Content-Type: application/json" -d \'{}\''.format(data_string)
			
			cmd = 'curl -s{}{} {} &'.format(auth_string, post_string, action['url'])
# 			print("cmd:", cmd)
			os.system('curl -s{}{} {} &'.format(auth_string, post_string, action['url']))
			
		elif action['action'] == 'mqtt' and 'mqtt' in device:
# 			print("Send MQTT:", action['value'])
			publish.single(
				device['mqtt']['payload']['command_topic'],
				payload = action['value'],
				qos = 1,
				retain = True,
				hostname = device['mqtt']['broker'],
				port = device['mqtt']['port'],
				client_id = "",
				keepalive = 60,
				will = None,
				auth = device['mqtt']['auth'],
				tls = None,
				transport = "tcp"
			)
		elif action['action'] == 'sound' and 'file' in action:
			if re.search(r'\.mp3', action['file']):
				os.system('mpg123 -q -m /opt/control/sounds/{} &'.format(action['file']))
			elif re.search(r'\.wav', action['file']):
				os.system('aplay -q /opt/control/sounds/{} &'.format(action['file']))
		elif action['action'] == 'sns':
			response = publish_to_sns(action)
	

def publish_to_sns(action, debug=False):
	if 'message' not in action or 'topic_arn' not in action:
		return
	if type(action['topic_arn']) is not str or type(action['message']) is not str:
		return
	
	response = sns.publish(
		TopicArn = action['topic_arn'],
		Message = action['message'],
		MessageStructure = 'string'
	)
	
	if debug:
		print("response:", response)
	if type(response) is dict and 'ResponseMetadata' in response:
		if response['ResponseMetadata'].get('HTTPStatusCode') == 200:
			return response.get('MessageId')



main()
