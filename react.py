import os
import discord
from discord.ext import commands
from openai import OpenAI
import json
import re
from langchain.utilities.wolfram_alpha import WolframAlphaAPIWrapper
from multiprocessing import Process

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
api_key = os.environ['OPENAI_API_KEY']
client=OpenAI(api_key=api_key)
wolfram=WolframAlphaAPIWrapper()

admin_bot_token = os.environ['DISCORD_ADMIN_TOKEN']
calculator_bot_token= os.environ['DISCORD_WOLFRAM_TOKEN']

admin_bot_id=os.environ["DISCORD_ADMIN_ID"]
calculator_bot_id=os.environ["DISCORD_WOLFRAM_ID"]
pilot_id="1127528757738090586"

intents = discord.Intents.default()
intents.message_content = True # Adding the message content intent
admin_bot = commands.Bot(command_prefix="!", intents=intents)
calculator_bot = commands.Bot(command_prefix="!", intents=intents)

cal_name="Calculator_Bot#8892"
# Dictionary to keep track of conversation history for each user
conversations = {}


with open('react_template.txt', 'r') as file:
    react_template = file.read()

with open('react_json_format.txt', 'r') as file:
    react_json = file.read()


@admin_bot.event
async def on_ready():
    print(f"{admin_bot.user.name} has connected to Discord!")

@calculator_bot.event
async def on_ready():
    print(f"{calculator_bot.user.name} has connected to Discord!")
    print(cal_name)

@admin_bot.command(name='start', aliases=['welcome'])
async def welcome(ctx):
    print(conversations)

async def process_voice_message(message):
    # Check if the message has an attachment
    if message.attachments:
        attachment = message.attachments[0]
        # Check if the attachment is an audio file
        
        if attachment.filename.endswith(('.mp3', '.wav','.m4a', '.flac','.ogg')):
            # Download the audio file
            audio_file_path = f"./audio/{attachment.filename}"
            await attachment.save(audio_file_path)
            print("in function")

            with open(audio_file_path, "rb") as audio_file:
                whisper_results = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file = audio_file
                )

            text_content = whisper_results.text
            print(text_content)
            return text_content
            os.remove(audio_file_path)

@admin_bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    print(message.content)
    if message.author == admin_bot.user:
        return

    user_id = pilot_id
    conversation_history = conversations.get(user_id, [{"role": "system", "content": react_template}])
    
    content=str()
    if message.attachments:
        print("processing voice message")
        content=await process_voice_message(message)
    else:
        content=message.content
    
    new_message={"role": "user", "content": ""}
    if str(message.author) == cal_name:
        print("is calculator")
        previous_response=conversations[pilot_id][-1]["content"]

        previous_response=previous_response.replace("\n",'').replace("\r",'').replace("\t",'').replace("\xa0",'')
        json_tmp=json.loads(previous_response)
        json_tmp["Actions"][-1]["ActionOutput"]=content
        new_message["content"]=json.dumps(json_tmp)
    else:
        # starting a new react conversation
        new_message["content"]=react_json.format(content=content)
        conversation_history=[{"role": "system", "content": react_template}]
    conversation_history.append(new_message)

    completion=client.chat.completions.create(
        model="gpt-4o-mini",
        messages=conversation_history,
        max_tokens=800,
        temperature=0
    )
    response_text = completion.choices[0].message.content

    conversation_history.append({"role": "assistant", "content": response_text})
    conversations[user_id] = conversation_history
    response_text=response_text.replace("\n",'').replace("\r",'').replace("\t",'').replace("\xa0",'')
    response_json=json.loads(response_text)
    print(response_json)

    if 'FinalAnswer' in response_json:
        if response_json['FinalAnswer']!='':
            await message.channel.send(response_json['FinalAnswer'])
            return
    else:
        await message.channel.send(response_json['Actions'][-1]['Thoughts'])
        action_input=response_json["Actions"][-1]["ActionInput"]

        mention=f'<@!{calculator_bot_id}>'
        await message.channel.send(f'{mention} {action_input}')
        return

@calculator_bot.event
async def on_message(message):
    bot_mention_1 = f'<@{calculator_bot.user.id}>'
    bot_mention_2 = f'<@!{calculator_bot.user.id}>'
    if message.author == calculator_bot.user:
        return
    if bot_mention_1 in message.content or bot_mention_2 in message.content:
        clean_message = re.sub(r'<@!?(\d+)>', '', message.content)
        wolfram_response = wolfram.run(clean_message)
        await message.channel.send(wolfram_response.replace("\n",'\\n'))


def run_calculator_bot():
    calculator_bot.run(calculator_bot_token)

def run_admin_bot():
    admin_bot.run(admin_bot_token)

if __name__ == '__main__':
    print("Starting the bots...")
    p1 = Process(target=run_calculator_bot)
    p2 = Process(target=run_admin_bot)
    p1.start()
    p2.start()
    p1.join()
    p2.join()