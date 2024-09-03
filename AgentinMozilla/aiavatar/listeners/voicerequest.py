from . import SpeechListenerBase, SpeechListenerAdvanced
import threading


class VoiceRequestListener(SpeechListenerAdvanced):
    def __init__(self, participants, volume_threshold: int=200,  min_duration: float = 5,
                 max_duration: float = 60.0, rate: int = 16000, device_index: int = -1, cuda_device: str = 'cuda',
                 save_audio: str="", compute_type:str = "float16", driver = None, ASR_SilencePatience: float = 0.5):
        super().__init__(participants, volume_threshold, min_duration, max_duration, rate, device_index, cuda_device, save_audio, compute_type, driver, ASR_SilencePatience)

    async def get_request(self):
        self.is_listening = True
        self.logger.info("Start listening")

        Recording_thread = threading.Thread(target=self.Recording, args=(self.queue,))
        STT_thread = threading.Thread(target=self.SpeechtoText, args=(self.queue,))

        Recording_thread.start()
        STT_thread.start()
        try:
            print(input("Press Enter to stop recording.\n"))
            self.is_listening = False

        except KeyboardInterrupt:
            self.is_listening = False
        Recording_thread.join()
        self.queue.put("stop")
        STT_thread.join()
        self.logger.info("Stop listening")

        texts = ''.join(self.ASR_Text).strip()
        self.ASR_Text.clear()
        return texts