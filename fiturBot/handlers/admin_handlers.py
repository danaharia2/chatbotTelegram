from telegram import Update
from telegram.ext import ContextTypes
import logging
import io
from datetime import datetime, timedelta
from ..attendance_bot import AttendanceBot, ClassroomAutoReminder
from auto_functions import send_classroom_reminder, send_class_reminder, auto_check_attendance
from config import ADMIN_IDS, GROUP_CHAT_ID, GOOGLE_MEET_LINK
from .topic_utils import ANNOUNCEMENT_TOPIC_ID
import pandas as pd
from datetime import timezone

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
        warning_students = df[(df['Total Izin'] >= 2) | (df['Total Alpha'] >= 2)]
        
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
async def list_kehadiran(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim laporan kehadiran ke grup - ADMIN ONLY"""
    try:
        bot = AttendanceBot()
        df = bot.get_student_data()
        
        if df.empty:
            await update.message.reply_text("❌ Tidak ada data murid.")
            return

        # Dapatkan hari Senin minggu ini
        senin_minggu_ini = get_monday_wib()
        
        # Format tanggal Indonesia
        bulan_indonesia = {
            1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
            7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
        }
        
        tanggal_str = f"Senin, {senin_minggu_ini.day} {bulan_indonesia[senin_minggu_ini.month]} {senin_minggu_ini.year}"

        # Filter siswa yang hadir (status terakhir = 'Hadir')
        siswa_hadir = df[df['Status Terakhir'] == 'Hadir']
        
        if siswa_hadir.empty:
            await update.message.reply_text(
                f"❌ Tidak ada murid yang hadir pada {tanggal_str}"
            )
            return

        # List motivasi dan pantun
        motivasi_list = [
            "Terus pertahankan semangat belajarnya! 💪",
            "Kehadiran kalian membuat kelas semakin hidup! 🌟",
            "Langkah kecil setiap hari membawa hasil yang besar! 🚀",
            "Belajar bahasa Rusia itu menyenangkan, bukan? 😄",
            "Konsistensi adalah kunci kesuksesan! 📚",
            "Semangat yang luar biasa dari kalian semua! 🎉"
        ]
        
        pantun_list = [
            "Jalan-jalan ke pasar baru,\nBeli sepatu dan tas kanvas.\nJangan lupa absen hadir,\nBiar makin pinter bahasa Rusia! 🎒",
            "Makan bakso di warung,\nBaksonya enak sekali.\nKalau rajin masuk kelas,\nBisa jadi translator yang hebat! 🍲",
            "Lihat kucing manis sekali,\nKucingnya lagi tidur.\nJangan males datang ke kelas,\nBiar bisa baca buku Rusia! 😺",
            "Pergi ke mall naik bus,\nBusnya penuh sesak.\nYang rajin hadir dapat bonus,\nBisa ngobrol sama Ivan dan Sasha! 🚌",
            "Naik sepeda ke taman bunga,\nBunga mekar warna-warni.\nRajin hadir dapat pahala,\nNanti bisa jalan-jalan ke Moskwa! 🚴‍♀️",
            "Siang-siang panas sekali,\nMinum es kelapa muda.\nJangan sampai alpha terus,\nNanti nilai jadi muda! 🥥"
        ]

        import random
        motivasi = random.choice(motivasi_list)
        pantun = random.choice(pantun_list)

        total_siswa = len(df)
        # Format daftar nama siswa yang hadir
        daftar_siswa = []
        for idx, siswa in siswa_hadir.iterrows():
            nama = siswa['Nama']
            # Tambahkan username jika ada
            if 'Username' in siswa and pd.notna(siswa['Username']) and siswa['Username'] != '-':
                username = siswa['Username'].replace('@', '')
                daftar_siswa.append(f"• {nama} (@{username})")
            else:
                daftar_siswa.append(f"• {nama}")

        # Urutkan daftar siswa secara alfabetis
        daftar_siswa.sort()

        # Buat pesan
        message = (
            f"🎉 **LAPORAN KEHADIRAN KELAS** 🎉\n\n"
            f"Terima kasih atas kehadiran teman-teman yang telah hadir di kelas pada {tanggal_str}\n\n"
            f"**📊 DATA KEHADIRAN:**\n"
            f"• Total yang hadir: {len(siswa_hadir)} murid dari {total_siswa} murid\n"
            f"• Persentase kehadiran: {(len(siswa_hadir) / len(df) * 100):.1f}%\n\n"
            f"**👥 DAFTAR MURID YANG HADIR:**\n"
            f"{chr(10).join(daftar_siswa)}\n\n"
            f"**💫 KATA MOTIVASI:**\n"
            f"{motivasi}\n\n"
            f"**🎭 PANTUN LUCU:**\n"
            f"{pantun}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *Waktu sistem:* {get_wib_time().strftime('%d/%m/%Y %H:%M WIB')}\n"
            f"👑 *Dilaporkan oleh:* {update.effective_user.first_name}"
        )

        # Kirim ke grup
        try:
            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=message,
                parse_mode='Markdown',
                message_thread_id=ANNOUNCEMENT_TOPIC_ID
            )
            await update.message.reply_text(
                f"✅ Laporan kehadiran berhasil dikirim ke grup!\n"
                f"• Tanggal: {tanggal_str}\n"
                f"• Total hadir: {len(siswa_hadir)} murid"
            )
        except Exception as e:
            logger.error(f"Gagal mengirim ke grup: {e}")
            # Jika gagal ke grup, kirim ke admin saja
            await update.message.reply_text(
                f"❌ Gagal mengirim ke grup, berikut laporannya:\n\n{message}",
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Error in list_kehadiran: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

# Tambahkan juga helper function untuk mendapatkan hari Senin jika belum ada
def get_monday_wib():
    """Mendapatkan hari Senin minggu ini dalam WIB"""
    WIB = timezone(timedelta(hours=7))
    today = datetime.now(WIB)
    # weekday() -> Senin=0, Minggu=6
    monday = today - timedelta(days=today.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)

def get_wib_time():
    """Mendapatkan waktu sekarang dalam WIB"""
    WIB = timezone(timedelta(hours=7))
    return datetime.now(WIB)

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
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa menggunakan perintah ini.")
        return

    help_message = (
        "👑 PANDUAN PERINTAH ADMIN\n\n"
        
        "📊 MANAJEMEN DATA:\n"
        "• /admin_stats - Lihat statistik lengkap\n"
        "• /export_data - Export data ke CSV\n"
        "• /list_warnings - Lihat daftar peringatan\n"
        "• /list_kehadiran - Kirim laporan kehadiran ke grup\n\n"
        
        "🔄 RESET & MAINTENANCE:\n"
        "• /reset_attendance confirm - Reset SEMUA data kehadiran\n"
        "• /force_check - Paksa pengecekan kehadiran otomatis\n\n"
        
        "👤 MANAJEMEN MURID:\n"
        "• `/manual_kick 123456789 Alasan` - Keluarkan murid manual\n"
        "   Contoh: `/manual_kick 123456789 Alpha 3 kali`\n\n"
        
        "🔔 SISTEM REMINDER:\n"
        "• /classroom_reminder - Kirim reminder tugas sekarang\n"
        "**Langkah-langkahnya:**\n"
        "1. **Tambahkan kolom Email** di spreadsheet\n"
        "2. **Isi email siswa** yang sesuai dengan email Google Classroom mereka\n"
        "3. **Dapatkan Course ID & Coursework ID:**\n"
        "   • Buka classroom.google.com\n"
        "   • Course ID: dari URL `.../course/`**123456789**\n"
        "   • Coursework ID: dari URL tugas `.../view/`**987654321**\n"
        "4. **Gunakan perintah:**\n"
        "   `/classroom_reminder NzgxOTM4ODI5NTEz <coursework_id> -1002408972369`\n\n"
        "• `/class_reminder` - Kirim reminder kelas sekarang\n\n"
        
        "⚙️ SISTEM & INFO:\n"
        "• /check_topics - Cek informasi topik grup\n"
        "• /test - Test koneksi Google Sheets\n\n"
        
        "📋 FITUR OTOMATIS:\n"
        "• Auto-kick: Alpha 3x atau Izin 3x\n"
        "• Reminder tugas: Setiap hari jam 10:00\n"
        "• Reminder kelas: Minggu 18:00 & Senin 10:00\n"
        "• Pengecekan: Setiap hari jam 08:00 & 18:00\n\n"
        
        "💡 Tips Admin:\n"
        "• Gunakan /force_check untuk tes fitur auto-kick\n"
        "• Export data secara berkala untuk backup\n"
        "• Cek /list_warnings untuk monitoring murid"
    )
    
    await update.message.reply_text(help_message, parse_mode='Markdown')

@admin_required
async def test_classroom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test koneksi Google Classroom"""
    try:
        bot = AttendanceBot()
        classroom_service = bot.initialize_classroom_service()
        
        if not classroom_service:
            await update.message.reply_text("❌ Gagal menginisialisasi Google Classroom service")
            return
            
        # Test dengan mengambil daftar courses
        results = classroom_service.courses().list().execute()
        courses = results.get('courses', [])
        
        if not courses:
            await update.message.reply_text("✅ Connected to Google Classroom, but no courses found")
        else:
            course_list = []
            for course in courses:
                course_list.append(f"• {course['name']} (ID: {course['id']})")
            
            await update.message.reply_text(
                f"✅ **Google Classroom Connection Successful!**\n\n"
                f"📚 **Courses found:** {len(courses)}\n\n"
                f"{chr(10).join(course_list)}",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error connecting to Google Classroom: {e}")

auto_reminder = None
async def start_auto_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai reminder otomatis harian"""
    global auto_reminder
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa menggunakan perintah ini.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ **Format salah!**\n\n"
            "Gunakan: `/start_reminder <course_id> <group_chat_id>`\n\n"
            "Contoh: `/start_reminder 123456789 -1001234567890`\n\n"
            "💡 **Cara dapatkan:**\n"
            "• Course ID: dari URL Classroom\n"
            "• Group Chat ID: gunakan /myinfo di grup\n\n"
            "**Fitur:**\n"
            "• Bot akan cek otomatis setiap hari\n"
            "• Kirim reminder jam 08:00 & 18:00\n"
            "• Untuk semua tugas aktif\n"
            "• Hanya siswa yang belum mengumpulkan",
            parse_mode='Markdown'
        )
        return

    course_id = context.args[0]
    group_chat_id = context.args[1]

    try:
        bot = AttendanceBot()
        
        if auto_reminder is None:
            auto_reminder = ClassroomAutoReminder(bot)
        
        result = auto_reminder.start_daily_reminders(context, course_id, group_chat_id)
        await update.message.reply_text(result)
        
    except Exception as e:
        logger.error(f"Error starting auto reminder: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def stop_auto_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hentikan reminder otomatis"""
    global auto_reminder
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa menggunakan perintah ini.")
        return

    if auto_reminder:
        result = auto_reminder.stop_reminders()
        auto_reminder = None
        await update.message.reply_text(result)
    else:
        await update.message.reply_text("❌ Tidak ada reminder yang berjalan")

async def test_auto_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test reminder otomatis (langsung jalankan sekarang)"""
    global auto_reminder
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa menggunakan perintah ini.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ **Format salah!**\n\n"
            "Gunakan: `/test_reminder <course_id> <group_chat_id>`\n\n"
            "Contoh: `/test_reminder 123456789 -1001234567890`",
            parse_mode='Markdown'
        )
        return

    course_id = context.args[0]
    group_chat_id = context.args[1]

    try:
        bot = AttendanceBot()
        
        if auto_reminder is None:
            auto_reminder = ClassroomAutoReminder(bot)
        
        # Jalankan langsung sekarang (tanpa jadwal)
        auto_reminder.check_and_send_reminders(context, course_id, group_chat_id)
        await update.message.reply_text("✅ Test reminder telah dijalankan! Cek grup untuk melihat hasilnya.")
        
    except Exception as e:
        logger.error(f"Error testing auto reminder: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def classroom_reminder_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim reminder manual untuk tugas tertentu"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa menggunakan perintah ini.")
        return

    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "❌ **Format salah!**\n\n"
            "Gunakan: `/classroom_reminder <course_id> <coursework_id> <group_chat_id>`\n\n"
            "Contoh: `/classroom_reminder 123456789 987654321 -1001234567890`\n\n"
            "💡 **Cara dapatkan ID:**\n"
            "• Course ID & Coursework ID: dari URL Classroom\n"
            "• Group Chat ID: gunakan /myinfo di grup",
            parse_mode='Markdown'
        )
        return

    course_id = context.args[0]
    coursework_id = context.args[1]
    group_chat_id = context.args[2]

    await update.message.reply_text("🔄 Memeriksa tugas Classroom...")

    try:
        bot = AttendanceBot()
        
        # Inisialisasi classroom service
        classroom_service = bot.initialize_classroom_service()
        if not classroom_service:
            await update.message.reply_text("❌ Gagal menginisialisasi Google Classroom service")
            return
        
        # Buat instance reminder temporary
        auto_reminder_temp = ClassroomAutoReminder(bot)
        
        # Dapatkan detail tugas
        assignment = classroom_service.courses().courseWork().get(
            courseId=course_id,
            courseWorkId=coursework_id
        ).execute()
        
        students_without_submission, message = auto_reminder_temp.get_students_without_submission_for_coursework(
            course_id, coursework_id
        )
        
        if students_without_submission:
            reminder_message = auto_reminder_temp.format_reminder_message(
                assignment, students_without_submission, course_id
            )
            # Kirim ke grup
            await context.bot.send_message(
                chat_id=group_chat_id,
                text=reminder_message,
                parse_mode='Markdown'
            )
            await update.message.reply_text(f"✅ Reminder telah dikirim ke grup!\n\n{message}")
        else:
            await update.message.reply_text("✅ Semua siswa sudah mengumpulkan tugas!")

    except Exception as e:
        logger.error(f"Error in classroom reminder: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")






