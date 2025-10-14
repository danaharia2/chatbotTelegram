# quiz_handler.py
import logging
import random
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_IDS
from datetime import datetime

logger = logging.getLogger(__name__)

# State management untuk quiz
quiz_sessions = {}  # {chat_id: session_data}
user_scores = {}    # {user_id: score}
questions_db = []   # List of Question objects

# Struktur data untuk pertanyaan dengan multiple answers
class Question:
    def __init__(self, question, correct_answers, options=None):
        self.question = question
        self.correct_answers = correct_answers  # List of correct answers
        self.options = options or []  # Optional multiple choice options
        self.created_by = None
        self.created_at = datetime.now()

# Inisialisasi beberapa pertanyaan contoh dengan multiple answers
def initialize_sample_questions():
    sample_questions = [
        Question(
            "Sebutkan bagian tubuh wanita yang paling disukai cowok?",
            ["bibir", "dada", "mata", "rambut", "paha", "pantat", "pipi", "leher"]
        ),
        Question(
            "Sebutkan kota besar di Indonesia?",
            ["jakarta", "surabaya", "bandung", "medan", "makassar", "semarang", "palembang", "depok"]
        ),
        Question(
            "Sebutkan warna pelangi?",
            ["merah", "jingga", "kuning", "hijau", "biru", "nila", "ungu"]
        ),
    ]
    questions_db.extend(sample_questions)

# Format waktu seperti di screenshot (HH:MM)
def format_time():
    return datetime.now().strftime("%H:%M")

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
        await quiz_help_callback(query, context)
    elif callback_data == "quiz_start":
        await start_quiz_callback(query, context)
    elif callback_data == "quiz_surrender":
        await surrender_quiz_callback(query, context)
    elif callback_data == "quiz_next":
        await next_question_callback(query, context)
    elif callback_data == "quiz_score":
        await show_score_callback(query, context)
    elif callback_data == "quiz_points":
        await show_points_callback(query, context)
    elif callback_data == "quiz_topscore":
        await top_score_callback(query, context)
    elif callback_data == "quiz_rules":
        await quiz_rules_callback(query, context)
    elif callback_data == "quiz_donate":
        await quiz_donate_callback(query, context)
    elif callback_data == "quiz_report":
        await quiz_report_callback(query, context)
    elif callback_data == "quiz_create":
        if user_id in ADMIN_IDS:
            await create_question_start_callback(query, context)
        else:
            await query.message.reply_text("❌ Anda bukan admin!")

# Handler callback untuk setiap fungsi
async def quiz_help_callback(query, context):
    await quiz_help_command(query, context)

async def start_quiz_callback(query, context):
    await start_quiz(query, context)

async def surrender_quiz_callback(query, context):
    await surrender_quiz(query, context)

async def next_question_callback(query, context):
    await next_question(query, context)

async def show_score_callback(query, context):
    await show_score(query, context)

async def show_points_callback(query, context):
    await show_points(query, context)

async def top_score_callback(query, context):
    await top_score(query, context)

async def quiz_rules_callback(query, context):
    await quiz_rules(query, context)

async def quiz_donate_callback(query, context):
    await quiz_donate(query, context)

async def quiz_report_callback(query, context):
    await quiz_report(query, context)

async def create_question_start_callback(query, context):
    await create_question_start(query, context)

# Command handlers individual
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
    chat_id = update.effective_chat.id
    
    if not questions_db:
        initialize_sample_questions()
    
    # Inisialisasi session untuk chat
    if chat_id not in quiz_sessions:
        quiz_sessions[chat_id] = {
            'current_question_index': 0,
            'answered_questions': set(),
            'current_question_answers': {},  # {answer: {user_id, user_name, timestamp}}
            'message_id': None,
            'start_time': time.time()
        }
    
    session = quiz_sessions[chat_id]
    
    # Cari pertanyaan yang belum dijawab
    available_questions = [i for i in range(len(questions_db)) if i not in session['answered_questions']]
    
    if not available_questions:
        await update.message.reply_text("🎉 Selamat! Anda telah menyelesaikan semua pertanyaan!")
        return
    
    # Pilih pertanyaan secara acak
    question_index = random.choice(available_questions)
    session['current_question_index'] = question_index
    question = questions_db[question_index]
    
    # Reset jawaban untuk pertanyaan baru
    session['current_question_answers'] = {}
    
    # Format pertanyaan seperti di screenshot
    question_text = await format_question_text(question, session, chat_id)
    
    # Kirim pesan pertanyaan
    if isinstance(update, Update):
        message = await update.message.reply_text(question_text, parse_mode='Markdown')
    else:
        message = await update.message.reply_text(question_text, parse_mode='Markdown')
    
    # Simpan message_id untuk update nanti
    session['message_id'] = message.message_id

async def format_question_text(question, session, chat_id):
    """Format teks pertanyaan seperti di screenshot"""
    question_text = f"**{question.question}**\n\n"
    
    # Buat daftar jawaban sesuai urutan correct_answers
    for i, correct_answer in enumerate(question.correct_answers):
        # Cek apakah jawaban ini sudah dijawab
        if correct_answer in session['current_question_answers']:
            user_data = session['current_question_answers'][correct_answer]
            user_name = user_data['user_name']
            question_text += f"{i+1}. {correct_answer} (+1) [{user_name}]\n"
        else:
            question_text += f"{i+1}. ______\n"
    
    # Tambahkan waktu current
    current_time = format_time()
    question_text += f"\n{current_time}"
    
    return question_text

async def update_quiz_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, session: dict):
    """Update pesan quiz dengan jawaban terbaru"""
    try:
        question_index = session['current_question_index']
        question = questions_db[question_index]
        
        question_text = await format_question_text(question, session, chat_id)
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=session['message_id'],
            text=question_text,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error updating quiz message: {e}")

async def surrender_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id in quiz_sessions:
        session = quiz_sessions[chat_id]
        question_index = session['current_question_index']
        question = questions_db[question_index]
        
        # Tampilkan jawaban yang benar
        answer_text = "😔 Anda menyerah! Jawaban yang benar:\n\n"
        for i, answer in enumerate(question.correct_answers, 1):
            answer_text += f"{i}. {answer}\n"
        
        await update.message.reply_text(answer_text)
        del quiz_sessions[chat_id]
    else:
        await update.message.reply_text("ℹ️ Tidak ada game yang aktif.")

async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id not in quiz_sessions:
        if isinstance(update, Update):
            await update.message.reply_text("❌ Tidak ada game yang aktif. Gunakan /mulai untuk memulai.")
        else:
            await update.message.reply_text("❌ Tidak ada game yang aktif. Gunakan /mulai untuk memulai.")
        return
    
    session = quiz_sessions[chat_id]
    session['answered_questions'].add(session['current_question_index'])
    
    await start_quiz(update, context)

async def show_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id in quiz_sessions:
        session = quiz_sessions[chat_id]
        # Hitung total jawaban benar di sesi ini
        current_score = len(session['current_question_answers'])
        await update.message.reply_text(f"📊 Skor saat ini: {current_score}")
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
        "2. Jawab pertanyaan dengan mengirim pesan teks\n"
        "3. Setiap pertanyaan memiliki multiple jawaban benar\n"
        "4. Setiap jawaban benar mendapat 1 poin\n"
        "5. Gunakan /next untuk pertanyaan berikutnya\n"
        "6. Gunakan /nyerah jika ingin menyerah\n"
        "7. Skor akan disimpan secara global\n"
        "8. Bisa dimainkan di grup maupun private chat\n"
        "9. Semua anggota grup bisa menjawab pertanyaan yang sama\n"
    )
    await update.message.reply_text(rules_text)

async def quiz_donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        donate_text = (
            "❤️ **Donasi**\n\n"
            "Dukung pengembangan bot ini agar tetap aktif!\n\n"
            "**Metode Pembayaran:**\n"
            "• **QRIS** (Scan gambar di bawah)\n"
            "• **Dana:** 081234567890\n"
            "• **OVO:** 081234567890\n\n"
            "Terima kasih atas donasinya! ❤️"
        )
        
        # Coba kirim gambar QRIS dari file lokal
        try:
            qris_paths = [
                "assets/qris.jpg",
                "images/donation_qris.jpg", 
                "qris.jpg",
                "donation_qris.jpg"
            ]
            
            qris_file = None
            for path in qris_paths:
                try:
                    with open(path, 'rb') as f:
                        qris_file = f.read()
                    logger.info(f"✅ QRIS file found: {path}")
                    break
                except FileNotFoundError:
                    continue
            
            if qris_file:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=qris_file,
                    caption=donate_text,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(donate_text)
                
        except Exception as e:
            logger.error(f"❌ Error sending QRIS image: {e}")
            await update.message.reply_text(donate_text)
            
    except Exception as e:
        logger.error(f"❌ Error in donation function: {e}")
        await update.message.reply_text("❌ Terjadi error saat menampilkan informasi donasi.")

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
        if isinstance(update, Update):
            await update.message.reply_text("❌ Hanya admin yang bisa membuat pertanyaan!")
        else:
            await update.message.reply_text("❌ Hanya admin yang bisa membuat pertanyaan!")
        return
    
    instruction_text = (
        "✏️ **Buat Pertanyaan Baru**\n\n"
        "Silakan kirim pertanyaan dalam format:\n"
        "`Pertanyaan|Jawaban1|Jawaban2|Jawaban3|...`\n\n"
        "**Contoh:**\n"
        "`Sebutkan kota di Indonesia?|Jakarta|Bandung|Surabaya|Medan|Makassar`\n\n"
        "**Note:** Minimal 1 jawaban, maksimal tidak terbatas."
    )
    
    if isinstance(update, Update):
        await update.message.reply_text(instruction_text)
    else:
        await update.message.reply_text(instruction_text)
    
    # Set state untuk menunggu input pertanyaan
    context.user_data['waiting_for_question'] = True

# Handler untuk menerima pesan teks (jawaban quiz dan pembuatan pertanyaan)
async def handle_quiz_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    user_name = update.effective_user.first_name
    
    # Cek jika user sedang membuat pertanyaan (admin only)
    if context.user_data.get('waiting_for_question') and user_id in ADMIN_IDS:
        try:
            parts = text.split('|')
            if len(parts) >= 2:
                question_text = parts[0].strip()
                answers = [ans.strip() for ans in parts[1:]]
                
                new_question = Question(question_text, answers, answers)
                new_question.created_by = user_id
                questions_db.append(new_question)
                
                await update.message.reply_text(f"✅ Pertanyaan berhasil ditambahkan dengan {len(answers)} jawaban benar!")
            else:
                await update.message.reply_text("❌ Format salah! Minimal harus ada pertanyaan dan satu jawaban.")
        
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        
        context.user_data['waiting_for_question'] = False
        return
    
    # Cek jika chat sedang dalam sesi quiz
    if chat_id in quiz_sessions:
        session = quiz_sessions[chat_id]
        question_index = session['current_question_index']
        
        if question_index < len(questions_db):
            question = questions_db[question_index]
            
            # Check if answer is correct and not already answered
            is_correct = False
            correct_answer = None
            
            for correct_ans in question.correct_answers:
                if text.lower() == correct_ans.lower() and correct_ans not in session['current_question_answers']:
                    is_correct = True
                    correct_answer = correct_ans
                    break
            
            if is_correct:
                # Tambahkan ke jawaban yang sudah diberikan
                session['current_question_answers'][correct_answer] = {
                    'user_id': user_id,
                    'user_name': user_name,
                    'timestamp': time.time()
                }
                
                # Update user score
                user_scores[user_id] = user_scores.get(user_id, 0) + 1
                
                # Update pesan pertanyaan (tanpa kirim notifikasi terpisah)
                await update_quiz_message(context, chat_id, session)
                
                # Cek jika semua jawaban sudah ditemukan
                if len(session['current_question_answers']) == len(question.correct_answers):
                    # Tunggu sebentar sebelum pindah ke pertanyaan berikutnya
                    await asyncio.sleep(2)
                    await update.message.reply_text(
                        f"🎉 Selamat! Semua jawaban sudah ditemukan!\n"
                        f"Gunakan /next untuk pertanyaan berikutnya."
                    )
            
            else:
                # Jawaban salah atau sudah dijawab - tidak perlu beri feedback
                # Biarkan user terus mencoba tanpa gangguan notifikasi
                pass

# Inisialisasi questions saat module di-load
initialize_sample_questions()
