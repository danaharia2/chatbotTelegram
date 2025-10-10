# main.py
import logging
import asyncio
import signal
import sys
from telegram.ext import Application, CommandHandler
from datetime import time

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotManager:
    def __init__(self):
        self.application = None
        self.is_running = False

    async def error_handler(self, update: object, context):
        """Handle errors dalam bot"""
        logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    async def setup_bot(self):
        """Setup bot application"""
        try:
            # Test koneksi terlebih dahulu
            logger.info("Testing koneksi Google Sheets...")
            from fiturBot.attendance_bot import AttendanceBot
            bot = AttendanceBot()
            bot.get_student_data()
            
            # Buat application Telegram
            from config import BOT_TOKEN
            self.application = Application.builder().token(BOT_TOKEN).build()
            
            # Add error handler
            self.application.add_error_handler(self.error_handler)
            
            # Import handlers
            from fiturBot.handlers import (
                start, status, test_connection, get_my_info, register, absen, admin_stats, reset_attendance, force_attendance_check, export_data,
                manual_kick, list_warnings, classroom_reminder_now, class_reminder_now, check_topics
            )
            
            # ==================== 🎯 COMMAND UNTUK SEMUA USER ====================
            self.application.add_handler(CommandHandler("start", start))
            self.application.add_handler(CommandHandler("absen", absen))
            self.application.add_handler(CommandHandler("status", status))
            self.application.add_handler(CommandHandler("test", test_connection))
            self.application.add_handler(CommandHandler("myinfo", get_my_info))
            self.application.add_handler(CommandHandler("register", register))
            
            # ==================== 👑 COMMAND UNTUK ADMIN ONLY ====================
            self.application.add_handler(CommandHandler("admin_stats", admin_stats))
            self.application.add_handler(CommandHandler("reset_attendance", reset_attendance))
            self.application.add_handler(CommandHandler("force_check", force_attendance_check))
            self.application.add_handler(CommandHandler("export_data", export_data))
            self.application.add_handler(CommandHandler("manual_kick", manual_kick))
            self.application.add_handler(CommandHandler("list_warnings", list_warnings))
            self.application.add_handler(CommandHandler("classroom_reminder", classroom_reminder_now))
            self.application.add_handler(CommandHandler("class_reminder", class_reminder_now))
            self.application.add_handler(CommandHandler("check_topics", check_topics))
            
            # ==================== ⏰ JOB QUEUE UNTUK OTOMATISASI ====================
            job_queue = self.application.job_queue
            
            if job_queue is None:
                logger.warning("⚠️ JobQueue tidak tersedia. Fitur pengecekan otomatis akan dinonaktifkan.")
            else:
                # Import fungsi otomatisasi
                from auto_functions import periodic_check, send_classroom_reminder, send_class_reminder
                
                # ✅ Schedule untuk pengecekan kehadiran
                job_queue.run_daily(periodic_check, time=time(hour=8, minute=0))   # Jam 08:00
                job_queue.run_daily(periodic_check, time=time(hour=18, minute=0))  # Jam 18:00
                
                # ✅ Schedule untuk reminder classroom (setiap hari jam 10:00)
                job_queue.run_daily(send_classroom_reminder, time=time(hour=10, minute=0))
                
                # ✅ Schedule untuk reminder kelas (Minggu jam 18:00 dan Senin jam 10:00)
                job_queue.run_daily(send_class_reminder, time=time(hour=18, minute=0), days=(6,))  # Minggu
                job_queue.run_daily(send_class_reminder, time=time(hour=10, minute=0), days=(0,))  # Senin
                
                logger.info("✅ JobQueue berhasil di-setup untuk pengecekan otomatis dan reminder")
            
            self.is_running = True
            logger.info("🤖 Bot setup completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup bot: {e}")
            self.is_running = False
            raise

    async def start_bot(self):
        """Start bot polling"""
        if not self.application:
            await self.setup_bot()
        
        logger.info("🚀 Starting bot polling...")
        try:
            await self.application.run_polling()
        except Exception as e:
            logger.error(f"❌ Error during polling: {e}")
            raise

    async def stop_bot(self):
        """Stop bot gracefully"""
        if self.application and self.is_running:
            logger.info("🛑 Stopping bot gracefully...")
            try:
                await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
            finally:
                self.is_running = False
                logger.info("✅ Bot stopped successfully")

# Global instance
bot_manager = BotManager()

async def main():
    """Main function"""
    try:
        await bot_manager.start_bot()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        await bot_manager.stop_bot()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    # Don't try to stop here, just let the process exit

if __name__ == '__main__':
    # Import config untuk validasi
    try:
        from config import validate_config
        if not validate_config():
            sys.exit(1)
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        sys.exit(1)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run bot
    asyncio.run(main())


