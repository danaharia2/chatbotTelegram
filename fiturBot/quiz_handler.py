# fiturBot/quiz_handler.py
import logging
import random
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from config import ADMIN_IDS, GROUP_CHAT_ID

logger = logging.getLogger(__name__)

class QuizManager:
    def __init__(self):
        self.quizzes = {}
        self.active_quizzes = {}
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
    
    def start_quiz(self, quiz_id, chat_id):
        """Start a quiz in a chat"""
        if quiz_id not in self.quizzes:
            return False
        
        self.active_quizzes[chat_id] = {
            'quiz_id': quiz_id,
            'current_question': 0,
            'participants': {},
            'start_time': datetime.now().isoformat()
        }
        return True
    
    def get_current_question(self, chat_id):
        """Get current question for active quiz"""
        if chat_id not in self.active_quizzes:
            return None
        
        active_quiz = self.active_quizzes[chat_id]
        quiz_id = active_quiz['quiz_id']
        current_q = active_quiz['current_question']
        
        if current_q >= len(self.quizzes[quiz_id]['questions']):
            return None
        
        return self.quizzes[quiz_id]['questions'][current_q]
    
    def submit_answer(self, chat_id, user_id, username, answer_index):
        """Submit answer for current question"""
        if chat_id not in self.active_quizzes:
            return False, "No active quiz"
        
        active_quiz = self.active_quizzes[chat_id]
        current_question = self.get_current_question(chat_id)
        
        if not current_question:
            return False, "Quiz finished"
        
        is_correct = (answer_index == current_question['correct_answer'])
        
        # Initialize user data if not exists
        if user_id not in self.user_scores:
            self.user_scores[user_id] = {
                'username': username,
                'total_quizzes': 0,
                'total_score': 0,
                'quizzes_taken': []
            }
        
        # Update participant score
        if user_id not in active_quiz['participants']:
            active_quiz['participants'][user_id] = {
                'username': username,
                'score': 0,
                'answers': []
            }
        
        active_quiz['participants'][user_id]['answers'].append({
            'question': active_quiz['current_question'],
            'answer': answer_index,
            'correct': is_correct,
            'time': datetime.now().isoformat()
        })
        
        if is_correct:
            active_quiz['participants'][user_id]['score'] += 1
        
        return True, is_correct
    
    def next_question(self, chat_id):
        """Move to next question"""
        if chat_id not in self.active_quizzes:
            return False
        
        active_quiz = self.active_quizzes[chat_id]
        active_quiz['current_question'] += 1
        
        # Check if quiz finished
        if active_quiz['current_question'] >= len(self.quizzes[active_quiz['quiz_id']]['questions']):
            return self.finish_quiz(chat_id)
        
        return True
    
    def finish_quiz(self, chat_id):
        """Finish the quiz and calculate results"""
        if chat_id not in self.active_quizzes:
            return None
        
        active_quiz = self.active_quizzes[chat_id]
        quiz_id = active_quiz['quiz_id']
        participants = active_quiz['participants']
        
        # Update global scores
        for user_id, data in participants.items():
            if user_id not in self.user_scores:
                self.user_scores[user_id] = {
                    'username': data['username'],
                    'total_quizzes': 0,
                    'total_score': 0,
                    'quizzes_taken': []
                }
            
            self.user_scores[user_id]['total_quizzes'] += 1
            self.user_scores[user_id]['total_score'] += data['score']
            self.user_scores[user_id]['quizzes_taken'].append({
                'quiz_id': quiz_id,
                'score': data['score'],
                'total_questions': self.quizzes[quiz_id]['total_questions'],
                'date': datetime.now().isoformat()
            })
        
        self.save_data()
        
        # Prepare results
        results = {
            'quiz_title': self.quizzes[quiz_id]['title'],
            'participants': sorted(participants.items(), key=lambda x: x[1]['score'], reverse=True),
            'total_questions': self.quizzes[quiz_id]['total_questions']
        }
        
        # Remove active quiz
        del self.active_quizzes[chat_id]
        
        return results
    
    def get_leaderboard(self, limit=10):
        """Get global leaderboard"""
        sorted_scores = sorted(
            self.user_scores.items(),
            key=lambda x: x[1]['total_score'],
            reverse=True
        )[:limit]
        
        return sorted_scores

# Global quiz manager instance
quiz_manager = QuizManager()

# Quiz creation helper
async def create_quiz_interactive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interactive quiz creation"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa membuat quiz.")
        return
    
    context.user_data['quiz_creation'] = {
        'step': 'title',
        'questions': []
    }
    
    await update.message.reply_text(
        "🎯 **Membuat Quiz Baru**\n\n"
        "Silakan kirim judul untuk quiz ini:"
    )

async def handle_quiz_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle interactive quiz creation steps"""
    user_id = update.effective_user.id
    
    if 'quiz_creation' not in context.user_data:
        return
    
    creation_data = context.user_data['quiz_creation']
    step = creation_data['step']
    text = update.message.text
    
    if step == 'title':
        creation_data['title'] = text
        creation_data['step'] = 'question'
        await update.message.reply_text(
            "✅ Judul disimpan!\n\n"
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
            "✅ Pertanyaan disimpan!\n\n"
            "Silakan kirim opsi jawaban pertama:"
        )
    
    elif step.startswith('option_'):
        option_num = int(step.split('_')[1])
        creation_data['current_question']['options'].append(text)
        
        if option_num < 4:
            creation_data['step'] = f'option_{option_num + 1}'
            await update.message.reply_text(
                f"✅ Opsi {option_num} disimpan!\n\n"
                f"Silakan kirim opsi jawaban {option_num + 1}:"
            )
        else:
            creation_data['step'] = 'correct_answer'
            keyboard = [
                [InlineKeyboardButton("1", callback_data="quiz_correct_1")],
                [InlineKeyboardButton("2", callback_data="quiz_correct_2")],
                [InlineKeyboardButton("3", callback_data="quiz_correct_3")],
                [InlineKeyboardButton("4", callback_data="quiz_correct_4")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(creation_data['current_question']['options'])])
            
            await update.message.reply_text(
                f"📝 **Pertanyaan:** {creation_data['current_question']['question']}\n\n"
                f"📋 **Opsi:**\n{options_text}\n\n"
                f"Pilih jawaban yang benar:",
                reply_markup=reply_markup
            )
    
    elif step == 'add_more':
        if text.lower() in ['ya', 'yes', 'y']:
            creation_data['step'] = 'question'
            await update.message.reply_text("Silakan kirim pertanyaan berikutnya:")
        else:
            # Finish quiz creation
            quiz_id = f"quiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            quiz_manager.create_quiz(
                quiz_id,
                creation_data['title'],
                creation_data['questions'],
                user_id
            )
            
            await update.message.reply_text(
                f"✅ **Quiz Berhasil Dibuat!**\n\n"
                f"📖 Judul: {creation_data['title']}\n"
                f"❓ Jumlah Pertanyaan: {len(creation_data['questions'])}\n"
                f"🆔 ID: `{quiz_id}`\n\n"
                f"Gunakan `/start_quiz {quiz_id}` untuk memulai quiz!",
                parse_mode='Markdown'
            )
            del context.user_data['quiz_creation']

# Command handlers
async def quiz_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quiz help"""
    help_text = """
🎯 **FITUR QUIZ BOT** 🎯

**Untuk Peserta:**
• `/join_quiz` - Bergabung dengan quiz aktif
• `/quiz_leaderboard` - Lihat peringkat global
• `/my_quiz_stats` - Statistik quiz pribadi

**Untuk Admin:**
• `/create_quiz` - Buat quiz baru (interaktif)
• `/list_quizzes` - Daftar semua quiz
• `/start_quiz <quiz_id>` - Mulai quiz
• `/next_question` - Pertanyaan berikutnya
• `/finish_quiz` - Akhiri quiz
• `/quiz_results` - Lihat hasil quiz terakhir

**Cara Main:**
1. Admin buat quiz dengan `/create_quiz`
2. Admin mulai quiz dengan `/start_quiz`
3. Peserta join dengan `/join_quiz`
4. Jawab pertanyaan dengan tombol inline
5. Lihat hasil di akhir quiz
"""
    await update.message.reply_text(help_text)

async def create_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start quiz creation"""
    await create_quiz_interactive(update, context)

async def list_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available quizzes"""
    if not quiz_manager.quizzes:
        await update.message.reply_text("❌ Belum ada quiz yang dibuat.")
        return
    
    quizzes_text = "📚 **DAFTAR QUIZ**\n\n"
    for quiz_id, quiz_data in quiz_manager.quizzes.items():
        quizzes_text += f"📖 **{quiz_data['title']}**\n"
        quizzes_text += f"   🆔 `{quiz_id}`\n"
        quizzes_text += f"   ❓ {quiz_data['total_questions']} pertanyaan\n"
        quizzes_text += f"   👤 Dibuat oleh: {quiz_data['created_by']}\n"
        quizzes_text += f"   📅 {quiz_data['created_at'][:10]}\n\n"
    
    await update.message.reply_text(quizzes_text, parse_mode='Markdown')

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a quiz"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa memulai quiz.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Format: `/start_quiz <quiz_id>`", parse_mode='Markdown')
        return
    
    quiz_id = context.args[0]
    
    if quiz_manager.start_quiz(quiz_id, update.effective_chat.id):
        # Send first question
        question = quiz_manager.get_current_question(update.effective_chat.id)
        if question:
            await send_question(update, context, question)
        else:
            await update.message.reply_text("❌ Quiz tidak memiliki pertanyaan.")
    else:
        await update.message.reply_text("❌ Quiz ID tidak ditemukan.")

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question):
    """Send question with inline keyboard"""
    keyboard = []
    for i, option in enumerate(question['options']):
        keyboard.append([InlineKeyboardButton(
            f"{i+1}. {option}", 
            callback_data=f"quiz_answer_{i}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"❓ **PERTANYAAN**\n\n{question['question']}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Store message ID for possible editing
    if 'quiz_messages' not in context.chat_data:
        context.chat_data['quiz_messages'] = []
    context.chat_data['quiz_messages'].append(message.message_id)

async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Move to next question"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa mengontrol quiz.")
        return
    
    if update.effective_chat.id not in quiz_manager.active_quizzes:
        await update.message.reply_text("❌ Tidak ada quiz aktif.")
        return
    
    if quiz_manager.next_question(update.effective_chat.id):
        question = quiz_manager.get_current_question(update.effective_chat.id)
        if question:
            await send_question(update, context, question)
        else:
            await update.message.reply_text("❌ Tidak ada pertanyaan berikutnya.")
    else:
        # Quiz finished
        results = quiz_manager.finish_quiz(update.effective_chat.id)
        if results:
            await show_quiz_results(update, context, results)

async def finish_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force finish quiz"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa mengakhiri quiz.")
        return
    
    if update.effective_chat.id not in quiz_manager.active_quizzes:
        await update.message.reply_text("❌ Tidak ada quiz aktif.")
        return
    
    results = quiz_manager.finish_quiz(update.effective_chat.id)
    if results:
        await show_quiz_results(update, context, results)
    else:
        await update.message.reply_text("❌ Gagal mengakhiri quiz.")

async def show_quiz_results(update: Update, context: ContextTypes.DEFAULT_TYPE, results):
    """Show quiz results"""
    results_text = f"🏆 **HASIL QUIZ: {results['quiz_title']}** 🏆\n\n"
    
    if not results['participants']:
        results_text += "❌ Tidak ada peserta yang mengikuti quiz."
    else:
        for i, (user_id, data) in enumerate(results['participants'][:10], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            results_text += f"{medal} {data['username']} - {data['score']}/{results['total_questions']}\n"
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=results_text,
        parse_mode='Markdown'
    )

async def quiz_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show global leaderboard"""
    leaderboard = quiz_manager.get_leaderboard(10)
    
    if not leaderboard:
        await update.message.reply_text("❌ Belum ada data leaderboard.")
        return
    
    leaderboard_text = "🏆 **LEADERBOARD GLOBAL** 🏆\n\n"
    
    for i, (user_id, data) in enumerate(leaderboard, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        leaderboard_text += f"{medal} {data['username']} - {data['total_score']} poin ({data['total_quizzes']} quiz)\n"
    
    await update.message.reply_text(leaderboard_text, parse_mode='Markdown')

async def my_quiz_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's quiz statistics"""
    user_id = update.effective_user.id
    
    if user_id not in quiz_manager.user_scores:
        await update.message.reply_text("❌ Anda belum pernah mengikuti quiz.")
        return
    
    stats = quiz_manager.user_scores[user_id]
    
    stats_text = f"📊 **STATISTIK QUIZ ANDA**\n\n"
    stats_text += f"👤 **Username:** {stats['username']}\n"
    stats_text += f"📈 **Total Score:** {stats['total_score']} poin\n"
    stats_text += f"🎯 **Quiz Diselesaikan:** {stats['total_quizzes']}\n"
    
    if stats['total_quizzes'] > 0:
        avg_score = stats['total_score'] / stats['total_quizzes']
        stats_text += f"📊 **Rata-rata Score:** {avg_score:.1f} per quiz\n"
    
    stats_text += f"\n**Quiz Terakhir:**\n"
    for quiz in stats['quizzes_taken'][-5:]:  # Last 5 quizzes
        stats_text += f"• Score: {quiz['score']}/{quiz['total_questions']} ({quiz['date'][:10]})\n"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# Callback query handler for quiz answers
async def handle_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz callback queries"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("quiz_answer_"):
        answer_index = int(data.split("_")[2])
        user_id = query.from_user.id
        username = query.from_user.first_name
        
        success, result = quiz_manager.submit_answer(
            query.message.chat_id,
            user_id,
            username,
            answer_index
        )
        
        if success:
            if result:
                await query.edit_message_text(
                    text=query.message.text + f"\n\n✅ **{username} menjawab benar!**",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    text=query.message.text + f"\n\n❌ **{username} menjawab salah!**",
                    parse_mode='Markdown'
                )
        else:
            await query.edit_message_text(
                text=query.message.text + f"\n\n⚠️ {result}",
                parse_mode='Markdown'
            )
    
    elif data.startswith("quiz_correct_"):
        # Handle correct answer selection during quiz creation
        correct_answer = int(data.split("_")[2]) - 1
        
        if 'quiz_creation' in context.user_data:
            creation_data = context.user_data['quiz_creation']
            creation_data['current_question']['correct_answer'] = correct_answer
            creation_data['questions'].append(creation_data['current_question'])
            creation_data['step'] = 'add_more'
            
            await query.edit_message_text(
                text=query.message.text + f"\n\n✅ Jawaban benar disimpan: Opsi {correct_answer + 1}",
                parse_mode='Markdown'
            )
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="✅ Pertanyaan berhasil disimpan!\n\nTambah pertanyaan lagi? (ya/tidak)"
            )
