import asyncio
from threading import Thread
from typing import Callable
from . import SpeechListenerAdvanced


class WakewordInput:
    def __init__(self, wakewords: list):
        self.wakewords = wakewords

    async def start(self, app):
        while True:
            text = input('Please enter a command: ')
            if text in self.wakewords:
                await app.chat()
            else:
                print('Please enter a valid command')




