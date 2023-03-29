# print("Loaded UI module")

# The UI module handles terminal-based interfaces
# Converted from the Perl SitemasonPl::IO module

import getopt
import re
import os
import sys

import pi_control.__init__


"""
import pi_control.ui
"""

class Interface:
	"""
	ui = pi_control.ui.Interface()
	"""
	def __init__(self, use_slack_format=False, usage_message=None, log_level=4):
		self._log_level = log_level
		
		self._use_slack_format = False
		if use_slack_format:
			self._use_slack_format = True
		
		self._usage_message = usage_message
		
		self._colors = self._get_term_color_numbers()
	
	@property
	def supports_color(self):
		if os.environ.get('TERM') and os.environ.get('TERM') not in ['dumb', 'tty']:
			return True

	@property
	def is_person(self):
		if self.supports_color or os.environ.get('SSH_AUTH_SOCK'):
			return True
	
	
	### Arg handing
	"""
	arguments, options = self.get_options({
		"args": [ {
			"name": "function",
			"label": "Lambda function",
			"required": True
		}, {
			"name": "environment",
			"label": "Environment",
			"values": ["dev", "prod"],
			"required": True
		}, {
			"name": "file",
			"label": "JSON file",
			"type": "file",
			"required": True
		} ],
		"options": [ {
			"short": "v",
			"long": "verbose"
		} ]
	})
	"""
	def get_options(self, params={}):
		
		# Prep options
		options = {}
		short_opts = ""
		long_opts = []
		if self._usage_message:
			short_opts = "h"
			long_opts.append("help")
		if 'options' in params:
			for opt in params['options']:
				sa = ''
				la = ''
				if 'type' in opt and opt['type'] == 'input':
					sa = ':'
					la = '='
				if 'short' in opt:
					short_opts += opt['short'] + sa
					if 'type' not in opt or opt['type'] == 'bool':
						options[opt['short']] = False
					else:
						options[opt['short']] = None
				if 'long' in opt:
					long_opts.append(opt['long'] + la)
					if 'type' not in opt or opt['type'] == 'bool':
						options[opt['long']] = False
					else:
						options[opt['long']] = None
		
		# Parse options and arguments
		try:
			opts, args = getopt.gnu_getopt(sys.argv[1:], short_opts, long_opts)
		except getopt.GetoptError as err:
			self.error(err)  # will print something like "option -a not recognized"
			self.usage()
			sys.exit(2)
		
		# Handle options
		for o, a in opts:
			if o in ("-h", "--help"):
				self.usage()
				sys.exit()
			elif 'options' in params:
				for opt in params['options']:
					if ('short' in opt and o == '-' + opt['short']) or ('long' in opt and o == '--' + opt['long']):
						if 'type' not in opt or opt['type'] == 'bool':
							a = True
						if 'short' in opt:
							options[opt['short']] = a
						if 'long' in opt:
							options[opt['long']] = a
		
		# Handle arguments
		arguments = {}
		if 'args' in params:
			for param in params['args']:
				label = param['name']
				if 'label' in param:
					label = param['label']
				
				if 'required' in param and param['required'] and not len(args):
					self.error(f"argument '{label}' is required")
					self.usage()
					sys.exit(2)
				
				if len(args):
					value = args.pop(0)
					if 'values' in param and type(param['values']) is list:
						if value not in param['values']:
							self.error("argument '{}' must be one of '{}'".format(label, "', '".join(param['values'])))
							self.usage()
							sys.exit(2)
					if 'type' in param and param['type'] == 'file':
						if not os.path.isfile(value):
							self.error("file '{}' not found".format(value))
							self.usage()
							sys.exit(2)
					arguments[param['name']] = value
				else:
					arguments[param['name']] = None
		
		return arguments, options


	
	
	
	### Output formatting
	
	# https://en.wikipedia.org/wiki/ANSI_escape_code
	# https://en.wikipedia.org/wiki/Web_colors
	def _get_term_color_numbers(self):
		colors = self._get_term_color_number_list()
		color_hash = {}
		for color in colors:
			color_hash[color['name']] = color['num']
		return color_hash
	
	def _get_term_color_number_list(self):
		return [
			{ "name": "reset",			"num": 0 },
			{ "name": "default",		"num": 39 },
			{ "name": "default_bg",		"num": 49 },
		
			{ "name": "bold",			"num": 1 },	# reset 21 # yes
			{ "name": "faint",			"num": 2 },	# reset 22 # yes
			{ "name": "italic",			"num": 3 },	# reset 23
			{ "name": "underline",		"num": 4 },	# reset 24 # yes
			{ "name": "blink",			"num": 5 },	# reset 25 # yes
			{ "name": "rapid",			"num": 6 },	# reset 26
			{ "name": "inverse",		"num": 7 },	# reset 27 # yes
			{ "name": "conceal",		"num": 8 },	# reset 28 # yes
			{ "name": "crossed",		"num": 9 },	# reset 29
		
			{ "name": "white",			"num": 97 },
			{ "name": "silver",			"num": 37 },
			{ "name": "gray",			"num": 90 },
			{ "name": "black",			"num": 30 },
		
			{ "name": "red",			"num": 91 },
			{ "name": "maroon",			"num": 31 },
			{ "name": "yellow",			"num": 93 },
			{ "name": "olive",			"num": 33 },
			{ "name": "lime",			"num": 92 },
			{ "name": "green",			"num": 32 },
			{ "name": "cyan",			"num": 96 },
			{ "name": "teal",			"num": 36 },
			{ "name": "blue",			"num": 94 },
			{ "name": "azure",			"num": 34 },
			{ "name": "pink",			"num": 95 },
			{ "name": "magenta",		"num": 35 },
		
			{ "name": "white_bg",		"num": 107 },
			{ "name": "silver_bg",		"num": 47 },
			{ "name": "gray_bg",		"num": 100 },
			{ "name": "black_bg",		"num": 40 },
		
			{ "name": "red_bg",			"num": 101 },
			{ "name": "maroon_bg",		"num": 41 },
			{ "name": "yellow_bg",		"num": 103 },
			{ "name": "olive_bg",		"num": 43 },
			{ "name": "lime_bg",		"num": 102 },
			{ "name": "green_bg",		"num": 42 },
			{ "name": "cyan_bg",		"num": 106 },
			{ "name": "teal_bg",		"num": 46 },
			{ "name": "blue_bg",		"num": 104 },
			{ "name": "azure_bg",		"num": 44 },
			{ "name": "pink_bg",		"num": 105 },
			{ "name": "magenta_bg",		"num": 45 },
		
			{ "name": "reset_bg",		"num": 49 }
		]
	
	def print_term_colors(self):
		colors = self._get_term_color_number_list()
		e = self.get_term_color('reset')
		for ind in range(3, (len(colors)-1)):
			color = colors[ind]
			color_num = str(color['num'])
			if ind < 12:
				name = color['name']
				ds, de = self.get_term_color(name)
				print(f"{name:14s}: {ds:s}{name:s}{de:s}")
			else:
				name = 'default'
				ds, de = self.get_term_color(name)
				bs, be = self.get_term_color([name, 'bold'])
				fs, fe = self.get_term_color([name, 'faint'])
				ist, ie = self.get_term_color([name, 'inverse'])
				if ind == 12:
					print("")
					header = f"{' ':14s}  {'default':14s} {'bold':14s} {'faint':14s} {'inverse':14s}"
					self.header(header)
					print(f"{name:14s}: {ds:s}{name:14s}{de:s} {bs:s}{name:14s}{be:s} {fs:s}{name:14s}{fe:s} {ist:s}{name:14s}{ie:s}")
				elif ind == 28:
					print("")
				name = color['name']
				ds, de = self.get_term_color(name)
				bs, be = self.get_term_color([name, 'bold'])
				fs, fe = self.get_term_color([name, 'faint'])
				ist, ie = self.get_term_color([name, 'inverse'])
				print(f"{name:14s}: {ds:s}{name:14s}{de:s} {bs:s}{name:14s}{be:s} {fs:s}{name:14s}{fe:s} {ist:s}{name:14s}{ie:s}")
	
	def print_sample_sections(self):
		self.info("This is info")
		self.warning("This is a warning\n  Line 2")
		self.error("This is an error\n  Line 2")
		self.title("This is a title")
		self.header("This is a header")
		self.header2("This is a header2")
		self.body("This is a body")
		self.body("> This is a quote")
		self.success("This is success")
		self.dry_run("This is a dry run")
		self.verbose("This is verbose")
	
	
	# color_code = ui.get_term_color(color_name)
	def get_term_color(self, names):
		if not self.supports_color:
			return '', ''
		
		if type(names) is str:
			names = [names]
		color_nums = []
		for name in names:
			if name in self._colors:
				color_nums.append(str(self._colors[name]))
		if not len(color_nums):
			return '', ''
		
		code = "\033"
		start = "{}[{}m".format(code, ';'.join(color_nums))
		
		end = code + "[0m"
		if len(names) == 1:
			if self._colors[names[0]] >= 2 and self._colors[names[0]] <= 9:
				end = "{}[{}m".format(code, str(self._colors[name]+20))
			elif re.search(r'_bg$', names[0]):
				end = "{}[{}m".format(code, str(self._colors['reset_bg']))
		
		return start, end
	
	# formatted_string = ui.format_text(text, colors)
	# formatted_string = ui.format_text(text, 'blue')
	# formatted_string = ui.format_text(text, ['blue', 'white_bg', 'bold'])
	def format_text(self, text, colors, quote=None):
		text = str(text)
		start, end = self.get_term_color(colors)
		
		quote_string = ''
		if quote:
			quote_string = self.make_quote(quote)
		
		output = []
		lines = text.split("\n")
		for line in lines:
			output.append("{}{}{}{}".format(quote_string, start, line, end))
		return "\n".join(output)
	
	def convert_slack_to_ansi(self, text=None):
		if not text or not len(str(text)):
			return ''
		if not self._use_slack_format:
			return text
		
	# 	$text =~ s/(?:^|(?<=\s))\*(\S.*?)\*/\e[1m$1\e[21m/g;
		text = re.sub(r'(?:^|(?<=\s))\*(\S.*?)\*', lambda m: self.format_text(m.group(1), 'bold'), str(text))
		text = re.sub(r'(?:^|(?<=\s))\_(\S.*?)\_', lambda m: self.format_text(m.group(1), 'underline'), text)
		text = re.sub(r'(?:^|(?<=\s))~(\S.*?)~', lambda m: self.format_text(m.group(1), 'inverse'), text)
		text = re.sub(r'(?:^|(?<=\s))`(\S.*?)`', lambda m: self.format_text(m.group(1), ['red', 'silver_bg']), text)
		text = re.sub(r'^> ', lambda m: self.make_quote(), text)
# 		$text =~ s/^>/$self->make_quote('silver_bg')/egm;
		return text
	
	def make_quote(self, color_name='silver_bg'):
		if not re.search(r'_bg$', color_name) or not self.supports_color:
			return '| '
		indent = self.format_text(' ', color_name)
		return indent + ' '
	
	def bold(self, text=None):
		if not text or not len(str(text)):
			return ''
		return self.format_text(text, 'bold')
	
	def body(self, text=None):
		text = self.convert_slack_to_ansi(text)
		if not len(text):
			return
		print(text)
	
	def title(self, text=None):
		text = self.convert_slack_to_ansi(text)
		if not len(text):
			return
		print(self.format_text(f' {text:s} ', ['blue', 'bold', 'inverse']))
	
	def header(self, text=None):
		text = self.convert_slack_to_ansi(text)
		if not len(text):
			return
		print(self.format_text(text, ['blue', 'bold', 'underline']))
	
	def header2(self, text=None):
		text = self.convert_slack_to_ansi(text)
		if not len(text):
			return
		print(self.format_text(text, ['bold', 'underline']))
	
	def success(self, text=None):
		text = self.convert_slack_to_ansi(text)
		if not len(text):
			return
		print(self.format_text(text, ['green', 'bold']))
	
	def dry_run(self, text=None):
		text = self.convert_slack_to_ansi(text)
		if not len(text):
			return
		print(self.format_text(text, ['silver'], quote='silver_bg'))
	
	def verbose(self, text=None):
		text = self.convert_slack_to_ansi(text)
		if not len(text):
			return
		print(self.format_text(text, ['gray'], quote='gray_bg'))
	
	def info(self, text=None):
		text = self.convert_slack_to_ansi(text)
		if not len(text):
			return
		print(self.format_text(text, ['gray'], quote='gray_bg'))
	
	def warning(self, text=None):
		text = self.convert_slack_to_ansi(text)
		if not len(text):
			return
		print(self.format_text(text, ['olive', 'bold'], quote='olive_bg'))
	
	def error(self, text=None):
		text = self.convert_slack_to_ansi(text)
		if not len(text):
			return
		print(self.format_text('ERROR: ' + text, ['maroon', 'bold'], quote='maroon_bg'))
	
	def usage(self):
		if not self._usage_message:
			return
		self.info(self._usage_message)
	
	

