from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_socketio import SocketIO
import math
import pdb
from simulator import ChatProcessor


app = Flask(__name__)
app.debug = True
meeting_info = {}
socketio = SocketIO(app)
@app.template_filter('sin')
def sin_filter(value):
    return math.sin(math.radians(value))

@app.template_filter('cos')
def cos_filter(value):
    return math.cos(math.radians(value))
def is_valid(name, age, nationality, personality, occupation):
    if int(age) > 60 or int(age) <15:
        return False
    if len(personality.split(' ')) < 10:
        return False
    return True
@app.route('/')
def index():
    global meeting_info
    meeting_info = {}
    print(meeting_info)
    return render_template('index.html')

@app.route('/step1')
def step1():
    return render_template('step1.html')

@app.route('/step1', methods=['POST'])
def create_group():
    global meeting_info
    topic = request.form['topic'].strip()
    purpose = request.form['purpose'].strip()
    participants = request.form['participant_num'].strip()
    duration = request.form['duration'].strip()

    meeting_info['topic'] = topic
    meeting_info['purpose'] = purpose
    meeting_info['participant_num'] = participants
    meeting_info['duration'] = duration
    print(meeting_info)

    return redirect(url_for('step2'))

@app.route('/step2')
def step2():
    return render_template('step2.html')

@app.route('/step2', methods=['POST'])
def model_selection():
    global meeting_info
    meeting_info['user_list'] = []
    meeting_info['participants'] = []
    print(meeting_info)
    if 'participant' in request.form:
        return redirect(url_for('participant'))
    elif 'simulate' in request.form:
        return redirect(url_for('initialize_AI'))
    else:
        return 'Invalid operation'

@app.route('/step2/participant')
def participant():
    return render_template('participant.html')

@app.route('/step2/initialize_AI')
def initialize_AI():
    return render_template('initialize_AI.html', index=1)


@app.route('/step2/participant', methods=['POST'])
def process_participant():
    global meeting_info
    name = request.form['name'].strip()
    age = request.form['age'].strip()
    nationality = request.form['nationality'].strip()
    personality = request.form['personality'].strip()
    occupation = request.form['occupation'].strip()
    if not is_valid(name, age, nationality, personality, occupation):
        error_message = "Invalid input. you should introduce yourself more than 10 words. Please fill in all fields correctly."
        return render_template('participant.html', error_message=error_message)

    user_information = {'name':name, 'age':age, 'nationality':nationality, 'personality':personality, 'occupation':occupation}
    meeting_info['user_list'].append(user_information)
    print(meeting_info)

    return redirect(url_for('initialize_AI'))

def existance_name(name):
    global meeting_info
    for participant in meeting_info['participants']:
        if participant['name'] == name:
            return True
    for user in meeting_info['user_list']:
        if user['name'] == name:
            return True
    return False

def existance_per(personality):
    global meeting_info
    for participant in meeting_info['participants']:
        if participant['personality'] == personality:
            return True
    for user in meeting_info['user_list']:
        if user['personality'] == personality:
            return True
    return False

@app.route('/initialize_AI/<int:index>', methods=['GET', 'POST'])
def initialize(index):
    global meeting_info
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        nationality = request.form['nationality']
        personality = request.form['personality']
        occupation = request.form['occupation']


        if existance_name(name):
            return render_template('initialize_AI.html', index=index, error_message="This name is already exist.")
        elif existance_per(personality):
            return render_template('initialize_AI.html', index=index, error_message="This personality is already exist.")
        elif is_valid(name, age, nationality, personality, occupation):
            participant_dict = {'name': name, 'age': age, 'nationality': nationality, 'personality': personality,
                                'occupation': occupation}
            meeting_info['participants'].append(participant_dict)
        else:
            return render_template('initialize_AI.html', index=index, error_message="Invalid input, please try again.")

    if index == int(meeting_info['participant_num']) - len(meeting_info['user_list']) - 1:
        if meeting_info['user_list']:
            return redirect(url_for('focus_group_with_user'))
        return redirect(url_for('focus_group_without_user'))
    else:
        next_index = index + 1
        print(meeting_info)
        return render_template('initialize_AI.html', index=next_index)

@app.route('/focus_group_with_user')
def focus_group_with_user():
    participants = []
    global meeting_info
    for participant in meeting_info['participants']:
        participants.append(participant['name'])
    for user in meeting_info['user_list']:
        participants.append(user['name'])
    topic = meeting_info['topic']
    duration = meeting_info['duration']
    return render_template('focus_group_with_user.html', moderator='Able', participants=participants, topic=topic, duration=duration)

@app.route('/focus_group_without_user')
def focus_group_without_user():
    participants = []
    global meeting_info
    for participant in meeting_info['participants']:
        participants.append(participant['name'])
    topic = meeting_info['topic']
    duration = meeting_info['duration']
    return render_template('focus_group_without_user.html', moderator='Able', participants=participants, topic=topic, duration=duration)


@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    # global simulator
    # simulator.exit = True


@socketio.on('new_dialogue')
def generate_dialogue():
    global meeting_info, simulator
    simulator = ChatProcessor(meeting_info, api_key='Your OpenAI API Key', organization="Your OpenAI Organization", moderator_name = 'Moderator Name', model_name = "Model Name")
    pre_stage = simulator.stages.pop(0).strip()
    print("now_stage:{}".format(pre_stage))
    pre_requirement = simulator.requirements.pop(0).strip()
    Intro = simulator.generate_intro(pre_stage, pre_requirement)
    socketio.emit('new_dialogue', simulator.socketio_message(Intro))
    socketio.sleep(1)
    stage_conversation = []
    if simulator.time_range:
        time_limitation_stage = simulator.time_range.pop(0)
    else:
        time_limitation_stage = simulator.total_time / (len(simulator.stages) - 1)
    print(time_limitation_stage)
    while len(simulator.stages) > 1:
        cur_stage = simulator.stages.pop(0).strip()
        print("now_stage:{}".format(cur_stage))
        if simulator.time_range:
            time_limitation_stage = simulator.time_range.pop(0)
        else:
            time_limitation_stage = simulator.total_time / (len(simulator.stages) - 1)
        print(time_limitation_stage)
        cur_requirement = simulator.requirements.pop(0).strip()
        contexts = []
        stage_start_question = simulator.generate_question_stage(cur_stage, pre_stage, cur_requirement, stage_conversation)
        contexts.append(stage_start_question)
        speaker = 'Moderator'
        socketio.emit('new_dialogue', simulator.socketio_message(stage_start_question))
        socketio.sleep(1)
        while simulator.calculate_time(contexts) <= time_limitation_stage or speaker == "Moderator":
            speaker, tmp_value = simulator.speaker_selector(cur_stage, contexts)
            print(speaker, tmp_value)
            if speaker == "Moderator" and isinstance(tmp_value, str):
                texts = simulator.generate_question_to_participant(cur_stage, tmp_value)
                contexts.append(texts)
                socketio.emit('new_dialogue', simulator.socketio_message(texts))
                socketio.sleep(1)
                response = simulator.generate_reply(tmp_value, cur_stage, stage_conversation)
                contexts.append(response)
                socketio.emit('new_dialogue', simulator.socketio_message(response))
                socketio.sleep(1)
                continue
            if speaker == "Moderator" and isinstance(tmp_value, int):
                texts= simulator.generate_insight_question(cur_stage)
                contexts.append(texts)
                socketio.emit('new_dialogue', simulator.socketio_message(texts))
                socketio.sleep(1)
                continue
            texts = simulator.generate_reply(speaker, cur_stage, stage_conversation)
            contexts.append(texts)
            socketio.emit('new_dialogue', simulator.socketio_message(texts))
            socketio.sleep(1)
        stage_conversation = contexts
        pre_stage = cur_stage
        pre_requirement = cur_requirement
    last_stage = simulator.stages.pop(0).strip()
    print("now_stage:{}".format(last_stage))
    last_requirement = simulator.requirements.pop(0).strip()
    conclusion = simulator.generate_conclusion(last_stage, last_requirement)
    socketio.emit('new_dialogue', simulator.socketio_message(conclusion))
    socketio.sleep(1)
    socketio.emit('meeting_finished')




@socketio.on('user_question')
def handle_user_question(question):
    global simulator
    print(question)
    socketio.emit('new_dialogue', {'speaker': 'User', 'text': question})

    question = "<user>: "+question.strip()
    answer = simulator.answer_question(question)
    socketio.emit('new_dialogue', simulator.socketio_message(answer))


@socketio.on('exit')
def handle_exit():
    print('exit')
    # global simulator
    # simulator.exit = True
    socketio.emit('redirect', {'url': url_for('index')})


@socketio.on('dialogue_with_user')
def generate_dialogue_with_user():
    global meeting_info, simulator, contexts, stage_conversation, time_limitation_stage
    simulator = ChatProcessor(meeting_info, api_key='Your OpenAI API key', organization="Your OpenAI organization", moderator_name = 'Moderator Name', model_name = "Model Name")
    pre_stage = simulator.stages.pop(0).strip()
    print("now_stage:{}".format(pre_stage))
    pre_requirement = simulator.requirements.pop(0).strip()
    Intro = simulator.generate_intro(pre_stage, pre_requirement)
    socketio.emit('dialogue_with_user', simulator.socketio_message(Intro))
    socketio.sleep(1)
    stage_conversation = []
    if simulator.time_range:
        time_limitation_stage = simulator.time_range.pop(0)
    else:
        time_limitation_stage = simulator.total_time / (len(simulator.stages) - 1)
    print(time_limitation_stage)
    cur_stage = simulator.stages.pop(0).strip()
    print("now_stage:{}".format(cur_stage))
    if simulator.time_range:
        time_limitation_stage = simulator.time_range.pop(0)
    else:
        time_limitation_stage = simulator.total_time / (len(simulator.stages) - 1)
    print(time_limitation_stage)
    cur_requirement = simulator.requirements.pop(0).strip()
    contexts = []
    stage_start_question = simulator.generate_question_stage(cur_stage, pre_stage, cur_requirement, stage_conversation)
    contexts.append(stage_start_question)
    socketio.emit('dialogue_with_user', simulator.socketio_message(stage_start_question))


@socketio.on('user_reply')
def handle_user_reply(reply):
    global meeting_info, simulator, contexts, time_limitation_stage, stage_conversation
    if simulator.stages:
        cur_stage = list(simulator.moderator_history.keys())[-1]
        message = simulator.collect_user_input(cur_stage, reply)
        socketio.emit('dialogue_with_user', simulator.socketio_message(message))
        socketio.sleep(1)
        if simulator.calculate_time(contexts) <= time_limitation_stage:
            speaker, tmp_value = simulator.speaker_selector_with_user(cur_stage, contexts)
            print(speaker, tmp_value)
            if speaker == "Moderator" and isinstance(tmp_value, str):
                texts = simulator.generate_question_to_participant(cur_stage, tmp_value)
                contexts.append(texts)
                socketio.emit('dialogue_with_user', simulator.socketio_message(texts))
                if tmp_value != simulator.user_name[0]:
                    socketio.sleep(1)
                    response = simulator.generate_reply(tmp_value, cur_stage, stage_conversation)
                    contexts.append(response)
                    socketio.emit('dialogue_with_user', simulator.socketio_message(response))
            elif speaker == "Moderator" and isinstance(tmp_value, int):
                texts = simulator.generate_insight_question(cur_stage)
                contexts.append(texts)
                socketio.emit('dialogue_with_user', simulator.socketio_message(texts))
            else:
                texts = simulator.generate_reply(speaker, cur_stage, stage_conversation)
                contexts.append(texts)
                socketio.emit('dialogue_with_user', simulator.socketio_message(texts))
        else:
            stage_conversation = contexts
            pre_stage = cur_stage
            cur_stage = simulator.stages.pop(0).strip()
            print("now_stage:{}".format(cur_stage))
            if simulator.time_range:
                time_limitation_stage = simulator.time_range.pop(0)
            else:
                time_limitation_stage = simulator.total_time / (len(simulator.stages) - 1)
            print(time_limitation_stage)
            cur_requirement = simulator.requirements.pop(0).strip()
            stage_start_question = simulator.generate_question_stage(cur_stage, pre_stage, cur_requirement, stage_conversation)
            contexts = []
            contexts.append(stage_start_question)
            socketio.emit('dialogue_with_user', simulator.socketio_message(stage_start_question))
    else:
        message = "<{}>: Thank you for your participation. The meeting is finished. You can ask any question you want.".format(simulator.moderator_name)
        socketio.emit('dialogue_with_user', simulator.socketio_message(message))
        socketio.emit('meeting_finished')

@socketio.on('generation_for_user')
def handle_generation_for_user():
    global stage_conversation
    stage = list(simulator.moderator_history.keys())[-1]
    message = simulator.generate_reply_for_user(simulator.user_name[0], stage, stage_conversation)
    socketio.emit('generation_for_user', {"text":simulator.socketio_message(message)['text']})

@socketio.on('skip')
def handle_skip():
    global meeting_info, simulator, contexts, time_limitation_stage, stage_conversation
    if simulator.stages:
        cur_stage = list(simulator.moderator_history.keys())[-1]
        pre_speaker = contexts[-1].split(":")[0].strip().strip('<').strip('>')
        if simulator.calculate_time(contexts) <= time_limitation_stage or pre_speaker == "Moderator":
            speaker, tmp_value = simulator.speaker_selector_with_user(cur_stage, contexts)
            print(speaker, tmp_value)
            if speaker == "Moderator" and isinstance(tmp_value, str):
                texts = simulator.generate_question_to_participant(cur_stage, tmp_value)
                contexts.append(texts)
                socketio.emit('dialogue_with_user', simulator.socketio_message(texts))
            elif speaker == "Moderator" and isinstance(tmp_value, int):
                texts = simulator.generate_insight_question(cur_stage)
                contexts.append(texts)
                socketio.emit('dialogue_with_user', simulator.socketio_message(texts))
            else:
                texts = simulator.generate_reply(speaker, cur_stage, stage_conversation)
                contexts.append(texts)
                socketio.emit('dialogue_with_user', simulator.socketio_message(texts))
        else:
            stage_conversation = contexts
            pre_stage = cur_stage
            cur_stage = simulator.stages.pop(0).strip()
            print("now_stage:{}".format(cur_stage))
            cur_requirement = simulator.requirements.pop(0).strip()
            stage_start_question = simulator.generate_question_stage(cur_stage, pre_stage, cur_requirement, stage_conversation)
            contexts = []
            contexts.append(stage_start_question)
            socketio.emit('dialogue_with_user', simulator.socketio_message(stage_start_question))
    else:
        socketio.emit('meeting_finished')


@app.route('/download')
def download_file():
    global simulator
    filename = simulator.output_file


    return send_file(filename, as_attachment=True)









if __name__ == '__main__':
    socketio.run(app)
