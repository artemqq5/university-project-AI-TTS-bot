import asyncio
import base64
import io
import logging
import os

import requests
from aiogram import Dispatcher, Bot, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, FSInputFile

import config
from consts import HELLO_TEXT, ERROR_LEN_TEXT, ERROR_LEN_VOICE

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


async def main():
    logging.basicConfig(level=logging.INFO)

    default_properties = DefaultBotProperties(parse_mode=ParseMode.HTML)
    bot = Bot(token=config.BOT_TOKEN, default=default_properties, timeout=60)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        print(f"start tts bot: {e}")
        return


@dp.message(Command("start"))
async def wellcome(message: Message):
    await message.answer(HELLO_TEXT)


@dp.message(F.text)
async def text_to_voice(message: Message):
    if len(message.text) > 500:
        await message.answer(ERROR_LEN_TEXT.format(len(message.text)))
        return

    text = message.text.strip()

    headers = {"Authorization": f"Bearer {config.AUTH_TOKEN}"}
    json_data = {"text": text}

    try:
        response = requests.post(f"{config.API_URL}/generate-audio", json=json_data, headers=headers)
        response.raise_for_status()
        data = response.json()

        audio_base64 = data.get("audio_base64")
        if not audio_base64:
            await message.answer("Не вдалося отримати аудіо 😢")
            return

        audio_bytes = base64.b64decode(audio_base64)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "voice.ogg"  # Telegram очікує .ogg
        audio_path = "voice.ogg"

        with open(audio_path, "wb") as audio_file:
            audio_file.write(audio_bytes)

        await message.answer_voice(FSInputFile(audio_path))

        os.remove(audio_path)

    except requests.exceptions.RequestException as e:
        await message.answer(f"Помилка запиту: {e}")


@dp.message(F.voice)
async def voice_to_text(message: Message, bot: Bot):
    voice = message.voice
    file_id = voice.file_id

    if voice.duration > 30:
        await message.answer(ERROR_LEN_VOICE.format(voice.duration))
        return

    file = await bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file.file_path}"

    response = requests.get(file_url)
    if response.status_code != 200:
        await message.answer("Не вдалося отримати аудіофайл 😢")
        return

    audio_path = "received_voice.ogg"
    with open(audio_path, "wb") as f:
        f.write(response.content)

    headers = {"Authorization": f"Bearer {config.AUTH_TOKEN}"}
    files = {"file": open(audio_path, "rb")}

    try:
        response = requests.post(f"{config.API_URL}/transcribe-audio", files=files, headers=headers)
        response.raise_for_status()
        data = response.json()
        transcribed_text = data.get("transcribed_text", "Не вдалося розпізнати текст.")
        language = data.get("language", "невідома")

        await message.answer(
            f"📜 <b>Розпізнаний текст:</b> <code>{transcribed_text}</code>\n🌍 <b>Мова:</b> <code>{language}</code>")

    except requests.exceptions.RequestException as e:
        await message.answer(f"Помилка запиту: {e}")

    os.remove(audio_path)

if __name__ == '__main__':
    asyncio.run(main())
