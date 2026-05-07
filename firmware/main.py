import asyncio
from blink import Blink
from pico_config import PinConfig
# from my_feature import MyFeature  # add your own modules here


async def main():
    pc = PinConfig()

    blink = Blink(mode='digital')  # 'digital' or 'pwm'
    # feature = MyFeature()        # instantiate your modules here

    asyncio.create_task(blink.run())
    # asyncio.create_task(feature.run())  # each module runs as an async task

    # keeps the event loop alive
    while True:
        await asyncio.sleep(1)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    PinConfig.status_led.off()