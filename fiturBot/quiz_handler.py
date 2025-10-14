# quiz_handler.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_IDS
import random
import time

logger = logging.getLogger(__name__)

# State management untuk quiz
quiz_sessions = {}
user_scores = {}
questions_db = []

# Struktur data untuk pertanyaan
class Question:
    def __init__(self, question, answer, options=None):
        self.question = question
        self.answer = answer
        self.options = options or []
        self.created_by = None

# Inisialisasi beberapa pertanyaan contoh
def initialize_sample_questions():
    sample_questions = [
        Question("Apa warna langit pada siang hari?", "biru", ["merah", "kuning", "hijau", "biru"]),
        Question("2 + 2 = ?", "4", ["3", "4", "5", "6"]),
        Question("Ibu kota Indonesia?", "jakarta", ["bandung", "surabaya", "jakarta", "medan"]),
    ]
    questions_db.extend(sample_questions)

# Command /quiz - Menu utama quiz
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("📖 Bantuan", callback_data="quiz_help")],
        [InlineKeyboardButton("🎮 Mulai Game", callback_data="quiz_start")],
        [InlineKeyboardButton("🏃 Menyerah", callback_data="quiz_surrender")],
        [InlineKeyboardButton("➡️ Pertanyaan Berikutnya", callback_data="quiz_next")],
        [InlineKeyboardButton("📊 Skor Saat Ini", callback_data="quiz_score")],
        [InlineKeyboardButton("⭐ Poin Saya", callback_data="quiz_points")],
        [InlineKeyboardButton("🏆 Top Skor Global", callback_data="quiz_topscore")],
        [InlineKeyboardButton("📚 Aturan Bermain", callback_data="quiz_rules")],
        [InlineKeyboardButton("❤️ Donasi", callback_data="quiz_donate")],
        [InlineKeyboardButton("⚠️ Laporkan Pertanyaan", callback_data="quiz_report")],
    ]
    
    # Hanya admin yang bisa melihat tombol buat pertanyaan
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("✏️ Buat Pertanyaan", callback_data="quiz_create")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 **Bot Tebak-Tebakan**\n\n"
        "Pilih menu di bawah untuk bermain tebak-tebakan!",
        reply_markup=reply_markup
    )

# Handler untuk callback queries
async def quiz_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = query.from_user.id
    
    if callback_data == "quiz_help":
        await quiz_help_command(query, context)
    elif callback_data == "quiz_start":
        await start_quiz(query, context)
    elif callback_data == "quiz_surrender":
        await surrender_quiz(query, context)
    elif callback_data == "quiz_next":
        await next_question(query, context)
    elif callback_data == "quiz_score":
        await show_score(query, context)
    elif callback_data == "quiz_points":
        await show_points(query, context)
    elif callback_data == "quiz_topscore":
        await top_score(query, context)
    elif callback_data == "quiz_rules":
        await quiz_rules(query, context)
    elif callback_data == "quiz_donate":
        await quiz_donate(query, context)
    elif callback_data == "quiz_report":
        await quiz_report(query, context)
    elif callback_data == "quiz_create":
        if user_id in ADMIN_IDS:
            await create_question_start(query, context)
        else:
            await query.message.reply_text("❌ Anda bukan admin!")

# Command handlers individual (untuk integrasi dengan main.py)
async def quiz_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await quiz_help_command(update, context)

async def quiz_help_command(update, context):
    help_text = (
        "🤖 **Bot Tebak-Tebakan - Bantuan**\n\n"
        "**Perintah yang tersedia:**\n"
        "/mulai - Mulai game tebak-tebakan\n"
        "/nyerah - Menyerah dari game\n"
        "/next - Pertanyaan berikutnya\n"
        "/skor - Lihat skor saat ini\n"
        "/poin - Melihat poin kamu\n"
        "/topskor - Lihat top skor global\n"
        "/aturan - Aturan bermain\n"
        "/donasi - Dukung bot ini agar tetap aktif\n"
        "/lapor - Laporkan pertanyaan\n"
    )
    
    if isinstance(update, Update):
        await update.message.reply_text(help_text)
    else:
        await update.message.reply_text(help_text)

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not questions_db:
        initialize_sample_questions()
    
    # Inisialisasi session user
    if user_id not in quiz_sessions:
        quiz_sessions[user_id] = {
            'current_question_index': 0,
            'score': 0,
            'start_time': time.time(),
            'answered_questions': set()
        }
    
    session = quiz_sessions[user_id]
    
    # Cari pertanyaan yang belum dijawab
    available_questions = [i for i in range(len(questions_db)) if i not in session['answered_questions']]
    
    if not available_questions:
        await update.message.reply_text("🎉 Selamat! Anda telah menyelesaikan semua pertanyaan!")
        return
    
    question_index = random.choice(available_questions)
    session['current_question_index'] = question_index
    question = questions_db[question_index]
    
    # Format pertanyaan seperti di screenshot
    question_text = f"**{question.question}**\n\n"
    
    if question.options:
        for i, option in enumerate(question.options, 1):
            question_text += f"{i}. {option}\n"
    
    await update.message.reply_text(question_text)

async def surrender_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in quiz_sessions:
        score = quiz_sessions[user_id]['score']
        del quiz_sessions[user_id]
        await update.message.reply_text(f"😔 Anda menyerah! Skor akhir: {score}")
    else:
        await update.message.reply_text("ℹ️ Tidak ada game yang aktif.")

async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in quiz_sessions:
        await update.message.reply_text("❌ Tidak ada game yang aktif. Gunakan /mulai untuk memulai.")
        return
    
    await start_quiz(update, context)

async def show_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in quiz_sessions:
        score = quiz_sessions[user_id]['score']
        await update.message.reply_text(f"📊 Skor saat ini: {score}")
    else:
        await update.message.reply_text("ℹ️ Tidak ada game yang aktif.")

async def show_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    points = user_scores.get(user_id, 0)
    await update.message.reply_text(f"⭐ Poin Anda: {points}")

async def top_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_scores:
        await update.message.reply_text("📊 Belum ada skor yang tercatat.")
        return
    
    top_users = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    
    leaderboard = "🏆 **Top Skor Global**\n\n"
    for i, (user_id, score) in enumerate(top_users, 1):
        try:
            user = await context.bot.get_chat(user_id)
            username = user.username or user.first_name
        except:
            username = f"User_{user_id}"
        
        leaderboard += f"{i}. {username}: {score} poin\n"
    
    await update.message.reply_text(leaderboard)

async def quiz_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = (
        "📚 **Aturan Bermain**\n\n"
        "1. Gunakan /mulai untuk memulai game\n"
        "2. Jawab pertanyaan dengan mengirim pesan\n"
        "3. Gunakan /next untuk pertanyaan berikutnya\n"
        "4. Gunakan /nyerah jika ingin menyerah\n"
        "5. Setiap jawaban benar mendapat 1 poin\n"
        "6. Skor akan disimpan secara global\n"
    )
    await update.message.reply_text(rules_text)

async def quiz_donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    donate_text = (
        "❤️ **Donasi**\n\n"
        "Dukung pengembangan bot ini agar tetap aktif!\n\n"
        "**QRIS:** [Tampilkan QRIS]\n"
        "**Dana:** 081234567890\n"
        "**OVO:** 081234567890\n\n"
        "Terima kasih atas donasinya! ❤️"
    )
    await update.message.reply_text(donate_text)

async def quiz_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report_text = (
        "⚠️ **Laporkan Pertanyaan**\n\n"
        "Jika menemukan pertanyaan yang tidak pantas atau error, "
        "silahkan laporkan ke admin.\n\n"
        "Admin akan meninjau laporan Anda."
    )
    await update.message.reply_text(report_text)

# Fungsi khusus admin untuk membuat pertanyaan
async def create_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa membuat pertanyaan!")
        return
    
    await update.message.reply_text(
        "✏️ **Buat Pertanyaan Baru**\n\n"
        "Silakan kirim pertanyaan dalam format:\n"
        "`Pertanyaan|Jawaban|Opsi1|Opsi2|Opsi3|Opsi4`\n\n"
        "Contoh:\n"
        "`Apa warna langit?|Biru|Merah|Kuning|Hijau|Biru`"
    )
    
    # Set state untuk menunggu input pertanyaan
    context.user_data['waiting_for_question'] = True

# Handler untuk menerima pesan teks (jawaban quiz dan pembuatan pertanyaan)
async def handle_quiz_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Cek jika user sedang membuat pertanyaan (admin only)
    if context.user_data.get('waiting_for_question') and user_id in ADMIN_IDS:
        try:
            parts = text.split('|')
            if len(parts) >= 2:
                question_text = parts[0].strip()
                answer = parts[1].strip()
                options = [opt.strip() for opt in parts[2:6]] if len(parts) > 2 else []
                
                new_question = Question(question_text, answer, options)
                new_question.created_by = user_id
                questions_db.append(new_question)
                
                await update.message.reply_text("✅ Pertanyaan berhasil ditambahkan!")
            else:
                await update.message.reply_text("❌ Format salah! Gunakan: Pertanyaan|Jawaban|Opsi1|Opsi2|Opsi3|Opsi4")
        
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        
        context.user_data['waiting_for_question'] = False
        return
    
    # Cek jika user sedang bermain quiz
    if user_id in quiz_sessions:
        session = quiz_sessions[user_id]
        current_index = session['current_question_index']
        
        if current_index < len(questions_db):
            question = questions_db[current_index]
            
            # Check answer (case insensitive)
            if text.lower() == question.answer.lower():
                session['score'] += 1
                user_scores[user_id] = user_scores.get(user_id, 0) + 1
                session['answered_questions'].add(current_index)
                
                await update.message.reply_text(
                    f"✅ Benar! +1 poin\n"
                    f"Skor: {session['score']}"
                )
                
                # Auto next question setelah 2 detik
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
                await asyncio.sleep(2)
                await start_quiz(update, context)
            else:
                await update.message.reply_text("❌ Salah! Coba lagi.")

# Inisialisasi questions saat module di-load
initialize_sample_questions()
