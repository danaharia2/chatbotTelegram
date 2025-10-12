# main.py
import logging
from telegram.ext import Application, CommandHandler
from datetime import time
from fiturBot.quiz_handler import (
    quiz_help, create_quiz, list_quizzes, start_quiz, next_question, 
    finish_quiz, quiz_leaderboard, my_quiz_stats, handle_quiz_callback,
    handle_quiz_creation
)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Main function - synchronous version"""
    try:
        # Import config
        from config import validate_config, BOT_TOKEN
        if not validate_config():
            logger.error("❌ Config validation failed")
            return
        
        # Test connections
        logger.info("🔧 Testing connections...")
        from fiturBot.attendance_bot import AttendanceBot
        bot = AttendanceBot()
        df = bot.get_student_data()
        logger.info(f"✅ Connected to Google Sheets - {len(df)} records")
        
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Import handlers
        from fiturBot.handlers import (
            start, status, test_connection, get_my_info, register, absen, test_classroom,
            admin_help, admin_stats, reset_attendance, force_attendance_check, export_data,
            manual_kick, list_warnings, classroom_reminder_now, class_reminder_now, check_topics, materi, materi1, materi2, 
            start_auto_reminder, stop_auto_reminder, test_auto_reminder
        )
        
        # Add command handlers
        commands = [
            ("start", start),
            ("absen", absen),
            ("status", status),
            ("test", test_connection),
            ("myinfo", get_my_info),
            ("register", register),
            ("materi", materi),
            ("materi1", materi1),
            ("materi2", materi2),
            ("admin_help", admin_help),
            ("admin_stats", admin_stats),
            ("reset_attendance", reset_attendance),
            ("force_check", force_attendance_check),
            ("export_data", export_data),
            ("manual_kick", manual_kick),
            ("list_warnings", list_warnings),
            ("classroom_reminder", classroom_reminder_now),
            ("test_classroom", test_classroom),
            ("class_reminder", class_reminder_now),
            ("check_topics", check_topics),
            ("start_reminder", start_auto_reminder),
            ("stop_reminder", stop_auto_reminder),
            ("test_reminder", test_auto_reminder),
            ("quiz_help", quiz_help),
            ("create_quiz", create_quiz),
            ("list_quizzes", list_quizzes),
            ("start_quiz", start_quiz),
            ("next_question", next_question),
            ("finish_quiz", finish_quiz),
            ("quiz_leaderboard", quiz_leaderboard),
      time
            ("my_quiz_stats", my_quiz_stats),
        ]
        
        for command, handler in commands:
            application.add_handler(CommandHandler(command, handler))
            logger.info(f"✅ Added handler: /{command}") 

        application.add_handler(CallbackQueryHandler(handle_quiz_callback, pattern="^quiz_"))

        # Add message handler for quiz creation
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
        handle_quiz_creation
        ), group=1)

        logger.info("✅ Added quiz handlers")
        
        # Setup job queue for scheduled tasks
        if application.job_queue:
            from auto_functions import periodic_check, send_classroom_reminder, send_class_reminder
            
            # Schedule tasks
            application.job_queue.run_daily(periodic_check, time=time(hour=8, minute=0))
            application.job_queue.run_daily(periodic_check, time=time(hour=18, minute=0))
            application.job_queue.run_daily(send_classroom_reminder, time=time(hour=10, minute=0))
            application.job_queue.run_daily(send_class_reminder, time=time(hour=18, minute=0), days=(6,))
            application.job_queue.run_daily(send_class_reminder, time=time(hour=10, minute=0), days=(0,))
            
            logger.info("✅ Scheduled tasks configured")
        
        logger.info("🤖 Bot is starting polling...")
        
        # Start polling - this will run forever (blocking)
        application.run_polling()
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot failed: {e}")

if __name__ == '__main__':
    main()



