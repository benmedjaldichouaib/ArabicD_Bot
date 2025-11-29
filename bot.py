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
genai.configure(api_key=GENIE_API_KEY)

CSV_FILE = "sorted_cefr.csv" # CSV file in the same folder as bot.py

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
"""Remove diacritics and definite article"""
return dediac_ar(word).lstrip("ال")

def normalize_with_gemini(word):
prompt = f"""
الكلمة: "{word}"
هل الكلمة معرفة بـ "ال" أو جمع؟ إذا كانت كذلك، أعطني الكلمة بصيغتها الأساسية أو المفردة فقط، بدون شرح إضافي.
فقط الكلمة المفردة أو الأصلية.
إذا كانت الكلمة أصلية فعلًا، أعد نفس الكلمة فقط.
"""
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content(prompt)
return response.text.strip().split()[0] if response.text else word

def get_gemini_completion(word):
prompt = f"""
أعطني تحليلًا دقيقًا ومنسقًا للكلمة "{word}" بصيغة واضحة، حيث كل معلومة تكون في سطر مستقل وفقًا للتنسيق التالي:
كلمة: {word}
مستوى CEFR: (A1, A2, B1, B2, C1, C2 فقط)
المجال: (حدد مجالًا واحدًا فقط مثل: قانون، طب، هندسة...)
نوع الكلمة: (اسم، فعل، صفة، حال...)
الجذر: (اكتب الجذر فقط، بدون شرح)
التعريف: (جملة واحدة فقط تشرح المعنى بوضوح)
المرادفات: (قائمة مفصولة بفواصل)
الأضداد: (قائمة مفصولة بفواصل، أو اكتب "غير متوفر" إذا لم يكن هناك)
مثال استخدام: (جملة قصيرة توضح استخدام الكلمة)
السياق: (وضح كيف تُستخدم الكلمة في سياق معين، مثل: في المدرسة، في السوق، في الحياة اليومية...)
**مهم**: لا تضف أي شرح زائد خارج هذا التنسيق.
"""
model = genai.GenerativeModel("gemini-2.0-flash")
response = model.generate_content(prompt)
return response.text.strip() if response.text else "غير متوفر"

def fetch_word_data(word):
global df
base_word = normalize_with_gemini(word)
normalized_word = normalize_arabic_word(base_word)
result = df[df["Word"] == normalized_word]

```
is_new_word = result.empty
data = {}
if not is_new_word:
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
    # Add new word to CSV
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    df.to_csv(CSV_FILE, index=False)

return data
```

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
========================================

"""

# -------------------- TELEGRAM HANDLERS --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text("سلام! أرسل لي كلمة بالعربية باش نحللها لك.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
word = update.message.text.strip()
if not ARABIC_REGEX.match(word):
await update.message.reply_text("⚠️ يُسمح فقط بالكلمات العربية. حاول مرة أخرى!")
return

```
data = fetch_word_data(word)
# Send TTS audio
audio_file = speak(word)
await update.message.reply_audio(audio=InputFile(audio_file))
os.remove(audio_file)  # clean up after sending
# Send text result
await update.message.reply_text(format_result(data))
```

# -------------------- MAIN --------------------

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
print("🤖 Bot is running...")
app.run_polling()

