import base64
from logging import getLogger, NullHandler
import numpy
import time
import traceback
from typing import Callable
import aiohttp
import re
import sys
import signal
import pyaudio
import whisperx
import msvcrt
from selenium.webdriver.common.by import By
import subprocess
from selenium.webdriver.common.keys import Keys

import pdb
from pydub import AudioSegment
import torchaudio
import queue
import threading

from speechbrain.pretrained import EncoderClassifier
from torch.nn import CosineSimilarity
import torch


class SpeechListenerAdvanced:
    def __init__(self, participants, volume_threshold: int = 200, min_duration: float = 3,
                 max_duration: float = 90.0, rate: int = 16000, device_index: int = -1, cuda_device: str = 'cuda',
                 save_audio: str = "", compute_type: str = "float16",  ASR_SilencePatience: float = 0.5):
        self.logger = getLogger(__name__)
        self.logger.addHandler(NullHandler())

        self.is_listening = False
        self.lock = threading.Lock()
        self.participants = participants
        self.pa = pyaudio.PyAudio()
        self.volume_threshold = volume_threshold
        self.rate = rate
        self.ASR_SilencePatience = ASR_SilencePatience
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.audio_device_index = device_index
        self.save_audio = save_audio
        self.index = 0
        self.empty_ASR = 0
        self.queue = queue.Queue()
        self.device = cuda_device
        self.ASR = whisperx.load_model("large-v2", device=self.device, compute_type=compute_type, language="en")
        self.ASR_Text = []
        self.voiceprint = {}
        self.sim_function = CosineSimilarity(dim=-1, eps=1e-6)
        self.aligner, self.metadata = whisperx.load_align_model(language_code="en", device=self.device)
        self.voice_encoder = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                                            savedir="pretrained_models/spkrec-ecapa-voxceleb")
        self.register_all()

    def register_all(self):
        # while True:
        #     try:
        #         name = input("Please enter your name: ")
        #         if name == "exit":
        #             break
        #         file_path = input("Please enter the path of your audio file: ")
        #         self.register(name, file_path)
        #     except KeyboardInterrupt:
        #         break
        for participant in self.participants:
            name = participant
            file_path = './par_selection/candidates/{}.mp3'.format(name)
            self.register(name, file_path)

    def register(self, name, file_path):
        audio_data, _ = torchaudio.load(file_path)
        embedding = self.voice_encoder.encode_batch(audio_data)[0]
        self.voiceprint[name] = embedding

    # def find_speaker_web(self):
    #     self.driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[3]/div[1]/button[2]').click()  # click user list
    #     users = self.driver.find_elements(By.CLASS_NAME, 'List__list-item__Wa7vr')
    #     for i in range(1, len(users)):
    #         if 'Not' in users[i].find_elements(By.TAG_NAME, 'svg')[1].find_element(By.TAG_NAME, 'title').get_attribute('textContent'):
    #             continue
    #         else:
    #             user_name = users[i].find_element(By.TAG_NAME, 'p').get_attribute('textContent')
    #             self.driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[1]/div/div[1]/div[1]/button').click()  # exit user list
    #             return user_name
    #     self.driver.find_element(By.XPATH,
    #                              '/html/body/div[2]/div/div/div[1]/div/div[1]/div[1]/button').click()  # exit user list
    #     return None

    def convert_int16_to_float(self, audio_data):
        # 将 16 位整型音频字符串转换为 32 位浮点数数组
        int16_array = numpy.frombuffer(audio_data, dtype=numpy.int16)
        float32_array = int16_array.astype(numpy.float32) / 32768.0  # 进行归一化处理
        return float32_array

    def calculate_rms(self, audio_data):
        rms = numpy.sqrt(numpy.mean((audio_data * 32768.0) ** 2))

        return rms

    def combine_audio(self, audio_list):
        combined_audio = AudioSegment.empty()

        # 将每个字节流转换为 AudioSegment 对象，并逐个合并
        for byte_stream in audio_list:
            audio_segment = AudioSegment(byte_stream)
            combined_audio += audio_segment
        return combined_audio

    def remove_punctuation(self, text):
        pattern = r"[^\w\s-]"
        text = re.sub(pattern, " ", text)
        text = text.lower()  # 将文本转换为小写
        text = text.replace("\n", " ")  # 去除换行符
        return text

    def find_speaker(self, embedding):
        max_sim = 0
        speaker = ""
        for key in self.voiceprint.keys():
            sim = self.sim_function(embedding, self.voiceprint[key])
            if sim > max_sim:
                max_sim = sim
                speaker = key
        return speaker, max_sim

    def SpeechtoText(self, queue):
        last_speaker = ""
        while True:
            item = queue.get()
            if isinstance(item, str) and item == "stop":
                break
            transcript = self.ASR.transcribe(item, batch_size=4)['segments']
            if not transcript:
                self.empty_ASR += 1
                if self.empty_ASR >= 5:
                    self.empty_ASR = 0
                    self.logger.info("No response for 5 times, stop listening")
                    self.is_listening = False
                continue
            transcript = \
            whisperx.align(transcript, self.aligner, self.metadata, item, self.device, return_char_alignments=False)[
                'segments']
            text = ""
            for i in range(len(transcript)):
                start_time = int(transcript[i]['start']) * self.rate
                end_time = int(transcript[i]['end']) * self.rate
                text_tmp = transcript[i]['text'].strip()
                if item[start_time:end_time].shape[0] > 1024:
                    audio_embedding = \
                    self.voice_encoder.encode_batch(torch.from_numpy(item[start_time:end_time][numpy.newaxis, :]))[0]
                    speaker, sim = self.find_speaker(audio_embedding)
                    if not speaker:
                        speaker = last_speaker
                else:
                    continue
                if speaker == last_speaker:
                    text += ' ' + text_tmp
                else:
                    text += '\n' + '<{}>:'.format(speaker) + text_tmp
                    last_speaker = speaker
            if text:
                self.ASR_Text.append(text)
                self.empty_ASR = 0
                self.logger.info(f"ASR: {text}")
            else:
                self.logger.info(f"ASR: Empty")
                self.empty_ASR += 1
                if self.empty_ASR >= 5:
                    self.logger.info(f"No response for 2 times, stop listening")
                    self.empty_ASR = 0
                    self.is_listening = False

    def Recording(self, queue):
        audio_data = []
        silence = True
        recording = False
        silence_time = 0
        record_time = 0
        no_response_time = 0
        start_time = time.time()

        def callback(in_data, frame_count, time_info, status):
            nonlocal silence, silence_time, recording, record_time, no_response_time
            # if self.save_audio:
            #     self.ffmpeg_process.stdin.write(in_data)
            audio_piece = self.convert_int16_to_float(in_data)
            rms = self.calculate_rms(audio_piece)
            # self.logger.info(f"RMS: {rms}")
            if silence and rms > self.volume_threshold:
                silence = False
                recording = True
                audio_data.extend(audio_piece)
            elif silence and rms <= self.volume_threshold:
                if recording:
                    if silence_time > self.ASR_SilencePatience and record_time > self.min_duration:
                        self.logger.info(f"ASR Start:{record_time}")
                        recording = False
                        silence_time = 0
                        record_time = 0
                        queue.put(numpy.array(audio_data))
                        audio_data.clear()
                    else:
                        audio_data.extend(audio_piece)
            elif not silence and rms > self.volume_threshold:
                silence_time = 0
                audio_data.extend(audio_piece)
                if record_time > self.max_duration:
                    recording = False
                    silence = True
                    record_time = 0
                    self.logger.info(f"ASR Start:{record_time}")
                    queue.put(numpy.array(audio_data))
                    audio_data.clear()

            else:
                no_response_time = 0
                silence_time = 0
                silence = True
                audio_data.extend(audio_piece)
            if recording:
                record_time += frame_count / self.rate
            if silence:
                no_response_time += frame_count / self.rate
                silence_time += frame_count / self.rate
                if no_response_time >= 30:
                    self.logger.info(f"no response for 30s, stop listening")
                    self.is_listening = False
            return (None, pyaudio.paContinue)

        try:
            stream = self.pa.open(
                input_device_index=self.audio_device_index,
                format=pyaudio.paInt16,
                channels=1,
                rate=self.rate,
                input=True,
                frames_per_buffer=1024,
                stream_callback=callback
            )
            self.index += 1
            # self.ffmpeg_process = subprocess.Popen(
            #     ['ffmpeg', '-y', '-f', 's16le', '-ar', '16000', '-ac', '1', '-i', '-',
            #      '-c:a', 'libmp3lame', '-q:a', '2', '-update', '1', self.save_audio+"_{}.mp3".format(self.index)],
            #     stdin=subprocess.PIPE
            # )
            stream.start_stream()

            while stream.is_active():
                if time.time() - start_time > 1200:
                    self.logger.info("Recording for 20min, stop listening")
                    self.is_listening = False
                if self.is_listening == False:
                    break


        except Exception as e:
            self.logger.error(e)
            self.logger.error("Recording Error")

        finally:
            if audio_data and len(audio_data) > 1024:
                queue.put(numpy.array(audio_data))
                audio_data.clear()
            stream.stop_stream()
            stream.close()
            # self.pa.terminate()
            # self.ffmpeg_process.stdin.close()
            # self.ffmpeg_process.wait()

    def stop_listening(self):
        self.is_listening = False

    async def start_listening(self):
        self.is_listening = True
        self.logger.info("Start listening")

        Recording_thread = threading.Thread(target=self.Recording, args=(self.queue,))
        STT_thread = threading.Thread(target=self.SpeechtoText, args=(self.queue,))

        Recording_thread.start()
        STT_thread.start()

        Recording_thread.join()
        self.queue.put("stop")
        self.is_listening = False
        STT_thread.join()
        self.logger.info("Stop listening")

        texts = ''.join(self.ASR_Text).strip()
        self.ASR_Text.clear()
        return texts



