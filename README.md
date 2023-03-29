# control-raspi
A simple server that listens for interrupts and takes appropriate actions.


## Config layout
```
outputs:
  {output reference name}:
    type: {output type}
    ...
  ...
inputs:
  {input reference name}:
    type: {output type}
    ...
```

## Outputs
### LEDs
* type: "led"
* gpio_pin: (int)
* action: "on"
* action: "off"
* action: "value"
	* value: (float) - brightness value from 0.0 to 1.0
* action: "blink"
	* iterations: (int) - number of blinks
	* duration: (float) - number of seconds
* action: "flicker_on"
	* duration: (float) - number of seconds
* action: "flicker_off"
	* duration: (float) - number of seconds
* action: "fade_on"
	* duration: (float) - number of seconds
* action: "fade_off"
	* duration: (float) - number of seconds
    
### Haptic
* type: "haptic"
* source_bus: "i2c"
* motor: "lra" or "erm"
* effect: (int) - 1 to 123
* delay: (int)

### HTTP
* type: "http"
* method: "get" or "post"; defaults to "get"
* url: (string)
* bearer_token: (string)
* post_data: (hash or array)
* delay: (int)

### Message - Send SNS message
* type: "message"
* service: "print" or "sns"; defaults to "print"
* message: (string)
* topic_arn: (string) - Required for SNS service

### Sound
* type: "sound"
* file: (string) - File name relative to /opt/control/sounds



# Inputs
## type: "button"
## type: "potentiometer"
## type: "rotary_encoder"
## type: "selector_switch"




