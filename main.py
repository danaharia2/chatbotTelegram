# main.py
import logging
from telegram.ext import Application, CommandHandler
from datetime import time

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
            logger.error("Config validation failed")
            return
        
        # Test connections
        logger.info("Testing connections...")
        from fiturBot.attendance_bot import AttendanceBot
        bot = AttendanceBot()
        df = bot.get_student_data()
        logger.info(f"✅ Connected to Google Sheets - {len(df)} records")
        
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Import handlers
        from fiturBot.handlers import (
            start, status, test_connection, get_my_info, register, absen,
            admin_help, admin_stats, reset_attendance, force_attendance_check, export_data,
            manual_kick, list_warnings, classroom_reminder_now, class_reminder_now, check_topics
        )
        
        # Add command handlers
        commands = [
            ("start", start),
            ("absen", absen),
            ("status", status),
            ("test", test_connection),
            ("myinfo", get_my_info),
            ("register", register),
            ("admin_help", admin_help),
            ("admin_stats", admin_stats),
            ("reset_attendance", reset_attendance),
            ("force_check", force_attendance_check),
            ("export_data", export_data),
            ("manual_kick", manual_kick),
            ("list_warnings", list_warnings),
            ("classroom_reminder", classroom_reminder_now),
            ("class_reminder", class_reminder_now),
            ("check_topics", check_topics)
        ]
        
        for command, handler in commands:
            application.add_handler(CommandHandler(command, handler))
        
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
        
        # Start polling - this will run forever
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ Bot failed: {e}")

if __name__ == '__main__':
    main()
