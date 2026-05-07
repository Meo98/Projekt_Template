import asyncio
import time

class Button:
    def __init__(self, pin, active_low=True):
        """
        :param pin: Das Pin-Objekt (z.B. Pin(15, Pin.IN, Pin.PULL_UP))
        :param active_low: True, wenn Button bei Drücken 0 ist (GND). False bei 1 (VCC).
        """
        self.pin = pin
        self.active_low = active_low
        
        # Callbacks (Funktionen, die ausgeführt werden sollen)
        self._on_click = None
        self._on_double_click = None
        self._on_long_press = None
        
        # Konfiguration
        self.debounce_ms = 30
        self.long_press_ms = 800
        self.double_click_speed_ms = 300
        
        # Startet den Überwachungs-Task sofort im Hintergrund
        asyncio.create_task(self.run())

    # --- Setup Methoden ---
    def on_click(self, func):
        self._on_click = func

    def on_double_click(self, func):
        self._on_double_click = func

    def on_long_press(self, func):
        self._on_long_press = func

    # --- Interne Logik ---
    def _is_pressed(self):
        val = self.pin.value()
        return val == 0 if self.active_low else val == 1

    async def _trigger(self, callback):
            if callback:
                print(f"Button Event: {callback.__name__}")
                res = callback()
                if hasattr(res, "send"): # Check if generator/coroutine in MicroPython
                    await res

    async def run(self):
        click_count = 0
        
        while True:
            # 1. Warten bis Taste gedrückt wird
            if not self._is_pressed():
                await asyncio.sleep_ms(20)
                continue
            
            # 2. Debounce (Entprellen)
            await asyncio.sleep_ms(self.debounce_ms)
            if not self._is_pressed():
                continue # War nur ein Störsignal
            
            # 3. Zeitmessung starten für Long Press
            press_start = time.ticks_ms()
            long_triggered = False
            
            # 4. Warten solange gedrückt (Hier prüfen wir auf Long Press)
            while self._is_pressed():
                # Prüfen ob Zeit für Long Press erreicht ist
                if not long_triggered and time.ticks_diff(time.ticks_ms(), press_start) > self.long_press_ms:
                    long_triggered = True
                    await self._trigger(self._on_long_press)
                await asyncio.sleep_ms(20)
            
            # 5. Taste wurde losgelassen
            if long_triggered:
                # Wenn es schon ein Long Press war, zählen wir das nicht als Klick
                click_count = 0
                continue
            
            # Es war ein kurzer Klick -> Zählen
            click_count += 1
            
            # 6. Warten auf potenziellen zweiten Klick (Double Click Fenster)
            # Wir warten kurz. Wenn in der Zeit kein neuer Klick kommt, werten wir aus.
            # Wenn ein neuer Klick kommt (Schleife beginnt von vorne), zählt click_count hoch.
            
            # Trick: Wir warten nur, wenn wir noch nicht bei N Clicks sind
            # Hier vereinfacht: Wir warten die Double-Click-Zeit ab.
            # Um das sauber asynchron zu lösen ohne die Schleife zu blockieren, 
            # müssten wir Events nutzen. Für einfache Zwecke reicht aber folgendes:
            
            try:
                # Wir warten: Kommt ein neuer Klick innerhalb von 300ms?
                await asyncio.wait_for(self._wait_for_press(), timeout=self.double_click_speed_ms/1000)
                # Aha! Taste wurde nochmal gedrückt innerhalb der Zeit!
                # Der Loop fängt oben wieder an, click_count ist jetzt > 0
                continue 
            except asyncio.TimeoutError:
                # Zeit abgelaufen, keine weitere Taste gedrückt. Auswerten!
                if click_count == 1:
                    await self._trigger(self._on_click)
                elif click_count >= 2:
                    await self._trigger(self._on_double_click)
                
                # Reset
                click_count = 0

    async def _wait_for_press(self):
        """Hilfsfunktion: Wartet bis Taste gedrückt wird (für Double Click Erkennung)"""
        while not self._is_pressed():
            await asyncio.sleep_ms(10)