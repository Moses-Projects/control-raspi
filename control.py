#!/usr/bin/env python3.7

from gpiozero import Button, LED
import os
from signal import pause
import time

led4 = LED(4)
led14 = LED(14)


buttons = {
	'button': {
		'gpio': Button(19),
		'on_actions': [
			{ 'action': 'on', 'device': led4 },
			{ 'action': 'sound', 'sound': 'doorbell', 'delay': 3 }
		],
		'off_actions': [
			{ 'action': 'off', 'device': led4 }
		]
	},
	'switch': {
		'gpio': Button(26),
		'on_actions': [
			{ 'action': 'on', 'device': led14 },
			{ 'action': 'sound', 'sound': 'spark', 'delay': 1 }
		],
		'off_actions': [
			{ 'action': 'off', 'device': led14 }
		]
	}
}


def main():
	global buttons
	
	for name, button in buttons.items():
		button['last_status'] = False
		button['gpio'].when_pressed = button_handler
		button['gpio'].when_released = button_handler
	
	button_handler(True)
	while 42:
		time.sleep(1)
		button_handler()
	

def button_handler(is_startup=False):
	global buttons
	for name, button in buttons.items():
		# Pressed
		if button['gpio'].is_pressed and not button['last_status']:
			print("press", name)
			button['last_status'] = True
			if 'on_actions' in button:
				action_handler(button['on_actions'], is_startup)
		# Released
		elif not button['gpio'].is_pressed and button['last_status']:
			print("release", name)
			button['last_status'] = False
			if 'off_actions' in button:
				action_handler(button['off_actions'], is_startup)
		

def action_handler(actions, is_startup=False):
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
		if action['action'] == 'on' and 'device' in action:
			action['device'].on()
		elif action['action'] == 'off' and 'device' in action:
			action['device'].off()
		elif is_startup:
			continue
		elif action['action'] == 'sound' and 'sound' in action:
			os.system('curl -s http://sounds.mnk:8080/{}'.format(action['sound']))
	



main()
