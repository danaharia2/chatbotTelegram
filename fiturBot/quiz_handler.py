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
        return quiz_id
    
    def get_quiz(self, quiz_id):
        """Get quiz by ID"""
        return self.quizzes.get(quiz_id)
    
    def start_quiz(self, quiz_id, chat_id):
        """Start a quiz in a chat"""
        if quiz_id not in self.quizzes:
            return False
        
        self.active_quizzes[chat_id] = {
            'quiz_id': quiz_id,
            'current_question': 0,
            'participants': {},
            'start_time': datetime.now().isoformat(),
            'message_id': None,
            'timer_task': None,
            'answered_users': set(),
            'is_finished': False
        }
        return True
    
    async def start_question_timer(self, context, chat_id, question_num, duration=60):
        """Start timer untuk soal saat ini - VERSI YANG LEBIH ROBUST"""
        try:
            logger.info(f"⏰ Starting {duration} second timer for question {question_num} in chat {chat_id}")
            
            # Tunggu selama duration
            await asyncio.sleep(duration)
            
            # Cek apakah quiz masih aktif dan di soal yang sama
            if (chat_id in self.active_quizzes and 
                not self.active_quizzes[chat_id].get('is_finished', False) and
                self.active_quizzes[chat_id]['current_question'] == question_num - 1):
                
                logger.info(f"⏰ Timer expired for question {question_num}, moving to next question")
                
                # Kirim notifikasi waktu habis
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⏰ **Waktu habis untuk soal {question_num}!** Melanjutkan ke soal berikutnya..."
                    )
                except Exception as e:
                    logger.error(f"❌ Error sending timeout message: {e}")
                
                # Pindah ke soal berikutnya
                await self.next_question_auto(context, chat_id)
            else:
                logger.info(f"⏰ Timer cancelled - quiz no longer active or question changed")
                
        except asyncio.CancelledError:
            logger.info(f"⏰ Timer for question {question_num} was cancelled")
        except Exception as e:
            logger.error(f"❌ Error in question timer: {e}")
            # Coba lanjutkan ke soal berikutnya meskipun ada error
            try:
                if chat_id in self.active_quizzes and not self.active_quizzes[chat_id].get('is_finished', False):
                    await self.next_question_auto(context, chat_id)
            except Exception as e2:
                logger.error(f"❌ Error in error recovery: {e2}")
    
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
    
    async def submit_answer(self, chat_id, user_id, username, answer_index):
        """Submit answer for current question - SEMUA USER BISA JAWAB"""
        if chat_id not in self.active_quizzes:
            return False, "Tidak ada quiz aktif"
        
        active_quiz = self.active_quizzes[chat_id]
        
        if active_quiz.get('is_finished', False):
            return False, "Quiz sudah selesai"
        
        current_question = self.get_current_question(chat_id)
        
        if not current_question:
            return False, "Quiz sudah selesai"
        
        is_correct = (answer_index == current_question['correct_answer'])
        
        # Initialize user data if not exists
        if str(user_id) not in self.user_scores:
            self.user_scores[str(user_id)] = {
                'username': username,
                'total_quizzes': 0,
                'total_score': 0,
                'quizzes_taken': []
            }
        
        # Update participant score untuk quiz ini
        if str(user_id) not in active_quiz['participants']:
            active_quiz['participants'][str(user_id)] = {
                'username': username,
                'score': 0,
                'answers': []
            }
        
        # SEMUA USER BISA JAWAB - TIDAK ADA PEMBATASAN
        # Cuma catat saja, tidak perlu cek apakah sudah menjawab
        
        # Tambahkan jawaban user
        active_quiz['participants'][str(user_id)]['answers'].append({
            'question_index': active_quiz['current_question'],
            'answer': answer_index,
            'correct': is_correct,
            'time': datetime.now().isoformat()
        })
        
        # Update score jika benar
        if is_correct:
            active_quiz['participants'][str(user_id)]['score'] += 1
        
        # Update username in global scores
        if str(user_id) in self.user_scores:
            self.user_scores[str(user_id)]['username'] = username
        
        return True, is_correct
    
    async def next_question_auto(self, context, chat_id):
        """Move to next question automatically"""
        if chat_id not in self.active_quizzes:
            logger.error(f"❌ No active quiz found for chat {chat_id}")
            return False
        
        active_quiz = self.active_quizzes[chat_id]
        
        # Cancel previous timer jika ada
        if active_quiz['timer_task'] and not active_quiz['timer_task'].done():
            try:
                active_quiz['timer_task'].cancel()
                logger.info("✅ Previous timer cancelled")
            except Exception as e:
                logger.error(f"❌ Error cancelling timer: {e}")
        
        active_quiz['current_question'] += 1
        active_quiz['answered_users'] = set()  # Reset untuk soal baru
        
        # Check if quiz finished
        quiz_data = self.quizzes[active_quiz['quiz_id']]
        if active_quiz['current_question'] >= len(quiz_data['questions']):
            logger.info("🎯 Quiz finished - all questions completed")
            return await self.finish_quiz_auto(context, chat_id)
        
        # Send next question
        question = self.get_current_question(chat_id)
        if not question:
            logger.error("❌ No question found for current index")
            return await self.finish_quiz_auto(context, chat_id)
        
        current_q = active_quiz['current_question']
        total_q = quiz_data['total_questions']
        
        logger.info(f"📝 Sending question {current_q + 1}/{total_q}")
        await self.send_question(context, chat_id, question, current_q + 1, total_q)
        
        # Start timer untuk soal ini
        active_quiz['timer_task'] = asyncio.create_task(
            self.start_question_timer(context, chat_id, current_q + 1, 60)
        )
        
        logger.info(f"⏰ Timer started for question {current_q + 1}")
        return True
    
    async def finish_quiz_auto(self, context, chat_id):
        """Finish the quiz automatically"""
        if chat_id not in self.active_quizzes:
            return None
        
        active_quiz = self.active_quizzes[chat_id]
        active_quiz['is_finished'] = True
        
        # Cancel timer jika ada
        if active_quiz['timer_task'] and not active_quiz['timer_task'].done():
            try:
                active_quiz['timer_task'].cancel()
            except:
                pass
        
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
        
        # Remove active quiz setelah menampilkan results
        await self.show_quiz_results(context, chat_id, results)
        
        # Hapus dari active quizzes
        if chat_id in self.active_quizzes:
            del self.active_quizzes[chat_id]
        
        return results

    async def send_question(self, context, chat_id, question, current_q, total_q):
        """Send question dengan timer info"""
        keyboard = []
        for i, option in enumerate(question['options']):
            keyboard.append([InlineKeyboardButton(
                f"{i+1}. {option}", 
                callback_data=f"quiz_answer_{i}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Tambah info timer yang lebih jelas
        timer_info = f"\n\n⏰ **Timer:** 60 detik • Otomatis lanjut ke soal berikutnya"
        multiple_info = "\n\n👥 **Semua peserta bisa menjawab!**"
        
        try:
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=f"❓ **PERTANYAAN {current_q}/{total_q}**\n\n{question['question']}{timer_info}{multiple_info}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            # Store message ID
            if chat_id in self.active_quizzes:
                self.active_quizzes[chat_id]['message_id'] = message.message_id
                
        except Exception as e:
            logger.error(f"❌ Error sending question: {e}")

    async def show_quiz_results(self, context, chat_id, results):
        """Show quiz results"""
        results_text = f"🏆 **QUIZ SELESAI: {results['quiz_title']}** 🏆\n\n"
        results_text += f"📊 **Total Pertanyaan:** {results['total_questions']}\n"
        results_text += f"👥 **Total Peserta:** {len(results['participants'])}\n\n"
        
        if not results['participants']:
            results_text += "❌ Tidak ada peserta yang mengikuti quiz."
        else:
            results_text += "**🏅 PERINGKAT:**\n\n"
            for i, (user_id, data) in enumerate(results['participants'][:10], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                results_text += f"{medal} **{data['username']}** - {data['score']}/{results['total_questions']}\n"
        
        # Tambah info statistik
        if results['participants']:
            total_score = sum(data['score'] for _, data in results['participants'])
            avg_score = total_score / len(results['participants'])
            results_text += f"\n📈 **Rata-rata Score:** {avg_score:.1f}"
        
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=results_text,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Error sending results: {e}")
    
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
🎯 **FITUR QUIZ GRUP** 🎯

**Untuk Semua Peserta:**
• `/quiz_help` - Bantuan fitur quiz
• `/quiz_leaderboard` - Lihat peringkat global
• `/my_quiz_stats` - Statistik quiz pribadi

**Untuk Admin:**
• `/create_quiz` - Buat quiz baru (interaktif)
• `/list_quizzes` - Daftar semua quiz
• `/start_quiz <quiz_id>` - Mulai quiz dengan timer otomatis
• `/next_question` - Paksa lanjut ke soal berikutnya
• `/finish_quiz` - Akhiri quiz manual

**⏰ FITUR TIMER OTOMATIS:**
• Setiap soal punya timer 60 detik
• Otomatis lanjut ke soal berikutnya
• Otomatis berakhir ketika soal habis
• Bisa dijalankan dari private chat atau grup

**👥 FITUR JAWABAN:**
• Semua peserta bisa menjawab setiap soal
• Tidak ada batasan jumlah jawaban

**📝 Cara Pakai:**
1. Buat quiz: `/create_quiz`
2. Mulai quiz: `/start_quiz ID_QUIZ`
3. Bot otomatis kirim soal ke grup
4. Setiap soal: 60 detik → auto next
5. Quiz berakhir otomatis
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
                    f"**Untuk memulai quiz, gunakan:**\n"
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
    
    quizzes_text += "\n**Cara memulai:** `/start_quiz ID_QUIZ`"
    
    await update.message.reply_text(quizzes_text, parse_mode='Markdown')

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a quiz dengan timer otomatis"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa memulai quiz.")
        return
    
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
    
    # Tentukan chat_id target
    if update.effective_chat.type == 'private':
        # Jika di private chat, kirim ke GROUP_CHAT_ID
        from config import GROUP_CHAT_ID
        if not GROUP_CHAT_ID:
            await update.message.reply_text("❌ GROUP_CHAT_ID tidak dikonfigurasi.")
            return
        target_chat_id = GROUP_CHAT_ID
        start_location = "grup"
        
        # Konfirmasi ke admin
        await update.message.reply_text(
            f"✅ **Quiz akan dimulai di grup!**\n\n"
            f"📖 **Judul:** {quiz['title']}\n"
            f"❓ **Jumlah Soal:** {quiz['total_questions']}\n"
            f"⏰ **Timer:** 60 detik per soal\n\n"
            f"Bot sedang mengirim soal pertama ke grup..."
        )
    else:
        # Jika di grup, gunakan chat_id saat ini
        target_chat_id = update.effective_chat.id
        start_location = "grup ini"
    
    # Start the quiz
    if quiz_manager.start_quiz(quiz_id, target_chat_id):
        question = quiz_manager.get_current_question(target_chat_id)
        if question:
            quiz_data = quiz_manager.quizzes[quiz_id]
            
            # Kirim pesan mulai quiz
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=f"🎯 **QUIZ DIMULAI!** 🎯\n\n"
                     f"📖 **{quiz_data['title']}**\n"
                     f"❓ **{quiz_data['total_questions']} soal** • ⏰ **60 detik per soal**\n\n"
                     f"**Instruksi:**\n"
                     f"• Klik tombol untuk menjawab\n"
                     f"• Setiap soal punya waktu 60 detik\n"
                     f"• Semua peserta bisa menjawab\n"
                     f"• Otomatis lanjut ke soal berikutnya\n"
                     f"• Selamat bermain! 🎮"
            )
            
            # Tunggu sebentar sebelum kirim soal pertama
            await asyncio.sleep(2)
            
            # Kirim soal pertama
            await quiz_manager.send_question(context, target_chat_id, question, 1, quiz_data['total_questions'])
            
            # Start timer untuk soal pertama - PASTIKAN INI DIEKSEKUSI
            active_quiz = quiz_manager.active_quizzes[target_chat_id]
            active_quiz['timer_task'] = asyncio.create_task(
                quiz_manager.start_question_timer(context, target_chat_id, 1, 60)
            )
            
            logger.info(f"✅ Quiz started successfully with timer for question 1")
            
            # Konfirmasi jika di grup
            if update.effective_chat.type != 'private':
                await update.message.reply_text(
                    f"✅ **Quiz dimulai di {start_location}!**\n\n"
                    f"⏰ **Timer aktif:** 60 detik per soal\n"
                    f"🔢 **Total soal:** {quiz_data['total_questions']}\n"
                    f"👥 **Mode:** Semua peserta bisa menjawab"
                )
                
        else:
            await update.message.reply_text("❌ Quiz tidak memiliki pertanyaan.")
    else:
        await update.message.reply_text("❌ Gagal memulai quiz.")

async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paksa lanjut ke soal berikutnya (manual override)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa mengontrol quiz.")
        return
    
    # Tentukan chat_id target
    if update.effective_chat.type == 'private':
        from config import GROUP_CHAT_ID
        if not GROUP_CHAT_ID:
            await update.message.reply_text("❌ GROUP_CHAT_ID tidak dikonfigurasi.")
            return
        target_chat_id = GROUP_CHAT_ID
    else:
        target_chat_id = update.effective_chat.id
    
    if target_chat_id not in quiz_manager.active_quizzes:
        await update.message.reply_text("❌ Tidak ada quiz aktif.")
        return
    
    # Cancel timer saat ini
    active_quiz = quiz_manager.active_quizzes[target_chat_id]
    if active_quiz['timer_task'] and not active_quiz['timer_task'].done():
        try:
            active_quiz['timer_task'].cancel()
        except:
            pass
    
    await context.bot.send_message(
        chat_id=target_chat_id,
        text="⏩ **Admin memaksa lanjut ke soal berikutnya...**"
    )
    
    await quiz_manager.next_question_auto(context, target_chat_id)

async def finish_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Akhiri quiz manual"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa mengakhiri quiz.")
        return
    
    # Tentukan chat_id target
    if update.effective_chat.type == 'private':
        from config import GROUP_CHAT_ID
        if not GROUP_CHAT_ID:
            await update.message.reply_text("❌ GROUP_CHAT_ID tidak dikonfigurasi.")
            return
        target_chat_id = GROUP_CHAT_ID
    else:
        target_chat_id = update.effective_chat.id
    
    if target_chat_id not in quiz_manager.active_quizzes:
        await update.message.reply_text("❌ Tidak ada quiz aktif.")
        return
    
    # Cancel timer
    active_quiz = quiz_manager.active_quizzes[target_chat_id]
    if active_quiz['timer_task'] and not active_quiz['timer_task'].done():
        try:
            active_quiz['timer_task'].cancel()
        except:
            pass
    
    await context.bot.send_message(
        chat_id=target_chat_id,
        text="🛑 **Quiz diakhiri manual oleh admin...**"
    )
    
    # Paksa finish
    await quiz_manager.finish_quiz_auto(context, target_chat_id)

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
            "Ikuti quiz yang aktif untuk melihat statistik Anda!"
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
        stats_text += f"• {quiz_title}: {quiz['score']}/{quiz['total_questions']} ({quiz['date'][:10]})\n"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# Callback query handler for quiz answers
async def handle_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz callback queries - SEMUA USER BISA JAWAB"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.first_name
    chat_id = query.message.chat_id
    
    logger.info(f"Quiz callback - Data: {data}, User: {username}")
    
    try:
        if data.startswith("quiz_answer_"):
            answer_index = int(data.split("_")[2])
            
            success, result = await quiz_manager.submit_answer(
                chat_id,
                user_id,
                username,
                answer_index
            )
            
            if success:
                if result:
                    # Jawaban benar
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"✅ **{username} menjawab benar!** 🎉",
                        reply_to_message_id=query.message.message_id
                    )
                else:
                    # Jawaban salah
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ **{username} menjawab salah!**",
                        reply_to_message_id=query.message.message_id
                    )
            else:
                await query.answer(f"⚠️ {result}", show_alert=True)
        
        elif data.startswith("quiz_correct_"):
            # Handle correct answer selection selama pembuatan quiz
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
