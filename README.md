<h1 align="center">Focus Agent</h1>

<p align="center">
  <a href="https://github.com/AriaXR/FocusAgent/blob/main/LICENSE">
        <img src="https://img.shields.io/github/license/AriaXR/FocusAgent.svg"
             alt="GitHub license">
  </a>

  <a href="https://arxiv.org/abs/2409.01907">
        <img src="http://img.shields.io/badge/Arxiv-2409.01907-B31B1B.svg"
             alt="ArXiv paper">
  </a>

  <a href="https://aria.cs.kuleuven.be">
  	<img src="https://img.shields.io/badge/Lab-Homepage-blue"
   	     alt="Lab Homepage">
  </a>

<table style="width:100%; border-collapse: collapse; border: 0;">
<tr style="border: none;">
<td style="width:60%; border: 0; vertical-align: middle; font-size: 14px;">

<p style="font-size: 16px;">
	This is the official implementation of the paper <strong><em>“Focus Agent: LLM-Powered Virtual Focus Group”</em></strong> for IVA24. Focus Agent is a voice-based system designed to simulate focus group discussions or to guide human participants in a focus group as a moderator. This repo includes two parts of codes:  

 - ⚡️ Web Demo for Focus Group Simulation  
 - 🗣️ Online Focus Group System with AI Moderator

</td>
<td style="width:40%; border: 0; text-align: right; vertical-align: middle;">

<img src="image/FocusGroupSimulation.png" alt="Focus Agent" style="max-width:80%;">

</td>
</tr>
</table>

# Simulation
First, step into the directory  

    cd simulation  
    mkdir plan
    mkdir transcripts
    
  ## Environment
  Windows 11  
  python > 3.10  
  Install python environment  

    pip install -r env.txt       
  

  ## Change the API Keys before running
  find the codes in app.py and change the parameters in   
  
      simulator = ChatProcessor(meeting_info, api_key='Your OpenAI API Key', organization="Your OpenAI Organization", moderator_name = 'Moderator Name', model_name = "Model Name")  

      
  change the information according to [OpenAI Webset](https://platform.openai.com/docs/concepts)


  ## run WebDemo:  
  2. `python app.py`

 ## Example
<img src="image/AISimulation.png" alt="Simulation" width="500">
 


# Moderator
Step into the dir:  

    cd AgentinMozilla
  
 ## Dependency
 python > 3.10  
 Ram > 16GB  
 GPU RAM > 8GB (For Speech to Text) 
 Virtual audio cable like [VB-Audio Virtual Cable](https://vb-audio.com/Cable/#DownloadCable)
 Install python environments

   pip install -r env.txt

## Speech to Text

<img src="image/S2T.png" alt="Simulation" width="500">

This S2T system is based on [Whsper-X](https://github.com/m-bain/whisperX/blob/main).

## Change the API Keys before running

Find the codes in sender.py and change the parameters from  

    app = AIAvatar(
    openai_api_key='Your OpenAI API key',
    google_api_key='You Google API key',
    topic = 'Your topic',
    purpose="Your Purpose",
    total_time = 60, # <- Set to adjust total discussion time
    participants = ["A", "B"], #participants names
    volume_threshold=200,    # <- Set to adjust microphone sensitivity
    lang_TTS = 'en-US', # <- Set to adjust TTS language
    input_device= 'cable-B',
    output_device= 'cable-A',
    save_audio_path='Your save audio path',
    orgnization_key='org-WYPMYMdADrrxWFlo7jHFLftZ',
    )


 ## run 
 ```
python sender.py
 ```

 ## Example
 
<img src="image/FocusAgent.png" alt="Simulation" width="500">
	
This original work is based on Mozilla Hub, which ended its support this year. It can easily be transferred to any other online meeting platform by monitoring the microphone and headphones through the system and changing the input. What you need to do is to set up the virtual audio cable to make them monitor the meeting correctly.

 # Contact and Support 

 Contact taiyu.zhang@kuleuven.be for queries.


 



