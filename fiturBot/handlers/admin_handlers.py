from telegram import Update
from telegram.ext import ContextTypes
import logging
import io
from datetime import datetime, timedelta
from ..attendance_bot import AttendanceBot
from auto_functions import send_classroom_reminder, send_class_reminder, auto_check_attendance
from config import ADMIN_IDS, GROUP_CHAT_ID, GOOGLE_MEET_LINK
from .topic_utils import ANNOUNCEMENT_TOPIC_ID

logger = logging.getLogger(__name__)

def admin_required(func):
    """Decorator untuk mengecek admin"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                "❌ **Akses Ditolak!**\n"
                "Command ini hanya untuk admin grup."
            )
            return False
        
        return await func(update, context, *args, **kwargs)
    return wrapper

@admin_required
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lihat statistik lengkap - ADMIN ONLY"""
    try:
        bot = AttendanceBot()
        df = bot.get_student_data()
        
        if df.empty:
            await update.message.reply_text("❌ Tidak ada data murid.")
            return
        
        total_students = len(df)
        total_alpha = df['Total Alpha'].sum()
        total_izin = df['Total Izin'].sum()
        
        # Hitung murid dalam status warning
        warning_students = df[(df['Total Izin'] >= 2) & (df['Total Alpha'] >= 1)]
        
        stats_message = (
            "📊 **STATISTIK ADMIN**\n\n"
            f"• 👥 Total Murid: {total_students}\n"
            f"• ❌ Total Alpha: {total_alpha}\n"
            f"• ⚠️ Total Izin: {total_izin}\n"
            f"• 🚨 Murid Warning: {len(warning_students)}"
        )
        
        await update.message.reply_text(stats_message)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

@admin_required
async def reset_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset data kehadiran - ADMIN ONLY"""
    try:
        bot = AttendanceBot()
        
        # Konfirmasi reset
        if context.args and context.args[0] == 'confirm':
            bot.reset_daily_attendance()
            await update.message.reply_text(
                "✅ **Data kehadiran berhasil direset!**\n"
                "Semua data alpha/izin telah dikembalikan ke 0."
            )
        else:
            await update.message.reply_text(
                "⚠️ **Konfirmasi Reset Data**\n\n"
                "Anda akan mereset SEMUA data kehadiran:\n"
                "• Total Alpha → 0\n"
                "• Total Izin → 0\n"
                "• Status → Belum Absen\n\n"
                "Ketik: `/reset_attendance confirm` untuk melanjutkan.",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

@admin_required
async def force_attendance_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paksa pengecekan kehadiran - ADMIN ONLY"""
    try:
        await auto_check_attendance(context)
        await update.message.reply_text("✅ Pengecekan kehadiran dipaksa selesai!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

@admin_required
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export data ke CSV - ADMIN ONLY"""
    try:
        bot = AttendanceBot()
        df = bot.get_student_data()
        
        if df.empty:
            await update.message.reply_text("❌ Tidak ada data untuk di-export.")
            return
        
        # Create CSV string
        csv_data = df.to_csv(index=False)
        
        # Send as file
        await update.message.reply_document(
            document=io.BytesIO(csv_data.encode()),
            filename=f"data_kehadiran_{datetime.now().strftime('%Y%m%d')}.csv",
            caption="📁 Data kehadiran murid"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

@admin_required
async def manual_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kick murid manual - ADMIN ONLY"""
    try:
        if not context.args:
            await update.message.reply_text(
                "❌ Format: `/manual_kick <telegram_id> <alasan>`\n"
                "Contoh: `/manual_kick 123456789 Alpha 3 kali`",
                parse_mode='Markdown'
            )
            return
        
        telegram_id = context.args[0]
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "Manual kick by admin"
        
        # Kick dari grup
        await context.bot.ban_chat_member(
            chat_id=GROUP_CHAT_ID,
            user_id=int(telegram_id)
        )
        
        # Update spreadsheet
        bot = AttendanceBot()
        df = bot.get_student_data()
        for idx, row in df.iterrows():
            if str(row['Telegram ID']) == str(telegram_id):
                bot.worksheet.update_cell(idx + 2, 6, f"Dikeluarkan: {reason} - Manual")
                break
        
        await update.message.reply_text(
            f"✅ **Murid berhasil dikeluarkan!**\n"
            f"• ID: {telegram_id}\n"
            f"• Alasan: {reason}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

@admin_required
async def list_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lihat daftar murid yang dapat peringatan - ADMIN ONLY"""
    try:
        bot = AttendanceBot()
        _, students_to_warn = bot.check_auto_kick_conditions()
        
        if not students_to_warn:
            await update.message.reply_text("✅ Tidak ada murid yang perlu diperingatkan.")
            return
        
        warning_message = "🚨 **DAFTAR MURID PERINGATAN**\n\n"
        
        for student in students_to_warn:
            warning_message += (
                f"👤 **{student['nama']}**\n"
                f"   • ID: `{student['telegram_id']}`\n"
                f"   • Izin: {student['total_izin']}x\n"
                f"   • Alpha: {student['total_alpha']}x\n\n"
            )
        
        await update.message.reply_text(warning_message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

@admin_required
async def classroom_reminder_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim reminder classroom sekarang - ADMIN ONLY"""
    try:
        await send_classroom_reminder(context)
        await update.message.reply_text("✅ Reminder classroom berhasil dikirim!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

@admin_required
async def class_reminder_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim reminder kelas sekarang - ADMIN ONLY"""
    try:
        await send_class_reminder(context)
        await update.message.reply_text("✅ Reminder kelas berhasil dikirim!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

@admin_required
async def check_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek informasi topik yang tersedia - ADMIN ONLY"""
    try:
        from config import TOPIC_NAMES, ANNOUNCEMENT_TOPIC_ID, ASSIGNMENT_TOPIC_ID, ATTENDANCE_TOPIC_ID
        
        topic_info = (
            "📋 **INFORMASI TOPIK GRUP**\n\n"
            f"• 🎯 PENGUMUMAN & INFO: Topic ID {ANNOUNCEMENT_TOPIC_ID} ({TOPIC_NAMES.get(ANNOUNCEMENT_TOPIC_ID, 'Unknown')})\n"
            f"• 📚 TUGAS: Topic ID {ASSIGNMENT_TOPIC_ID} ({TOPIC_NAMES.get(ASSIGNMENT_TOPIC_ID, 'Unknown')})\n"
            f"• ✅ ABSENSI: Topic ID {ATTENDANCE_TOPIC_ID} ({TOPIC_NAMES.get(ATTENDANCE_TOPIC_ID, 'Unknown')})\n\n"
            "Bot akan mengirim pesan ke topik-topik tersebut sesuai dengan jenis pesannya."
        )
        
        await update.message.reply_text(topic_info, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

@admin_required
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command khusus admin"""
    help_message = (
        "👑 **PANDUAN PERINTAH ADMIN**\n\n"
        
        "📊 **MANAJEMEN DATA:**\n"
        "• `/admin_stats` - Lihat statistik lengkap\n"
        "• `/export_data` - Export data ke CSV\n"
        "• `/list_warnings` - Lihat daftar peringatan\n\n"
        
        "🔄 **RESET & MAINTENANCE:**\n"
        "• `/reset_attendance confirm` - Reset SEMUA data kehadiran\n"
        "• `/force_check` - Paksa pengecekan kehadiran otomatis\n\n"
        
        "👤 **MANAJEMEN MURID:**\n"
        "• `/manual_kick 123456789 Alasan` - Keluarkan murid manual\n"
        "   Contoh: `/manual_kick 123456789 Alpha 3 kali`\n\n"
        
        "🔔 **SISTEM REMINDER:**\n"
        "• `/classroom_reminder` - Kirim reminder tugas sekarang\n"
        "• `/class_reminder` - Kirim reminder kelas sekarang\n\n"
        
        "⚙️ **SISTEM & INFO:**\n"
        "• `/check_topics` - Cek informasi topik grup\n"
        "• `/test` - Test koneksi Google Sheets\n\n"
        
        "📋 **FITUR OTOMATIS:**\n"
        "• Auto-kick: Alpha 3x atau tidak hadir berturut-turut\n"
        "• Reminder tugas: Setiap hari jam 10:00\n"
        "• Reminder kelas: Minggu 18:00 & Senin 10:00\n"
        "• Pengecekan: Setiap hari jam 08:00 & 18:00\n\n"
        
        "💡 **Tips Admin:**\n"
        "• Gunakan /force_check untuk tes fitur auto-kick\n"
        "• Export data secara berkala untuk backup\n"
        "• Cek /list_warnings untuk monitoring murid"
    )
    
    await update.message.reply_text(help_message)

@admin_required
async def test_classroom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test koneksi Google Classroom"""
    try:
        from fiturBot.attendance_bot import AttendanceBot
        bot = AttendanceBot()
        
        if bot.classroom_manager is None:
            await update.message.reply_text("❌ Google Classroom tidak tersedia")
            return
        
        await update.message.reply_text("🔍 Checking Google Classroom...")
        
        unsubmitted = bot.classroom_manager.get_unsubmitted_assignments()
        
        if not unsubmitted:
            message = "✅ **SEMUA TUGAS SUDAH DIKUMPULKAN!** 🎉"
        else:
            message = "📚 **SISWA YANG BELUM KUMPUL TUGAS:**\n\n"
            for student, assignments in unsubmitted.items():
                message += f"👤 **{student}**\n"
                for assignment in assignments:
                    message += f"   • {assignment}\n"
                message += "\n"
            message += f"📊 Total: {len(unsubmitted)} siswa"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
