import base64
import os

from config import AUTH_TOKEN
from domain.model.ModelTextRequest import ModelTextRequest
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from gtts import gTTS
from langdetect import detect
from pydub import AudioSegment
import whisper

app = FastAPI()

whisper_model = whisper.load_model("small")


def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = authorization.split("Bearer ")[-1]
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


@app.post("/generate-audio", dependencies=[Depends(verify_token)])
async def generate_audio(request: ModelTextRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        detected_lang = detect(text)
        print(f"Detected language: {detected_lang}")

        tts = gTTS(text=text, lang=detected_lang)
        mp3_path = "output.mp3"
        tts.save(mp3_path)

        audio = AudioSegment.from_mp3(mp3_path)
        ogg_path = "output.ogg"
        audio.export(ogg_path, format="ogg", codec="libopus")

        with open(ogg_path, "rb") as audio_file:
            encoded_audio = base64.b64encode(audio_file.read()).decode("utf-8")

        os.remove(mp3_path)
        os.remove(ogg_path)

        return {"audio_base64": encoded_audio, "format": "ogg", "language": detected_lang}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")


@app.post("/transcribe-audio", dependencies=[Depends(verify_token)])
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        # Збереження файлу
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as audio_file:
            audio_file.write(await file.read())

        # Конвертація в WAV для Whisper
        audio = AudioSegment.from_file(temp_path)
        wav_path = temp_path.replace(".ogg", ".wav").replace(".mp3", ".wav")
        audio.export(wav_path, format="wav")

        # Використання Whisper для розпізнавання мови
        result = whisper_model.transcribe(wav_path)

        # Видалення тимчасових файлів
        os.remove(temp_path)
        os.remove(wav_path)

        return {"transcribed_text": result["text"], "language": result["language"]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")
