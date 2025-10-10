from telegram import Update
from telegram.ext import ContextTypes
import logging
from ..attendance_bot import AttendanceBot
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    user_id = update.effective_user.id

    #Base message untuk semua user
    message = (
        "Halo! Saya adalah bot yang dibuat Kak Dana untuk mengelola kehadiran murid Kelas Rusia Lvl1 Batch 11.\n\n"
        "Perintah yang tersedia:\n"
        "/absen - Absen dengan pilihan status\n"
        "/status - Lihat status kehadiran\n"
        "/test - Test koneksi Google Sheets\n"
        "/myinfo - Lihat info Anda\n"
        "/register - Buat pendaftaran ke sistem\n"
    )

    #Tambahkan perintah admin jika user adalah admin
    if user_id in ADMIN_IDS: 
        message += (
            "\n👑 **PERINTAH KHUSUS ADMIN:**\n"
            "/admin_stats - Lihat statistik lengkap\n"
            "/reset_attendance - Reset data kehadiran\n"
            "/force_check - Paksa pengecekan kehadiran\n"
            "/export_data - Export data ke CSV\n"
            "/manual_kick - Keluarkan murid manual\n"
            "/list_warnings - Lihat daftar peringatan\n"
            "/classroom_reminder - Kirim reminder tugas\n"
            "/class_reminder - Kirim reminder kelas\n"
            "/check_topics - Cek informasi topik grup\n"
            "\n📝 **Cara Penggunaan Admin:**\n"
            "• `/reset_attendance confirm` - Reset semua data\n"
            "• `/manual_kick 123456789 Alpha 3x` - Kick murid\n"
            "• Gunakan `/force_check` untuk tes auto-kick\n"
            )
        
        message += (
            "\n💡 **Tips:**\n"
        "• Gunakan /register NamaLengkap untuk mendaftar\n"
        "• User ID Anda akan digunakan untuk sistem\n"
        "• Cek /status secara berkala untuk monitoring"
        )

    await update.message.reply_text(message)

async def absen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk absen dengan pilihan status"""
    user_id = update.effective_user.id
    bot = AttendanceBot()
    
    # Cek apakah user sudah terdaftar
    df = bot.get_student_data()
    student_data = df[df['Telegram ID'] == user_id]
    
    if student_data.empty:
        await update.message.reply_text(
            "❌ **Anda belum terdaftar dalam sistem!**\n\n"
            "Silakan daftar terlebih dahulu dengan:\n"
            "`/register NamaLengkap`\n\n"
            "Contoh: `/register Andi Wijaya`\n"
            "Gunakan huruf kapital disetiap kata sesuai pada contoh",
            parse_mode='Markdown'
        )
        return
    
    student = student_data.iloc[0]
    student_name = student['Nama']

    # Konversi ke integer untuk memastikan tipe data benar
    try:
        total_alpha = int(student['Total Alpha'])
        total_izin = int(student['Total Izin'])
    except (ValueError, TypeError):
        total_alpha = 0
        total_izin = 0
    
    # Jika tidak ada argumen, tampilkan pilihan absen
    if not context.args:
        await update.message.reply_text(
            f"📝 **FORM ABSENSI - {student_name}**\n\n"
            "Pilih status kehadiran:\n\n"
            "✅ `/absen hadir` - Untuk kehadiran\n"
            "⚠️ `/absen izin` - Untuk izin tidak hadir\n"
            "❌ `/absen alpha` - Untuk tidak hadir\n\n"
            "💡 **Keterangan:**\n"
            "• **Hadir**: Status terakhir berubah menjadi 'Hadir'\n"
            "• **Izin**: Total Izin +1, Status menjadi 'Izin'\n"
            "• **Alpha**: Total Alpha +1, Status menjadi 'Alpha'\n\n"
            f"📊 **Status saat ini:**\n"
            f"• Alpha: {total_alpha}x\n"
            f"• Izin: {total_izin}x\n"
            f"• Status: {student['Status Terakhir']}",
            parse_mode='Markdown'
        )
        return
    
    # Proses absen
    status_absen = context.args[0].lower()
    
    if status_absen not in ['hadir', 'izin', 'alpha']:
        await update.message.reply_text(
            "❌ **Status tidak valid!**\n\n"
            "Gunakan salah satu:\n"
            "• `/absen hadir`\n"
            "• `/absen izin`\n"
            "• `/absen alpha`",
            parse_mode='Markdown'
        )
        return
    
    # Update data di spreadsheet
    success = bot.update_student_record(user_id, status_absen.capitalize())
    
    if success:
        # Dapatkan data terbaru untuk konfirmasi
        df_updated = bot.get_student_data()
        student_updated = df_updated[df_updated['Telegram ID'] == user_id].iloc[0]

        # Konversi ke integer untuk data terbaru
        try:
            total_alpha_updated = int(student_updated['Total Alpha'])
            total_izin_updated = int(student_updated['Total Izin'])
        except (ValueError, TypeError):
            total_alpha_updated = total_alpha
            total_izin_updated = total_izin
        
        emoji = {
            'hadir': '✅',
            'izin': '⚠️', 
            'alpha': '❌'
        }
        
        message = (
            f"{emoji[status_absen]} **ABSENSI BERHASIL DICATAT**\n\n"
            f"👤 **Nama:** {student_name}\n"
            f"📝 **Status:** {status_absen.capitalize()}\n"
            f"🕐 **Waktu:** {update.message.date.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"📊 **Update Status:**\n"
            f"• Total Alpha: {total_alpha_updated}x\n"
            f"• Total Izin: {total_izin_updated}x\n"
            f"• Status Terakhir: {student_updated['Status Terakhir']}"
        )
        
        # Tambahkan peringatan jika perlu (dengan tipe data ya sudah di konversi)
        if status_absen == 'alpha':
            message += "\n\n⚠️ **PERINGATAN:** Alpha akan mempengaruhi status kehadiran Anda!"
        elif status_absen == 'izin' and total_izin_updated >= 2:
            message += "\n\n⚠️ **PERINGATAN:** Total izin Anda sudah 2x, hati-hati!"
        
        await update.message.reply_text(message)
    else:
        await update.message.reply_text(
            "❌ **Gagal mencatat absensi!**\n"
            "Silakan coba lagi atau hubungi admin."
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk melihat status"""
    user_id = update.effective_user.id
    bot = AttendanceBot()
    df = bot.get_student_data()

    # Jika admin, tampilkan semua data
    if user_id in ADMIN_IDS:
        if df.empty:
            await update.message.reply_text("❌ Tidak ada data murid.")
            return
        
        # Konversi ke integer untuk perhitungan
        try:
            total_alpha = df['Total Alpha'].astype(int).sum()
            total_izin = df['Total Izin'].astype(int).sum()
        except (ValueError, TypeError):
            total_alpha = 0
            total_izin = 0
            
        total_students = len(df)
        
        stats_message = (
            "👑 **STATUS ADMIN**\n\n"
            f"• 👥 Total Murid: {total_students}\n"
            f"• ❌ Total Alpha: {total_alpha}\n"
            f"• ⚠️ Total Izin: {total_izin}\n\n"
            "Gunakan /admin_stats untuk info lebih detail\n"
            "Gunakan /list_warnings untuk lihat peringatan"
        )
        await update.message.reply_text(stats_message)
        return
    
    # Untuk user biasa
    student_data = df[df['Telegram ID'] == user_id]
    
    if student_data.empty:
        await update.message.reply_text(
            "❌ **Anda belum terdaftar dalam sistem kehadiran.**\n\n"
            "Gunakan `/register NamaLengkap` untuk mendaftar.\n"
            "Contoh: `/register Andi Wijaya`",
            parse_mode='Markdown'
        )
        return
    
    student = student_data.iloc[0]

    # Konversi ke integer
    try:
        total_alpha = int(student['Total Alpha'])
        total_izin = int(student['Total Izin'])
    except (ValueError, TypeError):
        total_alpha = 0
        total_izin = 0
    
    message = (
        f"📊 **STATUS KEHADIRAN**\n\n"
        f"👤 **Nama:** {student['Nama']}\n"
        f"❌ **Total Alpha:** {total_alpha}x\n"
        f"⚠️ **Total Izin:** {total_izin}x\n"
        f"📝 **Status Terakhir:** {student['Status Terakhir']}"
    )
    
    # Tambahkan peringatan jika memenuhi kriteria (dengan tipe data intenger)
    if total_alpha >= 1:
        message += f"\n\n🚨 **PERINGATAN:** Anda memiliki {total_alpha}x alpha!"
    if total_izin >= 2:
        message += f"\n\n⚠️ **PERINGATAN:** Total izin Anda {total_izin}x!"
    if student['Total Izin'] >= 2 or student['Total Alpha'] >= 1:
        message += "\n\n⚠️ **STATUS PERINGATAN:** Anda terancam akan dikeluarkan jika tidak hadir pada pertemuan selanjutnya!"
    
    await update.message.reply_text(message)

async def test_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test koneksi Google Sheets"""
    try:
        bot = AttendanceBot()
        df = bot.get_student_data()
        
        if df.empty:
            await update.message.reply_text("❌ Tidak ada data di spreadsheet")
        else:
            student_count = len(df)
            await update.message.reply_text(
                f"✅ Koneksi Google Sheets BERHASIL!\n"
                f"📊 Total murid terdaftar: {student_count}"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def get_my_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dapatkan informasi user lengkap"""
    user = update.effective_user
    chat = update.effective_chat
    
    info_message = (
        f"📋 **INFORMASI AKUN TELEGRAM ANDA**\n\n"
        f"🆔 **User ID:** `{user.id}`\n"
        f"📛 **Nama:** {user.first_name} {user.last_name or ''}\n"
        f"👤 **Username:** @{user.username or 'Tidak ada'}\n"
        f"💬 **Chat ID:** `{chat.id}`\n"
        f"🏷️ **Tipe Chat:** {chat.type}\n\n"
        f"**📝 Catatan:**\n"
        f"• **User ID** digunakan untuk pendaftaran sistem\n"
        f"• **Username** bisa berubah, User ID tetap\n"
    )
    
    await update.message.reply_text(info_message, parse_mode='Markdown')

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pendaftaran murid otomatis"""
    user = update.effective_user

    #Admin tidak perlu mendaftar
    if user.id in ADMIN_IDS:
        await update.message.reply_text(
            "👑 **Anda adalah Admin!**\n\n"
            "Sebagai admin, Anda tidak perlu mendaftar sebagai murid.\n"
            "Gunakan perintah admin untuk mengelola sistem kehadiran."
        )
        return 
    
    bot = AttendanceBot()
    
    # Cek apakah sudah terdaftar
    df = bot.get_student_data()
    existing_user = df[df['Telegram ID'] == user.id]
    
    if not existing_user.empty:
        await update.message.reply_text(
            "✅ Anda sudah terdaftar dalam sistem!\n"
            f"User ID Anda: `{user.id}`",
            parse_mode='Markdown'
        )
        return
    
    # Jika belum terdaftar
    if context.args:
        nama = ' '.join(context.args)

        # Validasi nama
        if len(nama) < 2:
            await update.message.reply_text("❌ Nama terlalu pendek. Minimal 2 karakter.")
            return
        
        # Tambahkan ke spreadsheet
        try:
            new_row = [nama, user.id, f"@{user.username}" if user.username else "-", 0, 0, "Belum Absen", "Auto-registered"]
            bot.worksheet.append_row(new_row)
            
            await update.message.reply_text(
                f"✅ **Pendaftaran Berhasil!**\n\n"
                f"• Nama: {nama}\n"
                f"• User ID: `{user.id}`\n"
                f"• Username: @{user.username or 'Tidak ada'}\n\n"
                f"Sekarang Anda bisa menggunakan /absen",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    else:
        await update.message.reply_text(
            "📝 **Form Pendaftaran**\n\n"
            "Untuk mendaftar, ketik:\n"
            "`/register Nama Lengkap`\n\n"
            "Contoh: `/register Andi Wijaya`",
            parse_mode='Markdown'
        )