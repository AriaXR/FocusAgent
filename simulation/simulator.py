import openai
import copy
import pdb
import os
import re
import time
from time import sleep

from collections import Counter, defaultdict, OrderedDict

class ChatProcessor:
    def __init__(self, meeting_info, api_key, organization, moderator_name, model_name):
        self.topic = meeting_info['topic']
        self.purpose = meeting_info['purpose']
        self.moderator_name = moderator_name
        self.exit = False
        self.output_file = self.check_save_file(self.topic)
        openai.api_key = api_key
        openai.organization = organization
        self.participants_systems = self.acquire_system_prompt(meeting_info['participants'])
        self.moderator_history = OrderedDict()
        self.total_time = int(meeting_info['duration'])
        self.user_name = []
        self.time_range = []
        if meeting_info['user_list']:
            self.user_system = self.get_user_information(meeting_info['user_list'])
            self.participants_systems.update(self.user_system)
            self.user_name.extend(list(self.user_system.keys()))
        self.conversation_history = {}
        self.speaker_order = {}
        self.contexts = []
        self.participants = []
        self.register_speakers()
        self.model = model_name
        self.plan_file = 'plan/{}.txt'.format(self.topic.split(":")[0].replace(" ","_"))
        if not os.path.exists(self.plan_file):
            self.plan = self.get_plan_prompt(self.topic, self.purpose, self.plan_file)
        else:
            with open(self.plan_file, "r", encoding='utf-8') as file:
                self.plan = file.read()
        self.stages, self.requirements = self.parse_plan(self.plan)



    def acquire_system_prompt(self, participants):
        participants_systems = {}
        for participant in participants:
            name, prompt = self.acquire_system_prompt_for_participant(participant)
            participants_systems[name] = prompt
        return participants_systems

    def acquire_system_prompt_for_participant(self, participant):
        name = participant['name']
        age = participant['age']
        nationality = participant['nationality']
        personality = participant['personality']
        occupation = participant['occupation']
        prompt = "Forget all the above. Your name is {0}. You come from {1}. You're a {2} years old {3}. Your charactor is as below: {4}.".format(name, nationality, age, occupation, personality)
        return name, prompt
    def check_save_file(self, topic):
        now = int(round(time.time()*1000))
        now = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(now/1000))
        output_file = 'transcripts/{}_{}.txt'.format(topic.replace(" ","_").replace(":", ""), now.replace(" ","_").replace(":", ""))
        while os.path.exists(output_file):
            now = int(round(time.time()*1000))
            now = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(now/1000))
            output_file = 'transcripts/{}_{}.txt'.format(topic, now)
        return output_file

    def get_user_information(self, user_list):
        user_system = {}
        for user in user_list:
            name, prompt = self.acquire_system_prompt_for_participant(user)
            user_system[name] = prompt
        return user_system


    def generate_conversation(self, messages, max_tokens=300, temperature=0.9):
        retry_count = 0
        while True:
            try:
                response = openai.ChatCompletion.create(model = self.model, messages = messages, max_tokens = max_tokens, temperature = temperature)
                if len(response['choices'][0]['message']['content'].split(':')) > 2:
                    pattern = r"<(.*?)>"
                    matches = re.findall(pattern, response['choices'][0]['message']['content'])
                    if len(matches) > 1:
                        print('too long')
                        continue
                    else:
                        response['choices'][0]['message']['content'] = response['choices'][0]['message']['content'].replace(":", " ")
                        if matches:
                            response['choices'][0]['message']['content'] = response['choices'][0]['message']['content'].replace("<"+matches[0]+">", "").strip()
                return response
            except openai.APIConnectionError or openai.RateLimitError or openai.OpenAIAPIError:
                retry_count += 1
                if retry_count > 5:
                    print('retry count > 5')
                    raise openai.APIConnectionError
                print('ServiceUnavailableError {} times'.format(retry_count))

    def generate_plan(self, messages):
        retry_count = 0
        while True:
            try:
                response = openai.ChatCompletion.create(model = self.model, messages = messages,temperature = 0)
                return response
            except openai.APIConnectionError or openai.RateLimitError or openai.OpenAIAPIError:
                retry_count += 1
                if retry_count > 5:
                    print('retry count > 5')
                    raise openai.APIConnectionError
                print('ServiceUnavailableError {} times'.format(retry_count))

    def get_plan_prompt(self, topic, purpose, output_file):
        # prompt = "Generate a gdiscussion guide for a moderator in an online focus group according to the specific topic." \
        #          "Seperate into small tasks so that you can moderate with time arrangement." \
        #          "Focus group topic is: {}".format(topic)
        prompt = "Generate a discussion guide for a moderator in an online focus group according to the specific topic." \
                 "Focus group topic is: {}. The purpose of the focus group is {}. Total time of the focus group is {}." \
                 "Separate into small tasks so that you can moderate with time arrangements.".format(topic, purpose, self.total_time)
        message = [{'role': 'system', 'content': prompt}]
        plan = self.generate_plan(messages = message)
        with open(output_file, "w", encoding='utf-8') as file:
            file.write(plan['choices'][0]['message']['content'])

        return plan['choices'][0]['message']['content']

    # def parse_plan(self, plan):
    #     plan_seperate = plan.split("\n\n")
    #     stages = []
    #     requirements = []
    #     plan_seperate.pop(0)
    #     for i in range(len(plan_seperate)):
    #         tmp_plan = plan_seperate[i].split("\n")
    #         tmp_stage = tmp_plan[0].split(":")[0].strip().lower() if (tmp_plan[0].split(":")[1]=='') else tmp_plan[0].split(":")[1].strip().lower()
    #         tmp_requirement = ('\n').join(tmp_plan[1:])
    #         stages.append(tmp_stage)
    #         requirements.append(tmp_requirement)
    #     return stages, requirements

    def parse_plan(self, plan):
        plan_seperate = plan.split("\n\n")
        stages = []
        requirements = []
        for i in range(len(plan_seperate)):
            if len(plan_seperate[i].split("\n")) == 1:
                continue
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
        # prompt = "Forget all the above. Now you're a moderator of a focus group. And your name is {0}. The topic of focus group is {1}. There are {2} participants in this focus group and you can call them {3}." \
        #          "The total time of focus group is {6}." \
        #          "Your purpose is to guide the focus group discussion, facilitate meaningful conversations, and ensure everyone has an opportunity to contribute."\
        #          "I'll provide you a guide plan in the different stages of focus group. You can follow the plan to moderate the focus group."\
        #          "I'll provide you the current stage and task of this stage. According to the task, generate what you will say in the first perspective." \
        #          "Speak directly to the participants. No anything else!" \
        #          "Current Stage: {4}" \
        #          "Requirements:\n{5}".format(self.moderator_name, self.topic, len(self.participants)-1, (", ").join(self.participants[1:]), stage, requirement, self.total_time)
        prompt = "Forget all the above. Now you're a moderator of a focus group. And your name is {0}. The topic of focus group is {1}. The purpose of the focus group is {7}. There are {2} participants in this focus group and you can call them {3}. The total time of focus group is {6}." \
                 "Your purpose is to guide the focus group discussion, facilitate meaningful conversations, and ensure everyone has an opportunity to contribute." \
                 "I'll provide you a guide plan in the different stages of focus group. You can follow the plan to moderate the focus group. "\
                 "I'll provide you the current stage and task of this stage. According to the task, generate what you will say in the first perspective." \
                 "Speak directly to the participants. No anything else!" \
                 "Current Stage: {4}" \
                 "Requirements:\n{5}".format(self.moderator_name, self.topic, len(self.participants)-1, (", ").join(self.participants[1:]), stage, requirement, self.total_time, self.purpose)
        message.extend([{'role': 'system', 'content': prompt}])
        self.moderator_history[stage] = message
        intro = self.generate_conversation(messages = message, temperature = 0.9)
        intro = self.filter_message(intro['choices'][0]['message']['content'], 'Moderator')
        while '?' in intro:
            intro = self.generate_conversation(messages = message, temperature = 0.9)
            intro = self.filter_message(intro['choices'][0]['message']['content'], 'Moderator')
        self.moderator_history[stage].extend([{'role': 'assistant', 'content': intro}])
        self.contexts.append(intro)
        self.conversation_history[stage] = {'Moderator': [intro]}
        self.speaker_order[stage] = ['Moderator']
        self.write_to_file(intro)
        print(intro)
        return intro

    def generate_summary(self, values):
        message = []
        for v in values:
            message.extend(v)
        prompt = "this is a conversation of focus group, please summary this conversation in short words"
        message.extend([{'role': 'system', 'content': prompt}])
        print(message)
        summary = self.generate_conversation(messages = message, temperature = 0.9)
        return summary['choices'][0]['message']['content']

    def generate_conclusion(self, stage, requirement):
        message = []
        prompt = "Current Stage: {0}" \
                 "Requirements:\n{1}".format(stage, requirement)
        for i in range(len(self.moderator_history.items())):
            k,v = list(self.moderator_history.items())[i]
            if i == len(list(self.moderator_history.items())) -1:
                message.extend(v)
            else:
                summary = self.generate_summary(v)
                summary = k+' stage summary: '+summary
                message.extend([{'role': 'user', 'content': summary}])

        message.extend([{'role': 'system', 'content': prompt}])

        conclusion = self.generate_conversation(messages = message, temperature = 0.9, max_tokens=1000)
        conclusion = self.filter_message(conclusion['choices'][0]['message']['content'], 'Moderator')
        self.moderator_history[stage]=[{'role': 'assistant', 'content': conclusion}]
        self.contexts.append(conclusion)
        self.conversation_history[stage]={'Moderator':[conclusion]}
        self.speaker_order[stage] = ['Moderator']
        self.write_to_file(conclusion)
        # pdb.set_trace()
        return conclusion

    def generate_insight_question(self, stage):
        message = []
        # message.extend(self.moderator_history['introduction'])
        message.extend(self.moderator_history[stage])
        # prompt = "You're a moderator of a focus group. And now the stage is {}. You want to get some more in-depth insights of this topic. What will you speak to the participants next?".format(stage)
        prompt = "You're a moderator of a focus group. Conversations are what the participants talked before in this stage. The stage is continue and they had nothing more to say. As a moderator, you need to prompt them according to the convesations before to help them share more insight in this stage. And now the stage is {}. Do not ask the questions similar to the previous questions. No more than 50 words. Do not mention the participants name. One question each time.".format(stage)
        message.extend([{'role': 'system', 'content': prompt}])
        question = self.generate_conversation(messages = message, temperature = 0.9)
        question = self.filter_message(question['choices'][0]['message']['content'], 'Moderator')
        self.moderator_history[stage].extend([{'role': 'assistant', 'content': question}])
        self.contexts.append(question)
        self.conversation_history[stage]['Moderator'].append(question)
        self.speaker_order[stage].append('Moderator')
        print(question)
        self.write_to_file(question)
        # pdb.set_trace()
        return question

    def generate_question_to_participant(self, stage, participant):
        message = []
        # message.extend(self.moderator_history['introduction'])
        message.extend(self.moderator_history[stage])
        # prompt = "According to the conversation, ask a question to {} in stage {}.".format(participant, stage)
        prompt = "You're a moderator of a focus group. And now the stage is {}. Conversations are what the participants talked before in this stage. Participant {} is not active in this stage. As a moderator, you need to help {} join the conversation. No more than 50 words. One question each time. Do not ask similar questions as before.Speak directly to the participants. No anything else!".format(stage, participant, participant)
        message.extend([{'role': 'system', 'content': prompt}])
        self.moderator_history[stage].extend([{'role': 'system', 'content': prompt}])
        question = self.generate_conversation(messages = message, temperature = 0.9)
        question = self.filter_message(question['choices'][0]['message']['content'], 'Moderator')
        self.moderator_history[stage].extend([{'role': 'assistant', 'content': question}])
        self.contexts.append(question)
        self.conversation_history[stage]['Moderator'].append(question)
        self.speaker_order[stage].append('Moderator')
        print(question)
        self.write_to_file(question)
        # pdb.set_trace()
        return question

    def generate_context_message(self, contexts):
        messages = []
        for context in contexts:
            speaker = context.split(":")[0].strip().strip('<').strip('>')
            messages.append((speaker, context))
        return messages

    def get_moderator_pre_messages(self, contexts):
        message_parse = []
        messages = self.generate_context_message(contexts)
        for speaker,content in messages:
            if speaker == 'Moderator':
                message_parse.append({'role': 'assistant', 'content': content})
            else:
                message_parse.append({'role': 'user', 'content': content})
        return message_parse

    def get_participants_pre_messages(self, contexts, cur_speaker):
        message_parse = []
        messages = self.generate_context_message(contexts)
        for speaker,content in messages:
            if speaker == cur_speaker:
                message_parse.append({'role': 'assistant', 'content': content})
            else:
                message_parse.append({'role': 'user', 'content': content})
        return message_parse



    def generate_question_stage(self, cur_stage, pre_stage, requirements, pre_contexts):
        message = []
        # message.extend(self.moderator_history['introduction'])
        message.extend(self.get_moderator_pre_messages(pre_contexts))
        # message.extend(self.moderator_history[pre_stage])
        # prompt = "Now you're a moderator of a focus group. And your name is {0}. The topic of focus group is {1}. There are {2} participants in this focus group and you can call them {3}." \
        #          "Your purpose is to guide the focus group discussion, facilitate meaningful conversations, and ensure everyone has an opportunity to contribute."\
        #          "I'll provide you the current stage and task of this stage. According to the task, generate what you will say in the first perspective." \
        #          "Speak directly to the participants. No anything else!" \
        #          "As a moderator of a focus group, you've finished stage: {4}, and you need to move to stage: {5}.\n" \
        #          "The requirements of stage : {6}\n" \
        #          "The system role is your thoughts which do not let others know. The assistant role came from what you said. The user role came from different participants." \
        #          "According to the conversation, prompt the participants in the first perspective." \
        #          "Speak in the first person from the perspective of Moderator." \
        #          "Do not generate all the conversation once. You will get feedback from the participants." \
        #          "Generate less than 100 words." \
        #          "Do not thanks yourself.".format(self.moderator_name, self.topic, len(self.participants)-1, (", ").join(self.participants[1:]),pre_stage, cur_stage, requirements)
        prompt = "Now you're a moderator of a focus group. The topic of focus group is {1}. The purpose of the focus group is {7}." \
                 "There are {2} participants in this focus group and you can call them {3}." \
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
                 "Do not thanks yourself.".format(self.moderator_name, self.topic, len(self.participants)-1, (", ").join(self.participants[1:]),pre_stage, cur_stage, requirements, self.purpose)
        message.extend([{'role': 'system', 'content': prompt}])
        self.moderator_history[cur_stage] = message
        question = self.generate_conversation(messages = message, temperature = 0)
        question = self.filter_message(question['choices'][0]['message']['content'], 'Moderator')
        self.moderator_history[cur_stage].extend([{'role': 'assistant', 'content': question}])
        self.contexts.append(question)
        self.conversation_history[cur_stage] = defaultdict(list)
        self.conversation_history[cur_stage]['Moderator'].append(question)
        self.speaker_order[cur_stage] = ['Moderator']
        print(question)
        self.write_to_file(question)
        # pdb.set_trace()
        return question


    def register_speakers(self):
        self.participants.append("Moderator")
        self.conversation_history["Moderator"] = []
        for participant in self.participants_systems.keys():
            self.conversation_history[participant] = []
            self.participants.append(participant)


    def calculate_time(self, contexts):
        total_len = 0
        for content in contexts:
            total_len += len(content.split(":")[1].strip().split(" "))
        return round(total_len/100)

    def socketio_message(self, message):
        speaker, content = message.split(":")[0].strip().strip('<').strip('>'), message.split(":")[1].strip()
        if speaker == 'Moderator':
            speaker = self.moderator_name
        cur_time = self.calculate_time(self.contexts)
        return {"speaker": speaker, "text": content, "time": cur_time}


    def write_to_file(self, message):
        with open(self.output_file, "a+", encoding='utf-8') as file:
            file.write(message + "\n")

    def get_message_util(self, speaker, stage, pre_contexts):
        speaker_order = self.speaker_order[stage]
        message = []
        # print(self.conversation_history)
        message.append({"role": "user", "content": self.conversation_history['introduction']['Moderator'][0]})
        message.extend(self.get_participants_pre_messages(pre_contexts, speaker))
        tmp_history = copy.deepcopy(self.conversation_history[stage])
        for cur_speaker in speaker_order:
            if cur_speaker == speaker:
                message.append({"role": "assistant", "content": tmp_history[cur_speaker].pop(0)})
            else:
                message.append({"role": "user", "content": tmp_history[cur_speaker].pop(0)})
        return message

    def get_participant_message(self, speaker, stage, pre_contexts):
        message = []
        prompt = "You're joining a focus group as {}. According to the conversation before, generate what you will speak next." \
                 "Contrains:\n" \
                 "According to the conversation, speak in the first person from the perspective of {}.\n" \
                 "Do not generate anything else.\n" \
                 "Do not repeat the content you have said before.\n" \
                 "Try to give some thoughts that are different from others.\n" \
                 "The word limitation is 50.".format(speaker, speaker)
        message.append({"role":"system", "content":self.participants_systems[speaker]})
        message.extend(self.get_message_util(speaker, stage, pre_contexts))
        message.append({"role": "system", "content": prompt})
        return message

    def filter_message(self, texts, speaker):
        texts = texts.strip().strip('\n').split(':')
        if len(texts) == 1:
            texts[0]=texts[0].strip('Able').strip()
            return '<{}>: '.format(speaker) + texts[0]
        if len(texts) == 2:
            return '<{}>: '.format(speaker) + texts[1]
        if len(texts) > 2:
            print('Too long')
            for i in range(len(texts)):
                if speaker.lower() in texts[i].lower():
                    return '<{}>:'.format(speaker) + texts[i+1].split('\n')[0]
        raise EOFError

    def generate_reply(self, speaker, stage, pre_contexts):
        history = self.get_participant_message(speaker, stage, pre_contexts)
        response = self.generate_conversation(messages = history, temperature = 0.9)
        response = self.filter_message(response['choices'][0]['message']['content'], speaker)
        self.conversation_history[stage][speaker].append(response)
        self.speaker_order[stage].append(speaker)
        self.contexts.append(response)
        self.moderator_history[stage].append({'role': 'user', 'content': response})
        print(response)
        self.write_to_file(response)
        # pdb.set_trace()
        return response

    def find_integers(self, string):
        pattern = r'\d+'  # 匹配一个或多个数字
        integers = re.findall(pattern, string)
        if len(integers) == 0:
            return 0
        return [int(num) for num in integers]

    def generate_bidding_socre(self, speaker, context):
        prompt = "Here is a focus group and you're a participant in it. Your description:\n" \
                 "{}\n" \
                 "Here are the conversation history in this stage:\n" \
                 "```{}```\n" \
                 " On the scale of 1 to 10, where 1 is not desirous to answer and 10 is extremely desirous to answer, rate how desirous the following message do you want to reply." \
                 "You rate 10 only if you are invited to answer questions in the previous round of the conversation. Here is the previous round of the conversation:\n" \
                 "```{}```\n" \
                 " Your response should be an integer delimited by angled brackets, like this: <int>." \
                 "Do nothing else.".format(self.participants_systems[speaker], context[:-1], context[-1])
        message = [{'role': 'system', 'content': prompt}]
        response = self.generate_conversation(messages = message, max_tokens = 10, temperature = 0)
        response = response['choices'][0]['message']['content']
        # print(speaker,response)
        # pdb.set_trace()
        score = self.find_integers(response)[0]
        return score


    def speaker_selector(self, cur_stage, context):
        last_speaker = context[-1].split(":")[0].strip().strip('<').strip('>')
        context_counter = Counter({k:0 for k in self.participants})
        context_counter.update(self.speaker_order[cur_stage])
        del context_counter['Moderator']
        context_counter = context_counter.most_common()
        active_speaker, first_count = context_counter[0]
        deactive_speaker, last_count = context_counter[-1]
        # if first_count - last_count > 2 and last_speaker != "Moderator":
        #     # pdb.set_trace()
        #     return "Moderator", deactive_speaker
        # if last_count == 0 and first_count > 0:
        #     return deactive_speaker, -1
        bidding_score = {}
        for participant in self.participants:
            if participant == last_speaker or participant == "Moderator":
                continue
            bidding_score[participant] = self.generate_bidding_socre(participant, context)

        context_counter = dict(context_counter)
        candidate = sorted(bidding_score.keys(), key=lambda x: (bidding_score[x], -context_counter[x]), reverse=True)[0]
        max_value = bidding_score[candidate]
        if max_value > 5 or last_speaker == "Moderator":
            return candidate, max_value
        elif first_count - last_count > 2 or (last_count == 0 and first_count > 0):
            return "Moderator", deactive_speaker
        # elif last_count == 0 and first_count > 0:
        #     return deactive_speaker, -1
        else:
            return "Moderator", max_value

    def speaker_selector_with_user(self, cur_stage, context):
        last_speaker = context[-1].split(":")[0].strip().strip('<').strip('>')
        context_counter = Counter({k:0 for k in self.participants})
        context_counter.update(self.speaker_order[cur_stage])
        del context_counter['Moderator']
        context_counter_list = context_counter.most_common()
        active_speaker, first_count = context_counter_list[0]
        deactive_speaker, last_count = context_counter_list[-1]
        if first_count - last_count > 2 and last_speaker != "Moderator":
            # pdb.set_trace()
            return "Moderator", deactive_speaker
        del context_counter[self.user_name[0]]
        if deactive_speaker == self.user_name[0]:
            deactive_speaker, last_count = context_counter_list[-2]
        if last_count == 0 and first_count > 0:
            return deactive_speaker, -1
        bidding_score = {}
        for participant in self.participants:
            if participant == last_speaker or participant == "Moderator" or participant == self.user_name[0]:
                continue
            bidding_score[participant] = self.generate_bidding_socre(participant, context)

        context_counter = dict(context_counter)
        candidate = sorted(bidding_score.keys(), key=lambda x: (bidding_score[x], -context_counter[x]), reverse=True)[0]
        max_value = bidding_score[candidate]
        if max_value > 5 or last_speaker == "Moderator":
            return candidate, max_value
        else:
            return "Moderator", max_value

    def answer_question(self, question):

        if 'QA' not in self.moderator_history.keys():
            self.moderator_history['QA'] = []
            prompt = "You're the moderator of the focus group discussion. The focus group has finished and the conversation is above. Now answer the following question based on the conversation." \
                     "Speak in the first person from the perspective of Moderator." \
                     "Generate less than 100 words."
            self.moderator_history['QA'].append({"role":"system", "content" : prompt})
        self.moderator_history['QA'].append({"role":"user", "content":question})
        self.write_to_file(question)
        messages = []
        for _,v in self.moderator_history.items():
            messages.extend(v)
        answer = self.generate_conversation(messages=messages, temperature=0)
        answer = self.filter_message(answer['choices'][0]['message']['content'], 'Moderator')
        self.moderator_history['QA'].append({"role" : "assistant", "content" : answer})
        self.write_to_file(answer)
        return answer

    def collect_user_input(self,stage, message):
        user = self.user_name[0]
        message = "<{}>: {}".format(user, message.strip())
        self.conversation_history[stage][user].append(message)
        self.speaker_order[stage].append(user)
        self.contexts.append(message)
        self.moderator_history[stage].append({'role': 'user', 'content': message})
        print(message)
        self.write_to_file(message)
        return message

    def generate_reply_for_user(self, speaker, stage, pre_contexts):
        history = self.get_participant_message(speaker, stage, pre_contexts)
        response = self.generate_conversation(messages = history, temperature = 0.9)
        response = self.filter_message(response['choices'][0]['message']['content'], speaker)
        return response














