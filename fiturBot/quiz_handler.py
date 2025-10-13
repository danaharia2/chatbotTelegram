# fiturBot/quiz_handler.py
import logging
import json
import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler, MessageHandler, filters
from config import ADMIN_IDS, GROUP_CHAT_ID

logger = logging.getLogger(__name__)

class QuizManager:
    def __init__(self):
        self.quizzes = {}
        self.user_sessions = {}  # {user_id: {quiz_id, current_question, answers, score}}
        self.user_scores = {}
        self.quiz_file = "quizzes.json"
        self.scores_file = "quiz_scores.json"
        self.load_data()
    
    def load_data(self):
        """Load quiz data and scores from files"""
        try:
            if os.path.exists(self.quiz_file):
                with open(self.quiz_file, 'r', encoding='utf-8') as f:
                    self.quizzes = json.load(f)
                logger.info(f"✅ Loaded {len(self.quizzes)} quizzes from file")
        except Exception as e:
            logger.error(f"❌ Error loading quizzes: {e}")
            self.quizzes = {}
        
        try:
            if os.path.exists(self.scores_file):
                with open(self.scores_file, 'r', encoding='utf-8') as f:
                    self.user_scores = json.load(f)
                logger.info(f"✅ Loaded scores for {len(self.user_scores)} users")
        except Exception as e:
            logger.error(f"❌ Error loading scores: {e}")
            self.user_scores = {}
    
    def save_data(self):
        """Save quiz data and scores to files"""
        try:
            with open(self.quiz_file, 'w', encoding='utf-8') as f:
                json.dump(self.quizzes, f, ensure_ascii=False, indent=2)
            
            with open(self.scores_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_scores, f, ensure_ascii=False, indent=2)
            
            logger.info("✅ Quiz data saved successfully")
        except Exception as e:
            logger.error(f"❌ Error saving quiz data: {e}")
    
    def create_quiz(self, quiz_id, title, questions, created_by):
        """Create a new quiz"""
        self.quizzes[quiz_id] = {
            'title': title,
            'questions': questions,
            'created_by': created_by,
            'created_at': datetime.now().isoformat(),
            'total_questions': len(questions)
        }
        self.save_data()
        return quiz_id
    
    def get_quiz(self, quiz_id):
        """Get quiz by ID"""
        return self.quizzes.get(quiz_id)
    
    def start_user_quiz(self, user_id, quiz_id):
        """Start a quiz session for a user"""
        if quiz_id not in self.quizzes:
            return False
        
        self.user_sessions[user_id] = {
            'quiz_id': quiz_id,
            'current_question': 0,
            'answers': [],
            'score': 0,
            'start_time': datetime.now().isoformat(),
            'completed': False
        }
        return True
    
    def get_current_question(self, user_id):
        """Get current question for user's quiz session"""
        if user_id not in self.user_sessions:
            return None
        
        session = self.user_sessions[user_id]
        quiz_id = session['quiz_id']
        current_q = session['current_question']
        
        if current_q >= len(self.quizzes[quiz_id]['questions']):
            return None
        
        return self.quizzes[quiz_id]['questions'][current_q]
    
    def submit_answer(self, user_id, answer_index):
        """Submit answer and move to next question"""
        if user_id not in self.user_sessions:
            return False, "No active quiz session"
        
        session = self.user_sessions[user_id]
        current_question = self.get_current_question(user_id)
        
        if not current_question:
            return False, "Quiz finished"
        
        is_correct = (answer_index == current_question['correct_answer'])
        
        # Record the answer
        session['answers'].append({
            'question_index': session['current_question'],
            'answer': answer_index,
            'correct': is_correct,
            'time': datetime.now().isoformat()
        })
        
        # Update score if correct
        if is_correct:
            session['score'] += 1
        
        # Move to next question
        session['current_question'] += 1
        
        # Check if quiz completed
        quiz_data = self.quizzes[session['quiz_id']]
        if session['current_question'] >= len(quiz_data['questions']):
            session['completed'] = True
            # Save to global scores
            self._save_user_score(user_id, session)
            return True, "completed"
        
        return True, "next_question"
    
    def _save_user_score(self, user_id, session):
        """Save user's quiz score to global scores"""
        quiz_id = session['quiz_id']
        score = session['score']
        total_questions = self.quizzes[quiz_id]['total_questions']
        
        # Initialize user data if not exists
        if str(user_id) not in self.user_scores:
            self.user_scores[str(user_id)] = {
                'username': f"User_{user_id}",  # Will be updated when we have actual username
                'total_quizzes': 0,
                'total_score': 0,
                'quizzes_taken': []
            }
        
        # Update user scores
        self.user_scores[str(user_id)]['total_quizzes'] += 1
        self.user_scores[str(user_id)]['total_score'] += score
        self.user_scores[str(user_id)]['quizzes_taken'].append({
            'quiz_id': quiz_id,
            'score': score,
            'total_questions': total_questions,
            'date': datetime.now().isoformat()
        })
        
        self.save_data()
    
    def get_user_session(self, user_id):
        """Get user's current quiz session"""
        return self.user_sessions.get(user_id)
    
    def get_leaderboard(self, limit=10):
        """Get global leaderboard"""
        try:
            if not self.user_scores:
                return []
            
            # Convert to list and sort by total_score descending
            leaderboard_data = []
            for user_id, data in self.user_scores.items():
                leaderboard_data.append((user_id, data))
            
            # Sort by total_score descending
            sorted_scores = sorted(
                leaderboard_data,
                key=lambda x: x[1]['total_score'],
                reverse=True
            )[:limit]
            
            return sorted_scores
        except Exception as e:
            logger.error(f"❌ Error in get_leaderboard: {e}")
            return []

# Global quiz manager instance
quiz_manager = QuizManager()

# Command handlers
async def quiz_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quiz help"""
    help_text = """
🎯 **FITUR QUIZ PERSONAL** 🎯

**Untuk Semua Peserta:**
• `/start_quiz <quiz_id>` - Mulai mengerjakan quiz
• `/continue_quiz` - Lanjutkan quiz yang sedang dikerjakan
• `/quiz_leaderboard` - Lihat peringkat global
• `/my_quiz_stats` - Statistik quiz pribadi
• `/my_score` - Lihat score quiz terakhir

**Untuk Admin:**
• `/create_quiz` - Buat quiz baru (interaktif)
• `/list_quizzes` - Daftar semua quiz
• `/quiz_status` - Lihat status quiz participants

**📝 Cara Mengerjakan:**
1. Lihat daftar quiz: `/list_quizzes`
2. Mulai quiz: `/start_quiz ID_QUIZ`
3. Jawab soal satu per satu
4. Otomatis lanjut ke soal berikutnya
5. Dapatkan score di akhir quiz

**🏆 Fitur:**
• Setiap peserta punya progress sendiri
• Bisa dikerjakan kapan saja
• Score otomatis tersimpan
• Leaderboard real-time
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def create_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start quiz creation process"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa membuat quiz.")
        return
    
    # Initialize quiz creation process
    context.user_data['quiz_creation'] = {
        'step': 'title',
        'questions': [],
        'title': None
    }
    
    await update.message.reply_text(
        "🎯 **Membuat Quiz Baru**\n\n"
        "Silakan kirim judul untuk quiz ini:"
    )

async def handle_quiz_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz creation messages"""
    user_id = update.effective_user.id
    
    # Check if user is in quiz creation mode
    if 'quiz_creation' not in context.user_data:
        return
    
    creation_data = context.user_data['quiz_creation']
    step = creation_data['step']
    text = update.message.text
    
    logger.info(f"Quiz creation - Step: {step}, User: {user_id}")
    
    try:
        if step == 'title':
            creation_data['title'] = text
            creation_data['step'] = 'question'
            await update.message.reply_text(
                "✅ **Judul disimpan!**\n\n"
                "Silakan kirim pertanyaan pertama:"
            )
        
        elif step == 'question':
            creation_data['current_question'] = {
                'question': text,
                'options': [],
                'correct_answer': None
            }
            creation_data['step'] = 'option_1'
            await update.message.reply_text(
                "✅ **Pertanyaan disimpan!**\n\n"
                "Silakan kirim opsi jawaban **pertama**:"
            )
        
        elif step.startswith('option_'):
            option_num = int(step.split('_')[1])
            creation_data['current_question']['options'].append(text)
            
            if option_num < 4:
                creation_data['step'] = f'option_{option_num + 1}'
                await update.message.reply_text(
                    f"✅ Opsi {option_num} disimpan!\n\n"
                    f"Silakan kirim opsi jawaban **{option_num + 1}**:"
                )
            else:
                creation_data['step'] = 'correct_answer'
                
                # Create inline keyboard for correct answer selection
                keyboard = []
                for i, option in enumerate(creation_data['current_question']['options']):
                    keyboard.append([InlineKeyboardButton(
                        f"Opsi {i+1}: {option}", 
                        callback_data=f"quiz_correct_{i}"
                    )])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                question_text = creation_data['current_question']['question']
                options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(creation_data['current_question']['options'])])
                
                await update.message.reply_text(
                    f"📝 **Pertanyaan:** {question_text}\n\n"
                    f"📋 **Opsi Jawaban:**\n{options_text}\n\n"
                    "**Pilih jawaban yang benar:**",
                    reply_markup=reply_markup
                )
        
        elif step == 'add_more':
            if text.lower() in ['ya', 'yes', 'y', 'iya', 'yup']:
                creation_data['step'] = 'question'
                await update.message.reply_text(
                    "✅ **Mari tambah pertanyaan lagi!**\n\n"
                    "Silakan kirim pertanyaan berikutnya:"
                )
            else:
                # Finish quiz creation
                quiz_id = f"quiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                quiz_title = creation_data['title']
                questions = creation_data['questions']
                
                quiz_manager.create_quiz(
                    quiz_id,
                    quiz_title,
                    questions,
                    user_id
                )
                
                # Clear creation data
                del context.user_data['quiz_creation']
                
                await update.message.reply_text(
                    f"🎉 **QUIZ BERHASIL DIBUAT!** 🎉\n\n"
                    f"📖 **Judul:** {quiz_title}\n"
                    f"❓ **Jumlah Pertanyaan:** {len(questions)}\n"
                    f"🆔 **ID Quiz:** `{quiz_id}`\n\n"
                    f"**Bagikan ke peserta:**\n"
                    f"`/start_quiz {quiz_id}`\n\n"
                    f"**Atau lihat daftar quiz:** `/list_quizzes`",
                    parse_mode='Markdown'
                )
                
    except Exception as e:
        logger.error(f"Error in quiz creation: {e}")
        await update.message.reply_text(
            "❌ Terjadi error saat membuat quiz. Silakan mulai ulang dengan `/create_quiz`"
        )
        # Clear faulty creation data
        if 'quiz_creation' in context.user_data:
            del context.user_data['quiz_creation']

async def list_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available quizzes"""
    if not quiz_manager.quizzes:
        await update.message.reply_text("❌ Belum ada quiz yang dibuat.")
        return
    
    quizzes_text = "📚 **DAFTAR QUIZ YANG TERSEDIA**\n\n"
    
    for i, (quiz_id, quiz_data) in enumerate(quiz_manager.quizzes.items(), 1):
        quizzes_text += f"**{i}. {quiz_data['title']}**\n"
        quizzes_text += f"   🆔 `{quiz_id}`\n"
        quizzes_text += f"   ❓ {quiz_data['total_questions']} pertanyaan\n"
        quizzes_text += f"   👤 Dibuat oleh: {quiz_data['created_by']}\n"
        quizzes_text += f"   📅 {quiz_data['created_at'][:10]}\n\n"
    
    quizzes_text += "\n**Cara mengerjakan:** `/start_quiz ID_QUIZ`"
    
    await update.message.reply_text(quizzes_text, parse_mode='Markdown')

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a personal quiz session for user"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Format salah!**\n\n"
            "**Cara yang benar:**\n"
            "`/start_quiz ID_QUIZ`\n\n"
            "**Contoh:**\n"
            "`/start_quiz quiz_20241012_143022`\n\n"
            "Lihat daftar quiz dengan `/list_quizzes`",
            parse_mode='Markdown'
        )
        return
    
    quiz_id = context.args[0]
    
    # Check if quiz exists
    quiz = quiz_manager.get_quiz(quiz_id)
    if not quiz:
        await update.message.reply_text(
            f"❌ Quiz dengan ID `{quiz_id}` tidak ditemukan.\n\n"
            "Gunakan `/list_quizzes` untuk melihat daftar quiz yang tersedia.",
            parse_mode='Markdown'
        )
        return
    
    # Check if user already has an active session
    current_session = quiz_manager.get_user_session(user_id)
    if current_session and not current_session['completed']:
        await update.message.reply_text(
            f"⚠️ **Anda memiliki quiz yang belum selesai!**\n\n"
            f"Quiz: {quiz_manager.quizzes[current_session['quiz_id']]['title']}\n"
            f"Progress: {current_session['current_question']}/{quiz_manager.quizzes[current_session['quiz_id']]['total_questions']} soal\n\n"
            f"Gunakan `/continue_quiz` untuk melanjutkan quiz yang sedang berjalan.",
            parse_mode='Markdown'
        )
        return
    
    # Start new quiz session
    if quiz_manager.start_user_quiz(user_id, quiz_id):
        # Update username in scores if exists
        if str(user_id) in quiz_manager.user_scores:
            quiz_manager.user_scores[str(user_id)]['username'] = username
        
        question = quiz_manager.get_current_question(user_id)
        if question:
            await send_question(update, context, question, 1, quiz['total_questions'])
        else:
            await update.message.reply_text("❌ Quiz tidak memiliki pertanyaan.")
    else:
        await update.message.reply_text("❌ Gagal memulai quiz.")

async def continue_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Continue user's current quiz session"""
    user_id = update.effective_user.id
    
    # Check if user has an active session
    session = quiz_manager.get_user_session(user_id)
    if not session:
        await update.message.reply_text(
            "❌ **Anda tidak memiliki quiz yang aktif!**\n\n"
            "Gunakan `/start_quiz ID_QUIZ` untuk memulai quiz baru."
        )
        return
    
    if session['completed']:
        await update.message.reply_text(
            "✅ **Quiz sudah selesai!**\n\n"
            f"Score akhir: {session['score']}/{quiz_manager.quizzes[session['quiz_id']]['total_questions']}\n\n"
            "Gunakan `/start_quiz ID_QUIZ` untuk memulai quiz baru."
        )
        return
    
    question = quiz_manager.get_current_question(user_id)
    if question:
        quiz_data = quiz_manager.quizzes[session['quiz_id']]
        current_q = session['current_question'] + 1
        total_q = quiz_data['total_questions']
        
        await update.message.reply_text(
            f"🔄 **Melanjutkan Quiz**\n\n"
            f"📖 {quiz_data['title']}\n"
            f"📍 Soal {current_q} dari {total_q}\n"
            f"🏆 Score sementara: {session['score']}"
        )
        
        await send_question(update, context, question, current_q, total_q)
    else:
        await update.message.reply_text("❌ Tidak ada soal yang tersedia.")

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question, current_q, total_q):
    """Send question with inline keyboard"""
    keyboard = []
    for i, option in enumerate(question['options']):
        keyboard.append([InlineKeyboardButton(
            f"{i+1}. {option}", 
            callback_data=f"quiz_answer_{i}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        f"❓ **SOAL {current_q}/{total_q}**\n\n"
        f"{question['question']}\n\n"
        f"⏳ **Waktu:** Tidak terbatas\n"
        f"💡 **Tips:** Jawab dengan menekan tombol di bawah"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz answer callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.first_name
    
    logger.info(f"Quiz callback - Data: {data}, User: {username}")
    
    try:
        if data.startswith("quiz_answer_"):
            answer_index = int(data.split("_")[2])
            
            success, result = quiz_manager.submit_answer(user_id, answer_index)
            
            if success:
                session = quiz_manager.get_user_session(user_id)
                current_question = quiz_manager.get_current_question(user_id)
                
                if result == "completed":
                    # Quiz finished
                    quiz_data = quiz_manager.quizzes[session['quiz_id']]
                    score = session['score']
                    total_questions = quiz_data['total_questions']
                    
                    # Calculate percentage
                    percentage = (score / total_questions) * 100
                    
                    # Determine grade
                    if percentage >= 90:
                        grade = "🅰️ LUAR BIASA!"
                    elif percentage >= 80:
                        grade = "🅱️ BAIK SEKALI!"
                    elif percentage >= 70:
                        grade = "🅱️ BAIK!"
                    elif percentage >= 60:
                        grade = "🅲️ CUKUP!"
                    else:
                        grade = "🅳️ PERLU BELAJAR LAGI!"
                    
                    results_text = (
                        f"🏆 **SELAMAT! QUIZ SELESAI** 🏆\n\n"
                        f"📖 **Quiz:** {quiz_data['title']}\n"
                        f"✅ **Score:** {score}/{total_questions}\n"
                        f"📊 **Persentase:** {percentage:.1f}%\n"
                        f"🎓 **Grade:** {grade}\n\n"
                    )
                    
                    # Add correct answers review
                    results_text += "**📝 Review Jawaban:**\n"
                    for i, answer in enumerate(session['answers']):
                        question_data = quiz_data['questions'][i]
                        user_answer = question_data['options'][answer['answer']]
                        correct_answer = question_data['options'][question_data['correct_answer']]
                        status = "✅" if answer['correct'] else "❌"
                        
                        results_text += f"{status} Soal {i+1}: {user_answer}\n"
                        if not answer['correct']:
                            results_text += f"   💡 Jawaban benar: {correct_answer}\n"
                    
                    results_text += f"\n**🏅 Peringkat Anda:**\n"
                    results_text += f"Gunakan `/my_score` untuk melihat score\n"
                    results_text += f"Gunakan `/quiz_leaderboard` untuk melihat leaderboard\n"
                    results_text += f"Gunakan `/start_quiz ID_QUIZ` untuk quiz baru"
                    
                    await query.edit_message_text(
                        text=query.message.text + f"\n\n🎯 **Jawaban {'benar' if session['answers'][-1]['correct'] else 'salah'}!**",
                        parse_mode='Markdown'
                    )
                    
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=results_text,
                        parse_mode='Markdown'
                    )
                    
                else:
                    # Next question
                    quiz_data = quiz_manager.quizzes[session['quiz_id']]
                    current_q = session['current_question'] + 1
                    total_q = quiz_data['total_questions']
                    
                    # Update username
                    if str(user_id) in quiz_manager.user_scores:
                        quiz_manager.user_scores[str(user_id)]['username'] = username
                    
                    await query.edit_message_text(
                        text=query.message.text + f"\n\n{'✅' if session['answers'][-1]['correct'] else '❌'} **Jawaban {'benar' if session['answers'][-1]['correct'] else 'salah'}!**\n\n⏩ **Lanjut ke soal berikutnya...**",
                        parse_mode='Markdown'
                    )
                    
                    # Send next question after a short delay
                    await asyncio.sleep(1)
                    
                    next_question = quiz_manager.get_current_question(user_id)
                    if next_question:
                        await send_question(update, context, next_question, current_q, total_q)
            
            else:
                await query.answer(f"⚠️ {result}", show_alert=True)
        
        elif data.startswith("quiz_correct_"):
            # Handle correct answer selection during quiz creation
            correct_answer = int(data.split("_")[2])
            
            if 'quiz_creation' in context.user_data:
                creation_data = context.user_data['quiz_creation']
                creation_data['current_question']['correct_answer'] = correct_answer
                creation_data['questions'].append(creation_data['current_question'])
                creation_data['step'] = 'add_more'
                
                await query.edit_message_text(
                    text=query.message.text + f"\n\n✅ **Jawaban benar disimpan: Opsi {correct_answer + 1}**",
                    parse_mode='Markdown'
                )
                
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="✅ **Pertanyaan berhasil disimpan!**\n\n"
                         "Mau tambah pertanyaan lagi?\n"
                         "Ketik **`ya`** untuk tambah pertanyaan\n"
                         "Ketik **`tidak`** untuk selesai"
                )
                
    except Exception as e:
        logger.error(f"Error in quiz callback: {e}")
        await query.answer("❌ Terjadi error saat memproses jawaban.", show_alert=True)

async def my_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's current quiz score"""
    user_id = update.effective_user.id
    
    session = quiz_manager.get_user_session(user_id)
    if not session:
        await update.message.reply_text(
            "❌ **Anda belum mengerjakan quiz!**\n\n"
            "Gunakan `/start_quiz ID_QUIZ` untuk memulai quiz."
        )
        return
    
    quiz_data = quiz_manager.quizzes[session['quiz_id']]
    
    if session['completed']:
        score_text = (
            f"📊 **HASIL QUIZ TERAKHIR**\n\n"
            f"📖 **Quiz:** {quiz_data['title']}\n"
            f"✅ **Score:** {session['score']}/{quiz_data['total_questions']}\n"
            f"📅 **Waktu:** {session['start_time'][:10]}\n\n"
            f"🏆 **Status:** Selesai"
        )
    else:
        score_text = (
            f"📊 **PROGRESS QUIZ SAAT INI**\n\n"
            f"📖 **Quiz:** {quiz_data['title']}\n"
            f"📍 **Progress:** {session['current_question']}/{quiz_data['total_questions']} soal\n"
            f"✅ **Score sementara:** {session['score']}\n"
            f"📅 **Mulai:** {session['start_time'][:10]}\n\n"
            f"🔄 **Status:** Sedang berjalan\n"
            f"Gunakan `/continue_quiz` untuk melanjutkan"
        )
    
    await update.message.reply_text(score_text, parse_mode='Markdown')

async def quiz_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show global leaderboard"""
    try:
        leaderboard = quiz_manager.get_leaderboard(10)
        
        if not leaderboard:
            await update.message.reply_text(
                "❌ **Belum ada data leaderboard!**\n\n"
                "Ikuti quiz terlebih dahulu untuk melihat peringkat."
            )
            return
        
        leaderboard_text = "🏆 **LEADERBOARD GLOBAL** 🏆\n\n"
        
        for i, (user_id, data) in enumerate(leaderboard, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            leaderboard_text += f"{medal} **{data['username']}** - {data['total_score']} poin ({data['total_quizzes']} quiz)\n"
        
        leaderboard_text += f"\n**Total pemain:** {len(quiz_manager.user_scores)}"
        
        await update.message.reply_text(leaderboard_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Error in quiz_leaderboard: {e}")
        await update.message.reply_text("❌ Terjadi error saat mengambil leaderboard.")

async def my_quiz_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's quiz statistics"""
    user_id = update.effective_user.id
    
    if str(user_id) not in quiz_manager.user_scores:
        await update.message.reply_text(
            "❌ **Anda belum pernah mengikuti quiz!**\n\n"
            "Gunakan `/start_quiz ID_QUIZ` untuk memulai quiz pertama Anda!"
        )
        return
    
    stats = quiz_manager.user_scores[str(user_id)]
    
    stats_text = f"📊 **STATISTIK QUIZ ANDA**\n\n"
    stats_text += f"👤 **Nama:** {stats['username']}\n"
    stats_text += f"📈 **Total Score:** {stats['total_score']} poin\n"
    stats_text += f"🎯 **Quiz Diselesaikan:** {stats['total_quizzes']}\n"
    
    if stats['total_quizzes'] > 0:
        avg_score = stats['total_score'] / stats['total_quizzes']
        stats_text += f"📊 **Rata-rata Score:** {avg_score:.1f} per quiz\n"
    
    stats_text += f"\n**📅 5 Quiz Terakhir:**\n"
    for quiz in stats['quizzes_taken'][-5:]:
        quiz_data = quiz_manager.get_quiz(quiz['quiz_id'])
        quiz_title = quiz_data['title'] if quiz_data else "Quiz Terhapus"
        percentage = (quiz['score'] / quiz['total_questions']) * 100
        stats_text += f"• {quiz_title}: {quiz['score']}/{quiz['total_questions']} ({percentage:.1f}%) - {quiz['date'][:10]}\n"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def quiz_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quiz status (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa melihat status quiz.")
        return
    
    active_sessions = len([s for s in quiz_manager.user_sessions.values() if not s['completed']])
    total_users = len(quiz_manager.user_scores)
    total_quizzes = len(quiz_manager.quizzes)
    
    status_text = (
        f"📈 **STATUS SISTEM QUIZ**\n\n"
        f"📊 **Quiz Tersedia:** {total_quizzes}\n"
        f"👥 **Total Peserta:** {total_users}\n"
        f"🔄 **Session Aktif:** {active_sessions}\n"
        f"🏆 **Leaderboard Entries:** {len(quiz_manager.user_scores)}\n\n"
    )
    
    # Show recent active sessions
    if active_sessions > 0:
        status_text += "**🎯 Session Aktif:**\n"
        for user_id, session in list(quiz_manager.user_sessions.items())[:5]:
            if not session['completed']:
                quiz_data = quiz_manager.quizzes[session['quiz_id']]
                username = quiz_manager.user_scores.get(str(user_id), {}).get('username', f'User_{user_id}')
                status_text += f"• {username}: {session['current_question']}/{quiz_data['total_questions']} soal\n"
    
    await update.message.reply_text(status_text, parse_mode='Markdown')
