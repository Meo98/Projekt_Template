from machine import Pin, ADC, PWM
from modules import Button

print("pico booting...")


# PinConfig is the single source of truth for all hardware pin assignments.
# Every feature module inherits from this class to access pins.
# Define ALL pins here – never hardcode pin numbers elsewhere in the project.
class PinConfig:

    # Built-in LED (Pico W: use "LED", Pico: use Pin(25))
    status_led = Pin("LED", Pin.OUT)
    # status_led = PWM(Pin("LED"))  # uncomment for PWM brightness control

    # --- Add your project pins below ---
    # Example digital output:
    # relay = Pin(2, Pin.OUT)

    # Example PWM output:
    # motor_pwm = PWM(Pin(3))

    # Example ADC input:
    # sensor = ADC(Pin(26))

    # Example button (wraps Pin in Button class for click/double-click/long-press callbacks):
    # _btn_pin = Pin(14, Pin.IN, Pin.PULL_UP)
    # my_button = Button(_btn_pin, active_low=True)