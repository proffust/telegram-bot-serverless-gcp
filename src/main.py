"""
This file is part of the Telegram Bot project.
It contains the main logic for handling Telegram messages and interactions.
"""
import json
import time
import re
import base64
import os
from functools import wraps
import requests

from openai import OpenAI
from anthropic import Anthropic
from anthropic.types import TextBlock
from loguru import logger
from google.cloud import storage
from google.cloud import parametermanager_v1
from google.genai.types import Content, Part, UserContent, Image
from google.genai import Client as Gemini
from xai_sdk import Client as Xai
from xai_sdk.chat import user, assistant, image

from telegram.ext import (
    Dispatcher,
    MessageHandler,
    Filters,
    CommandHandler,
    CallbackQueryHandler,
)
from telegram import ParseMode, Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, ChatAction

# Telegram token
TOKEN = os.environ.get("TELEGRAM_TOKEN")
BUCKET_NAME = os.environ.get("CONVERSATION_BUCKET")
GCP_REGION = os.environ.get("GCP_REGION")
GCP_PROJECT = os.environ.get("GCP_PROJECT")
parameter_manager_client = parametermanager_v1.ParameterManagerClient(
    client_options={"api_endpoint": f"parametermanager.{GCP_REGION}.rep.googleapis.com"}
)
allowed_models_json = json.loads(
    parameter_manager_client.get_parameter_version(
        name=f"projects/{GCP_PROJECT}/locations/{GCP_REGION}/parameters/allowed_models/versions/v1"
    ).payload.data
)
allowed_models_openai = allowed_models_json["openai"]
allowed_models_antropic = allowed_models_json["antropic"]
allowed_models_google = allowed_models_json["google"]
allowed_models_xai = allowed_models_json["xai"]
allowed_models = (allowed_models_openai + allowed_models_antropic +
                  allowed_models_google + allowed_models_xai)
# Telegram bot
if TOKEN is not None:
    bot = Bot(token=TOKEN)
    dispatcher = Dispatcher(bot, None, use_context=True) # type: ignore[reportCallIssue]

else:
    logger.error("TELEGRAM_TOKEN environment variable not set")
    raise ValueError("TELEGRAM_TOKEN environment variable not set")
storage_client = storage.Client()
if allowed_models_openai:
    client = OpenAI()
if allowed_models_antropic:
    client_anthropic = Anthropic()
if allowed_models_google:
    client_googleai = Gemini(
        vertexai=True, project=GCP_PROJECT, location=GCP_REGION
    )
if allowed_models_xai:
    client_xai = Xai()

def last_conversation(file_key) -> float:
    """ 
    Функция для получения времени последнего изменения файла в S3.
    Возвращает время последнего изменения файла с заданным ключом.
    """
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_key)

    blob.reload()  # Загружает данные о blob, включая время последнего изменения
    if blob.updated is not None:
        return blob.updated.timestamp()  # Возвращает время последнего изменения файла
    return 0.0

def file_exists_in_s3(file_key) -> bool:
    """ 
    Функция для проверки существования файла в S3.
    Проверяет, существует ли файл с заданным ключом в указанном бакете.
    """
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_key)
    return blob.exists()

def load_s3_object(effective_user) -> dict:
    """    
    Функция для загрузки файла из S3.
    Загружает файл с именем effective_user.json и возвращает его содержимое в виде словаря.
    """
    try:
        file_name = f'{effective_user}.json'
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)
        file_content = blob.download_as_string()
        return json.loads(file_content)
    except Exception as e: #pylint: disable=W0718
        return {"statusCode": 400, "body": str(e)}

def save_file(model, messages, effective_user) -> None | dict:
    """    
    Функция для сохранения истории сообщений в S3.
    Сохраняет модель и сообщения в формате JSON.
    """
    try:
        file_name = f'{effective_user}.json'
        content = {"model": model, "msgs": messages}
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)
        blob.upload_from_string(json.dumps(content),content_type='application/json')
        return None
    except Exception as e: #pylint: disable=W0718
        return {"statusCode": 400, "body": str(e)}

def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        context.bot.send_chat_action(
            chat_id=update.effective_message.chat_id, action=ChatAction.TYPING
        )
        return func(update, context, *args, **kwargs)

    return command_func

def escape_markdown_v2(text: str) -> str:
    """
    Экранирует специальные символы MarkdownV2 в тексте.
    """
    # Экранируем специальные символы MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f"([{re.escape(escape_chars)}])", r'\\\1', text)

def split_markdown_message_safe(message: str, max_len: int = 4096) -> list:
    """
    Разбивает сообщение на части, сохраняя целостность код-блоков
    и экранируя Markdown-символы вне код-блоков.
    Для код-блоков добавляет правильный синтаксис MarkdownV2.
    """
    lines = message.split("\n")
    chunks = []
    current_chunk = ""
    inside_code_block = False

    for line in lines:
        if line.strip().startswith("```") or line.strip().startswith("~~~"):
            if not inside_code_block:
                # Начало блока кода
                inside_code_block = True
                processed_line = "```\n"  # MarkdownV2 корректный старт
            else:
                # Конец блока кода
                inside_code_block = False
                processed_line = "```\n"
        else:
            # Экранируем только вне блока кода
            processed_line = line if inside_code_block else escape_markdown_v2(line)

        if len(current_chunk) + len(processed_line) + 1 <= max_len:
            current_chunk += processed_line + "\n"
        else:
            if inside_code_block:
                current_chunk += "```\n"
                chunks.append(current_chunk.rstrip("\n"))
                current_chunk = "```\n" + processed_line + "\n"
            else:
                chunks.append(current_chunk.rstrip("\n"))
                current_chunk = processed_line + "\n"

    if current_chunk.strip():
        if inside_code_block:
            current_chunk += "```\n"
        chunks.append(current_chunk.rstrip("\n"))

    return chunks

def load_models_and_msgs(effective_user) -> tuple:
    """
    Функция для загрузки модели и сообщений из S3.
    Возвращает модель и список сообщений.
    Если файл не существует, возвращает модель по умолчанию и пустой список сообщений.
    """
    if file_exists_in_s3(f'{effective_user}.json'):
        content = load_s3_object(effective_user)
        try:
            msgs = content["msgs"]
            model = content["model"]
        except (KeyError, TypeError):
            model = "gpt-5-nano"
            msgs = content
    else:
        msgs = []
        model = "gpt-5-nano"
    return model, msgs

def ask_neural(text, effective_user) -> str:
    """    
    Функция для отправки запроса к нейросети и получения ответа.
    Использует OpenAI или Anthropic в зависимости от модели.
    """
    model, msgs = load_models_and_msgs(effective_user)
    history = []
    if model in allowed_models_openai:
        msgs.append({"role": "user", "content": text})
        for msg in msgs:
            if msg["role"]=="user":
                history.append({"role": "user",
                                "content":[{"type": "input_text", "text": msg["content"]}]})
            history.append({"role": "assistant",
                            "content":[{"type": "output_text","text": msg["content"]}]})
        chat = client.responses.create( #pylint: disable=E0606
            model=model,
            input=history,
        )
        #logger.info(f"Response: {chat}")
        msgs.append({"role": "assistant", "content": chat.output_text})
        save_file(model, msgs, effective_user)
        return str(chat.output_text)
    if model in allowed_models_antropic:
        msgs.append({"role": "user", "content": text})
        chat = client_anthropic.messages.create( #pylint: disable=E0606
            model=model,
            max_tokens=8192,
            messages=msgs
        )
        if isinstance(chat.content[0], TextBlock):
            answer = chat.content[0].text
            msgs.append({"role": "assistant", "content": answer})
            save_file(model, msgs, effective_user)
        else:
            answer = ""
        return answer
    if model in allowed_models_google:
        for msg in msgs:
            if msg["role"]=="user":
                history.append(UserContent(parts=[Part(text=msg["content"])]))
            history.append(Content(parts=[Part(text=msg["content"])],role="model"))
        msgs.append({"role": "user", "content": text})
        chat = client_googleai.chats.create( #pylint: disable=E0606
            model=model,
            history=history)
        response = chat.send_message(text)
        msgs.append({"role": "assistant", "content": response.text})
        save_file(model, msgs, effective_user)
        return str(response.text)
    if model in allowed_models_xai:
        msgs.append({"role": "user", "content": text})
        for msg in msgs:
            if msg["role"]=="user":
                history.append(user(msg["content"]))
            history.append(assistant(msg["content"]))
        chat = client_xai.chat.create( #pylint: disable=E0606
            model=model,
            messages=history
        )
        response = chat.sample()
        msgs.append({"role": "assistant", "content": response.content})
        return str(response.content)
    return ""

#####################
# Telegram Handlers #
#####################
@send_typing_action
def clear_context(update, context):
    """    
    Функция для очистки контекста и начала новой сессии.
    Сбрасывает историю сообщений
    """
    try:
        effective_user = update.message.chat_id
    except AttributeError:
        effective_user = update.callback_query.message.chat.id
    model, _ = load_models_and_msgs(effective_user)
    save_file(model,[],effective_user)
    context.bot.send_message(
        chat_id=effective_user,
        text="Начата новая сессия",
        parse_mode=ParseMode.MARKDOWN,
    )

@send_typing_action
def send_greeting(update, context):
    """
    Функция для отправки приветственного сообщения пользователю.
    """
    message = f'''Привет {update.effective_user.first_name}!'''
    context.bot.send_message(
        chat_id=update.message.chat_id,
        text=message,
        parse_mode=ParseMode.MARKDOWN,
    )

@send_typing_action
def send_help(update, context):
    """
    Функция для отправки справочного сообщения пользователю.
    """
    message = f'''Привет {update.effective_user.first_name}!
                Я бот созданный для тестирование Lambda функций и отправки запросов в chatGPT.'''
    context.bot.send_message(
        chat_id=update.message.chat_id,
        text=message,
        parse_mode=ParseMode.MARKDOWN,
    )

@send_typing_action
def set_model(update, context):
    """
    Функция для установки модели, которую будет использовать бот.
    Сохраняет модель в S3 и отправляет сообщение пользователю.
    """
    effective_user = update.message.chat_id
    try:
        model = update.message.text.split(" ")[1]
    except IndexError:
        model = ""
    if model in allowed_models:
        _, msgs = load_models_and_msgs(effective_user)
        save_file(model, msgs, effective_user)
        context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f'Сохранено в настройки использование модели {model}',
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        context.bot.send_message(
            chat_id=update.message.chat_id,
            text='Доступные модели ' + ', '.join(allowed_models),
            parse_mode=ParseMode.MARKDOWN,
        )

def button(update, context) -> None:
    """
    Функция для обработки нажатий на кнопки в InlineKeyboard.
    Если нажата кнопка "Да", очищает контекст, иначе отправляет ответ на предыдущий текст.
    """
    query = update.callback_query
    query.answer()
    print(query.data)
    if bool(int(query.data)):
        clear_context(update, context)
    else:
        chat_text = context.user_data.get('previous_message_text')
        chat_id = update.callback_query.message.chat.id
        try:
            message = ask_neural(chat_text, chat_id)
        except Exception as e: #pylint: disable=W0718
            context.bot.send_message(
                chat_id=chat_id,
                text=f"Ошибка при обработке сообщения: `{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            chunks = split_markdown_message_safe(message)
            #logger.info(f"Response: {chunks}")
            for chunk in chunks:
                context.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN_V2
                )

@send_typing_action
def get_model(update, context):
    """
    Функция для получения текущей модели, которую использует бот.
    Если модель сохранена в S3, отправляет её пользователю, иначе сообщает о модели по умолчанию.
    """
    effective_user = update.message.chat_id
    model, _ = load_models_and_msgs(effective_user)
    context.bot.send_message(
        chat_id=update.message.chat_id,
        text=f'Считано из настроек использование модели {model}',
        parse_mode=ParseMode.MARKDOWN,
    )

@send_typing_action
def generate_image(update, context):
    """
    Функция для генерации изображения по текстовому запросу.
    Если в запросе указана модель, использует её, иначе использует модель по умолчанию.
    Отправляет сгенерированное изображение пользователю.
    """
    text = update.message.text[7:]
    if text.find("model:")!=-1:
        match = re.search(r'model\:([^\s]+)\s(.+)', text)
        if match is not None:
            model = match.group(1)
            prompt = match.group(2)
        else:
            return
    else:
        model = "dall-e-2"
        prompt = text
    if bool(prompt):
        if model in ["dall-e-2", "dall-e-3"]:
            response = client.images.generate(
                model=model,
                prompt=prompt,
            )
            if response.data is not None:
                context.bot.send_photo(chat_id=update.effective_chat.id,
                                    photo=response.data[0].url,
                                    caption=response.data[0].revised_prompt
                                    )
            return
        if model in ["imagen-4.0-generate-001"]:
            response = client_googleai.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
            )
            if response.generated_images is not None:
                if isinstance(response.generated_images[0].image, Image):
                    context.bot.send_photo(chat_id=update.effective_chat.id,
                        photo=response.generated_images[0].image.image_bytes,
                    )
                    return
            logger.error("Error generate image from Google")
            return
        if model in ["grok-2-image"]:
            response = client_xai.image.sample(
                model=model,
                prompt=prompt,
            )
            if response.url is not None:
                context.bot.send_photo(chat_id=update.effective_chat.id,
                                    photo=response.url,
                                    caption=response.prompt
                                    )
            return
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Выбранная модель генерации изображений не поддерживается",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Промпт не может быть пустым",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

@send_typing_action
def unknown_command(update, context):
    """
    Функция для обработки неизвестных команд.
    Отправляет сообщение о том, что команда не распознана.
    """
    logger.warning(f"Unknown command: {update.message.text}")
    context.bot.send_message(
        chat_id=update.message.chat_id,
        text="Команда нераспознана",
        parse_mode=ParseMode.MARKDOWN,
    )

@send_typing_action
def process_voice_message(update, context):
    """
    Функция для обработки голосовых сообщений.
    Загружает голосовое сообщение, генерирует его транскрипцию и отправляет ответ пользователю.
    """
    # Get the voice message from the update object
    voice_message = update.message.voice
    file_id = voice_message.file_id
    file = bot.get_file(file_id)
    file.download("/tmp/voice_message.ogg")
    downloaded_file = open("/tmp/voice_message.ogg", "rb")
    # Download the voice message file
    #transcript_msg = generate_transcription(file)
    transcript_msg = client.audio.transcriptions.create(
        model="whisper-1",
        file=downloaded_file,
    )

    chat_id = update.message.chat_id
    context.bot.send_message(
        chat_id=chat_id,
        text=f'Распознанное сообщение:\n{transcript_msg.text}',
        parse_mode=ParseMode.MARKDOWN,
    )

    message = ask_neural(transcript_msg.text, update.message.chat_id)

    speech_file_path = "/tmp/voice_answer.ogg"
    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="nova",
        input=message,
        response_format="opus",
    ) as streaming_response:
        with open(speech_file_path, "wb") as f:
            for chunk in streaming_response.iter_bytes():
                f.write(chunk)

    with open(speech_file_path, 'rb') as audio_file:
        context.bot.send_voice(
            chat_id=chat_id,
            voice=audio_file,
        )

    context.bot.send_message(
        chat_id=chat_id,
        text=f'Ответ :\n{message}',
        parse_mode=ParseMode.MARKDOWN,
    )

@send_typing_action
def process_message(update, context):
    """
    Функция для обработки текстовых сообщений.
    Проверяет, есть ли предыдущая сессия, и если нет, предлагает начать новую.
    Отправляет текстовое сообщение в нейросеть и возвращает ответ пользователю.
    """
    chat_id = update.message.chat_id
    chat_text = update.message.text
    if file_exists_in_s3(f'{chat_id}.json'):
        last_message_time = last_conversation(f'{chat_id}.json')
        if time.time() - last_message_time > 3600:
            keyboard = [[InlineKeyboardButton("Да", callback_data="1"),
                         InlineKeyboardButton("Нет", callback_data="0")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text('Вы очень долго не общались с ботом, начать новую сессию?',
                                      reply_markup=reply_markup)
            context.user_data['previous_message_text'] = update.message.text
            return
    try:
        message = ask_neural(chat_text, chat_id)
    except Exception as e: #pylint: disable=W0718
        context.bot.send_message(
            chat_id=chat_id,
            text=f"Ошибка при обработке сообщения: `{str(e)}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        try:
            chunks = split_markdown_message_safe(message)
            #logger.info(f"Response: {chunks}")
            for chunk in chunks:
                context.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
        except Exception as e: #pylint: disable=W0718
            context.bot.send_message(
                chat_id=chat_id,
                text=f"Ошибка при отправке сообщения: `{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
            )

@send_typing_action
def handle_photo(update, context):
    """
    Функция для обработки фотографий, отправленных пользователем.
    Получает фотографию, кодирует её в base64 и отправляет в нейросеть для анализа.
    """
    # Получаем идентификатор пользователя и чата
    effective_user = update.message.from_user.id
    chat_id = update.message.chat_id
    # Получаем информацию о файле
    file = context.bot.get_file(update.message.photo[-1].file_id)

    # Скачиваем файл
    image_data = requests.get(file.file_path, timeout=30).content

    # Кодируем изображение в base64
    base64_image = base64.b64encode(image_data).decode('utf-8')

    # Получаем текст подписи, если есть
    caption = update.message.caption or "Опиши это изображение."

    # Загружаем предыдущую историю сообщений
    model, msgs = load_models_and_msgs(effective_user)

    # Используем только это сообщение для текущего запроса
    try:
        if model in allowed_models_antropic:
            # Создаем мультимодальное сообщение
            current_msg = {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",  # предполагаем JPEG формат
                            "data": base64_image
                        }
                    },
                    {
                        "type": "text",
                        "text": caption
                    }
                ]
            }
            msgs.append(current_msg)

            chat = client_anthropic.messages.create(
                model=model,
                max_tokens=2000,
                messages=msgs
            )
            if isinstance(chat.content[0], TextBlock):
                message = chat.content[0].text
                msgs.append({"role": "assistant", "content": message})
                save_file(model, msgs, effective_user)
                context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                )
            return
        if model in allowed_models_openai:
            if model!="gpt-3.5-turbo":
                current_msg = {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{base64_image}"
                        },
                        {
                            "type": "input_text",
                            "text": caption
                        }
                    ]
                }
                msgs.append(current_msg)

                chat = client.responses.create(
                    model=model,
                    input=msgs,
                    max_output_tokens=2000
                )
                #logger.info(f"Response from model {model}: {chat}")
                message = chat.output_text
                # Сохраняем в историю текстовое представление запроса и ответа
                msgs.append({"role": "assistant",
                             "content":[{"type": "output_text","text": message}]})
                save_file(model, msgs, effective_user)
                context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                context.bot.send_message(
                    chat_id=chat_id,
                    text="gpt-3.5-turbo не поддерживает мультимодальность",
                    parse_mode=ParseMode.MARKDOWN,
                )
            return
        if model in allowed_models_google:
            response = client_googleai.models.generate_content(
                model=model,
                contents=[
                    caption,
                    Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                ],
            )
            message = response.text
            # Сохраняем в историю текстовое представление запроса и ответа
            msgs.append({"role": "assistant",
                            "content":[{"type": "output_text","text": message}]})
            save_file(model, msgs, effective_user)
            context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        if model in allowed_models_xai:
            chat = client_xai.chat.create(model=model)
            chat.append(
                user(
                    caption,
                    image(image_url=f"data:image/jpeg;base64,{base64_image}", detail="auto"),
                )
            )
            response = chat.sample()
            message = response.content
            msgs.append({"role": "assistant",
                "content":[{"type": "output_text","text": message}]})
            save_file(model, msgs, effective_user)
            context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        context.bot.send_message(
            chat_id=chat_id,
            text="Выбранная вами модель пока поддерживает мультимодальность в боте",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    except Exception as e: #pylint: disable=W0718
        logger.error(f"Error processing image: {str(e)}")
        update.message.reply_text(f"Ошибка при обработке изображения: `{str(e)}`")
        return

############################
# Lambda Handler functions #
############################


def message_handler(event):
    """
    Основная функция-обработчик для Lambda, которая принимает события от Telegram.
    Обрабатывает команды и сообщения, отправленные пользователем.
    """
    dispatcher.add_handler(CommandHandler("new_session",clear_context))
    dispatcher.add_handler(CommandHandler("start",send_greeting))
    dispatcher.add_handler(CommandHandler("help",send_help))
    dispatcher.add_handler(CommandHandler("set_model",set_model))
    dispatcher.add_handler(CommandHandler("get_model",get_model))
    dispatcher.add_handler(CommandHandler("image",generate_image))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, process_message))
    dispatcher.add_handler(MessageHandler(Filters.voice, process_voice_message))
    dispatcher.add_handler(MessageHandler(Filters.command, unknown_command))

    try:
        dispatcher.process_update(Update.de_json(event.get_json(force=True), bot))
    except Exception as e: #pylint: disable=W0718
        logger.error(f"Error processing image: {str(e)}")
        return {"statusCode": 500}

    return {"statusCode": 200}
