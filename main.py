# ═══════════════════════════════════════════════════════════════
# 🤖 FLASK + AIOGRAM TELEGRAM BOT - MULTILANG v2.1 (FIXED)
# ═══════════════════════════════════════════════════════════════

import asyncio
import logging
import json
import re
import os
import time
import threading
from datetime import datetime
from html import escape as html_escape

# Flask imports
from flask import Flask, jsonify, request

# Aiogram imports
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.exceptions import TelegramForbiddenError

# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 1: FLASK WEB SERVER
# ═══════════════════════════════════════════════════════════════

app = Flask(__name__)


@app.route("/", methods=["GET"])
def home():
    """Asosiy sahifa"""
    return "✅ Bot ishlamoqda! | Bot is running!", 200


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "registered_users": len(registered_users),
        "languages": {"uz": "O'zbekcha", "en": "English", "ru": "Русский"}
    }), 200


@app.route("/stats", methods=["GET"])
def get_stats():
    """Statistika - faqat admin uchun"""
    if request.args.get("key") != "admin_secret_123":
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "total_users": len(registered_users),
        "test_results": len(test_results),
        "by_level": {
            "elementary": len([u for u in registered_users if u.get("level") == "elementary"]),
            "pre_intermediate": len([u for u in registered_users if u.get("level") == "pre_intermediate"]),
            "intermediate": len([u for u in registered_users if u.get("level") == "intermediate"]),
            "pre_ielts": len([u for u in registered_users if u.get("level") == "pre_ielts"]),
        }
    }), 200


# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 2: BOT KONFIGURATSIYASI
# ═══════════════════════════════════════════════════════════════

load_dotenv()

TOKEN = "8087643882:AAFI7B02iUify-7SD8rsGAXfMB0qRWF9Xk8"
DATA_FILE = "registered_users.json"
TEST_RESULTS_FILE = "test_results.json"
ADMIN_ID = 5027894185
TEST_TIME = 30
READING_TIME = 60
WRITING_TIME = 1200

dp = Dispatcher()


# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 3: FSM STATELARI
# ═══════════════════════════════════════════════════════════════

class Registration(StatesGroup):
    full_name = State()
    age = State()
    branch = State()
    level = State()
    phone = State()
    test_answers = State()
    current_question = State()
    test_correct_count = State()
    reading_msg_id = State()
    reading_shown = State()
    timer_task = State()


class SendMessage(StatesGroup):
    choose_type = State()
    enter_text = State()
    upload_photo = State()
    upload_video = State()
    confirm_send = State()


class WritingState(StatesGroup):
    text = State()
    timer_msg_id = State()
    timer_task = State()


# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 4: MA'LUMOTLAR BILAN ISHLASH
# ═══════════════════════════════════════════════════════════════

registered_users = []
test_results = []


def load_data():
    global registered_users, test_results
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            registered_users = json.load(f)
    except FileNotFoundError:
        registered_users = []
    try:
        with open(TEST_RESULTS_FILE, "r", encoding="utf-8") as f:
            test_results = json.load(f)
    except FileNotFoundError:
        test_results = []


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(registered_users, f, ensure_ascii=False, indent=2)
    with open(TEST_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)


load_data()

# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 5: 🌍 MULTILANG TARJIMALAR
# ═══════════════════════════════════════════════════════════════

LANG = {
    "uz": {
        "welcome": "🎓 O'quv markaziga xush kelibsiz!\n\n👥 Ro'yxatdan o'tganlar: {total} ta\n\n🌐 Tilni tanlang:",
        "lang_selected": "✅ {lang_name} tili tanlandi!\n👥 Ro'yxatdan o'tganlar: {total} ta",
        "start_reg": "📝 Ro'yxatdan o'tish",
        "full_name": "✍️ Ism va familiyangizni to'liq kiriting:",
        "full_name_error": "❌ Ism va familiyani to'liq kiriting (kamida 3 ta harf).",
        "age": "🧍 Yoshingizni kiriting (raqamda):",
        "age_error": "❌ Yosh 5-80 oralig'ida bo'lishi kerak.",
        "branch": "📍 Qaysi filialda o'qimoqchisiz?",
        "level": "📊 Qaysi darajada o'qimoqchisiz?",
        "phone": "📱 Telefon raqamingizni yuboring\n(Misol: +998901234567)",
        "phone_invalid": "❌ Iltimos, to'g'ri telefon raqamini kiriting (+998 bilan boshlansin).",
        "phone_saved": "✅ Telefon raqamingiz qabul qilindi.",
        "test_start": "📝 {test_name}\n\n📋 Jami savollar: {total} ta\n⏱️ Har bir savolga: {time} soniya",
        "test_question": "📝 Savol {current}/{total}\n⏱️ Vaqt: {time}s\n\n{question}",
        "test_finish": "✅ Test yakunlandi!\n📊 Natijangiz: {correct}/{total} to'g'ri javob\n💯 Foiz: {percent}%",
        "test_results_detail": "📋 <b>TAFSILIY NATIJALAR:</b>\n\n{details}\n\n✍️ Endi writing qismiga o'tamiz!",
        "writing_task": "✍️ WRITING TASK\n\nWrite a letter to your parents about your holiday (100-150 words).\n\nJavobingizni matn ko'rinishida yuboring:",
        "writing_short": "❌ Javob juda qisqa! Kamida 50 ta belgi yozing.",
        "writing_sent": "✅ Writing javobingiz saqlandi va adminga yuborildi!\n\nAdmin tekshirgandan so'ng siz bilan bog'lanadi. Rahmat! 🎉",
        "saved": "✅ Saqlandi.",
        "success": "✅ Siz guruhga ro'yxatga olindingiz!",
        "admin_contact": "📞 Endi tez orada adminlar siz bilan bog'lanadi.\n\nRahmat! 🎉",
        "not_admin": "❌ Siz admin emassiz!",
        "cancelled": "❌ Jarayon bekor qilindi.",
        "unknown": "❓ Iltimos, /start buyrug'ini bosing yoki menyudan tanlang.",
        "timer_expired": "⏱️ Vaqt tugadi! Keyingi savolga o'tamiz...",
        "answer_accepted": "✅ Javob qabul qilindi",
        "send_title": "📨 TARQATISH\n👥 {count} ta foydalanuvchi",
        "send_text": "📝 Matn",
        "send_photo": "📷 Rasm",
        "send_video": "🎥 Video",
        "send_cancel": "❌ Bekor qilish",
        "enter_text": "📝 MATN KIRITING:\n/cancel - bekor qilish",
        "send_photo_prompt": "📷 Rasm yuboring:",
        "send_video_prompt": "🎥 Video yuboring:",
        "confirm_send": "📨 Tayyor! Yuborilsinmi?",
        "sending": "📤 Yuborilmoqda... {percent}% ({current}/{total})",
        "send_done": "✅ YAKUNLANDI!\n✅ {success} | ❌ {fail}",
        "empty_list": "⚠️ Ro'yxat bo'sh!"
    },
    "en": {
        "welcome": "🎓 Welcome to our Education Center!\n\n👥 Registered users: {total}\n\n🌐 Select your language:",
        "lang_selected": "✅ {lang_name} language selected!\n👥 Registered users: {total}",
        "start_reg": "📝 Start Registration",
        "full_name": "✍️ Please enter your full name:",
        "full_name_error": "❌ Please enter your full name (at least 3 characters).",
        "age": "🧍 Please enter your age (as a number):",
        "age_error": "❌ Age must be between 5 and 80.",
        "branch": "📍 Which branch would you like to study at?",
        "level": "📊 Which level would you like to study at?",
        "phone": "📱 Please send your phone number\n(Example: +998901234567)",
        "phone_invalid": "❌ Please enter a valid phone number (starting with +998).",
        "phone_saved": "✅ Your phone number has been accepted.",
        "test_start": "📝 {test_name}\n\n📋 Total questions: {total}\n⏱️ Time per question: {time} seconds",
        "test_question": "📝 Question {current}/{total}\n⏱️ Time: {time}s\n\n{question}",
        "test_finish": "✅ Test completed!\n📊 Your result: {correct}/{total} correct answers\n💯 Percentage: {percent}%",
        "test_results_detail": "📋 <b>DETAILED RESULTS:</b>\n\n{details}\n\n✍️ Now let's move to the writing section!",
        "writing_task": "✍️ WRITING TASK\n\nWrite a letter to your parents about your holiday (100-150 words).\n\nPlease send your answer as text:",
        "writing_short": "❌ Answer is too short! Please write at least 50 characters.",
        "writing_sent": "✅ Your writing answer has been saved and sent to the admin!\n\nThe admin will contact you after review. Thank you! 🎉",
        "saved": "✅ Saved.",
        "success": "✅ You have been registered to the group!",
        "admin_contact": "📞 Admins will contact you soon.\n\nThank you! 🎉",
        "not_admin": "❌ You are not an admin!",
        "cancelled": "❌ Process cancelled.",
        "unknown": "❓ Please use /start command or select from menu.",
        "timer_expired": "⏱️ Time's up! Moving to next question...",
        "answer_accepted": "✅ Answer accepted",
        "send_title": "📨 BROADCAST\n👥 {count} users",
        "send_text": "📝 Text",
        "send_photo": "📷 Photo",
        "send_video": "🎥 Video",
        "send_cancel": "❌ Cancel",
        "enter_text": "📝 ENTER TEXT:\n/cancel to cancel",
        "send_photo_prompt": "📷 Please send a photo:",
        "send_video_prompt": "🎥 Please send a video:",
        "confirm_send": "📨 Ready! Send now?",
        "sending": "📤 Sending... {percent}% ({current}/{total})",
        "send_done": "✅ COMPLETED!\n✅ {success} | ❌ {fail}",
        "empty_list": "⚠️ User list is empty!"
    },
    "ru": {
        "welcome": "🎓 Добро пожаловать в наш учебный центр!\n\n👥 Зарегистрировано пользователей: {total}\n\n🌐 Выберите язык:",
        "lang_selected": "✅ Выбран язык: {lang_name}!\n👥 Зарегистрировано: {total}",
        "start_reg": "📝 Начать регистрацию",
        "full_name": "✍️ Пожалуйста, введите ваше полное имя:",
        "full_name_error": "❌ Пожалуйста, введите полное имя (минимум 3 символа).",
        "age": "🧍 Пожалуйста, введите ваш возраст (числом):",
        "age_error": "❌ Возраст должен быть от 5 до 80 лет.",
        "branch": "📍 В каком филиале вы хотите учиться?",
        "level": "📊 На каком уровне вы хотите учиться?",
        "phone": "📱 Пожалуйста, отправьте ваш номер телефона\n(Пример: +998901234567)",
        "phone_invalid": "❌ Пожалуйста, введите правильный номер телефона (начинается с +998).",
        "phone_saved": "✅ Ваш номер телефона принят.",
        "test_start": "📝 {test_name}\n\n📋 Всего вопросов: {total}\n⏱️ Время на вопрос: {time} секунд",
        "test_question": "📝 Вопрос {current}/{total}\n⏱️ Время: {time}с\n\n{question}",
        "test_finish": "✅ Тест завершён!\n📊 Ваш результат: {correct}/{total} правильных ответов\n💯 Процент: {percent}%",
        "test_results_detail": "📋 <b>ПОДРОБНЫЕ РЕЗУЛЬТАТЫ:</b>\n\n{details}\n\n✍️ Теперь переходим к части writing!",
        "writing_task": "✍️ WRITING TASK\n\nWrite a letter to your parents about your holiday (100-150 words).\n\nПожалуйста, отправьте ваш ответ текстом:",
        "writing_short": "❌ Ответ слишком короткий! Напишите минимум 50 символов.",
        "writing_sent": "✅ Ваш ответ writing сохранён и отправлен админу!\n\nАдмин свяжется с вами после проверки. Спасибо! 🎉",
        "saved": "✅ Сохранено.",
        "success": "✅ Вы зарегистрированы в группе!",
        "admin_contact": "📞 Админы скоро свяжутся с вами.\n\nСпасибо! 🎉",
        "not_admin": "❌ Вы не администратор!",
        "cancelled": "❌ Процесс отменён.",
        "unknown": "❓ Пожалуйста, используйте команду /start или выберите из меню.",
        "timer_expired": "⏱️ Время вышло! Переходим к следующему вопросу...",
        "answer_accepted": "✅ Ответ принят",
        "send_title": "📨 РАССЫЛКА\n👥 {count} пользователей",
        "send_text": "📝 Текст",
        "send_photo": "📷 Фото",
        "send_video": "🎥 Видео",
        "send_cancel": "❌ Отмена",
        "enter_text": "📝 ВВЕДИТЕ ТЕКСТ:\n/cancel для отмены",
        "send_photo_prompt": "📷 Пожалуйста, отправьте фото:",
        "send_video_prompt": "🎥 Пожалуйста, отправьте видео:",
        "confirm_send": "📨 Готово! Отправить?",
        "sending": "📤 Отправка... {percent}% ({current}/{total})",
        "send_done": "✅ ЗАВЕРШЕНО!\n✅ {success} | ❌ {fail}",
        "empty_list": "⚠️ Список пользователей пуст!"
    }
}

LANG_NAMES = {
    "uz": "🇺🇿 O'zbekcha",
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский"
}

# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 6: TEST SAVOLLARI - ELEMENTARY (67 ta)
# ═══════════════════════════════════════════════════════════════

elementary_questions = [
    {"q": "1. My sisters _____ both very pretty.", "a": ["A) have", "B) are", "C) is", "D) has"], "c": "B"},
    {"q": "2. My little sister, Rosie, _____ only ten.", "a": ["A) are", "B) is", "C) have", "D) has"], "c": "B"},
    {"q": "3. Our house _____ a big garden.", "a": ["A) have", "B) are", "C) is", "D) has"], "c": "D"},
    {"q": "4. Our parents both _____ jobs in town.", "a": ["A) has", "B) is", "C) are", "D) have"], "c": "D"},
    {"q": "5. My school _____ 20 classrooms.", "a": ["A) have", "B) has", "C) are", "D) is"], "c": "B"},
    {"q": "6. I _____ a lot of friends.", "a": ["A) has", "B) is", "C) have", "D) are"], "c": "C"},
    {"q": "7. We _____ all very happy at school.", "a": ["A) has", "B) have", "C) is", "D) are"], "c": "D"},
    {"q": "8. I went there _____ Wednesday.", "a": ["A) in", "B) at", "C) on", "D) to"], "c": "C"},
    {"q": "9. I went there _____ 8 o'clock.", "a": ["A) on", "B) in", "C) at", "D) by"], "c": "C"},
    {"q": "10. I went there _____ the morning.", "a": ["A) on", "B) in", "C) at", "D) by"], "c": "B"},
    {"q": "11. I went there _____ week.", "a": ["A) on", "B) in", "C) last", "D) at"], "c": "C"},
    {"q": "12. I went there _____ 2017.", "a": ["A) on", "B) at", "C) in", "D) by"], "c": "C"},
    {"q": "13. I went there _____ month.", "a": ["A) last", "B) in", "C) on", "D) at"], "c": "A"},
    {"q": "14. I went there _____ June 3rd.", "a": ["A) in", "B) at", "C) on", "D) by"], "c": "C"},
    {"q": "15. I went there _____ the weekend.", "a": ["A) on", "B) in", "C) at", "D) by"], "c": "C"},
    {"q": "16. I went there _____ Monday morning.", "a": ["A) in", "B) at", "C) on", "D) by"], "c": "C"},
    {"q": "17. I went there _____ evening.", "a": ["A) last", "B) yesterday", "C) tomorrow", "D) next"], "c": "B"},
    {"q": "18. _____ are you doing?", "a": ["A) Where", "B) When", "C) What", "D) Who"], "c": "C"},
    {"q": "19. _____ are you going?", "a": ["A) What", "B) When", "C) Where", "D) Who"], "c": "C"},
    {"q": "20. _____ are you leaving?", "a": ["A) Where", "B) When", "C) What", "D) How"], "c": "B"},
    {"q": "21. _____ are you going with?", "a": ["A) What", "B) Where", "C) When", "D) Who"], "c": "D"},
    {"q": "22. _____ are you staying?", "a": ["A) When", "B) What", "C) Where", "D) Who"], "c": "C"},
    {"q": "23. _____ are you going to travel?", "a": ["A) Where", "B) When", "C) What", "D) How"], "c": "D"},
    {"q": "24. _____ are you going to stay?", "a": ["A) How much", "B) How long", "C) How many", "D) What"], "c": "B"},
    {"q": "25. _____ is it going to cost?", "a": ["A) How long", "B) How many", "C) How much", "D) What"], "c": "C"},
    {"q": "26. Choose correct:", "a": ["A) I'd like to leave early", "B) I like leave early"], "c": "A"},
    {"q": "27. Choose correct:", "a": ["A) Do you like your job?", "B) Would you like your job?"], "c": "A"},
    {"q": "28. Choose correct:", "a": ["A) Would you like tea or coffee?", "B) You like tea or coffee?"], "c": "A"},
    {"q": "29. Choose correct:", "a": ["A) I'd love some cake", "B) I'd love any cake"], "c": "A"},
    {"q": "30. Choose correct:", "a": ["A) They'd like something to eat", "B) They like something to eat"], "c": "A"},
    {"q": "31. Choose correct:", "a": ["A) I don't need any stamps", "B) I don't need some stamps"], "c": "A"},
    {"q": "32. Find mistake: 'What l you doing this evening?'", "a": ["A) What", "B) l", "C) you", "D) doing"],
     "c": "B"},
    {"q": "33. Find mistake: 'I'm going see some friends tonight.'",
     "a": ["A) I'm", "B) going", "C) see", "D) friends"], "c": "C"},
    {"q": "34. Find mistake: 'When they going to France?'", "a": ["A) When", "B) they", "C) going", "D) France"],
     "c": "B"},
    {"q": "35. Find mistake: 'She seeing the doctor tomorrow.'",
     "a": ["A) She", "B) seeing", "C) doctor", "D) tomorrow"], "c": "B"},
    {"q": "36. Find mistake: 'What time are you to leave?'", "a": ["A) What", "B) are", "C) you", "D) to leave"],
     "c": "D"},
    {"q": "37. Find mistake: 'I going to the cinema on Saturday evening.'",
     "a": ["A) I", "B) going", "C) cinema", "D) Saturday"], "c": "B"},
    {"q": "38. Odd one out:", "a": ["A) train", "B) bus", "C) bridge", "D) motorbike"], "c": "C"},
    {"q": "39. Odd one out:", "a": ["A) wife", "B) waiter", "C) daughter", "D) grandfather"], "c": "B"},
    {"q": "40. Odd one out:", "a": ["A) lovely", "B) fantastic", "C) amazing", "D) awful"], "c": "D"},
    {"q": "41. Odd one out:", "a": ["A) trainers", "B) trousers", "C) socks", "D) boots"], "c": "B"},
    {"q": "42. Odd one out:", "a": ["A) desk", "B) armchair", "C) sofa", "D) laptop"], "c": "D"},
    {"q": "43. Odd one out:", "a": ["A) actor", "B) journalist", "C) cooker", "D) builder"], "c": "C"},
    {"q": "44. get → _____", "a": ["A) getted", "B) got", "C) gotten", "D) getting"], "c": "B"},
    {"q": "45. buy → _____", "a": ["A) buyed", "B) bought", "C) buyt", "D) buying"], "c": "B"},
    {"q": "46. have → _____", "a": ["A) haved", "B) had", "C) has", "D) having"], "c": "B"},
    {"q": "47. meet → _____", "a": ["A) meeted", "B) met", "C) meet", "D) meeting"], "c": "B"},
    {"q": "48. do → _____", "a": ["A) doed", "B) done", "C) did", "D) doing"], "c": "C"},
    {"q": "49. go → _____", "a": ["A) goed", "B) gone", "C) went", "D) going"], "c": "C"},
    {"q": "50. see → _____", "a": ["A) see", "B) saw", "C) seen", "D) seeing"], "c": "B"},
    {"q": "51. leave → _____", "a": ["A) leaved", "B) left", "C) leave", "D) leaving"], "c": "B"},
    {"q": "52. I ran ten miles. I'm hot and _____", "a": ["A) cold", "B) thirsty", "C) hungry", "D) tired"], "c": "B"},
    {"q": "53. No coat, snowing. I'm _____", "a": ["A) hot", "B) cold", "C) tired", "D) bored"], "c": "B"},
    {"q": "54. Only apple for lunch. I'm so _____", "a": ["A) thirsty", "B) tired", "C) hungry", "D) worried"],
     "c": "C"},
    {"q": "55. Got up at 5am. I look _____", "a": ["A) hungry", "B) thirsty", "C) tired", "D) bored"], "c": "C"},
    {"q": "56. Nothing to do! We're _____", "a": ["A) tired", "B) bored", "C) worried", "D) hungry"], "c": "B"},
    {"q": "57. Want to live somewhere _____ all year.", "a": ["A) cold", "B) hot", "C) tired", "D) bored"], "c": "B"},
    {"q": "58. Can't stop sneezing. I have _____", "a": ["A) hot", "B) cold", "C) a cold", "D) tired"], "c": "C"},
    {"q": "59. Important exam tomorrow. I look _____", "a": ["A) bored", "B) tired", "C) worried", "D) hungry"],
     "c": "C"},
    {"q": "60. The Beckhams' children are all boys.", "a": ["A) True", "B) False"], "c": "B", "reading": True},
    {"q": "61. David Beckham is a footballer and works for UNICEF.", "a": ["A) True", "B) False"], "c": "A",
     "reading": True},
    {"q": "62. David's wife, Victoria, is a fashion model.", "a": ["A) True", "B) False"], "c": "B", "reading": True},
    {"q": "63. Their daughter is a model for Burberry.", "a": ["A) True", "B) False"], "c": "B", "reading": True},
    {"q": "64. Brooklyn sometimes works in a shop.", "a": ["A) True", "B) False"], "c": "A", "reading": True},
    {"q": "65. Louise is David's sister.", "a": ["A) True", "B) False"], "c": "B", "reading": True},
    {"q": "66. They have houses in England and America.", "a": ["A) True", "B) False"], "c": "A", "reading": True},
    {"q": "67. They all like family time at home.", "a": ["A) True", "B) False"], "c": "A", "reading": True},
]

# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 7: PRE-INTERMEDIATE (100 ta)
# ═══════════════════════════════════════════════════════════════

pre_intermediate_questions = [
    {"q": "1. What's _____ job?", "a": ["A) your", "B) yours", "C) you"], "c": "A"},
    {"q": "2. The traffic is _____ than it was many years ago.", "a": ["A) badder", "B) more bad", "C) worse"],
     "c": "C"},
    {"q": "3. I've _____ washed the floor. It's wet.", "a": ["A) already", "B) just", "C) yet"], "c": "B"},
    {"q": "4. He has the same car _____ his sister.", "a": ["A) as", "B) like", "C) than"], "c": "A"},
    {"q": "5. The girl on the picture _____ a blue dress.", "a": ["A) wears", "B) wearing", "C) is wearing"], "c": "C"},
    {"q": "6. My mother doesn't enjoy _____ by plane.", "a": ["A) travel", "B) travelling", "C) to travel"], "c": "B"},
    {"q": "7. I can't come because I _____ to study.", "a": ["A) must", "B) have", "C) has"], "c": "B"},
    {"q": "8. What would you do if you _____ the Loch Ness monster?", "a": ["A) saw", "B) will see", "C) see"],
     "c": "A"},
    {"q": "9. My brother _____ glasses.", "a": ["A) used to wear", "B) use to wear", "C) used to wearing"], "c": "A"},
    {"q": "10. 'My father loves Jazz' '_____!'", "a": ["A) So I do", "B) So am I", "C) So do I"], "c": "C"},
    {"q": "11. They've known each other _____ a long time.", "a": ["A) For", "B) Since"], "c": "A"},
    {"q": "12. She's studied English literature _____ five years.", "a": ["A) For", "B) Since"], "c": "A"},
    {"q": "13. He's been married _____ last September.", "a": ["A) For", "B) Since"], "c": "B"},
    {"q": "14. You've worn these old trainers _____ Christmas!", "a": ["A) For", "B) Since"], "c": "B"},
    {"q": "15. I've been working in London _____ 1998.", "a": ["A) For", "B) Since"], "c": "B"},
    {"q": "16. Past of 'break'?", "a": ["A) broke", "B) broken", "C) breaked"], "c": "A"},
    {"q": "17. Past of 'come'?", "a": ["A) came", "B) come", "C) comed"], "c": "A"},
    {"q": "18. Past of 'cost'?", "a": ["A) costed", "B) cost", "C) costing"], "c": "B"},
    {"q": "19. Past of 'build'?", "a": ["A) builded", "B) built", "C) building"], "c": "B"},
    {"q": "20. Past of 'eat'?", "a": ["A) ate", "B) eaten", "C) eated"], "c": "A"},
    {"q": "21. Opposite of 'rude'?", "a": ["A) polite", "B) loud", "C) angry"], "c": "A"},
    {"q": "22. Opposite of 'noisy'?", "a": ["A) quiet", "B) loud", "C) busy"], "c": "A"},
    {"q": "23. Opposite of 'possible'?", "a": ["A) impossible", "B) probable", "C) likely"], "c": "A"},
    {"q": "24. Opposite of 'dangerous'?", "a": ["A) safe", "B) risky", "C) harmful"], "c": "A"},
    {"q": "25. Opposite of 'patient'?", "a": ["A) impatient", "B) calm", "C) kind"], "c": "A"},
    {"q": "26. I saw a really _____ TV programme.", "a": ["A) interesting", "B) interested"], "c": "A"},
    {"q": "27. She failed all her exams, so she feels _____.", "a": ["A) disappointed", "B) disappointing"], "c": "A"},
    {"q": "28. My job is very _____.", "a": ["A) boring", "B) bored"], "c": "A"},
    {"q": "29. We had a very _____ holiday.", "a": ["A) relaxing", "B) relaxed"], "c": "A"},
    {"q": "30. I work too much. Now I feel really _____.", "a": ["A) tired", "B) tiring"], "c": "A"},
    {"q": "31. _____ are you doing this weekend?", "a": ["A) What", "B) How", "C) Where"], "c": "A"},
    {"q": "32. _____ English next year?",
     "a": ["A) Are you going to study", "B) Do you going study", "C) You are study"], "c": "A"},
    {"q": "33. _____ do you think will win the next elections?", "a": ["A) Who", "B) Whom", "C) Which"], "c": "A"},
    {"q": "34. _____ do you remember your dreams?", "a": ["A) How often", "B) When", "C) What"], "c": "A"},
    {"q": "35. _____ do you think it will rain tomorrow?", "a": ["A) Do", "B) Does", "C) Will"], "c": "A"},
    {"q": "36. Odd one out: SHIRT WORK COAT SKIRT", "a": ["A) WORK", "B) SHIRT", "C) COAT"], "c": "A"},
    {"q": "37. Odd one out: BLOUSE BOUGHT TROUSERS MOUTH", "a": ["A) MOUTH", "B) BLOUSE", "C) TROUSERS"], "c": "A"},
    {"q": "38. Odd one out: MAKE GREAT EARN TRAINERS", "a": ["A) TRAINERS", "B) MAKE", "C) EARN"], "c": "A"},
    {"q": "39. Odd one out: DECIDE LIKE PROMISE TIRED", "a": ["A) TIRED", "B) DECIDE", "C) PROMISE"], "c": "A"},
    {"q": "40. Odd one out: ZOO FOOD BOOK YOU'LL", "a": ["A) YOU'LL", "B) ZOO", "C) FOOD"], "c": "A"},
    {"q": "41. This connects your head to your body.", "a": ["A) head", "B) neck", "C) knee"], "c": "B"},
    {"q": "42. This is between your hand and your arm.", "a": ["A) neck", "B) elbow", "C) wrist"], "c": "C"},
    {"q": "43. You see with these.", "a": ["A) ears", "B) hair", "C) eyes"], "c": "C"},
    {"q": "44. You use this to smell.", "a": ["A) nose", "B) eye", "C) head"], "c": "A"},
    {"q": "45. This is the upper part of your leg.", "a": ["A) toe", "B) ankle", "C) thigh"], "c": "C"},
    {"q": "46. Plural of 'child'?", "a": ["A) children", "B) childs", "C) childes"], "c": "A"},
    {"q": "47. Plural of 'party'?", "a": ["A) partys", "B) parties", "C) partyes"], "c": "B"},
    {"q": "48. Plural of 'glass'?", "a": ["A) glasss", "B) glasses", "C) glass"], "c": "B"},
    {"q": "49. Plural of 'way'?", "a": ["A) ways", "B) waies", "C) way"], "c": "A"},
    {"q": "50. Plural of 'church'?", "a": ["A) churchs", "B) churches", "C) churchees"], "c": "B"},
    {"q": "51. It's the person _____ serves you in a café.", "a": ["A) WHO", "B) WHICH", "C) WHERE"], "c": "A"},
    {"q": "52. It's the kind of food _____ keeps vampires away.", "a": ["A) WHO", "B) WHICH", "C) WHERE"], "c": "B"},
    {"q": "53. It's a place _____ you can buy books.", "a": ["A) WHO", "B) WHICH", "C) WHERE"], "c": "C"},
    {"q": "54. It's a place _____ you can borrow books.", "a": ["A) WHO", "B) WHICH", "C) WHERE"], "c": "C"},
    {"q": "55. It's a thing _____ you use to open doors.", "a": ["A) WHO", "B) WHICH", "C) WHERE"], "c": "B"},
    {"q": "56. Stressed syllable in 'INTERESTING'?", "a": ["A) IN", "B) TER", "C) EST"], "c": "B"},
    {"q": "57. Stressed syllable in 'REMEMBER'?", "a": ["A) RE", "B) MEM", "C) BER"], "c": "B"},
    {"q": "58. Stressed syllable in 'IMPORTANT'?", "a": ["A) IM", "B) POR", "C) TANT"], "c": "B"},
    {"q": "59. Stressed syllable in 'DECISION'?", "a": ["A) DE", "B) CI", "C) SION"], "c": "B"},
    {"q": "60. Stressed syllable in 'SOMEBODY'?", "a": ["A) SOME", "B) BO", "C) DY"], "c": "A"},
    {"q": "61. Where did you _____ your husband?", "a": ["A) meet", "B) know"], "c": "A"},
    {"q": "62. Shh! They're _____ an exam.", "a": ["A) making", "B) doing"], "c": "B"},
    {"q": "63. How much money does he _____ working in England?", "a": ["A) win", "B) earn"], "c": "B"},
    {"q": "64. He was _____ a black umbrella.", "a": ["A) carrying", "B) wearing"], "c": "A"},
    {"q": "65. You _____ your father.", "a": ["A) look", "B) look like"], "c": "B"},
    {"q": "66. When I'm tired I don't want to see _____.", "a": ["A) nobody", "B) anybody"], "c": "B"},
    {"q": "67. She's just _____ her exams.", "a": ["A) taken", "B) passed"], "c": "B"},
    {"q": "68. You should _____ for the bus.", "a": ["A) wait", "B) hope"], "c": "A"},
    {"q": "69. They _____ TV everyday for at least 3 hours.", "a": ["A) look at", "B) watch"], "c": "B"},
    {"q": "70. She won the first _____ in a competition.", "a": ["A) price", "B) prize"], "c": "B"},
    {"q": "71. Lady Morton has had a lot of accidents.", "a": ["A) True", "B) False"], "c": "B", "reading": True},
    {"q": "72. She bought a Nissan Micra.", "a": ["A) True", "B) False"], "c": "B", "reading": True},
    {"q": "73. She couldn't see the traffic island because it had no lights.", "a": ["A) True", "B) False"], "c": "A",
     "reading": True},
    {"q": "74. She wasn't badly hurt.", "a": ["A) True", "B) False"], "c": "A", "reading": True},
    {"q": "75. After her latest accident she needs a new car.", "a": ["A) True", "B) False"], "c": "B",
     "reading": True},
    {"q": "76. She thinks she's a safe driver.", "a": ["A) True", "B) False"], "c": "A", "reading": True},
    {"q": "77. The amount of traffic isn't a problem for her.", "a": ["A) True", "B) False"], "c": "A",
     "reading": True},
    {"q": "78. My mobile stopped working when we went _____ a tunnel.", "a": ["A) ACROSS", "B) THROUGH"], "c": "B"},
    {"q": "79. The plane flew _____ the fields.", "a": ["A) ON", "B) OVER"], "c": "B"},
    {"q": "80. Come _____. The door is open.", "a": ["A) IN", "B) OUT"], "c": "A"},
    {"q": "81. If you go _____ the church, you'll see the school.", "a": ["A) OVER", "B) PAST"], "c": "B"},
    {"q": "82. Don't forget to write _____ me.", "a": ["A) TO", "B) FOR"], "c": "A"},
    {"q": "83. Are you listening _____ the teacher?", "a": ["A) AT", "B) TO"], "c": "B"},
    {"q": "84. He was waiting _____ a phone call.", "a": ["A) FOR", "B) TO"], "c": "A"},
    {"q": "85. I don't agree _____ you.", "a": ["A) WITH", "B) AT"], "c": "A"},
    {"q": "86. They wanted to speak _____ the hotel manager.", "a": ["A) TO", "B) WITH"], "c": "A"},
    {"q": "87. Cross out silent letter in KNIFE.", "a": ["A) K", "B) N"], "c": "A"},
    {"q": "88. Cross out silent letter in ANSWER.", "a": ["A) W", "B) E"], "c": "A"},
    {"q": "89. Delhi is the _____ city I've ever been to.", "a": ["A) busier", "B) busiest"], "c": "B"},
    {"q": "90. The restaurants are _____ than last time.", "a": ["A) more expensive", "B) expensiver"], "c": "A"},
    {"q": "91. In London the buses are _____ than the tube.", "a": ["A) slower", "B) slowest"], "c": "A"},
    {"q": "92. Harrods is the _____ shop in the world.", "a": ["A) gooder", "B) best"], "c": "B"},
    {"q": "93. _____ records did ABBA sell?", "a": ["A) How many", "B) How much"], "c": "A"},
    {"q": "94. _____ happened to them at the end?", "a": ["A) What", "B) When"], "c": "A"},
    {"q": "95. _____ ABBA song do you prefer?", "a": ["A) Which", "B) What"], "c": "A"},
    {"q": "96. Plural of 'key'?", "a": ["A) keys", "B) kies"], "c": "A"},
    {"q": "97. Plural of 'toy'?", "a": ["A) toies", "B) toys"], "c": "B"},
    {"q": "98. Plural of 'baby'?", "a": ["A) babys", "B) babies"], "c": "B"},
    {"q": "99. Plural of 'tooth'?", "a": ["A) tooths", "B) teeth"], "c": "B"},
    {"q": "100. Plural of 'sandwich'?", "a": ["A) sandwichs", "B) sandwiches"], "c": "B"},
]

# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 8: INTERMEDIATE (45 ta)
# ═══════════════════════════════════════════════════════════════

intermediate_questions = [
    {"q": "1. She _____ to the gym three times a week.", "a": ["A) goes", "B) is going", "C) go"], "c": "A"},
    {"q": "2. I _____ TV when the phone rang.", "a": ["A) watched", "B) was watching", "C) am watching"], "c": "B"},
    {"q": "3. He has lived here _____ 2010.", "a": ["A) for", "B) since", "C) ago"], "c": "B"},
    {"q": "4. We _____ here for two hours.", "a": ["A) have been waiting", "B) are waiting", "C) waited"], "c": "A"},
    {"q": "5. If I _____ rich, I would buy a yacht.", "a": ["A) am", "B) was", "C) were"], "c": "C"},
    {"q": "6. The book _____ by millions of people.", "a": ["A) has been read", "B) read", "C) is reading"], "c": "A"},
    {"q": "7. I enjoy _____ in the morning.", "a": ["A) to run", "B) running", "C) run"], "c": "B"},
    {"q": "8. This is the _____ movie I've ever seen.", "a": ["A) good", "B) better", "C) best"], "c": "C"},
    {"q": "9. She said she _____ call me later.", "a": ["A) will", "B) would", "C) can"], "c": "B"},
    {"q": "10. I wish I _____ taller.", "a": ["A) am", "B) was", "C) were"], "c": "C"},
    {"q": "11. By the time we arrived, the film _____.", "a": ["A) started", "B) had started", "C) has started"],
     "c": "B"},
    {"q": "12. He denied _____ the money.", "a": ["A) to steal", "B) stealing", "C) steal"], "c": "B"},
    {"q": "13. I look forward _____ from you.", "a": ["A) to hear", "B) to hearing", "C) hear"], "c": "B"},
    {"q": "14. The police officer asked me _____ I saw the accident.", "a": ["A) if", "B) do", "C) did"], "c": "A"},
    {"q": "15. It's time we _____ home.", "a": ["A) go", "B) went", "C) going"], "c": "B"},
    {"q": "16. The cake tastes _____.", "a": ["A) good", "B) well", "C) goodly"], "c": "A"},
    {"q": "17. She is used to _____ early.", "a": ["A) get up", "B) getting up", "C) got up"], "c": "B"},
    {"q": "18. I'll call you as soon as I _____ there.", "a": ["A) arrive", "B) will arrive", "C) arrived"], "c": "A"},
    {"q": "19. Despite _____ tired, he finished the work.", "a": ["A) he was", "B) being", "C) to be"], "c": "B"},
    {"q": "20. The meeting has been postponed _____ Monday.", "a": ["A) to", "B) until", "C) for"], "c": "B"},
    {"q": "21. Synonym for 'happy'?", "a": ["A) joyful", "B) sad", "C) angry"], "c": "A"},
    {"q": "22. Synonym for 'fast'?", "a": ["A) quick", "B) slow", "C) lazy"], "c": "A"},
    {"q": "23. Synonym for 'big'?", "a": ["A) large", "B) small", "C) tiny"], "c": "A"},
    {"q": "24. Synonym for 'difficult'?", "a": ["A) hard", "B) easy", "C) simple"], "c": "A"},
    {"q": "25. Synonym for 'smart'?", "a": ["A) intelligent", "B) stupid", "C) dumb"], "c": "A"},
    {"q": "26. Correct: He don't like coffee.", "a": ["A) He doesn't like", "B) He don't likes"], "c": "A"},
    {"q": "27. Correct: She has went home.", "a": ["A) She has gone", "B) She has go"], "c": "A"},
    {"q": "28. Correct: I am agree with you.", "a": ["A) I agree", "B) I am agreeing"], "c": "A"},
    {"q": "29. Correct: They was playing football.", "a": ["A) They were playing", "B) They was play"], "c": "A"},
    {"q": "30. Correct: We have been knowing him for years.", "a": ["A) We have known", "B) We have been know"],
     "c": "A"},
    {"q": "31. I need to buy _____ milk.", "a": ["A) some", "B) a", "C) many"], "c": "A"},
    {"q": "32. There are _____ apples on the table.", "a": ["A) any", "B) some", "C) much"], "c": "B"},
    {"q": "33. Do you have _____ brothers?", "a": ["A) some", "B) any", "C) much"], "c": "B"},
    {"q": "34. I haven't seen him _____ last year.", "a": ["A) for", "B) since", "C) ago"], "c": "B"},
    {"q": "35. She left ten minutes _____.", "a": ["A) for", "B) since", "C) ago"], "c": "C"},
    {"q": "36. He is _____ than his brother.", "a": ["A) tall", "B) taller", "C) tallest"], "c": "B"},
    {"q": "37. This is the _____ building in the city.", "a": ["A) high", "B) higher", "C) highest"], "c": "C"},
    {"q": "38. The more you practice, the _____ you become.", "a": ["A) good", "B) better", "C) best"], "c": "B"},
    {"q": "39. I'd rather _____ at home tonight.", "a": ["A) stay", "B) to stay", "C) staying"], "c": "A"},
    {"q": "40. You _____ wear a helmet on the bike.", "a": ["A) must", "B) can", "C) might"], "c": "A"},
    {"q": "41. Reading: The author claims technology improves education. (T/F)", "a": ["A) True", "B) False"], "c": "A",
     "reading": True},
    {"q": "42. Reading: Students spend less time reading now.", "a": ["A) True", "B) False"], "c": "A",
     "reading": True},
    {"q": "43. Reading: Online courses are completely replacing schools.", "a": ["A) True", "B) False"], "c": "B",
     "reading": True},
    {"q": "44. Reading: Teachers are no longer needed.", "a": ["A) True", "B) False"], "c": "B", "reading": True},
    {"q": "45. Reading: The passage suggests a blended approach is best.", "a": ["A) True", "B) False"], "c": "A",
     "reading": True},
]

# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 9: PRE-IELTS (50 ta)
# ═══════════════════════════════════════════════════════════════

pre_ielts_questions = [
    {"q": "1. The house is _____ wood.", "a": ["A) made of", "B) built by", "C) looked like", "D) got"], "c": "A"},
    {"q": "2. The man owns three hotels. He's very _____.", "a": ["A) healthy", "B) unique", "C) wealthy", "D) poor"],
     "c": "C"},
    {"q": "3. We need more _____ like Elon Musk in society.",
     "a": ["A) poor people", "B) frugal people", "C) wealthy people", "D) generous"], "c": "C"},
    {"q": "4. I do not have enough _____ to make this dish.",
     "a": ["A) fur", "B) hamburgers", "C) stories", "D) spices"], "c": "D"},
    {"q": "5. We should try to _____ the amount of electricity we use.",
     "a": ["A) create", "B) include", "C) reduce", "D) taste"], "c": "C"},
    {"q": "6. The body and mind _____ well to healthy exercise.",
     "a": ["A) care", "B) respond", "C) reaction", "D) look after"], "c": "B"},
    {"q": "7. You should not ask _____ questions such as a person's age.",
     "a": ["A) international", "B) normal", "C) personal", "D) tropical"], "c": "C"},
    {"q": "8. Most _____, like ants, are very strong for their size.",
     "a": ["A) mammals", "B) insects", "C) birds", "D) reptiles"], "c": "B"},
    {"q": "9. Bill is a very _____ guy in our school.",
     "a": ["A) famous", "B) well-known", "C) popular", "D) spectacular"], "c": "C"},
    {"q": "10. Locking the door at night was my _____.",
     "a": ["A) activity", "B) diversity", "C) misery", "D) responsibility"], "c": "D"},
    {"q": "11. The copy _____ in our office broke down last week.",
     "a": ["A) machine", "B) press", "C) shop", "D) thing"], "c": "A"},
    {"q": "12. Bob likes films. He's a big film _____.", "a": ["A) man", "B) buff", "C) fan", "D) fancy"], "c": "B"},
    {"q": "13. _____ is more important at my school than mathematics.",
     "a": ["A) Athletes", "B) Athletically", "C) Athletics"], "c": "C"},
    {"q": "14. My doctor told me to _____ the amount of coffee I drink.",
     "a": ["A) ruin", "B) reduce", "C) spread", "D) grow"], "c": "B"},
    {"q": "15. Everyone has two _____. They look like beans.",
     "a": ["A) intestines", "B) stomachs", "C) hobbies", "D) kidneys"], "c": "D"},
    {"q": "16. The police finished their _____.",
     "a": ["A) evidence", "B) condition", "C) behavior", "D) investigation"], "c": "D"},
    {"q": "17. Miyazaki's movies _____ fantasy and reality.",
     "a": ["A) add", "B) combine", "C) detect", "D) investigate"], "c": "B"},
    {"q": "18. Please close the curtains. The sunlight is too _____.",
     "a": ["A) bright", "B) enormous", "C) ordinary", "D) serious"], "c": "A"},
    {"q": "19. When my dog shows good _____, I give him a snack.",
     "a": ["A) activity", "B) light", "C) taste", "D) behavior"], "c": "D"},
    {"q": "20. Passive: They have made hundreds of employees redundant. -> Hundreds of employees _____.",
     "a": ["A) have made redundant", "B) have been made redundant", "C) had made"], "c": "B"},
    {"q": "21. Compound: 'motor + _____' = vehicle race", "a": ["A) racing", "B) bike", "C) way"], "c": "A"},
    {"q": "22. Compound: 'news + _____' = program", "a": ["A) glasses", "B) paper", "C) agent"], "c": "B"},
    {"q": "23. Vocab: John's family is very poor. They live in _____.", "a": ["A) slums", "B) mansion", "C) villa"],
     "c": "A"},
    {"q": "24. Vocab: They are saving their every last _____ to buy a house.",
     "a": ["A) penny", "B) fortune", "C) bill"], "c": "A"},
    {"q": "25. Vocab: My grandmother is old and _____.", "a": ["A) frail", "B) strong", "C) energetic"], "c": "A"},
    {"q": "26. Vocab: Surfing is my _____.", "a": ["A) passion", "B) hobby", "C) job"], "c": "A"},
    {"q": "27. Vocab: Football players earn _____ amount of money.", "a": ["A) a fortune", "B) a penny", "C) little"],
     "c": "A"},
    {"q": "28. Vocab: Pandas are becoming _____.", "a": ["A) extinct", "B) abundant", "C) common"], "c": "A"},
    {"q": "29. Vocab: Tom tried to commit _____.", "a": ["A) suicide", "B) murder", "C) crime"], "c": "A"},
    {"q": "30. Vocab: Juliet felt _____ when Romeo was expelled.", "a": ["A) desperate", "B) happy", "C) calm"],
     "c": "A"},
    {"q": "31. Vocab: It doesn't matter if you are _____ or president.",
     "a": ["A) a rubbish collector", "B) a king", "C) rich"], "c": "A"},
    {"q": "32. Vocab: We shouldn't _____ to our children's demands.", "a": ["A) give in", "B) stand up", "C) look out"],
     "c": "A"},
    {"q": "33. Vocab: John wants to _____ swimming.", "a": ["A) take up", "B) give up", "C) put off"], "c": "A"},
    {"q": "34. Vocab: Having a massage is _____.", "a": ["A) relaxing", "B) stressing", "C) tiring"], "c": "A"},
    {"q": "35. Vocab: Everybody played by their own rules. The result was _____.",
     "a": ["A) chaos", "B) order", "C) peace"], "c": "A"},
    {"q": "36. Vocab: Horse riding is physically _____ sport.", "a": ["A) demanding", "B) easy", "C) simple"],
     "c": "A"},
    {"q": "37. Vocab: Peter came from a _____ family.", "a": ["A) dysfunctional", "B) perfect", "C) ideal"], "c": "A"},
    {"q": "38. Vocab: The laptop cost me _____.", "a": ["A) a fortune", "B) a penny", "C) nothing"], "c": "A"},
    {"q": "39. Vocab: He is playing _____.", "a": ["A) truant", "B) football", "C) music"], "c": "A"},
    {"q": "40. Vocab: She _____ my heart.", "a": ["A) conquered", "B) lost", "C) broke"], "c": "A"},
    {"q": "41. Vocab: I'm not _____ to spending time alone.", "a": ["A) accustomed", "B) used", "C) addicted"],
     "c": "A"},
    {"q": "42. Vocab: There is _____ noise in the city.", "a": ["A) constant", "B) rare", "C) little"], "c": "A"},
    {"q": "43. Vocab: This medicine has _____ effects.", "a": ["A) side", "B) main", "C) good"], "c": "A"},
    {"q": "44. Conditionals: If I _____ rich, I would travel.", "a": ["A) were", "B) am", "C) will be"], "c": "A"},
    {"q": "45. Verb Patterns: Sally _____ having an en-suite bathroom.", "a": ["A) loved", "B) wanted", "C) hoped"],
     "c": "A"},
    {"q": "46. Verb Patterns: She is _____ staying two more days.",
     "a": ["A) planning", "B) looking forward to", "C) hoping"], "c": "B"},
    {"q": "47. Reading: Khao San Road is authentic Thai.", "a": ["A) True", "B) False"], "c": "B", "reading": True},
    {"q": "48. Reading: Phra Kanong is further from tourist sites.", "a": ["A) True", "B) False"], "c": "A",
     "reading": True},
    {"q": "49. Reading: River boats get stuck in traffic.", "a": ["A) True", "B) False"], "c": "B", "reading": True},
    {"q": "50. Reading: Skytrain is faster than taxi.", "a": ["A) True", "B) False"], "c": "A", "reading": True},
]

# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 10: CEFR MULTILEVEL (58 ta)
# ═══════════════════════════════════════════════════════════════

cefr_questions = [
    {"q": "1. _____ you interested in sport?", "a": ["A) Be", "B) Am", "C) Is", "D) Are"], "c": "D"},
    {"q": "2. My _____ is a writer and his books are very popular.",
     "a": ["A) aunt", "B) uncle", "C) sister", "D) mother"], "c": "B"},
    {"q": "3. Paul is very _____. He's very good at art.",
     "a": ["A) honest", "B) friendly", "C) polite", "D) creative"], "c": "D"},
    {"q": "4. We live in the city centre and our house _____ have a big garden.",
     "a": ["A) doesn't", "B) isn't", "C) aren't", "D) don't"], "c": "A"},
    {"q": "5. I _____ arrive at school before nine o'clock.",
     "a": ["A) has to", "B) have to", "C) doesn't have to", "D) haven't to"], "c": "B"},
    {"q": "6. The beach was very crowded _____ Monday.", "a": ["A) in", "B) on", "C) at", "D) to"], "c": "B"},
    {"q": "7. You _____ eat all that cake! It isn't good for you.",
     "a": ["A) don't", "B) may not", "C) shouldn't", "D) will not"], "c": "C"},
    {"q": "8. Cathy _____ a game on her computer at the moment.",
     "a": ["A) plays", "B) is playing", "C) to play", "D) play"], "c": "B"},
    {"q": "9. There _____ a lot of people outside the school.", "a": ["A) are", "B) is", "C) be", "D) am"], "c": "A"},
    {"q": "10. _____ you like to come out with us tonight?", "a": ["A) Do", "B) Would", "C) Are", "D) Will"], "c": "B"},
    {"q": "11. How _____ time have we got to do this exercise?", "a": ["A) long", "B) many", "C) much", "D) quick"],
     "c": "C"},
    {"q": "12. Turn _____ and you'll see the museum on the left.",
     "a": ["A) on the right", "B) rightly", "C) by the right", "D) right"], "c": "D"},
    {"q": "13. Don't forget to get _____ the bus at Station Road.", "a": ["A) out", "B) off", "C) over", "D) down"],
     "c": "B"},
    {"q": "14. Tom got the _____ marks in the class for his homework.",
     "a": ["A) worse", "B) worst", "C) baddest", "D) most bad"], "c": "B"},
    {"q": "15. There wasn't _____ milk for breakfast this morning.", "a": ["A) a", "B) some", "C) the", "D) any"],
     "c": "D"},
    {"q": "16. My sister _____ speak French when she was only six.", "a": ["A) was", "B) should", "C) could", "D) had"],
     "c": "C"},
    {"q": "17. Did you _____ shopping after school yesterday?", "a": ["A) went", "B) goed", "C) going", "D) go"],
     "c": "D"},
    {"q": "18. I _____ five emails before school today.", "a": ["A) sent", "B) sended", "C) did send", "D) was send"],
     "c": "A"},
    {"q": "19. Our teacher speaks English _____ so that we can understand her.",
     "a": ["A) slow", "B) slower", "C) more slow", "D) slowly"], "c": "D"},
    {"q": "20. Quick – get the food inside! It _____ any moment.",
     "a": ["A) rains", "B) is raining", "C) is going to rain", "D) can rain"], "c": "C"},
    {"q": "21. I _____ the new Batman film yet. Is it any good?",
     "a": ["A) haven't seen", "B) didn't see", "C) don't see", "D) am not seen"], "c": "A"},
    {"q": "22. I hope you _____ a good time at the moment in Greece!",
     "a": ["A) are having", "B) have", "C) have had", "D) had"], "c": "A"},
    {"q": "23. I wanted to see Harry. How long ago _____?",
     "a": ["A) he left", "B) has he left", "C) did he leave", "D) could he leave"], "c": "C"},
    {"q": "24. Do students in your country have to stand _____ when the teacher arrives?",
     "a": ["A) on", "B) at", "C) in", "D) up"], "c": "D"},
    {"q": "25. Which train _____ for when I saw you on the platform?",
     "a": ["A) did you wait", "B) were you waiting", "C) have you waited", "D) are you waiting"], "c": "B"},
    {"q": "26. You _____ hurry as we've still got twenty minutes.",
     "a": ["A) mustn't", "B) can't", "C) may not", "D) needn't"], "c": "D"},
    {"q": "27. That car is _____ dangerous to drive.", "a": ["A) too", "B) enough", "C) not enough", "D) the worst"],
     "c": "A"},
    {"q": "28. I _____ you in the café at about 4.30, OK?",
     "a": ["A) 'll see", "B) am going to see", "C) am seeing", "D) see"], "c": "A"},
    {"q": "29. My father has been a pilot _____ twenty years.", "a": ["A) since", "B) for", "C) until", "D) by"],
     "c": "B"},
    {"q": "30. I really enjoy _____ new languages.", "a": ["A) to learn", "B) learning", "C) learn", "D) learned"],
     "c": "B"},
    {"q": "31. If we _____ in the countryside, we'd have better views.",
     "a": ["A) lived", "B) were live", "C) would live", "D) live"], "c": "A"},
    {"q": "32. I wish Joe _____ to Hawaii on holiday.",
     "a": ["A) doesn't go", "B) didn't go", "C) hasn't gone", "D) hadn't gone"], "c": "C"},
    {"q": "33. Could I possibly _____ some money for the bus fare?", "a": ["A) lend", "B) owe", "C) borrow", "D) need"],
     "c": "C"},
    {"q": "34. Sam asked me if I _____ a lift home after the concert.",
     "a": ["A) had wanted", "B) wanted", "C) would want", "D) want"], "c": "B"},
    {"q": "35. People say that an avalanche _____ by loud noises.",
     "a": ["A) causes", "B) has caused", "C) is causing", "D) is caused"], "c": "D"},
    {"q": "36. Three cars _____ in a bad accident on the motorway.",
     "a": ["A) are involving", "B) involve", "C) have involved", "D) have been involved"], "c": "D"},
    {"q": "37. I _____ for arriving so late.", "a": ["A) sorry", "B) regret", "C) apologise", "D) afraid"], "c": "C"},
    {"q": "38. I think we're going to run _____ of petrol soon.", "a": ["A) down", "B) out", "C) off", "D) through"],
     "c": "B"},
    {"q": "39. I didn't realize how long _____ since we last met.",
     "a": ["A) it had been", "B) it was been", "C) it was being", "D) it is been"], "c": "A"},
    {"q": "40. The girls _____ to each other since the film started.",
     "a": ["A) talked", "B) were talking", "C) are talking", "D) have been talking"], "c": "D"},
    {"q": "41. By the time I hand in this project, I _____ on it for three weeks!",
     "a": ["A) 'll be working", "B) 'll have been working", "C) have worked", "D) 'll work"], "c": "B"},
    {"q": "42. Jonah's just fallen down the steps and there's _____ everywhere.",
     "a": ["A) bone", "B) blood", "C) skin", "D) cut"], "c": "B"},
    {"q": "43. I really wish people _____ dump litter in front of our house.",
     "a": ["A) won't", "B) wouldn't", "C) haven't", "D) don't"], "c": "B"},
    {"q": "44. You should be very proud _____ what you've achieved.", "a": ["A) of", "B) on", "C) to", "D) for"],
     "c": "A"},
    {"q": "45. _____ people know this but our school is being inspected today.",
     "a": ["A) Little", "B) Any", "C) None", "D) Few"], "c": "D"},
    {"q": "46. That's the office _____ my dad works.", "a": ["A) who", "B) where", "C) that", "D) which"], "c": "B"},
    {"q": "47. The lights went out while the footballer _____.",
     "a": ["A) had been interviewed", "B) was interviewed", "C) was being interviewed", "D) was interviewing"],
     "c": "C"},
    {"q": "48. They'd emailed her the job details the _____ day.",
     "a": ["A) last", "B) before", "C) previous", "D) earlier"], "c": "C"},
    {"q": "49. I must remember _____ Ed to take notes for me.",
     "a": ["A) ask", "B) to ask", "C) asking", "D) for asking"], "c": "B"},
    {"q": "50. If I'd gone to the sales yesterday, I _____ one of those bags.",
     "a": ["A) could have bought", "B) had bought", "C) would buy", "D) bought"], "c": "A"},
    {"q": "51. Reading: The article is from a magazine.", "a": ["A) True", "B) False"], "c": "A", "reading": True},
    {"q": "52. Reading: The writer says women are better referees.", "a": ["A) True", "B) False"], "c": "B",
     "reading": True},
    {"q": "53. Reading: Pat Dunn is still alive today.", "a": ["A) True", "B) False"], "c": "B", "reading": True},
    {"q": "54. Reading: Pat didn't get her certificate immediately.", "a": ["A) True", "B) False"], "c": "A",
     "reading": True},
    {"q": "55. Reading: Bibiana Steinhaus played in a football final.", "a": ["A) True", "B) False"], "c": "B",
     "reading": True},
    {"q": "56. Reading: Referees have a difficult job because they have to think quickly.",
     "a": ["A) True", "B) False"], "c": "A", "reading": True},
    {"q": "57. Reading: Tennis uses more technology.", "a": ["A) True", "B) False"], "c": "A", "reading": True},
    {"q": "58. Reading: First female referee appointed in 1976.", "a": ["A) True", "B) False"], "c": "A",
     "reading": True},
]

# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 11: READING MATNLARI
# ═══════════════════════════════════════════════════════════════

READING_TEXTS = {
    "elementary": """📖 <b>READING: DAVID BECKHAM & FAMILY</b>\nThe Beckhams are a very famous family. David Beckham is a world famous footballer and his wife, Victoria, has a fashion business. They have four children: three sons - Brooklyn, Romeo and Cruz, and a daughter, Harper. Both football and fashion are important for the family - all the children love football, even little Harper. Victoria's sister, Louise, has a fashion boutique and Brooklyn works there on Saturdays. Romeo is a fashion model for Burberry. They're a rich family - they have four houses: in London, California, Dubai and the South of France, but they are a 'normal' family too - they like family time at home. The parents work hard - they have a charity for young people, The Victoria and David Beckham Charitable Trust, and David works for UNICEF.""",
    "pre_intermediate": """📖 <b>READING: THE WORLD'S MOST EXPERIENCED DRIVER</b>\nOne of Scotland's most active centenarians, Lady Morton, has been a driver for nearly 80 years, although she has never taken a driving test. But last week she had her first ever accident – she hit a traffic island when she took her new car for a drive in Edinburgh. Lady Morton, who celebrated her 100th birthday in July, was given the Nissan Micra as a surprise present. Yesterday she talked about the accident. 'I wasn't going fast, but I hit the traffic island. I couldn't see it, because it had no lights, which I think is ridiculous. But I am all right and luckily my car wasn't badly damaged.' In spite of the accident, she is not planning to stop driving. 'Some people are just born to drive, and I think I am one of them. I've never taken a test, but I've been a good driver since the first time I got in a car. I'm musical, so I listen to the sound of the car to know when to change gear. Some people are very rude- they ask me if I'm still driving at my age. It really annoys me.' Lady Morton bought her first car in 1927. The main change she has noticed since then is the traffic. 'It's appalling. I don't mind it, because I am experienced, but I feel very sorry for beginners.'""",
    "intermediate": """📖 <b>READING: TECHNOLOGY IN EDUCATION</b>\nTechnology is rapidly changing the way students learn. While some argue that screens replace traditional reading, studies show that digital tools actually increase engagement when used correctly. Teachers now use interactive platforms, AI tutors, and virtual reality to make lessons more dynamic. However, the most effective approach combines modern tools with classic methods. This blended learning strategy ensures students develop both digital literacy and critical thinking skills. The future of education isn't about choosing between old and new, but integrating them wisely.""",
    "pre_ielts": """📖 <b>READING: BANGKOK TRAVEL GUIDE</b>\nWhether you're travelling to the islands or the mountains of Thailand, you're likely to spend at least one night in its capital city on the way. Bangkok might be noisy and polluted but it's also an exciting city with plenty of things to see and do. Why not make it a longer stay?\n\nWhere to stay: The Khao San Road was a famous traveller spot even before Leonardo di Caprio's character in the film The Beach stayed there. But it's noisy, not very pretty and not very Thai. For something more authentic, Phra Kanong offers an alternative place to stay, with its fantastic street markets where everyday Bangkok people eat, work and live. It's not as convenient for the main tourist sites, but it has a Skytrain station so you can be at the Grand Palace in 20 minutes.\n\nHow to get around: Bangkok's traffic can be a nightmare. Sure, you can easily take a taxi – if you want to spend hours stuck in traffic jams – but there are two much better ways to get around the city. To explore the temples and historical sites, catch an express boat river taxi or a longtail boat along the Chao Phraya river and the canals. For the modern part of the city, the Skytrain is a fast, cheap way to travel from the river to the shopping malls and nightlife of Sukhumvit, and the famous Chatuchak street market.""",
    "multilevel": """📖 <b>READING: AN UNUSUAL JOB!</b>\nHave you seen a football match recently? If you have, I'm sure that you heard lots of comments about the referee as well as about the players! Referees have a very difficult job. They have to make quick and important decisions in the middle of a fast-moving game. And, of course, there are thousands of people shouting at them too. The crowd is never happy when the ref sends off their favourite player. Also, in football today there still isn't the same technology as there is in other sports, like tennis. The job can get even more difficult when you're a woman who is refereeing a men's match!\n\nThere is no reason why there should not be the same number of male and female referees in the sport today. However, the number of female refs is still very low – particularly at the highest levels of professional football. This is something that one woman, Pat Dunn, who died in 1999, would have been very sad about.\n\nPat was the first woman in the UK to referee a men's football match but she wasn't allowed to do this for a long time. Pat was a strong supporter of women's rights in sport and became President of the Ladies' Football Association in 1969. Then she decided to train to be a referee. For a long time the Football Association refused to give her a certificate although she had passed the exams. But Pat continued fighting and she finally got permission in 1976. The next month she became famous when she refereed her first official FA game. Pat became a very good and successful referee and even saved a footballer's life. She helped him when he was injured during a match!\n\nToday there are some famous female referees, like Bibiana Steinhaus from Germany who has just refereed the final of the Women's Football World Cup. Bibiana decided to become a referee at the age of sixteen and later was the first female referee in the German men's professional league. But there are only a few like her.\n\nFootball is still mainly a men's game – both for players and referees. But for how long? Will we see more women referees in the future? We'd like to know what YOU think. So, please go online and leave a comment on our website. We'll print the most interesting ones in the magazine next week."""
}


# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 12: YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def get_test_data(level: str):
    mapping = {
        "elementary": elementary_questions,
        "pre_intermediate": pre_intermediate_questions,
        "intermediate": intermediate_questions,
        "pre_ielts": pre_ielts_questions,
        "multilevel": cefr_questions
    }
    return mapping.get(level, elementary_questions)


def get_test_name(level: str) -> str:
    names = {
        "elementary": "ELEMENTARY PLACEMENT TEST",
        "pre_intermediate": "PRE-INTERMEDIATE TEST",
        "intermediate": "INTERMEDIATE TEST",
        "pre_ielts": "PRE-IELTS TEST",
        "multilevel": "CEFR MULTILEVEL TEST"
    }
    return names.get(level, "PLACEMENT TEST")


def safe_escape(text: str) -> str:
    return html_escape(str(text)) if text else ""


def get_lang(message_or_callback) -> str:
    user_id = message_or_callback.from_user.id
    for user in registered_users:
        if user.get("user_id") == user_id:
            return user.get("language", "uz")
    return "uz"


# ✅ FIX QILINDI: user_data: dict (oldin user_ dict edi - xato!)
async def send_writing_to_admin(user_data: dict, writing_text: str, bot: Bot, language: str = "uz"):
    """Writing javobini adminga yuborish"""
    try:
        username = user_data.get("username")
        profile_url = f"https://t.me/{username}" if username else f"tg://user?id={user_data['user_id']}"

        lang = LANG[language]
        admin_msg = (
            f"📝 <b>{'YANGI WRITING JAVOB' if language == 'uz' else 'NEW WRITING ANSWER' if language == 'en' else 'НОВЫЙ ОТВЕТ WRITING'}</b>\n\n"
            f"👤 {lang.get('full_name', 'Name')}: {html.bold(user_data.get('full_name', 'N/A'))}\n"
            f"🆔 ID: <code>{user_data['user_id']}</code>\n"
            f"📱 Tel: {html.code(user_data.get('phone', ''))}\n"
            f"📊 {lang.get('level', 'Level')}: {html.bold(user_data.get('level', '-'))}\n"
            f"🧪 {lang.get('test_finish', '').split('!')[0].split(':')[-1].strip()}: {user_data.get('test_score', 'N/A')}\n\n"
            f"✍️ <b>WRITING:</b>\n{safe_escape(writing_text)}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="👤 Profile", url=profile_url)
        ]])
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_msg,
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
        return True
    except Exception as e:
        logging.error(f"Error sending to admin: {e}")
        return False


async def writing_timer_loop(message: Message, state: FSMContext, msg_id: int, bot: Bot, language: str):
    """Writing uchun vaqt hisoblagich"""
    lang = LANG[language]
    start = time.time()
    while True:
        await asyncio.sleep(10)
        elapsed = time.time() - start
        if elapsed >= WRITING_TIME:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=msg_id,
                    text="⏱️ " + lang["timer_expired"]
                )
            except:
                pass
            break
        rem = WRITING_TIME - elapsed
        rem_str = f"{int(rem // 60):02d}:{int(rem % 60):02d}"
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=f"⏳ WRITING\n🕒 {rem_str}"
            )
        except:
            break


# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 13: HANDLERS - TIL BILAN ISHLASH
# ═══════════════════════════════════════════════════════════════

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(language="uz")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")]
    ])
    await message.answer(
        LANG["uz"]["welcome"].format(total=len(registered_users)),
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )


@dp.callback_query(F.data.startswith("lang_"))
async def choose_language(callback: CallbackQuery, state: FSMContext):
    selected_lang = callback.data.replace("lang_", "")
    await state.update_data(language=selected_lang)
    lang_name = LANG_NAMES.get(selected_lang, selected_lang)
    lang = LANG[selected_lang]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=lang["start_reg"], callback_data="start_registration")
    ]])
    await callback.message.edit_text(
        lang["lang_selected"].format(lang_name=lang_name, total=len(registered_users)),
        reply_markup=kb
    )
    await callback.answer()


@dp.callback_query(F.data == "start_registration")
async def start_registration(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("language", "uz")
    lang = LANG[lang_code]
    await state.set_state(Registration.full_name)
    await callback.message.edit_text(lang["full_name"])
    await callback.answer()


@dp.message(Registration.full_name)
async def get_full_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("language", "uz")
    lang = LANG[lang_code]
    if len(message.text.strip()) < 3:
        await message.answer(lang["full_name_error"])
        return
    await state.update_data(full_name=message.text.strip())
    await state.set_state(Registration.age)
    await message.answer(lang["age"])


@dp.message(Registration.age)
async def get_age(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("language", "uz")
    lang = LANG[lang_code]
    try:
        age = int(message.text.strip())
        if not 5 <= age <= 80:
            raise ValueError
    except:
        await message.answer(lang["age_error"])
        return
    await state.update_data(age=age)
    await state.set_state(Registration.branch)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Dream Zone — Qarshi", callback_data="branch_DREAM")],
        [InlineKeyboardButton(text="📍 Korzinka ro'parasi", callback_data="branch_maqsad70")]
    ])
    await message.answer(lang["branch"], reply_markup=kb)


@dp.callback_query(F.data.startswith("branch_"))
async def choose_branch(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("language", "uz")
    lang = LANG[lang_code]
    await state.update_data(branch=callback.data.replace("branch_", ""))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔰 Beginner", callback_data="level_beginner")],
        [InlineKeyboardButton(text="📗 Elementary", callback_data="level_elementary")],
        [InlineKeyboardButton(text="📘 Pre-Intermediate", callback_data="level_pre_intermediate")],
        [InlineKeyboardButton(text="📙 Intermediate", callback_data="level_intermediate")],
        [InlineKeyboardButton(text="📕 Pre-IELTS", callback_data="level_pre_ielts")],
        [InlineKeyboardButton(text="🌍 Multilevel", callback_data="level_multilevel")]
    ])
    await callback.message.edit_text(lang["level"], reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("level_"))
async def choose_level(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("language", "uz")
    lang = LANG[lang_code]
    await state.update_data(level=callback.data.replace("level_", ""))
    await state.set_state(Registration.phone)
    await callback.message.edit_text(lang["phone"])
    await callback.answer()


@dp.message(Registration.phone)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("language", "uz")
    lang = LANG[lang_code]
    phone = re.sub(r'[^\d+]', '', message.text.strip())
    if not re.match(r'^\+?998\d{9}$', phone) and not re.match(r'^\d{9}$', phone):
        await message.answer(lang["phone_invalid"])
        return
    if phone.startswith('998') and len(phone) == 12:
        phone = '+' + phone
    elif len(phone) == 9:
        phone = '+998' + phone
    await state.update_data(phone=phone)
    await message.answer(lang["phone_saved"])
    level = data.get("level", "")
    need_test = level not in ["beginner"]
    if need_test:
        questions = get_test_data(level)
        await state.set_state(Registration.test_answers)
        await state.update_data(
            test_answers=[],
            current_question=0,
            test_correct_count=0,
            reading_shown=False
        )
        await message.answer(
            lang["test_start"].format(
                test_name=get_test_name(level),
                total=len(questions),
                time=TEST_TIME
            )
        )
        await asyncio.sleep(1)
        await start_test(message, state, bot=message.bot, language=lang_code)
    else:
        await finish_registration(message, state, bot=message.bot, language=lang_code)


# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 14: TEST LOGIKASI
# ═══════════════════════════════════════════════════════════════

async def start_test(message: Message, state: FSMContext, bot: Bot, language: str):
    data = await state.get_data()
    level = data.get("level", "elementary")
    q_index = data.get("current_question", 0)
    questions = get_test_data(level)
    lang = LANG[language]
    if q_index >= len(questions):
        await finish_test(message, state, bot, language)
        return
    question = questions[q_index]
    if question.get("reading") and not data.get("reading_shown"):
        reading_text = READING_TEXTS.get(level, READING_TEXTS["elementary"])
        msg = await message.answer(reading_text, parse_mode=ParseMode.HTML)
        await state.update_data(reading_msg_id=msg.message_id, reading_shown=True)
        await asyncio.sleep(1)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=opt, callback_data=f"e_{q_index}_{opt[0]}")]
        for opt in question["a"]
    ])
    current_time = READING_TIME if question.get("reading") else TEST_TIME
    text = lang["test_question"].format(
        current=q_index + 1,
        total=len(questions),
        time=current_time,
        question=question["q"]
    )
    sent = await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    task = asyncio.create_task(
        run_timer(message, state, q_index, sent.message_id, bot, current_time, language)
    )
    await state.update_data(timer_task=task)


async def run_timer(message: Message, state: FSMContext, q_idx: int, msg_id: int, bot: Bot, limit: int, language: str):
    await asyncio.sleep(limit)
    data = await state.get_data()
    lang = LANG[language]
    if data.get("current_question") == q_idx:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=f"⏱️ {lang['timer_expired']}"
            )
        except:
            pass
        await state.update_data(current_question=q_idx + 1)
        await start_test(message, state, bot, language)


@dp.callback_query(F.data.startswith("e_"))
async def process_answer(callback: CallbackQuery, state: FSMContext):
    try:
        _, q_idx, ans = callback.data.split("_")
        q_idx = int(q_idx)
    except:
        return
    data = await state.get_data()
    lang_code = data.get("language", "uz")
    lang = LANG[lang_code]
    task = data.get("timer_task")
    if task and not task.done():
        task.cancel()
    questions = get_test_data(data.get("level", "elementary"))
    correct = data.get("test_correct_count", 0)
    is_ok = (ans == questions[q_idx]["c"])
    if is_ok:
        correct += 1
    answers = data.get("test_answers", [])
    answers.append({
        "q": questions[q_idx]["q"],
        "user": ans,
        "correct": questions[q_idx]["c"],
        "ok": is_ok
    })
    await state.update_data(
        test_answers=answers,
        current_question=q_idx + 1,
        test_correct_count=correct
    )
    try:
        await callback.message.edit_text(lang["answer_accepted"])
        await asyncio.sleep(0.3)
        await callback.message.delete()
    except:
        pass
    await callback.answer()
    await start_test(callback.message, state, bot=callback.bot, language=lang_code)


async def finish_test(message: Message, state: FSMContext, bot: Bot, language: str):
    data = await state.get_data()
    lang = LANG[language]
    correct = data.get("test_correct_count", 0)
    questions = get_test_data(data.get("level", "elementary"))
    total = len(questions)
    percent = round(correct / total * 100, 1) if total > 0 else 0
    await message.answer(
        lang["test_finish"].format(correct=correct, total=total, percent=percent)
    )
    details = [
        f"{'✅' if a['ok'] else '❌'} {a['q']}\n   Siz: {a['user']} | To'g'ri: {a['correct']}"
        for a in data.get("test_answers", [])[:10]
    ]
    await message.answer(
        lang["test_results_detail"].format(details="\n".join(details)),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(WritingState.text)
    timer_msg = await message.answer("⏳ WRITING\n⏱️ 20:00")
    task = asyncio.create_task(
        writing_timer_loop(message, state, timer_msg.message_id, message.bot, language)
    )
    await state.update_data(timer_msg_id=timer_msg.message_id, timer_task=task)
    await message.answer(lang["writing_task"])


@dp.message(WritingState.text)
async def process_writing(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("language", "uz")
    lang = LANG[lang_code]
    writing_text = message.text.strip()
    if len(writing_text) < 50:
        await message.answer(lang["writing_short"])
        return
    task = data.get("timer_task")
    if task and not task.done():
        task.cancel()
    try:
        await message.bot.delete_message(
            chat_id=message.chat.id,
            message_id=data.get("timer_msg_id")
        )
    except:
        pass
    questions = get_test_data(data.get("level", "elementary"))
    user_info = {
        "user_id": message.from_user.id,
        "username": message.from_user.username,
        "full_name": data.get("full_name"),
        "age": data.get("age"),
        "phone": data.get("phone"),
        "course": "english",
        "branch": data.get("branch"),
        "level": data.get("level"),
        "language": lang_code,
        "test_score": f"{data.get('test_correct_count', 0)}/{len(questions)}",
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    registered_users.append(user_info)
    save_data()
    test_results.append({
        **user_info,
        "writing_text": writing_text,
        "submitted_at": datetime.now().isoformat()
    })
    save_data()
    if await send_writing_to_admin(user_info, writing_text, message.bot, lang_code):
        await message.answer(lang["writing_sent"])
    else:
        await message.answer(lang["saved"])
    await state.clear()


async def finish_registration(message: Message, state: FSMContext, bot: Bot, language: str):
    data = await state.get_data()
    lang = LANG[language]
    user_info = {
        "user_id": message.from_user.id,
        "username": message.from_user.username,
        "full_name": data.get("full_name"),
        "age": data.get("age"),
        "phone": data.get("phone"),
        "course": "english",
        "branch": data.get("branch"),
        "level": data.get("level"),
        "language": language,
        "test_score": "N/A",
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    registered_users.append(user_info)
    save_data()
    level_display = data.get("level", "").replace("_", " ").title()
    await message.answer(
        f"✅ <b>{lang['success']}</b>\n\n"
        f"👤 {html.bold(data.get('full_name'))}\n"
        f"📱 {html.code(data.get('phone'))}\n"
        f"📍 {data.get('branch')}\n"
        f"📊 {html.bold(level_display)}",
        parse_mode=ParseMode.HTML
    )
    await message.answer(lang["admin_contact"], parse_mode=ParseMode.HTML)
    if bot:
        profile_url = f"https://t.me/{user_info.get('username')}" if user_info.get(
            "username") else f"tg://user?id={user_info['user_id']}"
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 New student!\n{html.bold(user_info.get('full_name'))}\n{html.code(user_info.get('phone'))}\n{html.bold(user_info.get('level'))}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="👤 Profile", url=profile_url)
                ]]),
                parse_mode=ParseMode.HTML
            )
        except:
            pass
    await state.clear()


# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 15: ADMIN /send BUYRUG'I
# ═══════════════════════════════════════════════════════════════

@dp.message(Command("send"))
async def send_cmd(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        lang_code = get_lang(message)
        await message.answer(LANG[lang_code]["not_admin"])
        return
    lang = LANG["uz"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang["send_text"], callback_data="send_text")],
        [InlineKeyboardButton(text=lang["send_photo"], callback_data="send_photo")],
        [InlineKeyboardButton(text=lang["send_video"], callback_data="send_video")],
        [InlineKeyboardButton(text=lang["send_cancel"], callback_data="send_cancel")]
    ])
    await message.answer(
        lang["send_title"].format(count=len(registered_users)),
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(SendMessage.choose_type)


@dp.callback_query(F.data == "send_cancel")
async def cancel_send(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = LANG["uz"]
    await callback.message.edit_text(lang["cancelled"])
    await callback.answer()


@dp.callback_query(F.data == "send_text")
async def send_text_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SendMessage.enter_text)
    lang = LANG["uz"]
    await callback.message.edit_text(lang["enter_text"])
    await callback.answer()


@dp.message(SendMessage.enter_text)
async def proc_text(message: Message, state: FSMContext):
    await state.update_data(media_type="text", media_text=message.text)
    await confirm_send(message, state)


@dp.callback_query(F.data == "send_photo")
async def send_photo_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SendMessage.upload_photo)
    lang = LANG["uz"]
    await callback.message.edit_text(lang["send_photo_prompt"])
    await callback.answer()


@dp.message(SendMessage.upload_photo, F.photo)
async def proc_photo(message: Message, state: FSMContext):
    await state.update_data(
        media_type="photo",
        media_id=message.photo[-1].file_id,
        media_caption=message.caption or ""
    )
    await confirm_send(message, state)


@dp.callback_query(F.data == "send_video")
async def send_video_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SendMessage.upload_video)
    lang = LANG["uz"]
    await callback.message.edit_text(lang["send_video_prompt"])
    await callback.answer()


@dp.message(SendMessage.upload_video, F.video)
async def proc_video(message: Message, state: FSMContext):
    await state.update_data(
        media_type="video",
        media_id=message.video.file_id,
        media_caption=message.caption or ""
    )
    await confirm_send(message, state)


async def confirm_send(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = LANG["uz"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Send", callback_data="send_confirm")],
        [InlineKeyboardButton(text=lang["send_cancel"], callback_data="send_cancel")]
    ])
    if data["media_type"] == "photo":
        await message.answer_photo(
            photo=data["media_id"],
            caption=lang["confirm_send"],
            reply_markup=kb
        )
    elif data["media_type"] == "video":
        await message.answer_video(
            video=data["media_id"],
            caption=lang["confirm_send"],
            reply_markup=kb
        )
    else:
        preview = safe_escape(data['media_text'][:100])
        await message.answer(
            f"📨 {lang['confirm_send']}\n\n{preview}...",
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
    await state.set_state(SendMessage.confirm_send)


@dp.callback_query(F.data == "send_confirm")
async def exec_send(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    bot = callback.bot
    lang = LANG["uz"]
    total = len(registered_users)
    if total == 0:
        await callback.message.edit_text(lang["empty_list"], reply_markup=None)
        await state.clear()
        return
    await callback.message.edit_text(lang["sending"].format(percent=0, current=0, total=total))
    success = fail = 0
    for i, user in enumerate(registered_users, 1):
        try:
            if data["media_type"] == "text":
                await bot.send_message(
                    user["user_id"],
                    text=data["media_text"],
                    parse_mode=ParseMode.HTML
                )
            elif data["media_type"] == "photo":
                await bot.send_photo(
                    user["user_id"],
                    photo=data["media_id"],
                    caption=data.get("media_caption", "")
                )
            else:
                await bot.send_video(
                    user["user_id"],
                    video=data["media_id"],
                    caption=data.get("media_caption", "")
                )
            success += 1
        except TelegramForbiddenError:
            fail += 1
        except Exception as e:
            logging.warning(f"Failed to send to {user.get('user_id')}: {e}")
            fail += 1
        await asyncio.sleep(0.1)
        if i % 10 == 0 or i == total:
            try:
                await callback.message.edit_text(
                    lang["sending"].format(
                        percent=round(i / total * 100),
                        current=i,
                        total=total
                    )
                )
            except:
                pass
    await state.clear()
    await callback.message.edit_text(
        lang["send_done"].format(success=success, fail=fail),
        parse_mode=ParseMode.HTML
    )


@dp.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext):
    lang_code = get_lang(message)
    await state.clear()
    await message.answer(LANG[lang_code]["cancelled"])


@dp.message()
async def echo(message: Message, state: FSMContext):
    if not await state.get_state():
        lang_code = get_lang(message)
        await message.answer(LANG[lang_code]["unknown"])


# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 16: FLASK + AIOGRAM INTEGRATSIYASI
# ═══════════════════════════════════════════════════════════════

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logging.info("🚀 Multilang bot started!")
    for f in [DATA_FILE, TEST_RESULTS_FILE]:
        if not os.path.exists(f):
            with open(f, "w", encoding="utf-8") as ff:
                json.dump([], ff, indent=2)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logging.info("🌐 Flask: http://0.0.0.0:5000")
    await dp.start_polling(bot)


# ═══════════════════════════════════════════════════════════════
# 🔹 SECTION 17: ISHGA TUSHIRISH
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    asyncio.run(main())