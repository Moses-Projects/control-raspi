#!/usr/bin/env python3.7

import time

import pi_control.panel

panel = pi_control.panel.Panel('monitor_panel', '/opt/control/control2.yml', True)

# print("{}: {}".format(panel.name, panel.devices))
# print(panel.devices['power_switch']._actions)

def main():
	while 42:
		time.sleep(1)
# 		print('tick')



main()

