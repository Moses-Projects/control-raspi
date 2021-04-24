#!/usr/bin/env python3.7

from gpiozero import Button, LED
import os
from signal import pause
import time
import yaml
import boto3
from botocore.exceptions import ClientError

sns = boto3.client('sns')
sns.set_sms_attributes(attributes = { 'DefaultSMSType': 'Transactional' })

conf = []


def main():
	global conf
	conf = read_conf()
	
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
	for device in conf:
		if 'type' not in device or 'pin' not in device:
			continue
		
		if device['type'] == 'led':
			device['gpio'] = LED(int(device['pin']))
		if device['type'] == 'button':
			device['gpio'] = Button(int(device['pin']))
			device['last_status'] = False
			device['gpio'].when_pressed = button_handler
			device['gpio'].when_released = button_handler
	

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
				action_handler(device['on_actions'], is_startup)
		# Released
		elif not device['gpio'].is_pressed and device['last_status']:
			print("release", device['name'])
			device['last_status'] = False
			if 'off_actions' in device:
				action_handler(device['off_actions'], is_startup)
		

def action_handler(actions, is_startup=False):
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
		elif action['action'] == 'url' and 'url' in action:
			os.system('curl -s {}'.format(action['url']))
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
