import math
import asyncio

class Fade:
    def __init__(self, led, start_value, end_value, steps):
        """
        Initialisiert den Fader.
        :param led: Das PWM-Objekt (z.B. PWM(Pin(25)))
        :param start_value: Startwert für PWM (muss > 0 sein für log)
        :param end_value: Endwert für PWM (z.B. 65535)
        :param steps: Anzahl der Schritte für die Tabelle (Auflösung)
        """
        self.led = led
        self.start_value = max(1, start_value) # Verhindert log(0)
        self.end_value = end_value
        self.steps = steps
        
        # Interner Status
        self.current_step_index = 0
        self.target_step_index = 0
        self.speed_ms = 10
        self.values = []
        
        # Tabelle generieren
        self._generate_pwm_list()
        
        # LED auf Startwert (0 oder Minimum) setzen
        self.led.duty_u16(self.values[0])
        self.current_step_index = 0

        # Background Task starten
        asyncio.create_task(self._run())

    def _generate_pwm_list(self):
        """Generiert eine logarithmische Helligkeitskurve (exponentielle PWM Werte)"""
        self.values = []
        # Exponentieller Anstieg: y = a * e^(bx)
        # Wir berechnen das so, dass wir von start_value bis end_value gehen
        
        # Falls steps zu klein, mindestens 2 (Start + Ende)
        steps = max(2, self.steps)
        
        # Berechnung des Skalierungsfaktors
        # log(end/start) / (steps-1)
        k = math.log(self.end_value / self.start_value) / (steps - 1)
        
        for i in range(steps):
            val = self.start_value * math.exp(i * k)
            val_int = min(round(val), self.end_value)
            self.values.append(val_int)
            
        # Debug
        # print("Fade Werte:", self.values)

    def fade(self, target_index, speed_ms):
        """
        Startet das Fading zu einem bestimmten Index in der Tabelle.
        :param target_index: Ziel-Index (0 bis steps-1)
        :param speed_ms: Pause zwischen den Schritten in ms (kleiner = schneller)
        """
        # Begrenzung auf gültigen Bereich
        if target_index < 0:
            target_index = 0
        if target_index >= len(self.values):
            target_index = len(self.values) - 1
            
        self.target_step_index = target_index
        self.speed_ms = speed_ms

    def set_value(self, index):
        """Setzt den Wert sofort ohne Fading"""
        if index < 0: index = 0
        if index >= len(self.values): index = len(self.values) - 1
        
        self.current_step_index = index
        self.target_step_index = index
        self.led.duty_u16(self.values[index])

    async def _run(self):
        """Interne Loop, die die Helligkeit anpasst"""
        while True:
            if self.current_step_index != self.target_step_index:
                # Richtung bestimmen
                if self.current_step_index < self.target_step_index:
                    self.current_step_index += 1
                else:
                    self.current_step_index -= 1
                
                # PWM setzen
                self.led.duty_u16(self.values[self.current_step_index])
                
                # Warten
                await asyncio.sleep_ms(self.speed_ms)
            else:
                # Nichts zu tun, kurz schlafen um CPU zu sparen
                await asyncio.sleep_ms(50)
