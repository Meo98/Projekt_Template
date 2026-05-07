import asyncio
from machine import PWM
from pico_config import PinConfig

class Blink(PinConfig):
    # Wir fügen 'mode' als Parameter hinzu. Standard ist 'digital'.
    # Mögliche Werte: 'digital' oder 'pwm'
    def __init__(self, mode='digital'):       
        self.mode = mode
        
        # Logik-Weiche: Wir definieren hier, was "An" und "Aus" bedeutet
        if self.mode == 'pwm':
            # PWM Konfiguration
            self.pwm_led = PWM(self.status_led)
            self.pwm_led.freq(1000) # 1 kHz Frequenz
            
            # Wir erstellen kleine Hilfsfunktionen für PWM
            # 32768 ist 50% Helligkeit (max ist 65535)
            self._turn_on = lambda: self.pwm_led.duty_u16(32768) 
            self._turn_off = lambda: self.pwm_led.duty_u16(0)
            
        else:
            # Standard Digital Konfiguration (Pin.OUT)
            # Wir nutzen direkt die Methoden des Pin-Objekts
            self._turn_on = self.status_led.on
            self._turn_off = self.status_led.off

    async def run(self):
        # Die loop ist jetzt komplett sauber von if/else Logik
        while True:
            self._turn_on()      # Ruft je nach Modus die richtige Funktion auf
            await asyncio.sleep(0.5)
            self._turn_off()     # Ruft je nach Modus die richtige Funktion auf
            await asyncio.sleep(0.5)