import asyncio
import pdb
import re
from logging import getLogger, NullHandler
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from selenium.webdriver.common.action_chains import ActionChains
import traceback
from typing import Callable
# Device
from .device import AudioDevice
# Processor
from .processors.chatgpt import GPTProcessor,ChatGLMProcessor
# Listener
from .listeners.voicerequest import VoiceRequestListener
# Avatar
from .speech.voicevox import VoicevoxSpeechController,GoogleTTS
from .animation import AnimationController, AnimationControllerDummy
from .avatar import AvatarController



class AIAvatar:
    def __init__(
        self,
        openai_api_key: str,
        google_api_key: str,
        topic: str,
        purpose: str,
        total_time: int,
        participants: list,
        volume_threshold: int=200,
        animation_controller: AnimationController=None,
        avatar_request_parser: Callable=None,
        input_device: int=-1,
        output_device: int=-1,
        lang_TTS = 'en-GB',
        save_audio_path: str=None,
        orgnization_key: str=None,
        model_name : str = "gpt-3.5-turbo-16k-0613",
    ):

        self.logger = getLogger(__name__)
        self.logger.addHandler(NullHandler())

        self.openai_api_key = openai_api_key
        self.google_api_key = google_api_key
        # self.voicevox_url = voicevox_url
        # self.voicevox_speaker_id = voicevox_speaker_id
        self.volume_threshold = volume_threshold
        self.lang_speaker = lang_TTS
        self.save_audio_path = save_audio_path
        self.orgnization = orgnization_key
        self.topic = topic
        self.purpose = purpose
        self.model_name = model_name
        self.total_time = total_time
        self.participants = participants


        # Audio Devices
        if isinstance(input_device, int):
            if input_device < 0:
                input_device_info = AudioDevice.get_default_input_device_info()
                input_device = input_device_info["index"]
            else:
                input_device_info = AudioDevice.get_device_info(input_device)
        elif isinstance(input_device, str):
            input_device_info = AudioDevice.get_input_device_by_name(input_device)
            if input_device_info is None:
                input_device_info = AudioDevice.get_default_input_device_info()
            input_device = input_device_info["index"]

        self.input_device = input_device
        self.logger.info(f"Input device: [{input_device}] {input_device_info['name']}")

        if isinstance(output_device, int):
            if output_device < 0:
                output_device_info = AudioDevice.get_default_output_device_info()
                output_device = output_device_info["index"]
            else:
                output_device_info = AudioDevice.get_device_info(output_device)
        elif isinstance(output_device, str):
            output_device_info = AudioDevice.get_output_device_by_name(output_device)
            if output_device_info is None:
                output_device_info = AudioDevice.get_default_output_device_info()
            output_device = output_device_info["index"]

        self.output_device = output_device
        self.logger.info(f"Output device: [{output_device}] {output_device_info['name']}")

        now = int(round(time.time()*1000))
        now = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(now/1000))

        # Processor
        self.chat_processor = GPTProcessor(output_file='Your_output_path/{}{}.txt'.format(self.topic.replace(" ","_").replace(":", ""), now.replace(" ","_").replace(":", "")), api_key=self.openai_api_key, organization=self.orgnization, topic=self.topic, purpose=self.purpose, plan_file='plan_file', moderator_name='Able', model_name=self.model_name, total_time=self.total_time, participants= self.participants)
        # self.chat_processor = ChatGLMProcessor()

        # Listeners
        self.request_listener = VoiceRequestListener(participants = self.participants, volume_threshold=self.volume_threshold, min_duration=5, max_duration=60,
                                                     rate=16000, device_index=self.input_device, cuda_device='cuda',
                                                     save_audio=self.save_audio_path, ASR_SilencePatience=0.5)


        # Avatar
        # speech_controller = VoicevoxSpeechController(self.voicevox_url, self.voicevox_speaker_id, device_index=self.output_device)
        speech_controller = GoogleTTS(self.google_api_key, device_index=self.output_device, lang=self.lang_speaker)
        animation_controller = animation_controller or AnimationControllerDummy()
        self.avatar_controller = AvatarController(speech_controller, animation_controller, avatar_request_parser)

        # Chat
        self.chat_task = None

    def cut_name(self, text):
        pattern = r"<([^>]+)>:"
        return re.sub(pattern, "", text).strip()



    async def chat(self):
        try:
            await self.avatar_controller.speech_controller.speak(self.cut_name(self.chat_processor.intro))
            self.logger.info("{}:{}".format("Moderator", self.chat_processor.intro))
        except Exception as ex:
            self.logger.error(f"Error at starting chat: {str(ex)}\n{traceback.format_exc()}")


        while True:
            try:
                req = await self.request_listener.get_request()

                self.logger.info(f"User: {req}")

                avatar_task = asyncio.create_task(self.avatar_controller.start())

                # for ChatGPT
                stream_buffer = ""
                speak = False
                self.avatar_controller.begin_sentence = True
                response = ""
                async for t in self.chat_processor.chat(req):
                    stream_buffer += t
                    sp = stream_buffer.replace(".", ".|").replace("!", "!|").replace("?", "?|").split("|")
                    if len(sp) > 1: # >1 means `|` is found (splited at the end of sentence)
                        sentence = sp.pop(0)
                        if self.avatar_controller.begin_sentence:
                            self.avatar_controller.begin_sentence = False
                            speak = True
                            if len(sentence.split(":")) >1:
                                sentence = sentence.split(":")[1].strip()
                        elif re.findall(r"<([^>]+)>:|([^:]+):", sentence):
                            speak = False
                        if speak:
                            stream_buffer = "".join(sp)
                            self.avatar_controller.set_text(sentence)
                            response += sentence
                # for ChatGLM
                # response= self.chat_processor.chat(req)
                #
                # if self.driver:
                #     self.driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[2]/div[2]/section[3]/div[1]/button').click()  # click chat
                #     self.driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[1]/div/div[2]/div/div/div[2]/textarea').send_keys(stream_buffer + Keys.ENTER)  # send message
                #     self.driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[1]/div/div[1]/div[1]/button').click()  # exit chat

                # self.avatar_controller.set_text(response)

                self.avatar_controller.set_stop()
                await avatar_task
                if response:
                    response = self.chat_processor.filter_message(response, 'Moderator')
                    self.logger.info("{}".format(response))
                    self.chat_processor.write_to_file(response)
                    self.chat_processor.moderator_history.append({'role': 'assistant', 'content': response})
            
            except Exception as ex:
                self.logger.error(f"Error at chatting loop: {str(ex)}\n{traceback.format_exc()}")

    def stop_chat(self):
        if self.chat_task is not None:
            self.chat_task.cancel()
