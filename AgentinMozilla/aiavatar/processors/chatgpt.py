from logging import getLogger, NullHandler
import traceback
from typing import Iterator
from openai import ChatCompletion
from . import ChatProcessor
import openai

from transformers import AutoModel, AutoTokenizer
import copy
import pdb
import os
import re
import time

from collections import Counter, defaultdict

class GPTProcessor(ChatProcessor):
    def __init__(self, output_file, api_key, organization, topic, purpose, plan_file, moderator_name, model_name, total_time, participants):
        self.logger = getLogger(__name__)
        self.logger.addHandler(NullHandler())

        self.output_file = output_file
        openai.api_key = api_key
        openai.organization = organization
        self.moderator_history = []
        self.total_time = total_time
        self.moderator_name = moderator_name
        self.participants = participants
        self.speaker_order = defaultdict(list)
        self.topic = topic
        self.purpose = purpose
        self.time_range = []
        self.model = model_name
        self.plan_file = plan_file
        self.start_time = time.time()
        self.client = openai.OpenAI(api_key=api_key)
        if not os.path.exists(self.plan_file):
            self.plan = self.get_plan_prompt(self.topic, self.purpose, self.plan_file)
        else:
            with open(self.plan_file, "r", encoding='utf-8') as file:
                self.plan = file.read()
        self.stages, self.requirements = self.parse_plan(self.plan)
        self.norm_stage_time = self.total_time / (len(self.stages)-1)
        self.stage_time_limitation = -1
        self.current_stage = self.stages.pop(0)
        self.current_requirement = self.requirements.pop(0)
        self.intro = self.generate_intro(self.current_stage, self.current_requirement)
        # self.intro = 'hello'
        self.stage_start_time = time.time()

    def generate_conversation(self, messages, max_tokens=300, temperature=0.9):
        retry_count = 0
        while True:
            try:
                response = self.client.chat.completions.create(model = self.model, messages = messages, max_tokens = max_tokens, temperature = temperature)
                if len(response.choices[0].message.content.split(':')) > 2:
                    print('too long')
                    # pdb.set_trace()
                    continue
                return response
            except openai.APIConnectionError or openai.RateLimitError or openai.OpenAIAPIError:
                retry_count += 1
                if retry_count > 5:
                    print('retry count > 5')
                    raise openai.APIConnectionError
                print('ServiceUnavailableError {} times'.format(retry_count))

    def generate_plan(self, messages):
        response = self.client.chat.completions.create(model = self.model, messages = messages, temperature = 0)
        return response

    def get_plan_prompt(self, topic, purpose, output_file):
        prompt = "Generate a gdiscussion guide for a moderator in an online focus group according to the specific topic with time arrangement." \
                 "Seperate into small tasks so that you can moderate with time arrangement." \
                 "Focus group topic is: {}. Purpose of the focus group is {}.".format(topic, purpose)
        message = [{'role': 'system', 'content': prompt}]
        plan = self.generate_plan(messages = message)
        with open(output_file, "w", encoding='utf-8') as file:
            file.write(plan.choices[0].message.content)

        return plan.choices[0].message.content

    def parse_plan(self, plan):
        plan_seperate = plan.split("\n\n")
        stages = []
        requirements = []
        plan_seperate.pop(0)
        for i in range(len(plan_seperate)):
            tmp_plan = plan_seperate[i].split("\n")
            if ':' in tmp_plan[0]:
                tmp_stage = tmp_plan[0].split(":")[0].strip().lower() if (tmp_plan[0].split(":")[1]=='') else tmp_plan[0].split(":")[1].strip().lower()
            else:
                tmp_stage = tmp_plan[0].strip().lower()
            time_arr = re.findall(r'\((.*?)\)', tmp_stage)
            tmp_stage = re.sub(r'\(.*?\)', '', tmp_stage)
            for arr in time_arr:
                if "min" in arr:
                    time_tmp = re.findall(r'-?\b\d+\b', arr)
                    self.time_range.append(int(time_tmp[0]))
            tmp_requirement = ('\n').join(tmp_plan[1:])
            stages.append(tmp_stage)
            requirements.append(tmp_requirement)
        return stages, requirements

    def generate_intro(self, stage, requirement):
        message = []
        prompt = "Forget all the above. Now you're a moderator of a focus group. And your name is {0}. The topic of focus group is {1}. There are {2} participants in this focus group and you can call them {3}." \
                 "Your purpose is to guide the focus group discussion, facilitate meaningful conversations, and ensure everyone has an opportunity to contribute." \
                 "Purpose of this focus group is {7}."\
                 "I'll provide you a guide plan in the different stages of focus group. You can follow the plan to moderate the focus group. Total time of the focus group is {6}"\
                 "I'll provide you the current stage and task of this stage. According to the task, generate what you will say in the first perspective." \
                 "You should Explain the purpose of the focus group and the rules of the focus group to the participants as detailed as possible. " \
                 "Speak directly to the participants. No anything else!" \
                 "Current Stage: {4}" \
                 "Requirements:\n{5}".format(self.moderator_name, self.topic, len(self.participants), (", ").join(self.participants), stage, requirement, self.total_time, self.purpose)
        message.extend([{'role': 'system', 'content': prompt}])
        intro = self.generate_conversation(messages = message, temperature = 0.9)
        intro = self.filter_message(intro.choices[0].message.content, 'Moderator')
        while '?' in intro:
            intro = self.generate_conversation(messages = message, temperature = 0.9)
            intro = self.filter_message(intro.choices[0].message.content, 'Moderator')
        self.moderator_history.extend(message)
        self.moderator_history.extend([{'role': 'assistant', 'content': intro}])
        self.write_to_file(intro)
        return intro


    def generate_insight_question(self, stage, requirement):
        message = []
        message.extend(self.moderator_history)
        prompt = "You're a moderator of a focus group. Conversations are what the participants talked before in this stage. The stage is continue and they had nothing more to say. As a moderator, you need to prompt them according to the convesations before to help them share more insight in this stage. And now the stage is {}, the purpose of this stage is {}. Do not ask the questions similar to the previous questions. No more than 50 words. Do not mention the participants name. One question each time.".format(stage, requirement)
        message.extend([{'role': 'system', 'content': prompt}])
        return message

    def generate_question_to_participant(self, stage, participant, requirement):
        message = []
        message.extend(self.moderator_history)
        prompt = "You're a moderator of a focus group. And now the stage is {}, the purpose of this stage is {}. Conversations are what the participants talked before in this stage. Participant {} is not active in this stage. As a moderator, you need to help {} join the conversation. No more than 50 words. One question each time. Do not ask similar questions as before.Speak directly to the participants. No anything else!".format(stage, requirement, participant, participant)
        message.extend([{'role': 'system', 'content': prompt}])
        return message



    def generate_question_stage(self, cur_stage, pre_stage, requirements):
        message = []
        message.extend(self.moderator_history)
        prompt = "Now you're a moderator of a focus group. And your name is {0}. The topic of focus group is {1}. There are {2} participants in this focus group and you can call them {3}." \
                 "Your purpose is to guide the focus group discussion, facilitate meaningful conversations, and ensure everyone has an opportunity to contribute."\
                 "I'll provide you the current stage and task of this stage. According to the task, generate what you will say in the first perspective." \
                 "Speak directly to the participants. No anything else!" \
                 "As a moderator of a focus group, you've finished stage: {4}, and you need to move to stage: {5}.\n" \
                 "The requirements of the new stage : {6}\n" \
                 "The system role is your thoughts which do not let others know. The assistant role came from what you said. The user role came from different participants." \
                 "According to the conversation, prompt the participants in the first perspective." \
                 "Speak in the first person from the perspective of Moderator." \
                 "Do not generate all the conversation once. You will get feedback from the participants." \
                 "Generate less than 100 words." \
                 "Do not mention the participants name." \
                 "Do not thanks yourself." \
                 "One question each time." \
                 "Do not ask similiar questions.".format(self.moderator_name, self.topic, len(self.participants), (", ").join(self.participants),pre_stage, cur_stage, requirements)
        message.extend([{'role': 'system', 'content': prompt}])
        return message
    def write_to_file(self, message):
        with open(self.output_file, "a+", encoding='utf-8') as file:
            file.write(message + "\n")

    def get_participant_message(self, speaker, stage, pre_contexts):
        message = []
        prompt = "You're joining a focus group as {}. According to the conversation before, generate what you will speak next." \
                 "Contrains:\n" \
                 "According to the conversation, speak in the first person from the perspective of {}.\n" \
                 "Do not generate anything else.\n" \
                 "Do not repeat the content you have said before.\n" \
                 "Generate less than 100 words.".format(speaker, speaker)
        message.append({"role":"system", "content":self.participants_systems[speaker]})
        message.extend(self.get_message_util(speaker, stage, pre_contexts))
        message.append({"role": "system", "content": prompt})
        return message

    def filter_message(self, texts, speaker):
        texts = texts.strip().strip('\n').split(':')
        if len(texts) == 1:
            return "<{}>: ".format(speaker)+texts[0]
        if len(texts) == 2:
            return  "<{}>: ".format(speaker)+texts[1]
        if len(texts) > 2:
            print('Too long')
            for i in range(len(texts)):
                if speaker.lower() in texts[i].lower():
                    return "<{}>: ".format(speaker)+texts[i+1].split('\n')[0]
        raise EOFError



    def speaker_selector(self):
        context_counter = Counter({k:0 for k in self.participants})
        context_counter.update(self.speaker_order[self.current_stage])
        context_counter = context_counter.most_common()
        active_speaker, first_count = context_counter[0]
        deactive_speaker, last_count = context_counter[-1]
        if first_count - last_count > 5 or (first_count > 0 and last_count == 0):
            return deactive_speaker
        return  ''

    async def chat(self, texts):
        for text in texts.split('\n'):
            if text and len(text.split(":")) > 1:
                speaker = text.split(":")[0].strip().strip('<').strip('>')
                self.moderator_history.append({'role': 'user', 'content': text})
                self.write_to_file(text)
                self.logger.info("{}".format(text))
                self.speaker_order[self.current_stage].append(speaker)
        self.logger.info("Length history: {}".format(len(self.moderator_history)))
        cur_time = time.time()
        if self.stages:
            self.logger.info("Current stage: {}, time of this stage: {} mins".format(self.current_stage, int((cur_time - self.stage_start_time)/60)))
            if int((cur_time - self.stage_start_time)/60) > self.stage_time_limitation or (int((cur_time - self.stage_start_time)/60) > self.stage_time_limitation/2 and len(texts) == 0):
                pre_stage = self.current_stage
                self.current_stage = self.stages.pop(0)
                self.stage_start_time = cur_time
                self.stage_time_limitation = self.time_range.pop(0) if self.time_range else self.norm_stage_time
                # self.stage_time_limitation = -1
                self.current_requirement = self.requirements.pop(0)
                prompt = self.generate_question_stage(self.current_stage, pre_stage, self.current_requirement)
                self.logger.info("Generate new stage question, Stage:{}".format(self.current_stage))
                # pdb.set_trace()
                while True:
                    retry_count = 0
                    try:
                        response = openai.ChatCompletion.create(model = self.model, messages = prompt, temperature = 0, stream = True)
                        response_texts = ""
                        for chunk in response:
                            if chunk and 'content' in chunk['choices'][0]['delta']:
                                content = chunk['choices'][0]['delta']['content']
                                response_texts += content
                                yield content


                        break
                    except openai.APIConnectionError or openai.RateLimitError or openai.OpenAIAPIError:
                        retry_count += 1
                        if retry_count > 5:
                            print('retry count > 5')
                            raise openai.APIConnectionError
                        print('ServiceUnavailableError {} times'.format(retry_count))
            else:
                candidate_speaker = self.speaker_selector()
                if candidate_speaker:
                    prompt = self.generate_question_to_participant(candidate_speaker, self.current_stage, self.current_requirement)
                    self.logger.info("Ask {} to speak".format(candidate_speaker))
                    # pdb.set_trace()
                    while True:
                        retry_count = 0
                        try:
                            response = openai.ChatCompletion.create(model=self.model, messages=prompt, temperature=0.9,
                                                                    stream=True)
                            response_texts = ""
                            for chunk in response:
                                if chunk and 'content' in chunk['choices'][0]['delta']:
                                    content = chunk['choices'][0]['delta']['content']
                                    response_texts += content
                                    yield content
                            break
                        except openai.APIConnectionError or openai.RateLimitError or openai.OpenAIAPIError:
                            retry_count += 1
                            if retry_count > 5:
                                print('retry count > 5')
                                raise openai.APIConnectionError
                            print('ServiceUnavailableError {} times'.format(retry_count))
                else:
                    prompt = self.generate_insight_question(self.current_stage, self.current_requirement)
                    self.logger.info("Ask an insight question")
                    # pdb.set_trace()
                    while True:
                        retry_count = 0
                        try:
                            response = ChatCompletion.create(model=self.model, messages=prompt, temperature=0.9,
                                                                    stream=True)
                            response_texts = ""
                            for chunk in response:
                                if chunk and 'content' in chunk['choices'][0]['delta']:
                                    content = chunk['choices'][0]['delta']['content']
                                    response_texts += content
                                    yield content
                            break
                        except openai.APIConnectionError or openai.RateLimitError or openai.OpenAIAPIError:
                            retry_count += 1
                            if retry_count > 5:
                                print('retry count > 5')
                                raise openai.APIConnectionError
                            print('ServiceUnavailableError {} times'.format(retry_count))


class ChatGLMProcessor(ChatProcessor):
    def __init__(self, max_tokens: int=256):
        self.logger = getLogger(__name__)
        self.logger.addHandler(NullHandler())

        self.max_tokens = max_tokens

        self.model = AutoModel.from_pretrained("THUDM/chatglm-6b-int4", trust_remote_code=True).half().cuda().eval()
        self.tokenizer = AutoTokenizer.from_pretrained("THUDM/chatglm-6b-int4", trust_remote_code=True)

        self.histories = []

    def reset_histories(self):
        self.histories.clear()

    def chat(self, text: str):
        try:
            if len(text) > self.max_tokens:
                text = text[:self.max_tokens]

            response, self.histories = self.model.chat(self.tokenizer, query=text, history=self.histories)
            return response
        except Exception as ex:
            self.logger.error(f"Error at chat: {str(ex)}\n{traceback.format_exc()}")
            raise ex
