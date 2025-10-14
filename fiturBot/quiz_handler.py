# quiz_handler.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_IDS
import random
import time
import asyncio

logger = logging.getLogger(__name__)

# State management untuk quiz
group_quiz_sessions = {}
user_scores = {}
questions_db = []

# Struktur data untuk pertanyaan
class Question:
    def __init__(self, question, correct_answer, options=None):
        self.question = question
        self.correct_answer = correct_answer
        self.options = options
        self.created_by = None

# Inisialisasi beberapa pertanyaan contoh
def initialize_sample_questions():
    sample_questions = [
        Question(
            "2 + 2 = ?",
            "4",
            ["3", "4", "5", "6", "7", "8"]
        ),
        Question(
            "Apa warna langit pada siang hari?",
            "biru", 
            ["merah", "kuning", "hijau", "biru", "ungu", "hitam"]
        ),
        Question(
            "Ibu kota Indonesia?",
            "jakarta",
            ["bandung", "surabaya", "jakarta", "medan", "yogyakarta", "semarang"]
        ),
    ]
    questions_db.extend(sample_questions)

def format_question(question, answered_options=None):
    if answered_options is None:
        answered_options = {}
    question_text = f"**{question.question}**\n\n"

    for i, option in enumerate(question.options, 1):
        if i in answered_options:
            user_name = answered_options[i]['user_name']
            question_text += f"{i}. {option} (+1) [{user_name}]\n"

        else:
            question_text += f"{i}. ______\n"
    
    return question_text
    
# Fungsi untuk setup bot commands (menu)
async def setup_bot_commands(application):
    """Setup bot commands menu"""
    commands = [
        BotCommand("start", "Memulai Bot"),
        BotCommand("help", "Membuka pesan bantuan"),
        BotCommand("mulai", "Memulai permainan"),
        BotCommand("nyerah", "Menyerah dari pertanyaan"),
        BotCommand("next", "Pertanyaan berikutnya"),
        BotCommand("skor", "Melihat skor saat ini"),
        BotCommand("poin", "Melihat poin kamu"),
        BotCommand("topskor", "Melihat 10 pemain teratas"),
        BotCommand("aturan", "Melihat aturan bermain"),
        BotCommand("donasi", "Dukungan untuk bot"),
        BotCommand("lapor", "Laporkan pertanyaan"),
    ]
    
    # Tambahkan command buat hanya untuk admin
    admin_commands = commands + [BotCommand("buat", "Buat pertanyaan (Admin)")]
    
    try:
        # Set commands untuk semua user
        await application.bot.set_my_commands(commands)
        logger.info("✅ Bot commands menu setup completed")
        
        # Set commands khusus untuk admin (optional)
        for admin_id in ADMIN_IDS:
            try:
                await application.bot.set_my_commands(
                    admin_commands, 
                    scope=BotCommandScopeChat(admin_id)
                )
            except Exception as e:
                logger.warning(f"⚠️ Could not set admin commands for {admin_id}: {e}")
                
    except Exception as e:
        logger.error(f"❌ Error setting bot commands: {e}")

# Modifikasi fungsi start untuk menampilkan pesan welcome
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /start - menampilkan pesan welcome"""
    welcome_text = (
        "🤖 **Quiz Tebak-Tebakan**\n\n"
        "Halo, ayo kita main tebak-tebakan. Kamu juga bisa main sendiri dengan chat botnya langsung\n"
        "Gunakan menu di bawah atau ketik perintah:\n"
        "• /help - melihat bantuan\n" 
        "• /mulai - mulai game\n"
        "• /aturan - aturan bermain\n"
        "• /donasi - dukung bot ini"
    )
    
    await update.message.reply_text(welcome_text)

# Modifikasi fungsi help untuk menampilkan pesan seperti di screenshot
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /help - menampilkan pesan bantuan lengkap"""
    help_text = (
        "🤖 **Quiz Tebak-Tebakan**\n\n"
        "Halo, ayo kita main tebak-tebakan. Kamu juga bisa main sendiri dengan chat botnya langsung\n"
        "**Perintah yang tersedia:**\n\n"
        "**Memulai Bot**\n"
        "/start\n\n"
        "**Membuka pesan bantuan**\n" 
        "/help\n\n"
        "**Memulai permainan**\n"
        "/mulai\n\n"
        "**Menyerah dari pertanyaan**\n"
        "/nyerah\n\n"
        "**Pertanyaan berikutnya**\n"
        "/next\n\n"
        "**Melihat skor saat ini**\n"
        "/skor\n\n"
        "**Melihat poin kamu**\n"
        "/poin\n\n"
        "**Melihat 10 pemain teratas**\n"
        "/topskor\n\n"
        "**Melihat aturan bermain**\n"
        "/aturan\n\n"
        "**Dukungan untuk bot**\n"
        "/donasi"
    )
    
    await update.message.reply_text(help_text)

# Modifikasi fungsi quiz untuk menggunakan inline keyboard
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /quiz - Menu utama dengan inline keyboard"""
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("🎮 Mulai Game", callback_data="start_quiz")],
        [InlineKeyboardButton("📖 Bantuan", callback_data="quiz_help")],
        [InlineKeyboardButton("📊 Skor Saya", callback_data="quiz_score")],
        [InlineKeyboardButton("🏆 Top Skor", callback_data="quiz_topscore")],
        [InlineKeyboardButton("📚 Aturan", callback_data="quiz_rules")],
        [InlineKeyboardButton("❤️ Donasi", callback_data="quiz_donate")],
        [InlineKeyboardButton("⚠️ Laporkan", callback_data="quiz_report")],
    ]
    
    # Hanya admin yang bisa melihat tombol buat pertanyaan
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("✏️ Buat Pertanyaan", callback_data="quiz_create")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎯 **Menu Utama Bot Tebak-Tebakan**\n\n"
        "Pilih aksi yang ingin dilakukan:",
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
    elif callback_data == "start_quiz":
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
        "🤖 **Quiz Tebak-Tebakan - Bantuan**\n\n"
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
    chat_id = update.effective_chat.id
    user = update.effective_user

    # Cek jika chat adalah grup
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ Quiz hanya bisa dimulai di grup!")
        return
        
    if not questions_db:
        initialize_sample_questions()

    # Inisialisasi sesi quiz untuk grup
    if chat_id not in group_quiz_sessions:
        group_quiz_sessions[chat_id] = {
            'active': True,
            'current_question_index': random.randint(0, len(questions_db) - 1),
            'answered_options': {},  # {option_number: {'user_id': x, 'user_name': y}}
            'start_time': time.time(),
            'message_id': None
        }

    session = group_quiz_sessions[chat_id]
    question = questions_db[session['current_question_index']]

    # Kirim pertanyaan
    question_text = format_question(question)
    message = await update.message.reply_text(
        question_text,
        parse_mode='Markdown'
    )

    # Simpan ID pesan untuk update nanti
    session['message_id'] = message.message_id
    session['active'] = True
    
async def surrender_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id in group_quiz_sessions:
        group_quiz_sessions[chat_id]['active'] = False
        await update.message.reply_text("🏳️ Quiz dihentikan!")
    else:
        await update.message.reply_text("ℹ️ Tidak ada quiz yang aktif.")
        
async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in group_quiz_sessions:
        await update.message.reply_text("❌ Tidak ada quiz yang aktif!")
        return

    session = group_quiz_sessions[chat_id]
    
    # Pilih pertanyaan acak berikutnya
    available_questions = [i for i in range(len(questions_db)) if i != session['current_question_index']]
    if not available_questions:
        # Reset jika semua pertanyaan sudah digunakan
        available_questions = list(range(len(questions_db)))

    session['current_question_index'] = random.choice(available_questions)
    session['answered_options'] = {}
    question = questions_db[session['current_question_index']]
    question_text = format_question(question)

    try:
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=question_text,
            parse_mode='Markdown'
        )
        session['message_id'] = message.message_id

    except Exception as e:
        logger.error(f"Error sending next question: {e}")
        await update.message.reply_text("❌ Gagal memuat pertanyaan berikutnya")
        
async def show_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    score = user_scores.get(user_id, 0)
    await update.message.reply_text(f"📊 Skor Anda: {score}")
   
async def top_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_scores:
        await update.message.reply_text("📊 Belum ada skor yang tercatat.")
        return
    
    top_users = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    
    leaderboard = "🏆 **Top Skor Global**\n\n"
    for i, (user_id, score) in enumerate(top_users, 1):
        try:
            user = await context.bot.get_chat(user_id)
            username = f"@{user.username}" if user.username else user.first_name
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
        "**Dana:** 083180442386\n"
        "**Seabank:** xxx\n\n"
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

async def handle_question_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        parts = text.split('|')
        if len(parts) >= 3:
            question_text = parts[0].strip()
            correct_answer = parts[1].strip()
            options = [opt.strip() for opt in parts[2:8]]  # Maksimal 6 opsi

            if correct_answer not in options:
                await update.message.reply_text("❌ Jawaban benar harus ada dalam opsi!")
                return
                
            new_question = Question(question_text, correct_answer, options)
            new_question.created_by = update.effective_user.id
            questions_db.append(new_question)

            await update.message.reply_text("✅ Pertanyaan berhasil ditambahkan!")
        else:
            await update.message.reply_text("❌ Format salah! Minimal: Pertanyaan|Jawaban|Opsi1|Opsi2")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    
    context.user_data['waiting_for_question'] = False

# Handler untuk menerima pesan teks (jawaban quiz dan pembuatan pertanyaan)
async def handle_quiz_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    text = update.message.text.strip().lower()
    
    # Cek jika user sedang membuat pertanyaan (admin only)
    if context.user_data.get('waiting_for_question') and user_id in ADMIN_IDS:
        await handle_question_creation(update, context, text)
        return

    if chat_id not in group_quiz_sessions or not group_quiz_sessions[chat_id]['active']:
        return
                                       
    session = group_quiz_sessions[chat_id]
    question = questions_db[session['current_question_index']]
    
    # Cek jika jawaban benar
    if text == question.correct_answer.lower():
        # Cari nomor opsi yang sesuai dengan jawaban
        option_number = None
        for i, option in enumerate(question.options, 1):
            if option.lower() == text:
                option_number = i
                break

        if option_number and option_number not in session['answered_options']:
            # Tambahkan ke jawaban yang sudah dijawab
            session['answered_options'][option_number] = {
                'user_id': user_id,
                'user_name': user_name
            }
            # Update skor user
            user_scores[user_id] = user_scores.get(user_id, 0) + 1
            
            # Update pesan pertanyaan
            question_text = format_question(question, session['answered_options'])
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=session['message_id'],
                    text=question_text,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error updating message: {e}")

            # Kirim konfirmasi
            await update.message.reply_text(
                f"✅ @{user_name} benar! +1 poin\n"
                f"Total poin: {user_scores[user_id]}"
            )
            # Cek jika semua opsi sudah terjawab atau sudah ada yang benar
            # Lanjut ke soal berikutnya setelah delay
            await asyncio.sleep(3)
            await next_question(update, context)

        # Cek jika user mencoba menjawab dengan nomor opsi
    elif text.isdigit():
        option_num = int(text)
        if 1 <= option_num <= len(question.options):
            option_text = question.options[option_num - 1].lower()
            if option_text == question.correct_answer.lower():
                # Jawaban benar via nomor opsi
                if option_num not in session['answered_options']:
                    session['answered_options'][option_num] = {
                        'user_id': user_id,
                        'user_name': user_name
                    }
                    
                    user_scores[user_id] = user_scores.get(user_id, 0) + 1
                    question_text = format_question(question, session['answered_options'])
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=session['message_id'],
                            text=question_text,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Error updating message: {e}")
                    
                    await update.message.reply_text(
                        f"✅ @{user_name} benar! +1 poin\n"
                        f"Total poin: {user_scores[user_id]}"
                    )
                    await asyncio.sleep(3)
                    await next_question(update, context)

# Inisialisasi
initialize_sample_questions()
