import logging
from aiavatar import AIAvatar, WakewordListener, WakewordInput

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import asyncio
from threading import Thread





# Configure root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
log_format = logging.Formatter("[%(levelname)s] %(asctime)s : %(message)s")
streamHandler = logging.StreamHandler()
streamHandler.setFormatter(log_format)
logger.addHandler(streamHandler)



## Control Avatar
driver = None
prefs = {
        "profile.default_content_setting_values.notifications": 1,
        "profile.default_content_setting_values.media_stream_mic": 1,
        "profile.default_content_setting_values.media_stream_camera": 1
        }  ### allow microphone and camera access

options = Options()
options.add_experimental_option("prefs", prefs)
driver = webdriver.Edge(options=options)
driver.implicitly_wait(10)
driver.get('Your Mozilla hubs link')


driver.find_element(By.CLASS_NAME, 'Button__accent4__rpZEP').click() #click joint room
driver.find_element(By.CLASS_NAME, 'Button__accept__Vxz39').click()  #click accept


driver.find_element(By.CLASS_NAME,'MicSetupModal__selection-input__mrlP_').click() #click mic
# driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[3]/div[1]/div[2]/div/div/div[1]/div[3]/div/div/button').click() #click mic
driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[3]/div[1]/div[2]/div/div/div[1]/div[3]/div/div/ul/li[contains(text(), "CABLE-A")]').click() #select mic

driver.find_element(By.XPATH,'/html/body/div[2]/div/div/div[3]/div[1]/div[2]/div/div/div[2]/div[3]/div/div/button').click() #click speaker
driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[3]/div[1]/div[2]/div/div/div[2]/div[3]/div/div/ul/li[contains(text(), "CABLE-B")]').click() #select speaker

driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[3]/div[1]/div[2]/div/button').click() # click next
driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[3]/div[3]/div[1]/div/div[2]/button[2]').click() # click skip tour

driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[2]/div[2]/section[3]/div[1]/button').click()  # click chat
exit1 = driver.find_element(By.XPATH, '/html/body/div[2]/div/div/div[1]/div/div[1]/div[1]/button')

ActionChains(driver).move_to_element(exit1).click().perform() #exit chat

# move to the table
ActionChains(driver).key_down('w').pause(2.1).key_up('w').perform() # move forward
ActionChains(driver).move_by_offset(100,400).click_and_hold().pause(1).move_by_offset(-300,0).release().perform()
ActionChains(driver).key_down('w').pause(2.2).key_up('w').perform() # move forward




# Create AIAvatar
app = AIAvatar(
    openai_api_key='Your OpenAI API key',
    google_api_key='Your Google API key',
    topic = 'Your topic',
    purpose="Your Purpose",
    total_time = 60, # <- Set to adjust total discussion time
    participants = ["A", "B"], #participants names
    volume_threshold=200,    # <- Set to adjust microphone sensitivity
    lang_TTS = 'en-US', # <- Set to adjust TTS language
    input_device= 'cable-B',
    output_device= 'cable-A',
    driver = driver,
    save_audio_path='Your save audio path',
    orgnization_key='Your orgazation',
)

# Create WakewordListener
wakewords = ["Start", "start"]


wakeword_input = WakewordInput(wakewords=wakewords)

th = Thread(target=asyncio.run, args=(wakeword_input.start(app),), daemon=True)
th.start()

th.join()

print('finished')









