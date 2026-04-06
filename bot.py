# -*- coding: utf-8 -*-
"""
By @doxbinyetkili
Universal File Hosting Bot - OPTIMIZED FOR RENDER.COM
+ DÜŞÜK CPU/RAM KULLANIMI
+ SANAL ORTAMDA ÇALIŞTIRMA
+ PERFORMANS İZLEME
"""

import telebot
import subprocess
import os
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import sqlite3
import json
import logging
import signal
import threading
import re
import sys
import atexit
import requests
import hashlib
import random
import string
import resource
import psutil

# --- Flask Keep Alive (Hafif) ---
from flask import Flask, render_template, jsonify, request, send_file
from threading import Thread

app = Flask(__name__)

# --- Konfigürasyon ---
TOKEN = '8777921082:AAFIck8aFtI_NZ-kebORLXe0l13Hd3Gv2v0'
OWNER_ID = 8666122626
ADMIN_ID = 8666122626
LOG_CHANNEL = "-1003860868923"

# CPU ve RAM limitleri (Render.com için optimize)
MAX_CPU_PERCENT = 10.0  # Maksimum CPU kullanımı %10
MAX_RAM_MB = 256  # Maksimum RAM 256MB

# Dizinler
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')
LOGS_DIR = os.path.join(BASE_DIR, 'execution_logs')
SANDBOX_DIR = os.path.join(BASE_DIR, 'sandbox')  # Sanal ortam için

for directory in [UPLOAD_BOTS_DIR, IROTECH_DIR, LOGS_DIR, SANDBOX_DIR]:
    os.makedirs(directory, exist_ok=True)

# Bot başlatma
bot = telebot.TeleBot(TOKEN)

# --- CPU/RAM Limitleme ---
def set_resource_limits():
    """CPU ve RAM limitlerini ayarla"""
    try:
        # CPU zaman limiti (saniye)
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        
        # Bellek limiti (256 MB)
        resource.setrlimit(resource.RLIMIT_AS, (MAX_RAM_MB * 1024 * 1024, MAX_RAM_MB * 1024 * 1024))
        
        # İşlem sayısı limiti
        resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))
        
        logger.info("✅ CPU/RAM limitleri ayarlandı")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Limit ayarlanamadı: {e}")
        return False

def get_system_stats():
    """Sistem istatistiklerini al"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu': cpu_percent,
            'ram_used': memory.used / (1024 * 1024),  # MB
            'ram_total': memory.total / (1024 * 1024),  # MB
            'ram_percent': memory.percent,
            'disk_used': disk.used / (1024 * 1024 * 1024),  # GB
            'disk_total': disk.total / (1024 * 1024 * 1024),  # GB
            'disk_percent': disk.percent
        }
    except Exception as e:
        return {'error': str(e)}

def check_resource_usage():
    """Kaynak kullanımını kontrol et ve limit aşılırsa uyar"""
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        
        if cpu > MAX_CPU_PERCENT:
            logger.warning(f"⚠️ CPU limit aşıldı: {cpu}% > {MAX_CPU_PERCENT}%")
            return False, f"CPU kullanımı çok yüksek: {cpu}%"
        
        if ram > 80:  # RAM %80 üzeri uyarı
            logger.warning(f"⚠️ RAM yüksek: {ram}%")
            
        return True, "OK"
    except Exception as e:
        return True, str(e)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'bot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Veritabanı ---
def init_db():
    """Veritabanını başlat"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
                  join_date TEXT, last_seen TEXT, file_count INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS files
                 (user_id INTEGER, file_name TEXT, file_type TEXT, 
                  upload_time TEXT, file_size INTEGER, 
                  PRIMARY KEY (user_id, file_name))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS running_scripts
                 (user_id INTEGER, file_name TEXT, start_time TEXT, pid INTEGER,
                  PRIMARY KEY (user_id, file_name))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS banned_users
                 (user_id INTEGER PRIMARY KEY, reason TEXT, ban_date TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
                 (referrer_id INTEGER, referred_id INTEGER, referral_date TEXT,
                  PRIMARY KEY (referrer_id, referred_id))''')
    
    conn.commit()
    conn.close()
    logger.info("Veritabanı başlatıldı")

init_db()

# --- Veri yapıları ---
active_users = set()
user_files = {}
running_scripts = {}
banned_users = set()
user_referrals = {}
referral_stats = {}

# --- Flask Routes ---
@app.route('/')
def home():
    stats = get_system_stats()
    return f"""
    <html>
    <head><title>Universal File Host</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body {{ font-family: Arial; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }}
        .stats {{ background: rgba(0,0,0,0.5); border-radius: 10px; padding: 15px; margin: 10px auto; max-width: 500px; }}
        .cpu {{ color: {'red' if stats.get('cpu',0)>10 else 'lime'}; }}
    </style>
    </head>
    <body>
        <h1>📁 Universal File Host</h1>
        <div class="stats">
            <h2>📊 Sistem Durumu</h2>
            <p class="cpu">💻 CPU: {stats.get('cpu', 0):.1f}% / {MAX_CPU_PERCENT}%</p>
            <p>💾 RAM: {stats.get('ram_used', 0):.0f}MB / {stats.get('ram_total', 0):.0f}MB ({stats.get('ram_percent', 0):.1f}%)</p>
            <p>💿 Disk: {stats.get('disk_used', 0):.1f}GB / {stats.get('disk_total', 0):.1f}GB</p>
            <p>👥 Aktif Kullanıcı: {len(active_users)}</p>
            <p>📁 Toplam Dosya: {sum(len(files) for files in user_files.values())}</p>
        </div>
        <p>✅ Bot çalışıyor - Düşük CPU/RAM modu</p>
    </body>
    </html>
    """

@app.route('/stats')
def stats():
    return jsonify(get_system_stats())

@app.route('/file/<path:filename>')
def serve_file(filename):
    """Dosya servisi"""
    try:
        # Dosyayı bul
        for user_id, files in user_files.items():
            for file_name, file_type in files:
                if file_name == filename:
                    file_path = os.path.join(UPLOAD_BOTS_DIR, str(user_id), file_name)
                    if os.path.exists(file_path):
                        return send_file(file_path, as_attachment=False)
        return "Dosya bulunamadı", 404
    except Exception as e:
        return f"Hata: {e}", 500

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()
    print("🌐 Flask sunucusu başlatıldı")

# --- Sanal Ortamda Çalıştırma ---
def run_in_sandbox(script_path, user_id):
    """Script'i sanal ortamda düşük kaynakla çalıştır"""
    script_name = os.path.basename(script_path)
    script_ext = os.path.splitext(script_name)[1].lower()
    
    # Kullanıcı için sandbox dizini
    user_sandbox = os.path.join(SANDBOX_DIR, str(user_id))
    os.makedirs(user_sandbox, exist_ok=True)
    
    # Script'i sandbox'a kopyala
    sandbox_script = os.path.join(user_sandbox, script_name)
    shutil.copy2(script_path, sandbox_script)
    
    # CPU ve RAM limitleri ile çalıştır
    env = os.environ.copy()
    env['PYTHONPATH'] = ''
    env['LD_LIBRARY_PATH'] = ''
    
    # Nice değeri ile düşük öncelik
    cmd = ['nice', '-n', '19']
    
    if script_ext == '.py':
        cmd.extend([sys.executable, sandbox_script])
    elif script_ext == '.js':
        cmd.extend(['node', sandbox_script])
    elif script_ext == '.sh':
        cmd.extend(['bash', sandbox_script])
    else:
        cmd.append(sandbox_script)
    
    try:
        # Zaman aşımı ile çalıştır (30 saniye max)
        process = subprocess.Popen(
            cmd,
            cwd=user_sandbox,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=set_resource_limits if hasattr(os, 'preexec_fn') else None
        )
        
        return process, sandbox_script
    except Exception as e:
        logger.error(f"Sandbox çalıştırma hatası: {e}")
        return None, None

def execute_with_timeout(script_path, user_id, timeout=30):
    """Zaman aşımı ile script çalıştır"""
    process, sandbox_path = run_in_sandbox(script_path, user_id)
    
    if not process:
        return False, "Çalıştırılamadı"
    
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        
        if process.returncode == 0:
            return True, stdout.decode('utf-8', errors='ignore')
        else:
            return False, stderr.decode('utf-8', errors='ignore')
    except subprocess.TimeoutExpired:
        process.kill()
        return False, "Zaman aşımı (30 saniye)"
    except Exception as e:
        return False, str(e)

# --- Dosya yükleme limitleri ---
FREE_USER_LIMIT = 9
SUBSCRIBED_USER_LIMIT = 50

def get_user_limit(user_id):
    """Kullanıcı limitini döndür"""
    if user_id == OWNER_ID or user_id == ADMIN_ID:
        return 9999
    return FREE_USER_LIMIT

def get_user_file_count(user_id):
    """Kullanıcının dosya sayısı"""
    return len(user_files.get(user_id, []))

# --- Yardımcı fonksiyonlar ---
def get_user_folder(user_id):
    """Kullanıcı klasörü"""
    folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(folder, exist_ok=True)
    return folder

def save_user_info(user_id, username, first_name):
    """Kullanıcı bilgilerini kaydet"""
    active_users.add(user_id)
    
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO users (user_id, username, first_name, join_date, last_seen) VALUES (?, ?, ?, ?, ?)',
             (user_id, username, first_name, datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def check_malicious_code(file_path):
    """Basit güvenlik kontrolü (düşük CPU)"""
    zararli_patterns = [
        'rm -rf', 'sudo', 'su ', 'shutdown', 'reboot',
        'format', 'del /', 'rd /', 'os.system', 'subprocess',
        'eval(', 'exec(', '__import__', 'base64.b64decode'
    ]
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()
        
        for pattern in zararli_patterns:
            if pattern in content:
                return False, f"Zararlı kod tespit edildi: {pattern}"
        
        return True, "Güvenli"
    except:
        return True, "Kontrol edilemedi"

# --- Buton düzenleri ---
MAIN_BUTTONS = [
    ["📤 Dosya Yükle", "📂 Dosyalarım"],
    ["📊 İstatistik", "⚡ Bot Hızı"],
    ["👥 Referans", "📞 İletişim"]
]

ADMIN_BUTTONS = [
    ["📤 Dosya Yükle", "📂 Dosyalarım"],
    ["📊 İstatistik", "⚡ Bot Hızı"],
    ["👥 Referans", "📞 İletişim"],
    ["📢 Duyuru", "🔒 Kilit"],
    ["👑 Admin Panel", "📈 Sistem"]
]

# --- Komutlar ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    if user_id in banned_users:
        bot.reply_to(message, "🚫 Yasaklandınız!")
        return
    
    save_user_info(user_id, message.from_user.username, message.from_user.first_name)
    
    welcome = f"🔐 Hoş geldin {message.from_user.first_name}!\n\n"
    welcome += f"📁 Dosya limitin: {get_user_limit(user_id)}\n"
    welcome += f"📄 Mevcut dosya: {get_user_file_count(user_id)}\n\n"
    welcome += f"⚡ Düşük CPU/RAM modunda çalışıyor\n"
    welcome += f"💻 CPU limit: %{MAX_CPU_PERCENT}\n"
    welcome += f"💾 RAM limit: {MAX_RAM_MB}MB\n\n"
    welcome += f"📤 Dosya göndererek başlayabilirsin!"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ADMIN_BUTTONS if user_id in [OWNER_ID, ADMIN_ID] else MAIN_BUTTONS
    for row in buttons:
        markup.add(*[types.KeyboardButton(b) for b in row])
    
    bot.reply_to(message, welcome, reply_markup=markup)

@bot.message_handler(content_types=['document'])
def handle_file(message):
    """Dosya yükleme - optimize edilmiş"""
    user_id = message.from_user.id
    
    if user_id in banned_users:
        bot.reply_to(message, "🚫 Yasaklandınız!")
        return
    
    # Limit kontrolü
    if get_user_file_count(user_id) >= get_user_limit(user_id):
        bot.reply_to(message, f"❌ Dosya limitin doldu! Maksimum: {get_user_limit(user_id)}")
        return
    
    # Dosya boyutu kontrolü (5MB max)
    if message.document.file_size > 5 * 1024 * 1024:
        bot.reply_to(message, "❌ Dosya çok büyük! Maksimum 5MB")
        return
    
    file_name = message.document.file_name
    file_info = bot.get_file(message.document.file_id)
    
    msg = bot.reply_to(message, f"🔍 {file_name} taranıyor...")
    
    try:
        # Dosyayı indir
        downloaded = bot.download_file(file_info.file_path)
        
        # Kullanıcı klasörüne kaydet
        user_folder = get_user_folder(user_id)
        file_path = os.path.join(user_folder, file_name)
        
        with open(file_path, 'wb') as f:
            f.write(downloaded)
        
        # Güvenlik kontrolü (hızlı)
        is_safe, result = check_malicious_code(file_path)
        
        if not is_safe and user_id not in [OWNER_ID, ADMIN_ID]:
            os.remove(file_path)
            bot.edit_message_text(f"❌ {result}\n\nDosya reddedildi!", msg.chat.id, msg.message_id)
            return
        
        # Dosya tipini belirle
        ext = os.path.splitext(file_name)[1].lower()
        file_type = 'executable' if ext in ['.py', '.js', '.sh', '.bash'] else 'file'
        
        # Kaydet
        if user_id not in user_files:
            user_files[user_id] = []
        user_files[user_id].append((file_name, file_type))
        
        # Veritabanına kaydet
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO files (user_id, file_name, file_type, upload_time, file_size) VALUES (?, ?, ?, ?, ?)',
                 (user_id, file_name, file_type, datetime.now().isoformat(), message.document.file_size))
        c.execute('UPDATE users SET file_count = file_count + 1, last_seen = ? WHERE user_id = ?',
                 (datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
        
        # Başarılı mesajı
        success_msg = f"✅ {file_name} yüklendi!\n\n"
        success_msg += f"📁 Tip: {file_type}\n"
        success_msg += f"📊 Kullanım: {get_user_file_count(user_id)}/{get_user_limit(user_id)}\n\n"
        
        if file_type == 'executable':
            success_msg += f"🚀 Çalıştırmak için 'Dosyalarım' menüsünü kullan.\n"
            success_msg += f"⚠️ Düşük CPU/RAM modunda çalışacak (max 30 saniye)"
        else:
            # Dosya hash'i
            file_hash = hashlib.md5(f"{user_id}_{file_name}".encode()).hexdigest()[:8]
            success_msg += f"🔗 Link: /file/{file_name}"
        
        bot.edit_message_text(success_msg, msg.chat.id, msg.message_id)
        
    except Exception as e:
        bot.edit_message_text(f"❌ Hata: {str(e)}", msg.chat.id, msg.message_id)
        logger.error(f"Dosya yükleme hatası: {e}")

@bot.message_handler(func=lambda m: m.text == "📂 Dosyalarım")
def list_files(message):
    user_id = message.from_user.id
    files = user_files.get(user_id, [])
    
    if not files:
        bot.reply_to(message, "📂 Henüz dosyan yok!\n\n📤 Dosya göndererek başla.")
        return
    
    text = "📂 **Dosyaların:**\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for i, (file_name, file_type) in enumerate(files, 1):
        icon = "🚀" if file_type == 'executable' else "📄"
        
        # Çalışıyor mu kontrolü
        is_running = False
        for sk in running_scripts:
            if sk.startswith(f"{user_id}_{file_name}"):
                is_running = True
                break
        
        status = "🟢 Çalışıyor" if is_running else "⚪ Durduruldu"
        text += f"{i}. {icon} {file_name}\n   📁 {file_type} | {status}\n\n"
        
        markup.add(types.InlineKeyboardButton(
            f"{icon} {file_name[:30]}",
            callback_data=f"file_{user_id}_{file_name}"
        ))
    
    text += f"\n📊 Kullanım: {len(files)}/{get_user_limit(user_id)}"
    
    bot.reply_to(message, text, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('file_'))
def handle_file_control(call):
    _, user_id, file_name = call.data.split('_', 2)
    user_id = int(user_id)
    
    if call.from_user.id != user_id:
        bot.answer_callback_query(call.id, "🚫 Bu dosya sana ait değil!")
        return
    
    # Dosyayı bul
    file_path = os.path.join(get_user_folder(user_id), file_name)
    if not os.path.exists(file_path):
        bot.answer_callback_query(call.id, "❌ Dosya bulunamadı!")
        return
    
    ext = os.path.splitext(file_name)[1].lower()
    is_executable = ext in ['.py', '.js', '.sh', '.bash']
    
    # Çalışıyor mu?
    script_key = f"{user_id}_{file_name}"
    is_running = script_key in running_scripts
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if is_executable:
        if is_running:
            markup.add(types.InlineKeyboardButton("🛑 Durdur", callback_data=f"stop_{user_id}_{file_name}"))
            markup.add(types.InlineKeyboardButton("🔄 Yeniden Başlat", callback_data=f"restart_{user_id}_{file_name}"))
        else:
            markup.add(types.InlineKeyboardButton("🚀 Çalıştır", callback_data=f"run_{user_id}_{file_name}"))
    
    markup.add(types.InlineKeyboardButton("🗑️ Sil", callback_data=f"delete_{user_id}_{file_name}"))
    markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data=f"back_{user_id}"))
    
    info = f"📄 **{file_name}**\n\n"
    info += f"📁 Tip: {'Çalıştırılabilir' if is_executable else 'Dosya'}\n"
    info += f"📊 Durum: {'🟢 Çalışıyor' if is_running else '⚪ Durduruldu'}\n"
    info += f"💾 Boyut: {os.path.getsize(file_path) // 1024}KB\n"
    
    if is_executable:
        info += f"\n⚡ Düşük CPU/RAM modunda çalışacak\n"
        info += f"⏱️ Maksimum çalışma süresi: 30 saniye\n"
        info += f"💻 CPU limiti: %{MAX_CPU_PERCENT}"
    
    bot.edit_message_text(info, call.message.chat.id, call.message.message_id, 
                         reply_markup=markup, parse_mode='Markdown')
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('run_'))
def run_file(call):
    _, user_id, file_name = call.data.split('_', 2)
    user_id = int(user_id)
    
    if call.from_user.id != user_id:
        bot.answer_callback_query(call.id, "🚫 Yetkisiz!")
        return
    
    # Kaynak kontrolü
    ok, msg = check_resource_usage()
    if not ok:
        bot.answer_callback_query(call.id, f"❌ {msg}")
        return
    
    file_path = os.path.join(get_user_folder(user_id), file_name)
    
    bot.edit_message_text(f"🚀 {file_name} çalıştırılıyor...\n\n⚡ Düşük CPU/RAM modu aktif\n⏱️ Maksimum 30 saniye",
                         call.message.chat.id, call.message.message_id)
    
    # Zaman aşımı ile çalıştır
    success, output = execute_with_timeout(file_path, user_id, timeout=30)
    
    script_key = f"{user_id}_{file_name}"
    
    if success:
        running_scripts[script_key] = {'start': datetime.now(), 'pid': 0}
        
        # Kısa çıktı göster
        output_preview = output[:500] if output else "Çıktı yok"
        
        result_msg = f"✅ {file_name} çalıştı!\n\n"
        result_msg += f"📊 Çıktı:\n```\n{output_preview}\n```\n"
        
        if len(output) > 500:
            result_msg += f"\n... ve {len(output)-500} karakter daha"
        
        bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
        # Çalışan script listesinden temizle
        if script_key in running_scripts:
            del running_scripts[script_key]
    else:
        bot.edit_message_text(f"❌ Çalıştırma başarısız:\n\n{output[:300]}",
                             call.message.chat.id, call.message.message_id)
    
    bot.answer_callback_query(call.id, "Tamamlandı!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('stop_'))
def stop_file(call):
    _, user_id, file_name = call.data.split('_', 2)
    user_id = int(user_id)
    script_key = f"{user_id}_{file_name}"
    
    if script_key in running_scripts:
        del running_scripts[script_key]
        bot.answer_callback_query(call.id, "🛑 Durduruldu!")
    else:
        bot.answer_callback_query(call.id, "⚠️ Zaten çalışmıyor!")
    
    # Geri dön
    call.data = f"file_{user_id}_{file_name}"
    handle_file_control(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('restart_'))
def restart_file(call):
    _, user_id, file_name = call.data.split('_', 2)
    user_id = int(user_id)
    script_key = f"{user_id}_{file_name}"
    
    if script_key in running_scripts:
        del running_scripts[script_key]
    
    call.data = f"run_{user_id}_{file_name}"
    run_file(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_file(call):
    _, user_id, file_name = call.data.split('_', 2)
    user_id = int(user_id)
    
    # Durdur
    script_key = f"{user_id}_{file_name}"
    if script_key in running_scripts:
        del running_scripts[script_key]
    
    # Sil
    file_path = os.path.join(get_user_folder(user_id), file_name)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Listedən çıkar
    if user_id in user_files:
        user_files[user_id] = [(fn, ft) for fn, ft in user_files[user_id] if fn != file_name]
    
    # Veritabanından sil
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
    c.execute('UPDATE users SET file_count = file_count - 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, f"🗑️ {file_name} silindi!")
    
    # Geri dön
    call.data = f"back_{user_id}"
    handle_back(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('back_'))
def handle_back(call):
    _, user_id = call.data.split('_', 1)
    user_id = int(user_id)
    
    files = user_files.get(user_id, [])
    
    if not files:
        bot.edit_message_text("📂 Henüz dosyan yok!", call.message.chat.id, call.message.message_id)
        return
    
    text = "📂 **Dosyaların:**\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for file_name, file_type in files:
        icon = "🚀" if file_type == 'executable' else "📄"
        markup.add(types.InlineKeyboardButton(
            f"{icon} {file_name[:30]}",
            callback_data=f"file_{user_id}_{file_name}"
        ))
    
    text += f"\n📊 Kullanım: {len(files)}/{get_user_limit(user_id)}"
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                         reply_markup=markup, parse_mode='Markdown')
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.text == "📊 İstatistik")
def stats_command(message):
    user_id = message.from_user.id
    sys_stats = get_system_stats()
    
    text = f"📊 **İstatistikler**\n\n"
    text += f"👤 Kullanıcı ID: {user_id}\n"
    text += f"📁 Dosyaların: {get_user_file_count(user_id)}\n"
    text += f"📈 Dosya limiti: {get_user_limit(user_id)}\n\n"
    text += f"💻 **Sistem Durumu:**\n"
    text += f"⚡ CPU: {sys_stats.get('cpu', 0):.1f}% / {MAX_CPU_PERCENT}%\n"
    text += f"💾 RAM: {sys_stats.get('ram_used', 0):.0f}MB / {sys_stats.get('ram_total', 0):.0f}MB\n"
    text += f"💿 Disk: {sys_stats.get('disk_used', 0):.1f}GB / {sys_stats.get('disk_total', 0):.1f}GB\n\n"
    text += f"👥 Toplam Kullanıcı: {len(active_users)}\n"
    text += f"📁 Toplam Dosya: {sum(len(f) for f in user_files.values())}\n"
    text += f"🚀 Çalışan Script: {len(running_scripts)}"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "⚡ Bot Hızı")
def speed_command(message):
    start = time.time()
    msg = bot.reply_to(message, "🏃 Hız testi yapılıyor...")
    response = (time.time() - start) * 1000
    
    stats = get_system_stats()
    
    text = f"⚡ **Bot Performansı**\n\n"
    text += f"📨 Tepki Süresi: {response:.0f}ms\n"
    text += f"💻 CPU Kullanımı: {stats.get('cpu', 0):.1f}%\n"
    text += f"💾 RAM Kullanımı: {stats.get('ram_used', 0):.0f}MB\n\n"
    text += f"✅ Düşük CPU/RAM modu aktif\n"
    text += f"🔒 Limitler aktif\n"
    text += f"⚡ Tüm sistemler çalışıyor!"
    
    bot.edit_message_text(text, msg.chat.id, msg.message_id, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "👥 Referans")
def referral_command(message):
    user_id = message.from_user.id
    code = hashlib.md5(str(user_id).encode()).hexdigest()[:8]
    
    text = f"👥 **Referans Sistemi**\n\n"
    text += f"🔗 Referans Kodun: `{code}`\n"
    text += f"📊 Toplam Referansın: {len(user_referrals.get(user_id, []))}\n\n"
    text += f"📤 Linkin:\n"
    text += f"`https://t.me/{bot.get_me().username}?start=ref_{code}`\n\n"
    text += f"🎁 Her referansta +1 dosya hakkı!"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📞 İletişim")
def contact_command(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📩 Mesaj Gönder", url="https://t.me/doxbinyetkili"))
    markup.add(types.InlineKeyboardButton("📢 Kanal", url="https://t.me/ensorgupanelimiz"))
    
    bot.reply_to(message, "📞 **İletişim**\n\nSahip: @doxbinyetkili\nKanal: @ensorgupanelimiz", 
                reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "📢 Duyuru")
def broadcast_command(message):
    if message.from_user.id not in [OWNER_ID, ADMIN_ID]:
        bot.reply_to(message, "🚫 Yetkin yok!")
        return
    
    bot.reply_to(message, "📢 Duyuru metnini gönder:")
    bot.register_next_step_handler(message, send_broadcast)

def send_broadcast(message):
    text = message.text
    success = 0
    
    for user_id in active_users:
        try:
            bot.send_message(user_id, f"📢 **DUYURU**\n\n{text}")
            success += 1
            time.sleep(0.05)  # Rate limiting
        except:
            pass
    
    bot.reply_to(message, f"✅ Duyuru {success} kullanıcıya gönderildi!")

@bot.message_handler(func=lambda m: m.text == "🔒 Kilit")
def lock_command(message):
    if message.from_user.id not in [OWNER_ID, ADMIN_ID]:
        bot.reply_to(message, "🚫 Yetkin yok!")
        return
    
    global bot_locked
    bot_locked = not bot_locked
    status = "🔒 Kilitli" if bot_locked else "🔓 Açık"
    bot.reply_to(message, f"🔒 Bot durumu: {status}")

@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel")
def admin_panel(message):
    if message.from_user.id not in [OWNER_ID, ADMIN_ID]:
        bot.reply_to(message, "🚫 Yetkin yok!")
        return
    
    stats = get_system_stats()
    
    text = f"👑 **Admin Panel**\n\n"
    text += f"👥 Kullanıcı: {len(active_users)}\n"
    text += f"📁 Dosya: {sum(len(f) for f in user_files.values())}\n"
    text += f"🚀 Script: {len(running_scripts)}\n"
    text += f"🚫 Yasaklı: {len(banned_users)}\n\n"
    text += f"💻 CPU: {stats.get('cpu', 0):.1f}%\n"
    text += f"💾 RAM: {stats.get('ram_used', 0):.0f}MB\n\n"
    text += f"📊 **Komutlar:**\n"
    text += f"/ban <id> - Kullanıcıyı yasakla\n"
    text += f"/unban <id> - Yasağı kaldır\n"
    text += f"/stats - Detaylı istatistik\n"
    text += f"/clean - Geçici dosyaları temizle"
    
    bot.reply_to(message, text)

@bot.message_handler(func=lambda m: m.text == "📈 Sistem")
def system_stats_command(message):
    if message.from_user.id not in [OWNER_ID, ADMIN_ID]:
        bot.reply_to(message, "🚫 Yetkin yok!")
        return
    
    stats = get_system_stats()
    
    text = f"📈 **Sistem İstatistikleri**\n\n"
    text += f"🕐 Zaman: {datetime.now().strftime('%H:%M:%S')}\n"
    text += f"💻 CPU: {stats.get('cpu', 0):.1f}%\n"
    text += f"💾 RAM: {stats.get('ram_used', 0):.0f}/{stats.get('ram_total', 0):.0f}MB ({stats.get('ram_percent', 0):.1f}%)\n"
    text += f"💿 Disk: {stats.get('disk_used', 0):.1f}/{stats.get('disk_total', 0):.1f}GB\n\n"
    text += f"👥 Aktif Kullanıcı: {len(active_users)}\n"
    text += f"📁 Toplam Dosya: {sum(len(f) for f in user_files.values())}\n"
    text += f"🚀 Çalışan Script: {len(running_scripts)}\n"
    text += f"🚫 Yasaklı Kullanıcı: {len(banned_users)}\n"
    text += f"👥 Referanslar: {sum(len(r) for r in user_referrals.values())}"
    
    bot.reply_to(message, text)

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if message.from_user.id not in [OWNER_ID, ADMIN_ID]:
        return
    
    try:
        user_id = int(message.text.split()[1])
        banned_users.add(user_id)
        
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO banned_users (user_id, reason, ban_date) VALUES (?, ?, ?)',
                 (user_id, "Admin tarafından yasaklandı", datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Kullanıcı {user_id} yasaklandı!")
    except:
        bot.reply_to(message, "❌ Kullanım: /ban <user_id>")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if message.from_user.id not in [OWNER_ID, ADMIN_ID]:
        return
    
    try:
        user_id = int(message.text.split()[1])
        banned_users.discard(user_id)
        
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Kullanıcı {user_id} yasağı kaldırıldı!")
    except:
        bot.reply_to(message, "❌ Kullanım: /unban <user_id>")

@bot.message_handler(commands=['clean'])
def clean_temp(message):
    if message.from_user.id not in [OWNER_ID, ADMIN_ID]:
        return
    
    try:
        # Sandbox temizle
        for item in os.listdir(SANDBOX_DIR):
            item_path = os.path.join(SANDBOX_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
        
        # Log temizle (30 günden eski)
        for log in os.listdir(LOGS_DIR):
            log_path = os.path.join(LOGS_DIR, log)
            if os.path.getmtime(log_path) < time.time() - 30*86400:
                os.remove(log_path)
        
        bot.reply_to(message, "✅ Geçici dosyalar temizlendi!")
    except Exception as e:
        bot.reply_to(message, f"❌ Hata: {e}")

@bot.message_handler(commands=['stats'])
def detailed_stats(message):
    if message.from_user.id not in [OWNER_ID, ADMIN_ID]:
        return
    
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM files')
    total_files = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM banned_users')
    total_banned = c.fetchone()[0]
    
    conn.close()
    
    text = f"📊 **Detaylı İstatistikler**\n\n"
    text += f"👥 Toplam Kullanıcı: {total_users}\n"
    text += f"📁 Toplam Dosya: {total_files}\n"
    text += f"🚫 Yasaklı Kullanıcı: {total_banned}\n"
    text += f"🚀 Çalışan Script: {len(running_scripts)}\n"
    text += f"👥 Aktif (Bu oturum): {len(active_users)}\n\n"
    text += f"⚡ CPU Limiti: %{MAX_CPU_PERCENT}\n"
    text += f"💾 RAM Limiti: {MAX_RAM_MB}MB\n"
    text += f"⏱️ Script Limiti: 30 saniye"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def unknown(message):
    bot.reply_to(message, "🔒 Menü butonlarını kullan veya /start yaz.")

# --- Başlangıç ---
bot_locked = False

if __name__ == "__main__":
    # CPU/RAM limitlerini dene
    set_resource_limits()
    
    # Flask başlat
    keep_alive()
    
    # Botu başlat
    logger.info("🚀 Bot başlatılıyor... (Düşük CPU/RAM modu)")
    print("=" * 50)
    print("📁 UNIVERSAL FILE HOST BOT")
    print(f"💻 CPU Limit: %{MAX_CPU_PERCENT}")
    print(f"💾 RAM Limit: {MAX_RAM_MB}MB")
    print(f"⚡ Script Limiti: 30 saniye")
    print("=" * 50)
    
    try:
        bot_info = bot.get_me()
        print(f"✅ Bot çalışıyor: @{bot_info.username}")
        print(f"🌐 Web: http://localhost:{os.environ.get('PORT', 5000)}")
        
        bot.infinity_polling(timeout=30, long_polling_timeout=10)
    except Exception as e:
        logger.error(f"Bot hatası: {e}")
        print(f"❌ Hata: {e}")
