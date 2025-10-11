# config.py
import os
from dotenv import load_dotenv
import base64
import json
import sys

# ==================== ENVIRONMENT DETECTION ====================
def is_railway():
    """Detect if running on Railway"""
    return 'RAILWAY_ENVIRONMENT' in os.environ or 'RAILWAY_SERVICE_NAME' in os.environ

def is_local():
    """Detect if running locally"""
    return not is_railway()

# Load .env hanya jika di local
if is_local():
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded .env file for local development")
    except ImportError:
        print("⚠️  python-dotenv not installed, skipping .env load")

# ==================== TELEGRAM CONFIG ====================
BOT_TOKEN = os.getenv('BOT_TOKEN')

GROUP_CHAT_ID_STR = os.getenv('GROUP_CHAT_ID', '')
try:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID_STR) if GROUP_CHAT_ID_STR else None
except (ValueError, TypeError):
    GROUP_CHAT_ID = None

# Admin IDs (convert string to list of integers)
admin_ids_str = os.getenv('ADMIN_IDS', '')
#ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()] if admin_ids_str else []
if admin_ids_str:
    try:
        if admin_ids_str.startswith('[') and admin_ids_str.endswith(']'):
            ADMIN_IDS = [int(id.strip()) for id in admin_ids_str[1:-1].split(',') if id.strip()]
        else:
            ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
    except (ValueError, TypeError) as e:
        print(f"⚠️  Error parsing ADMIN_IDS: {e}")
else:
    ADMIN_IDS = []

# ==================== GOOGLE SHEETS CONFIG ====================
SPREADSHEET_URL = os.getenv('SPREADSHEET_URL')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'Sheet1')
#CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', 'credentials.json')

# ==================== GOOGLE CLASSROOM CONFIG ====================
CLASSROOM_COURSE_ID = os.getenv('CLASSROOM_COURSE_ID', 'your_classroom_course_id_here')
GOOGLE_MEET_LINK = os.getenv('GOOGLE_MEET_LINK', 'meet.google.com/your-actual-meet-code')

# ==================== BOT BEHAVIOR CONFIG ====================
AUTO_CHECK_MORNING = os.getenv('AUTO_CHECK_MORNING', '08:00')
AUTO_CHECK_EVENING = os.getenv('AUTO_CHECK_EVENING', '18:00')
CLASSROOM_REMINDER_TIME = os.getenv('CLASSROOM_REMINDER_TIME', '10:00')
CLASS_REMINDER_SUNDAY = os.getenv('CLASS_REMINDER_SUNDAY', '18:00')
CLASS_REMINDER_MONDAY = os.getenv('CLASS_REMINDER_MONDAY', '10:00')

ENABLE_AUTO_KICK = os.getenv('ENABLE_AUTO_KICK', 'true').lower() == 'true'
ENABLE_WARNINGS = os.getenv('ENABLE_WARNINGS', 'true').lower() == 'true'
ENABLE_CLASSROOM_REMINDER = os.getenv('ENABLE_CLASSROOM_REMINDER', 'true').lower() == 'true'
ENABLE_CLASS_REMINDER = os.getenv('ENABLE_CLASS_REMINDER', 'true').lower() == 'true'

# ==================== TOPIC CONFIG ====================
# Topic IDs untuk berbagai jenis pesan
ANNOUNCEMENT_TOPIC_ID = int(os.getenv('ANNOUNCEMENT_TOPIC_ID', '1'))  # Default ke General
ASSIGNMENT_TOPIC_ID = int(os.getenv('ASSIGNMENT_TOPIC_ID', '1'))      # Default ke General
ATTENDANCE_TOPIC_ID = int(os.getenv('ATTENDANCE_TOPIC_ID', '1'))      # Default ke General

# Topic Names untuk reference
TOPIC_NAMES = {
    1: "General",
    2: "Tugas", 
    3: "PENGUMUMAN & INFO",
    4: "Perihal Absensi Kelas"
}

# ==================== CREDENTIALS HANDLING ====================
def setup_credentials():
    """
    Handle credentials untuk berbagai environment:
    1. Local dengan file credentials.json
    2. Railway dengan CREDENTIALS_BASE64
    3. Railway dengan uploaded credentials.json file
    """
    
    # Opsi 1: File credentials.json langsung (local development)
    if os.path.exists('credentials.json'):
        print("✅ Using credentials.json file")
        return 'credentials.json'
    
    # Opsi 2: Base64 encoded credentials (Railway environment variable)
    elif 'CREDENTIALS_BASE64' in os.environ:
        try:
            print("🔧 Decoding CREDENTIALS_BASE64...")
            # Decode base64 credentials
            creds_data = base64.b64decode(os.environ['CREDENTIALS_BASE64']).decode()
            
            # Write to credentials.json
            with open('credentials.json', 'w') as f:
                f.write(creds_data)
            
            print("✅ credentials.json created from CREDENTIALS_BASE64")
            return 'credentials.json'
            
        except Exception as e:
            print(f"❌ Error decoding CREDENTIALS_BASE64: {e}")
            return None
    
    # Opsi 3: CREDENTIALS_FILE environment variable
    elif 'CREDENTIALS_FILE' in os.environ:
        creds_file = os.environ['CREDENTIALS_FILE']
        if os.path.exists(creds_file):
            print(f"✅ Using CREDENTIALS_FILE: {creds_file}")
            return creds_file
        else:
            print(f"❌ CREDENTIALS_FILE not found: {creds_file}")
            return None
    
    else:
        print("❌ No credentials configuration found!")
        print("   Available options:")
        print("   - credentials.json file")
        print("   - CREDENTIALS_BASE64 environment variable") 
        print("   - CREDENTIALS_FILE environment variable")
        return None
    
# Setup credentials
CREDENTIALS_FILE = setup_credentials()

# Google API Scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.course-work.readonly',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/classroom.student-submissions.me.readonly'
]

# ==================== VALIDATION ====================
def validate_topics():
    """Validasi topic IDs"""
    print("\n🔔 TOPIC CONFIGURATION:")
    print(f"   • ANNOUNCEMENT_TOPIC_ID: {ANNOUNCEMENT_TOPIC_ID} ({TOPIC_NAMES.get(ANNOUNCEMENT_TOPIC_ID, 'Unknown')})")
    print(f"   • ASSIGNMENT_TOPIC_ID: {ASSIGNMENT_TOPIC_ID} ({TOPIC_NAMES.get(ASSIGNMENT_TOPIC_ID, 'Unknown')})")
    print(f"   • ATTENDANCE_TOPIC_ID: {ATTENDANCE_TOPIC_ID} ({TOPIC_NAMES.get(ATTENDANCE_TOPIC_ID, 'Unknown')})")
    
    # Cek jika masih menggunakan default (1)
    if ANNOUNCEMENT_TOPIC_ID == 1:
        print("   ⚠️  ANNOUNCEMENT_TOPIC_ID masih default (1) - pastikan di set ke 3")
    if ASSIGNMENT_TOPIC_ID == 1:
        print("   ⚠️  ASSIGNMENT_TOPIC_ID masih default (1) - pastikan di set ke 2")
    if ATTENDANCE_TOPIC_ID == 1:
        print("   ⚠️  ATTENDANCE_TOPIC_ID masih default (1) - pastikan di set ke 4")

def validate_config():
    """Validasi konfigurasi yang diperlukan"""
    errors = []
    warnings = []
    
    # Tampilkan environment info
    if is_railway():
        print("🚄 Running on RAILWAY")
    else:
        print("💻 Running LOCALLY")
    
    # Validasi required variables
    required_vars = {
        'BOT_TOKEN': BOT_TOKEN,
        'GROUP_CHAT_ID': GROUP_CHAT_ID,
        'SPREADSHEET_URL': SPREADSHEET_URL,
    }
    
    for var_name, var_value in required_vars.items():
        if not var_value:
            errors.append(f"{var_name} tidak ditemukan di .env")
        else:
            print(f"✅ {var_name}: {'***' if 'TOKEN' in var_name else var_value}")
    
    # Validasi file credentials
    if not CREDENTIALS_FILE:
        errors.append("CREDENTIALS_FILE tidak dikonfigurasi")
    else:
        print(f"✅ CREDENTIALS_FILE: {CREDENTIALS_FILE}")
        # Cek file exists hanya jika CREDENTIALS_FILE adalah string path
        if isinstance(CREDENTIALS_FILE, str) and not os.path.exists(CREDENTIALS_FILE):
            errors.append(f"File {CREDENTIALS_FILE} tidak ditemukan")

    # Validasi format GROUP_CHAT_ID
    if GROUP_CHAT_ID and GROUP_CHAT_ID > 0:
        errors.append("GROUP_CHAT_ID harus negatif untuk grup super (format: -1001234567890)")
    
    # Validasi ADMIN_IDS
    if not ADMIN_IDS:
        warnings.append("ADMIN_IDS tidak dikonfigurasi - beberapa fitur admin tidak akan bekerja")
    else:
        print(f"✅ ADMIN_IDS: {ADMIN_IDS}")
    
    # Validasi Google Classroom (opsional, hanya warning)
    if CLASSROOM_COURSE_ID == "your_classroom_course_id_here":
        warnings.append("CLASSROOM_COURSE_ID masih menggunakan nilai default - fitur Classroom akan dinonaktifkan")
    
    if GOOGLE_MEET_LINK == "meet.google.com/your-actual-meet-code":
        warnings.append("GOOGLE_MEET_LINK masih menggunakan nilai default")
    
    validate_topics()
    
    # Tampilkan warnings
    if warnings:
        print("\n⚠️  PERINGATAN:")
        for warning in warnings:
            print(f"   • {warning}")
    
    if errors:
        print("\n❌ ERROR KONFIGURASI:")
        for error in errors:
            print(f"   • {error}")
        
        print("\n📝 CARA PERBAIKI:")
        if is_railway():
            print("   • Buka Railway Dashboard → Variables")
            print("   • Tambahkan BOT_TOKEN, GROUP_CHAT_ID, SPREADSHEET_URL")
            print("   • Tambahkan CREDENTIALS_BASE64 atau upload credentials.json")
        else:
            print("   • Pastikan file .env sudah diisi dengan benar")
            print("   • Pastikan credentials.json ada di folder yang sama")
        
        return False

    print("✅ Konfigurasi berhasil divalidasi!")
    return True

# Jalankan validasi saat module di-load
if __name__ != '__name__':
    config_valid = validate_config()
