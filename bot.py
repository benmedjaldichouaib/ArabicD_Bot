import re
import pandas as pd
import google.generativeai as genai
from camel_tools.utils.dediac import dediac_ar
from gtts import gTTS
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import os

# -------------------- CONFIGURATION --------------------
TOKEN = os.environ.get("TOKEN")
GENIE_API_KEY = os.environ.get("GENIE_API_KEY")
CSV_FILE = "sorted_cefr.csv"  # Upload this CSV to your GitHub repo

genai.configure(api_key=GENIE_API_KEY)

# -------------------- LOAD CSV --------------------
df = pd.read_csv(CSV_FILE)
df.columns = df.columns.str.strip()

# -------------------- REGEX --------------------
ARABIC_REGEX = re.compile(r'^[\u0600-\u06FF]+$')

# -------------------- FUNCTIONS --------------------
def speak(word, filename="word_output.mp3"):
    tts = gTTS(word, lang="ar")
    tts.save(filename)
    return filename

def normalize_arabic_word(word):
    return dediac_ar(word).lstrip("ال")

def normalize_with_gemini(word):
    prompt = f"""
    الكلمة: "{word}"
    هل الكلمة معرفة بـ "ال" أو جمع؟ إذا كانت كذلك، أعطني الكلمة بصيغتها الأساسية أو المفردة فقط.
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip().split()[0] if response.text else word

def get_gemini_completion(word):
    prompt = f"""
    أعطني تحليلًا دقيقًا للكلمة "{word}" بصيغة واضحة:
    كلمة: {word}
    مستوى CEFR:
    المجال:
    نوع الكلمة:
    الجذر:
    التعريف:
    المرادفات:
    الأضداد:
    مثال استخدام:
    السياق:
    """
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text.strip() if response.text else "غير متوفر"

def fetch_word_data(word):
    global df
    base_word = normalize_with_gemini(word)
    normalized_word = normalize_arabic_word(base_word)
    result = df[df["Word"] == normalized_word]

    data = {}
    if not result.empty:
        data.update(result.iloc[0].to_dict())
    else:
        generated_text = get_gemini_completion(normalized_word)
        fields = {
            "CEFR Level": "مستوى CEFR",
            "Field": "المجال",
            "Part of Speech": "نوع الكلمة",
            "Lemma": "الجذر",
            "Definition": "التعريف",
            "Synonyms": "المرادفات",
            "Antonyms": "الأضداد",
            "Phrase Example": "مثال استخدام",
            "السياق": "السياق"
        }
        data["Word"] = normalized_word
        for field, label in fields.items():
            for line in generated_text.split("\n"):
                if line.startswith(label):
                    data[field] = line.split(": ", 1)[1] if ": " in line else "غير متوفر"
                    break
            else:
                data[field] = "غير متوفر"
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)

    return data

def format_result(data):
    return f"""
=== نتيجة التحليل ===
كلمة: {data.get('Word','غير متوفر')}
مستوى CEFR: {data.get('CEFR Level','غير متوفر')}
المجال: {data.get('Field','غير متوفر')}
نوع الكلمة: {data.get('Part of Speech','غير متوفر')}
الجذر: {data.get('Lemma','غير متوفر')}
التعريف: {data.get('Definition','غير متوفر')}
المرادفات: {data.get('Synonyms','غير متوفر')}
الأضداد: {data.get('Antonyms','غير متوفر')}
مثال استخدام: {data.get('Phrase Example','غير متوفر')}
السياق: {data.get('السياق','غير متوفر')}
=====================
"""

# -------------------- TELEGRAM HANDLERS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! أرسل لي كلمة بالعربية باش نحللها لك.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word = update.message.text.strip()
    if not ARABIC_REGEX.match(word):
        await update.message.reply_text("⚠️ يُسمح فقط بالكلمات العربية. حاول مرة أخرى!")
        return
    data = fetch_word_data(word)
    audio_file = speak(word)
    await update.message.reply_audio(audio=InputFile(audio_file))
    os.remove(audio_file)
    await update.message.reply_text(format_result(data))

# -------------------- MAIN --------------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("🤖 Bot is running...")
    app.run_polling()



