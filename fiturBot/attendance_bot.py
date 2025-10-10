import gspread
import pandas as pd
import os
import logging
from google.oauth2.service_account import Credentials
from config import SCOPES, CREDENTIALS_FILE, SPREADSHEET_URL, WORKSHEET_NAME, CLASSROOM_COURSE_ID
from .classroom_manager import ClassroomManager

logger = logging.getLogger(__name__)

class AttendanceBot:
    def __init__(self):
        self.gc = None
        self.worksheet = None
        self.classroom_manager = None
        self.setup_sheets()
        self.setup_classroom()
    
    def setup_sheets(self):
        """Setup koneksi ke Google Sheets"""
        try:
            logger.info("Memulai koneksi ke Google Sheets...")
            
            # Validasi file credentials
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"File {CREDENTIALS_FILE} tidak ditemukan!")
            
            # Setup credentials dan koneksi
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
            self.gc = gspread.authorize(creds)
            self.worksheet = self.gc.open_by_url(SPREADSHEET_URL).worksheet(WORKSHEET_NAME)
            
            logger.info("✅ Berhasil terhubung ke Google Sheets!")
            
        except Exception as e:
            logger.error(f"❌ Error connecting to Google Sheets: {e}")
            raise
    
    def setup_classroom(self):
        """Setup koneksi ke Google Classroom"""
        try:
            self.classroom_manager = ClassroomManager()
        except Exception as e:
            logger.warning(f"Google Classroom tidak tersedia: {e}")
            self.classroom_manager = None
    
    def get_student_data(self):
        """Mengambil data murid dari spreadsheet dan konversi tipe data"""
        try:
            data = self.worksheet.get_all_records()
            df = pd.DataFrame(data)

            # Konversi kolom numerik dari string ke integer
            numeric_columns = ['Total Alpha', 'Total Izin', 'Telegram ID']

            for col in numeric_columns:
                if col in df.columns:
                    try:
                    # Coba konversi langsung ke numeric
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                    except:
                    # Jika gagal, bersihkan string terlebih dahulu
                        df[col] = pd.to_numeric(
                        df[col].astype(str).str.replace('[^0-9.-]', '', regex=True), 
                        errors='coerce'
                    ).fillna(0).astype(int)

            logger.info(f"📊 Berhasil membaca {len(df)} records")
            logger.info(f"📈 Sample data - Alpha: {df['Total Alpha'].iloc[0] if len(df) > 0 else 'N/A'}, Izin: {df['Total Izin'].iloc[0] if len(df) > 0 else 'N/A'}")
            return df
        
        except Exception as e:
            logger.error(f"Error getting student data: {e}")
            return pd.DataFrame()
    
    def update_student_record(self, telegram_id, status):
        """Update record kehadiran murid (simpan data angka)"""
        try:
            df = self.get_student_data()
            if df.empty:
                return False
            
            # Cari baris berdasarkan Telegram ID
            for idx, row in df.iterrows():
                if str(row['Telegram ID']) == str(telegram_id):
                    # Konversi nilai saat ini ke integer (pastikan angka)
                    current_alpha = int(row['Total Alpha']) if pd.notna(row['Total Alpha']) else 0
                    current_izin = int(row['Total Izin']) if pd.notna(row['Total Izin']) else 0

                    # Update total alpha atau izin berdasarkan status
                    if status == 'Alpha':
                        # Update Total Alpha (angka) dan Status Terakhir (teks)
                        new_alpha = current_alpha + 1
                        self.worksheet.update_cell(idx + 2, 4, new_alpha)  # Kolom D: Total Alpha (angka)
                        self.worksheet.update_cell(idx + 2, 6, 'Alpha')     # Kolom F: Status Terakhir (teks)
                        logger.info(f"✅ Updated Alpha for {row['Nama']}: {current_alpha} → {new_alpha}")

                    elif status == 'Izin':
                        # Update Total Izin (angka) dan Status Terakhir (teks)
                        new_izin = current_izin + 1
                        self.worksheet.update_cell(idx + 2, 5, new_izin)   # Kolom E: Total Izin (angka)
                        self.worksheet.update_cell(idx + 2, 6, 'Izin')     # Kolom F: Status Terakhir (teks)
                        logger.info(f"✅ Updated Izin for {row['Nama']}: {current_izin} → {new_izin}")

                    # Untuk status 'Hadir', hanya update status terakhir saja
                    elif status == 'Hadir':
                        # Hanya update Status Terakhir (teks), angka tetap
                        self.worksheet.update_cell(idx + 2, 6, 'Hadir')    # Kolom F: Status Terakhir (teks)
                        logger.info(f"✅ Updated status for {row['Nama']}: Hadir")
                    
                    logger.info(f"✅ Updated record for {row['Nama']}: {status}")
                    return True
            
            logger.warning(f"❌ Telegram ID {telegram_id} tidak ditemukan")
            return False
            
        except Exception as e:
            logger.error(f"Error updating student record: {e}")
            return False

    def check_auto_kick_conditions(self):
        """Memeriksa kondisi untuk mengeluarkan murid secara otomatis"""
        try:
            df = self.get_student_data()
            students_to_kick = []
            students_to_warn = []
            
            for _, student in df.iterrows():
                telegram_id = student['Telegram ID']
                total_alpha = int(student['Total Alpha']) if pd.notna(student['Total Alpha']) else 0
                total_izin = int(student['Total Izin']) if pd.notna(student['Total Izin']) else 0
                nama = student['Nama']
                
                # Kick: Alpha dan Izin 3 kali
                if total_alpha >= 3 or total_izin >=3:
                    students_to_kick.append({
                        'telegram_id': telegram_id,
                        'nama': nama,
                        'alasan': f"Alpha {total_alpha} kali"
                    })
                
                # Peringatan: Izin 2 kali dan Alpha 1 kali
                if total_izin >= 2 or total_alpha >= 1:
                    students_to_warn.append({
                        'telegram_id': telegram_id,
                        'nama': nama,
                        'total_izin': total_izin,
                        'total_alpha': total_alpha
                    })

            logger.info(f"🔍 Auto-kick check: {len(students_to_kick)} akan dikick, {len(students_to_warn)} peringatan")
            return students_to_kick, students_to_warn
        
        except Exception as e:
            logger.error(f"Error checking auto-kick conditions: {e}")
            return [], []

    def reset_daily_attendance(self):
        """Reset status kehadiran harian"""
        try:
            df = self.get_student_data()
            for idx, row in df.iterrows():
                self.worksheet.update_cell(idx + 2, 6, 'Belum Absen')  # Reset status terakhir
            logger.info("Status kehadiran harian direset")
        except Exception as e:
            logger.error(f"Error resetting attendance: {e}")