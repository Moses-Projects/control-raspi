#!/usr/bin/env python3.7

import time

import pi_control.panel
import pi_control.ui

ui = pi_control.ui.Interface(use_slack_format=True, log_level=6, usage_message = """
Usage:
  /opt/control/control.py [options]
  
  Options:
    -n,  --dry_run        Show likely output, but don't actually make changes.
    -h,  --help           This help text
    -v,  --verbose        Print extra output.
    -vv, --more_verbose   Print all output.
""")



# print("{}: {}".format(panel.name, panel.devices))
# print(panel.devices['power_switch']._actions)

def main():
	args, opts = ui.get_options({
		"options": [ {
			"short": "n",
			"long": "dry_run"
		}, {
			"short": "v",
			"long": "verbose"
		}, {
			"short": "vv",
			"long": "more_verbose"
		}, {
			"short": "vvv",
			"long": "very_verbose"
		} ]
	})
	
	dry_run = False
	if opts['dry_run']:
		dry_run = True
	
	log_level = 4
	if opts['v']:
		log_level = 5
	elif opts['vv']:
		log_level = 6
	elif opts['vvv']:
		log_level = 7
	
	panel = pi_control.panel.Panel('monitor_panel', '/opt/control/control.yml', log_level=log_level)
	
	while 42:
		time.sleep(1)
# 		print('tick')



main()

