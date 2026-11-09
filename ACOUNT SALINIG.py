import os
import sqlite3
import re
import asyncio
import time
import logging
import csv
import zipfile
import shutil
import html
import imaplib
import email
import urllib.request
import json
import ssl
import hashlib
from datetime import datetime
from urllib.parse import quote, urlencode

from telethon import TelegramClient, events, Button

# ================= GLOBAL BUTTON FONT =================
_ORIGINAL_BUTTON = Button

def _button_font(text):
    text = str(text)
    out = []
    for ch in text:
        o = ord(ch)
        if 65 <= o <= 90:          # A-Z
            out.append(chr(0x1D5D4 + (o - 65)))
        elif 97 <= o <= 122:      # a-z
            out.append(chr(0x1D5EE + (o - 97)))
        else:
            out.append(ch)
    return ''.join(out)

class _StyledButtonProxy:
    @staticmethod
    def inline(text, data=None, **kwargs):
        return _ORIGINAL_BUTTON.inline(_button_font(text), data=data, **kwargs)

    @staticmethod
    def url(text, url, **kwargs):
        return _ORIGINAL_BUTTON.url(_button_font(text), url, **kwargs)

Button = _StyledButtonProxy

from telethon.errors import (
  SessionPasswordNeededError, 
  MessageNotModifiedError,
  UserNotParticipantError,
  ChatAdminRequiredError
)
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator
from telethon.tl.functions.account import GetPasswordRequest

# ================= CONFIGURATION =================
API_ID = 39776296 
API_HASH = "39750d30671418c6fd01a96b6296ee82"
BOT_TOKEN = "9263012433:AAEDWHaVcYrvC2EgxJIcNbqCpqdfBCHv7iI" 
ADMIN_ID = 8781077406 

P_YES = ''
P_NO = ''
P_PKG = ''
P_MONEY = ''
P_USDT = ''
P_INR = '₹'
P_TG = ''
P_GIFT = ''
P_STATS = ''
P_CARD = ''
P_USERS = ''
P_CAL = ''
P_PC = ''
P_EYE = ''
P_CW = ''
P_ON = ''
P_OFF = ''
P_ID = ''
P_KEY = ''
P_GLOBE = ''
P_CART = ''
P_STORE = ''
P_OTP = ''
P_2FA = ''
P_FLAG = ''
P_PHONE = ''
P_WAIT = ''
P_TIME = ''
P_WARN = ''
P_DOC = ''
P_ASST = ''
P_ACC = ''
P_FIRE = ''
P_STAR = ''
P_DIAMOND = ''
P_BELL = ''
P_CROWN = ''
P_LIGHTNING = ''
P_ROCKET = ''
P_PARTY = ''
P_FOLDER = ''
P_GEAR = ''
P_PIN = ''
P_SEARCH = ''
P_LINK = ''
P_TITLE = ''
P_DESC = ''
P_RATE = ''
P_MIN = ''
P_MAX = ''
P_QTY = ''

def custom_emoji_text(text):
  if text is None: return text
  text = str(text)
  text = re.sub(r'<emoji\s+id=["\'][^"\']+["\']>(.*?)</emoji>', r'\1', text, flags=re.DOTALL | re.IGNORECASE)
  text = re.sub(r'[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]', '', text)
  return text

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

os.makedirs("sessions", exist_ok=True)
session_name = f"bot_session_{BOT_TOKEN.split(':')[0]}"
bot = TelegramClient(session_name, API_ID, API_HASH)
bot.parse_mode = 'html'

db = sqlite3.connect("otp_bot_final.db", check_same_thread=False, timeout=20)
db.execute("PRAGMA journal_mode=WAL;")
cur = db.cursor()

active_orders = {}   
waiting_proof = {}   
deposit_input = {} 
admin_dep_state = {}  
user_spam_cooldown = {} 
session_buy_state = {}   
smm_order_state = {}
refill_state = {}
redeem_state = {}
digital_shop_state = {}

def _country_token(country):
  return hashlib.sha256(str(country).encode("utf-8")).hexdigest()[:10]

def _resolve_country_ref(ref):
  ref = str(ref or "")
  if re.fullmatch(r"[0-9a-f]{10}", ref):
    rows = cur.execute("SELECT DISTINCT country_name FROM stock").fetchall()
    for (name,) in rows:
      if _country_token(name) == ref: return name
  return ref

user_locks = {}
def get_user_lock(uid):
  if uid not in user_locks: user_locks[uid] = asyncio.Lock()
  return user_locks[uid]

def setup_db():
  cur.executescript("""
  CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    total_deposited INTEGER DEFAULT 0,
    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    banned INTEGER DEFAULT 0,
    discount INTEGER DEFAULT 0,
    terms_accepted INTEGER DEFAULT 1
  );
  CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
  CREATE TABLE IF NOT EXISTS stock (
    phone TEXT PRIMARY KEY,
    session_file TEXT,
    country_name TEXT,
    country_icon TEXT DEFAULT '',
    account_year INTEGER,
    category TEXT DEFAULT 'Good',
    price INTEGER,
    available INTEGER DEFAULT 1,
    twofa TEXT DEFAULT 'None',
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS deposits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    method_name TEXT,
    status TEXT, 
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    utr TEXT DEFAULT '',
    gateway_order_id TEXT DEFAULT ''
  );
  CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    country TEXT,
    year INTEGER,
    price INTEGER,
    phone TEXT,
    otp TEXT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS smm_orders (
    bot_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service_id INTEGER,
    link TEXT,
    quantity INTEGER,
    total_price REAL,
    smm_order_id TEXT,
    status TEXT DEFAULT 'Completed',
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    p_add_stock INTEGER DEFAULT 1,
    p_manage_stock INTEGER DEFAULT 1,
    p_stats INTEGER DEFAULT 1,
    p_bal INTEGER DEFAULT 1,
    p_settings INTEGER DEFAULT 1
  );
  CREATE TABLE IF NOT EXISTS custom_countries (code TEXT PRIMARY KEY, name TEXT, flag TEXT DEFAULT '');
  CREATE TABLE IF NOT EXISTS force_channels (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, invite_url TEXT, title TEXT);
  CREATE TABLE IF NOT EXISTS smm_categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
  CREATE TABLE IF NOT EXISTS smm_services (
    service_id INTEGER PRIMARY KEY,
    category_id INTEGER,
    name TEXT,
    rate REAL,
    min INTEGER,
    max INTEGER,
    description TEXT
  );
  CREATE TABLE IF NOT EXISTS redeem_codes (
    code TEXT PRIMARY KEY,
    amount INTEGER NOT NULL,
    max_users INTEGER NOT NULL DEFAULT 1,
    used_count INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active INTEGER DEFAULT 1
  );
  CREATE TABLE IF NOT EXISTS redeem_claims (code TEXT NOT NULL, user_id INTEGER NOT NULL, claimed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (code, user_id));
  CREATE TABLE IF NOT EXISTS digital_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    price INTEGER NOT NULL,
    photo_file_id TEXT DEFAULT '',
    photo_path TEXT DEFAULT '',
    file_path TEXT DEFAULT '',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active INTEGER DEFAULT 1
  );
  """)
  
  # Settings Defaults for Multi-Gateway (FamPayGateway & SGVIP)
  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('active_gateway', 'fampaygateway')") # fampaygateway or sgvip
  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('fampaygateway_enabled', 'on')")
  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('fampaygateway_api_url', 'https://fampaygateway.site')")
  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('fampaygateway_api_key', '')")
  
  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('sgvip_enabled', 'off')")
  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('sgvip_api_url', 'https://sgvip.site')")
  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('sgvip_api_key', '')")

  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('log_channel_id', '-1003940330621')")
  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_url', 'https://t.me/XLARYAN_0100')")
  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_channel_url', 'https://t.me/FREEARUAN')")
  cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('usdt_rate', '94.0')")
  db.commit()

setup_db()

def is_bot_online():
  res = cur.execute("SELECT value FROM settings WHERE key='bot_status'").fetchone()
  return res[0] == 'on' if res else True

def is_admin(uid):
  if uid == ADMIN_ID: return True
  row = cur.execute("SELECT user_id FROM admins WHERE user_id=?", (uid,)).fetchone()
  return bool(row)

def has_perm(uid, perm):
  if uid == ADMIN_ID: return True
  row = cur.execute(f"SELECT {perm} FROM admins WHERE user_id=?", (uid,)).fetchone()
  return bool(row and row[0] == 1)

def get_all_admin_ids():
  ids = [ADMIN_ID]
  try:
    rows = cur.execute("SELECT user_id FROM admins").fetchall()
    ids.extend(int(row[0]) for row in rows if row and row[0])
  except Exception: pass
  return list(dict.fromkeys(ids))

def ensure_user(uid):
  cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
  db.commit()

def get_usdt_rate():
  res = cur.execute("SELECT value FROM settings WHERE key='usdt_rate'").fetchone()
  try: return float(res[0]) if res else 94.0
  except: return 94.0

def _normalize_tg_url(raw_url, fallback=""):
  url = str(raw_url or "").strip()
  if not url: return fallback
  if url.startswith("@"): url = "https://t.me/" + url[1:]
  elif not url.startswith(("http://", "https://")): url = "https://t.me/" + url.lstrip("/")
  return url

def get_setting(key, default=''):
  row = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
  return row[0] if row and row[0] is not None else default

def set_setting(key, value):
  cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
  db.commit()

def payment_enabled(key): return get_setting(key, 'on').lower() == 'on'

def get_log_channel_id():
  res = cur.execute("SELECT value FROM settings WHERE key='log_channel_id'").fetchone()
  try: return int(res[0]) if res and res[0] else -1003940330621
  except: return -1003940330621

def clean_html_url(raw_url):
  if not raw_url: return ""
  clean = re.sub(r'<.*?>', '', raw_url)
  match = re.search(r'https?://[^\s<>"]+', clean)
  return match.group(0).strip() if match else clean.strip()

def _spoiler(value):
  return f"<tg-spoiler>{html.escape(str(value))}</tg-spoiler>"

async def _get_bot_buy_button():
  try:
    bot_info = await bot.get_me()
    username = getattr(bot_info, 'username', None)
    if username: return [[Button.url(" Buy Now", f"https://t.me/{username}", style="success")]]
  except Exception: pass
  return None

# ================= AUTOMATIC LOGS TO CHANNEL =================
async def _send_selling_log(msg):
  try:
    buttons = await _get_bot_buy_button()
    await bot.send_message(
      custom_emoji_text(get_log_channel_id()),
      custom_emoji_text(msg),
      buttons=buttons,
      parse_mode='html'
    )
    return True
  except Exception as ex:
    logger.error(f"Selling log send failed: {ex}")
    return False

async def log_primary_deposit_success(uid, amt, method, utr=None):
  try:
    try:
      user = await bot.get_entity(int(uid))
      username = user.username if user and user.username else "NoUsername"
    except Exception: username = "NoUsername"
    t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = (
      f"{P_YES} {P_FIRE} <b>NEW DEPOSIT SUCCESSFUL (AUTO)</b> {P_PARTY}\n\n"
      f"{P_ACC} User ID: {_spoiler(uid)}\n"
      f"{P_ACC} Username: {_spoiler('@' + username if username != 'NoUsername' else username)}\n"
      f"{P_MONEY} Amount: {P_INR}{amt}\n"
      f"{P_CARD} Gateway/Method: <b>{html.escape(str(method))}</b>\n"
      f"{P_TIME} Time: {t}\n\n"
      f"<i>{P_STAR} Deposit confirmed automatically via Gateway. {P_STAR}</i>"
    )
    await _send_selling_log(msg)
  except Exception as ex: logger.error(f"Deposit Log Err: {ex}")

async def log_primary_purchase(uid, country, price, amount, year, qty):
  try:
    t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = (
      f"{P_CART} {P_ROCKET} <b>NEW TELEGRAM ACCOUNT SALE</b> {P_PARTY}\n\n"
      f"{P_ID} User ID: {_spoiler(uid)}\n"
      f"{P_GLOBE} Country: {html.escape(str(country))}\n"
      f"{P_MONEY} Price: {P_INR}{price}\n"
      f"{P_CARD} Total Paid: {P_INR}{amount}\n"
      f"{P_CAL} Year: {year}\n"
      f"{P_PKG} Quantity: {qty}\n"
      f"{P_TIME} Time: {t}"
    )
    await _send_selling_log(msg)
  except Exception as ex: logger.error(f"Purchase Log Err: {ex}")

async def log_digital_sale(uid, product_name, price):
  try:
    t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = (
      f"{P_STORE} {P_ROCKET} <b>NEW DIGITAL PRODUCT SALE</b> {P_PARTY}\n\n"
      f"{P_ID} User ID: {_spoiler(uid)}\n"
      f"{P_DOC} Product: {html.escape(str(product_name))}\n"
      f"{P_MONEY} Total Paid: ₹{price}\n"
      f"{P_TIME} Time: {t}"
    )
    await _send_selling_log(msg)
  except Exception as ex: logger.error(f"Digital Sale Log Err: {ex}")

# ================= MULTI-GATEWAY API INTEGRATION =================
def get_active_gateway_config():
  active = get_setting('active_gateway', 'fampaygateway')
  if active == 'sgvip':
    url = get_setting('sgvip_api_url', 'https://sgvip.site')
    key = get_setting('sgvip_api_key', '')
    name = 'SGVIP Gateway'
    enabled = payment_enabled('sgvip_enabled')
  else:
    url = get_setting('fampaygateway_api_url', 'https://fampaygateway.site')
    key = get_setting('fampaygateway_api_key', '')
    name = 'FamPayGateway'
    enabled = payment_enabled('fampaygateway_enabled')
  
  base = url.strip().rstrip('/')
  for suffix in ('/api/create-order', '/api/verify-order.php', '/api'):
    if base.lower().endswith(suffix): base = base[:-len(suffix)].rstrip('/')
  return name, base, key, enabled

def gateway_request(path, api_key, payload=None, query=None):
  _, base, _ = get_active_gateway_config()
  if not base: raise ValueError('Gateway API URL not set.')
  url = base + path
  headers = {'Accept': 'application/json', 'User-Agent': 'AccStoreBot/1.0'}
  if api_key: headers['X-Api-Key'] = api_key
  data = None
  method = 'GET'
  if payload is not None:
    data = json.dumps(payload).encode('utf-8')
    headers['Content-Type'] = 'application/json'
    method = 'POST'
  if query: url += '?' + urlencode(query)
  
  req = urllib.request.Request(url, data=data, headers=headers, method=method)
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE
  with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
    raw = response.read().decode('utf-8', errors='replace')
  return json.loads(raw)

async def create_gateway_order(amount, uid, customer_name='Telegram User'):
  name, base, api_key = get_active_gateway_config()
  if not base or not api_key: raise ValueError(f'Admin has not configured API URL & Key for {name}.')
  payload = {'amount': float(amount), 'customer_name': str(customer_name)[:80]}
  result = await asyncio.to_thread(gateway_request, '/api/create-order', api_key, payload, None)
  if result.get('status') != 'success' or not isinstance(result.get('data'), dict):
    raise ValueError(str(result.get('message') or result.get('error') or 'Gateway order creation failed.'))
  return result['data']

async def verify_gateway_order(order_id):
  _, _, api_key = get_active_gateway_config()
  result = await asyncio.to_thread(gateway_request, '/api/verify-order.php', api_key, None, {'api_key': api_key, 'order_id': order_id})
  if isinstance(result.get('data'), dict):
    merged = dict(result)
    merged.update(result['data'])
    return merged
  return result

async def credit_gateway_deposit(dep_id, verified):
  row = cur.execute("SELECT user_id, amount, gateway_order_id, status, method_name FROM deposits WHERE id=?", (int(dep_id),)).fetchone()
  if not row or row[3] != 'pending': return False
  uid, expected_amount, order_id, _, method_name = row
  paid_amount = verified.get('amount', verified.get('payable_amount'))
  try: paid_amount = float(paid_amount)
  except: return False
  if abs(paid_amount - float(expected_amount)) > 0.01: return False
  utr = str(verified.get('utr') or order_id).strip()
  
  async with get_user_lock(int(uid)):
    try:
      cur.execute('BEGIN IMMEDIATE')
      cur.execute("UPDATE users SET balance=balance+?, total_deposited=total_deposited+? WHERE user_id=?", (int(expected_amount), int(expected_amount), int(uid)))
      cur.execute("UPDATE deposits SET status='approved', utr=? WHERE id=? AND status='pending'", (utr, int(dep_id)))
      db.commit()
    except Exception:
      db.rollback()
      return False
      
  await log_primary_deposit_success(uid, int(expected_amount), method_name, utr)
  try:
    bal = cur.execute('SELECT balance FROM users WHERE user_id=?', (int(uid),)).fetchone()
    await bot.send_message(int(uid), custom_emoji_text(
      f"{P_YES} <b>Payment Verified Automatically!</b>\n\n"
      f"{P_MONEY} Amount Added: <b>₹{int(expected_amount)}</b>\n"
      f"UTR/ID: <code>{html.escape(utr)}</code>\n"
      f"New Balance: <b>₹{bal[0] if bal else int(expected_amount)}</b>"
    ))
  except Exception: pass
  return True

async def poll_gateway_deposit(dep_id, order_id, chat_id=None, message_id=None):
  started = time.time()
  while time.time() - started < 330:
    row = cur.execute('SELECT status FROM deposits WHERE id=?', (int(dep_id),)).fetchone()
    if not row or row[0] != 'pending': return
    try:
      result = await verify_gateway_order(order_id)
      status = str(result.get('status') or '').lower()
      if status in ('success', 'paid', 'completed'):
        if await credit_gateway_deposit(dep_id, result):
          if chat_id and message_id:
            try:
              await bot.edit_message(chat_id, message_id, custom_emoji_text(f"{P_YES} <b>Payment Successful! Wallet Credited!</b>"), buttons=None)
            except Exception: pass
          return
    except Exception: pass
    await asyncio.sleep(4)

# ================= PERSISTENT MENU & BOT HANDLERS =================
def get_persistent_menu(uid):
  rows = [
    [Button.inline("Store", data="cb_store", style="primary"), Button.inline("Add Funds", data="cb_addfunds", style="success")],
    [Button.inline("Profile", data="cb_profile", style="primary"), Button.inline("Orders History", data="cb_orders", style="primary")],
    [Button.inline("Refill", data="cb_refill", style="primary"), Button.inline("Redeem Code", data="redeem_start", style="success")],
    [Button.url(" Selling Logs", "https://t.me/TG_ACCOUNT_070_BOT", style="primary")],
    [Button.inline("Support", data="cb_support", style="primary")],
    [Button.inline("Updates", data="cb_updates", style="primary")]
  ]
  return rows

async def send_main_menu(event, uid):
  ensure_user(uid)
  row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
  bal = row[0] if row else 0
  try:
    sender = await event.get_sender()
    user_name = html.escape(sender.first_name) if sender and sender.first_name else "User"
  except Exception: user_name = "User"

  msg = (
    f"{P_DIAMOND} <b>AccStore Marketplace</b> {P_STAR}\n"
    f"{P_TG} <b>Welcome back,</b> {P_ACC} <b>{user_name}</b> {P_LIGHTNING}\n\n"
    f"<blockquote>"
    f"{P_MONEY} <b>Wallet Balance:</b> {P_INR}{bal:.2f}\n"
    f"{P_ID} <b>Account UID:</b> <code>{uid}</code> {P_YES}\n"
    f"{P_CROWN} <b>Membership:</b> <b>Premium Member</b> {P_YES}"
    f"</blockquote>"
  )
  img_path = "23593.jpg"
  buttons = get_persistent_menu(uid)

  if isinstance(event, events.CallbackQuery.Event):
    try: await event.delete()
    except Exception: pass
    if os.path.exists(img_path): await bot.send_file(uid, img_path, caption=custom_emoji_text(msg), buttons=buttons, parse_mode='html')
    else: await bot.send_message(uid, custom_emoji_text(msg), buttons=buttons, parse_mode='html')
  else:
    if os.path.exists(img_path): await event.respond(file=img_path, message=custom_emoji_text(msg), buttons=buttons, parse_mode='html')
    else: await event.respond(custom_emoji_text(msg), buttons=buttons, parse_mode='html')

async def deposit_menu(event):
  name, base, key, enabled = get_active_gateway_config()
  if not enabled:
    return await event.edit(custom_emoji_text(f"{P_WARN} <b>Payment Gateway ({name}) is disabled.</b>"), buttons=[[Button.inline('Back', 'back_main', style='primary')]])
  
  uid = event.sender_id
  deposit_input[uid] = {'step': 'amount_keypad', 'method': name, 'amount': ''}
  await show_deposit_amount_keypad(event, uid)

async def show_deposit_amount_keypad(event, uid):
  state = deposit_input.get(uid, {})
  amount = state.get('amount', '') or '0'
  name, _, _, _ = get_active_gateway_config()
  msg = (
    f"{P_CARD} <b>{name} Automatic Payment</b>\n\n"
    f"{P_MONEY} <b>Amount: ₹{html.escape(amount)}</b>\n\n"
    f"Select amount using buttons below:"
  )
  btns = [
    [Button.inline('1', 'dep_key|1', style='success'), Button.inline('2', 'dep_key|2', style='success'), Button.inline('3', 'dep_key|3', style='success')],
    [Button.inline('4', 'dep_key|4', style='success'), Button.inline('5', 'dep_key|5', style='success'), Button.inline('6', 'dep_key|6', style='success')],
    [Button.inline('7', 'dep_key|7', style='success'), Button.inline('8', 'dep_key|8', style='success'), Button.inline('9', 'dep_key|9', style='success')],
    [Button.inline('Delete', 'dep_key_del', style='danger'), Button.inline('0', 'dep_key|0', style='success'), Button.inline('Confirm', 'dep_key_confirm', style='success')],
    [Button.inline('Back', 'back_main', style='primary')]
  ]
  await event.edit(custom_emoji_text(msg), buttons=btns)

async def generate_deposit_qr(event, uid):
  state = deposit_input.get(uid)
  if not state: return
  try: amount = int(state.get('amount') or 0)
  except: amount = 0
  if amount < 10: return await event.answer('Minimum deposit is ₹10.', alert=True)
  
  name, base, key, enabled = get_active_gateway_config()
  if not enabled: return await event.answer('Gateway disabled.', alert=True)
  
  try:
    sender = await bot.get_entity(uid)
    customer_name = getattr(sender, 'first_name', None) or 'Telegram User'
    order = await create_gateway_order(amount, uid, customer_name)
    order_id = str(order['order_id'])
    checkout_url = str(order.get('checkout_url') or '')
    
    cur.execute("INSERT INTO deposits (user_id, amount, method_name, status, gateway_order_id) VALUES (?,?,?,?,?)", (uid, amount, name, 'pending', order_id))
    db.commit()
    dep_id = cur.lastrowid
    
    caption = (
      f"{P_CARD} <b>{name} Payment Checkout</b>\n\n"
      f"{P_MONEY} Amount: <b>₹{amount}</b>\n"
      f"Order ID: <code>{order_id}</code>\n\n"
      f"Click 'Pay Now' to complete your payment. Wallet will be credited automatically!"
    )
    buttons = [[Button.url('Pay Now', checkout_url, style='success')], [Button.inline('Cancel', 'cancel_action', style='danger')]]
    sent = await bot.send_message(uid, custom_emoji_text(caption), buttons=buttons, parse_mode='html')
    deposit_input.pop(uid, None)
    asyncio.create_task(poll_gateway_deposit(dep_id, order_id, uid, sent.id))
    try: await event.delete()
    except Exception: pass
  except Exception as ex:
    logger.error(f"Gateway order err: {ex}")
    await event.answer(f"Error creating order: {ex}", alert=True)

# ================= ADMIN PANEL CONFIG =================
async def admin_panel_handler(event):
  uid = event.sender_id
  if not is_admin(uid): return
  
  status_text = "Bot is ON" if is_bot_online() else "Bot is OFF"
  active_gw = get_setting('active_gateway', 'fampaygateway').upper()
  
  btns = [
    [Button.inline(f"Status: {status_text}", "adm_togglebot", style="primary")],
    [Button.inline(f"Active Gateway: {active_gw}", "adm_switch_gateway", style="success")],
    [Button.inline("Configure Gateways (FamPay & SGVIP)", "adm_paymentmethods", style="primary")],
    [Button.inline("Statistics", "adm_stats", style="primary"), Button.inline("Broadcast", "adm_bcast", style="primary")],
    [Button.inline("Back to Main", "back_main", style="primary")]
  ]
  await bot.send_message(event.chat_id, custom_emoji_text(f"{P_PC} <b>ADMIN DASHBOARD (MULTI-GATEWAY)</b>"), buttons=btns)

async def admin_actions(event):
  data_full = event.data.decode()
  if not data_full.startswith("adm_"): return
  uid = event.sender_id
  action = data_full[4:]
  chat = event.chat_id

  if action == "adminmain":
    class FakeEvent: chat_id = chat; sender_id = uid
    return await admin_panel_handler(FakeEvent())

  elif action == "togglebot":
    new_status = 'off' if is_bot_online() else 'on'
    set_setting('bot_status', new_status)
    await event.answer(f"Bot turned {new_status.upper()}", alert=True)
    class FakeEvent: chat_id = chat; sender_id = uid
    return await admin_panel_handler(FakeEvent())

  elif action == "switch_gateway":
    current = get_setting('active_gateway', 'fampaygateway')
    new_gw = 'sgvip' if current == 'fampaygateway' else 'fampaygateway'
    set_setting('active_gateway', new_gw)
    await event.answer(f"Active Gateway switched to {new_gw.upper()}", alert=True)
    class FakeEvent: chat_id = chat; sender_id = uid
    return await admin_panel_handler(FakeEvent())

  elif action == "paymentmethods":
    f_en = payment_enabled('fampaygateway_enabled')
    s_en = payment_enabled('sgvip_enabled')
    msg = (
      f"{P_CARD} <b>Multi-Gateway Settings</b>\n\n"
      f"1. <b>FamPayGateway (fampaygateway.site):</b> {'ENABLED' if f_en else 'DISABLED'}\n"
      f"2. <b>SGVIP Gateway (sgvip.site):</b> {'ENABLED' if s_en else 'DISABLED'}\n\n"
      f"Select which gateway setting to edit:"
    )
    btns = [
      [Button.inline(f"FamPay: {'ON' if f_en else 'OFF'}", "adm_tog_fam", style="success" if not f_en else "danger")],
      [Button.inline("Set FamPay API Key", "adm_set_fam_key", style="primary")],
      [Button.inline(f"SGVIP: {'ON' if s_en else 'OFF'}", "adm_tog_sg", style="success" if not s_en else "danger")],
      [Button.inline("Set SGVIP API Key", "adm_set_sg_key", style="primary")],
      [Button.inline("Back", "adm_adminmain", style="primary")]
    ]
    return await event.edit(custom_emoji_text(msg), buttons=btns)

  elif action == "tog_fam":
    set_setting('fampaygateway_enabled', 'off' if payment_enabled('fampaygateway_enabled') else 'on')
    return await admin_actions(type('obj', (object,), {'data': b'adm_paymentmethods', 'sender_id': uid, 'chat_id': chat}))

  elif action == "tog_sg":
    set_setting('sgvip_enabled', 'off' if payment_enabled('sgvip_enabled') else 'on')
    return await admin_actions(type('obj', (object,), {'data': b'adm_paymentmethods', 'sender_id': uid, 'chat_id': chat}))

  async with bot.conversation(chat, timeout=300) as conv:
    if action == "set_fam_key":
      await conv.send_message("Send FamPay API Key for `fampaygateway.site`:")
      resp = await conv.get_response()
      if resp.text:
        set_setting('fampaygateway_api_key', resp.text.strip())
        await conv.send_message("FamPay API Key updated successfully!")
    elif action == "set_sg_key":
      await conv.send_message("Send API Key for `sgvip.site`:")
      resp = await conv.get_response()
      if resp.text:
        set_setting('sgvip_api_key', resp.text.strip())
        await conv.send_message("SGVIP API Key updated successfully!")

@bot.on(events.NewMessage(pattern=r"(?i)^/admin(?:@\w+)?\s*$"))
async def handle_admin_command(e):
  if not is_admin(e.sender_id): return await e.respond("Unauthorized.")
  await admin_panel_handler(e)

@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def handle_start(e):
  try:
    uid = e.sender_id
    if not uid: return
    ensure_user(uid)
    if not is_bot_online() and not is_admin(uid):
      return await e.respond("Bot is under maintenance.")
    await send_main_menu(e, uid)
  except Exception as ex: logger.error(f"Start Err: {ex}")

@bot.on(events.CallbackQuery)
async def handle_callback_query(e):
  try:
    uid = e.sender_id
    ensure_user(uid)
    data = e.data.decode("utf-8", errors="replace") if isinstance(e.data, bytes) else str(e.data)

    if data == "cb_store": await e.respond("Store section is active. Choose categories or items.")
    elif data == "cb_addfunds": await deposit_menu(e)
    elif data == "cb_profile": await e.respond(f"Profile: UID <code>{uid}</code>")
    elif data == "back_main": await send_main_menu(e, uid)
    elif data == "cancel_action":
      deposit_input.pop(uid, None)
      await e.edit("Action cancelled.")
    elif data.startswith("dep_key|"):
      state = deposit_input.get(uid)
      if state:
        state['amount'] += data.split("|")[1]
        await show_deposit_amount_keypad(e, uid)
    elif data == "dep_key_del":
      state = deposit_input.get(uid)
      if state:
        state['amount'] = state['amount'][:-1]
        await show_deposit_amount_keypad(e, uid)
    elif data == "dep_key_confirm":
      await generate_deposit_qr(e, uid)
    elif data.startswith("adm_") and is_admin(uid):
      await admin_actions(e)
  except Exception as ex: logger.error(f"Callback error: {ex}")

async def main():
  print("MULTI-GATEWAY BOT STARTED SUCCESSFULLY")
  pending = cur.execute("SELECT id, gateway_order_id, user_id FROM deposits WHERE status='pending' AND COALESCE(gateway_order_id,'') != ''").fetchall()
  for dep_id, order_id, uid in pending:
    asyncio.create_task(poll_gateway_deposit(dep_id, order_id, uid, None))
  await bot.run_until_disconnected()

if __name__ == '__main__':
  bot.start(bot_token=BOT_TOKEN)
  loop = asyncio.get_event_loop()
  loop.run_until_complete(main())
