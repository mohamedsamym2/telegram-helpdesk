import asyncio
import html
import logging
import os
import re
import httpx
from typing import Optional, Callable, Dict, Any
from database import (
    get_setting, set_setting, get_active_ticket_for_user,
    create_ticket, update_ticket_phone, add_message, update_ticket_status,
    get_ticket_details, update_ticket_last_message_id,
    save_user_profile, get_user_profile, get_latest_phone_for_user,
    save_ticket_rating, assign_ticket, match_faq, increment_faq_helpful, get_faq
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telegram_bot")

import sys
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Eastern Arabic numerals to standard ASCII translation
ARABIC_TO_ENGLISH_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def extract_phone_number(raw_text: str) -> Optional[str]:
    """
    Detects and normalizes phone numbers (Egyptian mobile numbers and international numbers),
    supporting both ASCII and Eastern Arabic numerals.
    """
    if not raw_text:
        return None
    # 1. Normalize Eastern Arabic digits
    norm = raw_text.translate(ARABIC_TO_ENGLISH_DIGITS)
    
    # 2. Egyptian mobile pattern (010, 011, 012, 015 + 8 digits)
    eg_pattern = re.compile(r'(?:(?:\+|00)?20\s*|0)?(1[0125][\s\-\.]*(?:\d[\s\-\.]*){8})\b')
    m = eg_pattern.search(norm)
    if m:
        digits = re.sub(r'\D', '', m.group(0))
        if digits.startswith('20') and len(digits) >= 12:
            digits = '0' + digits[2:]
        elif not digits.startswith('0') and len(digits) == 10:
            digits = '0' + digits
        if len(digits) == 11 and digits.startswith(('010', '011', '012', '015')):
            return digits

    # 3. General international phone pattern (e.g. +966..., +1..., etc.)
    intl_pattern = re.compile(r'(\+?\d{1,4}[\s\-\.]?\(?\d{2,4}\)?[\s\-\.]?\d{3,4}[\s\-\.]?\d{3,4})')
    m_intl = intl_pattern.search(norm)
    if m_intl:
        cleaned = re.sub(r'[\s\-\(\)\.]', '', m_intl.group(1))
        if len(cleaned) >= 9:
            return cleaned

    return None

def detect_ticket_category(text: str) -> str:
    """Auto-detects IT ticket category from user text keywords."""
    lower = (text or "").lower()
    if any(k in lower for k in ["طابعة", "طابعه", "برنتر", "printer", "طباعة", "حبر", "toner"]):
        return "Printers"
    if any(k in lower for k in ["نت", "انترنت", "واي فاي", "وايفاي", "wifi", "شبكة", "راوتر", "سويتش", "ip", "dns", "network"]):
        return "Network"
    if any(k in lower for k in ["ايميل", "بريد", "إيميل", "email", "outlook", "باسورد", "كلمة سر", "password", "حساب", "account"]):
        return "Email & Accounts"
    if any(k in lower for k in ["برنامج", "سيستم", "system", "software", "anydesk", "ويندوز", "windows", "office", "اوفيس", "excel"]):
        return "Software"
    if any(k in lower for k in ["شاشة", "كيبورد", "ماوس", "رام", "هارد", "جهاز", "كيسة", "hardware", "screen", "laptop", "كمبيوتر"]):
        return "Hardware"
    if any(k in lower for k in ["erp", "قاعدة بيانات", "سيرفر", "database", "sql", "sap"]):
        return "ERP / Database"
    return "General"

class TelegramBot:
    def __init__(self, broadcast_callback: Optional[Callable[[Dict[str, Any]], Any]] = None):
        self.broadcast = broadcast_callback
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.token = ""
        self.bot_info: Dict[str, Any] = {}
        self.client: Optional[httpx.AsyncClient] = None
        self.pending_faq_messages: Dict[int, Dict[str, Any]] = {}

    def get_token(self) -> str:
        token = get_setting("telegram_bot_token", "")
        if not token:
            token = os.getenv("TELEGRAM_BOT_TOKEN", "8825356962:AAH-IwHd43WBNSp34un-RVoQD2w3IjKwlbs").strip()
        return token.strip()

    def set_token(self, token: str):
        self.token = token.strip()
        set_setting("telegram_bot_token", self.token)

    def get_it_alert_group_id(self) -> str:
        gid = get_setting("it_alert_group_id", "")
        if not gid:
            gid = os.getenv("IT_ALERT_GROUP_ID", "").strip()
        return gid.strip()

    def set_it_alert_group_id(self, group_id: str):
        set_setting("it_alert_group_id", group_id.strip())

    async def notify_it_team_new_ticket(self, ticket: Dict[str, Any]):
        group_id = self.get_it_alert_group_id()
        if not group_id:
            return
            
        ticket_num = ticket.get("ticket_number", f"TK-{ticket['id']}")
        user_name = ticket.get("user_name", "User")
        username_str = f"@{ticket['username']}" if ticket.get("username") else "No username"
        phone = ticket.get("phone_number") or "Not registered"
        category = ticket.get("category", "General")
        priority = (ticket.get("priority") or "medium").upper()
        subject = ticket.get("subject", "No description")
        sla_deadline = ticket.get("sla_deadline", "Not specified")
        
        priority_emojis = {
            "CRITICAL": "🔴 Critical (2h)",
            "HIGH": "🟠 High (6h)",
            "MEDIUM": "🟡 Medium (24h)",
            "LOW": "🟢 Low (48h)"
        }
        prio_display = priority_emojis.get(priority, f"🟡 {priority}")

        alert_text = (
            f"🚨 <b>New IT Support Ticket #{ticket_num}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Requester:</b> {html.escape(user_name)} ({username_str})\n"
            f"📱 <b>Phone:</b> <code>{phone}</code>\n"
            f"🏷️ <b>Category:</b> {html.escape(category)}\n"
            f"⚡ <b>Priority:</b> {prio_display}\n"
            f"📝 <b>Issue:</b> {html.escape(subject)}\n"
            f"⏱️ <b>SLA Resolution Target:</b> <code>{sla_deadline}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>Click the button below to claim this ticket:</i>"
        )
        
        claim_keyboard = {
            "inline_keyboard": [
                [{"text": "🙋‍♂️ Claim Ticket", "callback_data": f"claim:{ticket['id']}"}]
            ]
        }
        try:
            chat_id_int = int(group_id)
            await self.send_message(chat_id_int, alert_text, reply_markup=claim_keyboard)
        except Exception as e:
            logger.error(f"Failed to send ticket alert to IT group {group_id}: {e}")

    async def send_sla_alert(self, ticket: Dict[str, Any], alert_type: str, remaining_mins: Optional[float] = None) -> bool:
        group_id = self.get_it_alert_group_id()
        if not group_id:
            return False
            
        ticket_num = ticket.get("ticket_number", f"TK-{ticket['id']}")
        user_name = ticket.get("user_name", "User")
        priority = (ticket.get("priority") or "medium").upper()
        category = ticket.get("category", "General")
        assigned = ticket.get("assigned_to") or "Unassigned"
        
        if alert_type == "warning":
            mins_val = int(remaining_mins or 0)
            text = (
                f"⚠️ <b>SLA Warning: Ticket Near Breach!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎫 <b>Ticket:</b> #{ticket_num}\n"
                f"👤 <b>Requester:</b> {html.escape(user_name)}\n"
                f"🏷️ <b>Category:</b> {html.escape(category)}\n"
                f"⚡ <b>Priority:</b> {priority}\n"
                f"⏳ <b>Time Remaining:</b> <b>{mins_val} minutes left!</b>\n"
                f"👨‍💻 <b>Assigned To:</b> {html.escape(assigned)}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Please expedite resolution before the SLA response time is breached."
            )
        else: # breached
            deadline = ticket.get("sla_deadline", "Not specified")
            text = (
                f"🚨 <b>URGENT: SLA Deadline Breached!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎫 <b>Ticket:</b> #{ticket_num}\n"
                f"👤 <b>Requester:</b> {html.escape(user_name)}\n"
                f"🏷️ <b>Category:</b> {html.escape(category)}\n"
                f"⚡ <b>Priority:</b> {priority}\n"
                f"⏰ <b>Target Deadline:</b> <code>{deadline}</code>\n"
                f"👨‍💻 <b>Assigned To:</b> {html.escape(assigned)}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ This ticket has exceeded its resolution SLA window! Immediate action required."
            )
        try:
            chat_id_int = int(group_id)
            return await self.send_message(chat_id_int, text)
        except Exception as e:
            logger.error(f"Failed to send SLA alert to group {group_id}: {e}")
            return False

    async def verify_token(self, token: Optional[str] = None) -> Dict[str, Any]:
        tok = token or self.get_token()
        if not tok:
            return {"ok": False, "error": "No bot token provided"}
        
        url = f"https://api.telegram.org/bot{tok}/getMe"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                data = res.json()
                if data.get("ok"):
                    self.bot_info = data.get("result", {})
                    return {"ok": True, "bot": self.bot_info}
                else:
                    return {"ok": False, "error": data.get("description", "Invalid bot token")}
        except Exception as e:
            return {"ok": False, "error": f"Failed to connect to Telegram: {str(e)}"}

    async def start(self):
        self.token = self.get_token()
        if not self.token:
            logger.warning("No bot token set yet. Bot will not poll until token is configured.")
            return

        verification = await self.verify_token(self.token)
        if not verification.get("ok"):
            logger.error(f"Cannot start bot: {verification.get('error')}")
            return

        self.is_running = True
        self.client = httpx.AsyncClient(timeout=35.0)
        self.task = asyncio.create_task(self._poll_loop())
        logger.info(f"Bot @{self.bot_info.get('username')} started polling successfully.")

    async def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.client:
            await self.client.aclose()
        logger.info("Bot stopped.")

    async def restart(self, new_token: Optional[str] = None):
        await self.stop()
        if new_token:
            self.set_token(new_token)
        await self.start()

    async def _download_telegram_file(self, file_id: str) -> str:
        """Download a photo/document from Telegram and return local relative URL"""
        try:
            get_file_url = f"https://api.telegram.org/bot{self.token}/getFile?file_id={file_id}"
            res = await self.client.get(get_file_url)
            data = res.json()
            if not data.get("ok"):
                return ""
            file_path = data["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            
            local_filename = f"{file_id[:16]}_{os.path.basename(file_path)}"
            local_path = os.path.join(UPLOAD_DIR, local_filename)
            
            file_res = await self.client.get(download_url)
            if file_res.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(file_res.content)
                return f"/static/uploads/{local_filename}"
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
        return ""

    async def send_message(self, chat_id: int, text: str, 
                           reply_markup: Optional[Dict] = None, 
                           reply_to_message_id: Optional[int] = None) -> bool:
        if not self.token:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
            
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code != 200:
                    logger.error(f"Failed to send telegram msg to {chat_id}: {res.text}")
                    return False
                return True
        except Exception as e:
            logger.error(f"Error sending message to {chat_id}: {e}")
            return False

    async def notify_ticket_status(self, ticket: Dict[str, Any], new_status: str):
        user_id = ticket["telegram_user_id"]
        ticket_num = ticket["ticket_number"]
        
        # Send status update privately to the user
        if new_status in ("resolved", "closed"):
            survey_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "1 ⭐", "callback_data": f"rate:{ticket['id']}:1"},
                        {"text": "2 ⭐", "callback_data": f"rate:{ticket['id']}:2"},
                        {"text": "3 ⭐", "callback_data": f"rate:{ticket['id']}:3"},
                        {"text": "4 ⭐", "callback_data": f"rate:{ticket['id']}:4"},
                        {"text": "5 ⭐", "callback_data": f"rate:{ticket['id']}:5"},
                    ]
                ]
            }
            text = (
                f"✅ <b>Ticket {ticket_num} has been resolved!</b>\n\n"
                f"Thank you for contacting IT Support. 🙏\n\n"
                f"🌟 <b>Customer Satisfaction Survey:</b>\n"
                f"How would you rate the IT support you received?\n"
                f"<i>(1 = Poor, 3 = Good, 5 = Excellent)</i>"
            )
            await self.send_message(user_id, text, reply_markup=survey_keyboard)
        elif new_status == "in_progress":
            text = (
                f"⚙️ <b>Ticket Update {ticket_num}:</b>\n\n"
                f"The IT Support team has started working on your request."
            )
            await self.send_message(user_id, text)

    async def send_agent_reply(self, ticket: Dict[str, Any], reply_text: str, agent_name: str = "IT Support") -> Dict[str, Any]:
        """
        Sends reply PRIVATELY to the user who opened the ticket (telegram_user_id).
        Does NOT send into the group.
        If the user has not started the bot in private yet, sends a prompt in the group.
        """
        user_id = ticket["telegram_user_id"]
        group_chat_id = ticket["telegram_chat_id"]
        is_from_group = ticket.get("chat_type") in ("group", "supergroup")
        ticket_num = ticket["ticket_number"]
        
        safe_reply = html.escape(reply_text)
        safe_agent = html.escape(agent_name)

        msg_text = (
            f"💬 <b>{safe_agent} Reply (Ticket {ticket_num}):</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{safe_reply}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>You can reply directly to this message to continue the conversation.</i>"
        )
        
        # Send direct message to the user
        delivered = await self.send_message(user_id, msg_text)
        
        if not delivered and is_from_group:
            # User hasn't started the bot in private yet (Telegram bot API restriction)
            bot_username = self.bot_info.get("username", "IT_Support3_bot")
            user_mention = f"@{ticket['username']}" if ticket.get("username") else html.escape(ticket.get("user_name", "User"))
            last_msg_id = ticket.get("last_message_id") or None
            
            prompt_text = (
                f"⚠️ <b>Action Required:</b> {user_mention}, the IT Support team tried to reply to your ticket <b>{ticket_num}</b> in private, "
                f"but you haven't started @{bot_username} in private chat yet!\n\n"
                f"👉 Please click the button below and press <b>START</b> to receive your response."
            )
            inline_keyboard = {
                "inline_keyboard": [
                    [{"text": "💬 Open Private Chat to Receive Reply", "url": f"https://t.me/{bot_username}"}]
                ]
            }
            await self.send_message(group_chat_id, prompt_text, reply_markup=inline_keyboard, reply_to_message_id=last_msg_id)
            return {"ok": False, "delivered": False, "reason": "user_not_started_private"}
            
        return {"ok": delivered, "delivered": delivered}

    async def request_user_phone(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends an interactive prompt with Share Contact button to the user on Telegram.
        """
        user_id = ticket["telegram_user_id"]
        ticket_num = ticket["ticket_number"]
        first_name = (ticket.get("user_name") or "User").split()[0]
        
        reply_keyboard = {
            "keyboard": [
                [{"text": "📱 Share Phone Number", "request_contact": True}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }
        
        prompt_text = (
            f"📞 <b>Hello {html.escape(first_name)}!</b>\n\n"
            f"The IT Support team needs your phone number to contact you regarding ticket <b>#{ticket_num}</b>.\n\n"
            f"👇 Please tap the button below to share your contact number with one click, or type it here in a reply:"
        )
        delivered = await self.send_message(user_id, prompt_text, reply_markup=reply_keyboard)
        if not delivered and ticket.get("chat_type") in ("group", "supergroup"):
            bot_username = self.bot_info.get("username", "IT_Support3_bot")
            user_mention = f"@{ticket['username']}" if ticket.get("username") else html.escape(ticket.get("user_name", "User"))
            group_msg = (
                f"📞 {user_mention}, the IT Support team is waiting for your phone number to proceed with ticket <b>#{ticket_num}</b>.\n"
                f"👉 Please open private chat to share your phone number: https://t.me/{bot_username}"
            )
            await self.send_message(ticket["telegram_chat_id"], group_msg)
            
        return {"ok": delivered, "delivered": delivered}

    async def _handle_update(self, update: Dict[str, Any]):
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return

        from_user = msg.get("from", {})
        chat = msg.get("chat", {})
        
        # Ignore messages sent by bots
        if from_user.get("is_bot"):
            return

        user_id = from_user.get("id")
        chat_id = chat.get("id")
        chat_type = chat.get("type", "private")
        chat_title = chat.get("title", "")
        is_group = chat_type in ("group", "supergroup")
        
        first_name = from_user.get("first_name", "")
        last_name = from_user.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip() or "Unknown User"
        username = from_user.get("username", "")

        msg_id = msg.get("message_id", 0)
        text = msg.get("text", "").strip()
        contact = msg.get("contact")
        photos = msg.get("photo")

        # 1. Handle Contact Sharing (Private chats)
        if contact:
            phone_number = contact.get("phone_number", "")
            if phone_number.startswith("+"):
                phone_number = phone_number[1:]
            if phone_number.startswith("20") and len(phone_number) == 12:
                phone_number = "0" + phone_number[2:]
                
            active_ticket = get_active_ticket_for_user(user_id)
            save_user_profile(user_id, full_name, username, phone_number)
            
            if active_ticket:
                update_ticket_phone(active_ticket["id"], phone_number)
                update_ticket_last_message_id(active_ticket["id"], msg_id)
                add_message(
                    ticket_id=active_ticket["id"],
                    sender_type="user",
                    sender_name=full_name,
                    text=f"📱 Phone number shared: {phone_number}",
                    telegram_message_id=msg_id
                )
                await self.send_message(
                    chat_id,
                    f"✅ <b>Thank you {html.escape(first_name)}!</b>\nYour phone number <code>{phone_number}</code> has been saved to ticket <b>#{active_ticket['ticket_number']}</b>.",
                    reply_markup={"remove_keyboard": True},
                    reply_to_message_id=msg_id
                )
                if self.broadcast:
                    await self.broadcast({
                        "type": "ticket_updated",
                        "ticket_id": active_ticket["id"],
                        "phone_number": phone_number
                    })
            else:
                await self.send_message(
                    chat_id,
                    f"✅ <b>Welcome {html.escape(first_name)}!</b>\nYour phone number <code>{phone_number}</code> has been saved. You can describe your issue anytime to open a support ticket! 🎫",
                    reply_markup={"remove_keyboard": True},
                    reply_to_message_id=msg_id
                )
            return

        # 2. Extract media if any
        media_url = ""
        media_type = "text"
        if photos:
            largest_photo = photos[-1]
            file_id = largest_photo["file_id"]
            media_url = await self._download_telegram_file(file_id)
            media_type = "photo"
            if not text:
                text = msg.get("caption", "[Attached Screenshot/Image]")

        if not text and not media_url:
            return

        # 3. Detect phone number automatically if user wrote it in the text (Arabic or English digits)
        extracted_phone = extract_phone_number(text)
        if extracted_phone:
            save_user_profile(user_id, full_name, username, extracted_phone)

        # 4. Handle commands like /start in private chat
        bot_username = self.bot_info.get("username", "IT_Support3_bot")
        text = text.replace(f"@{bot_username}", "").strip()

        if text.strip() == "/start" and not is_group:
            reply_keyboard = {
                "keyboard": [
                    [{"text": "📱 Share Phone Number", "request_contact": True}]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
            active_ticket = get_active_ticket_for_user(user_id)
            if active_ticket:
                p_num = active_ticket.get("phone_number")
                if p_num:
                    welcome_text = (
                        f"Welcome back {html.escape(first_name)}! 👋\n\n"
                        f"You have an open ticket: <b>#{active_ticket['ticket_number']}</b>.\n"
                        f"📱 Registered phone: <code>{p_num}</code>\n\n"
                        f"The IT Support team is working on your request and will reply shortly."
                    )
                    await self.send_message(chat_id, welcome_text, reply_markup={"remove_keyboard": True})
                else:
                    welcome_text = (
                        f"Welcome back {html.escape(first_name)}! 👋\n\n"
                        f"You have an open ticket: <b>#{active_ticket['ticket_number']}</b>.\n\n"
                        f"📲 <b>Please share your phone number so we can reach you quickly:</b>\n"
                        f"👇 Tap the button below to share your phone number, or type it here."
                    )
                    await self.send_message(chat_id, welcome_text, reply_markup=reply_keyboard)
            else:
                user_prof = get_user_profile(user_id)
                saved_phone = user_prof.get("phone_number") if user_prof else ""
                if saved_phone:
                    welcome_text = (
                        f"Welcome {html.escape(first_name)}! 👋 Welcome to IT Support.\n\n"
                        f"📱 Registered phone: <code>{saved_phone}</code>\n\n"
                        f"Please type your issue details here (or attach screenshots) and an IT ticket will be opened immediately! 🎫"
                    )
                    await self.send_message(chat_id, welcome_text, reply_markup={"remove_keyboard": True})
                else:
                    welcome_text = (
                        f"Welcome {html.escape(first_name)}! 👋 Welcome to IT Support.\n\n"
                        f"Please type your issue details here anytime to open a support ticket! 🎫\n\n"
                        f"📲 You can also tap the button below to share and save your phone number for contact:"
                    )
                    await self.send_message(chat_id, welcome_text, reply_keyboard=reply_keyboard)
            return
        elif text.startswith("/start "):
            text = text[7:].strip()
        elif text.startswith("/ticket "):
            text = text[8:].strip()
        elif text.strip() == "/ticket":
            text = "Technical support request"

        # 5. Check active open ticket for this user
        # While the ticket is open/in_progress: append messages to the open ticket thread.
        # Once closed/resolved: get_active_ticket_for_user returns None, so a brand new ticket is created!
        active_ticket = get_active_ticket_for_user(user_id)

        if active_ticket:
            # Update last message ID
            update_ticket_last_message_id(active_ticket["id"], msg_id)
            
            # If a phone number was detected in this message
            phone_acknowledged = False
            if extracted_phone:
                prev_phone = active_ticket.get("phone_number")
                if not prev_phone or prev_phone != extracted_phone:
                    update_ticket_phone(active_ticket["id"], extracted_phone)
                    active_ticket["phone_number"] = extracted_phone
                    phone_acknowledged = True
                    if self.broadcast:
                        await self.broadcast({
                            "type": "ticket_updated",
                            "ticket_id": active_ticket["id"],
                            "phone_number": extracted_phone
                        })

            # Append message to existing open ticket
            msg_record = add_message(
                ticket_id=active_ticket["id"],
                sender_type="user",
                sender_name=full_name,
                text=text,
                media_type=media_type,
                media_url=media_url,
                telegram_message_id=msg_id
            )
            
            # Send acknowledgement
            if phone_acknowledged and len(text.strip()) <= 25:
                ack_text = f"✅ Your phone number <code>{extracted_phone}</code> has been updated for ticket <b>#{active_ticket['ticket_number']}</b>!"
                await self.send_message(chat_id, ack_text, reply_markup={"remove_keyboard": True}, reply_to_message_id=msg_id)
            else:
                ack_text = f"📥 Your message has been received and added to ticket <b>#{active_ticket['ticket_number']}</b>."
                await self.send_message(chat_id, ack_text, reply_to_message_id=msg_id)
            
            if self.broadcast:
                await self.broadcast({
                    "type": "new_message",
                    "ticket_id": active_ticket["id"],
                    "ticket_number": active_ticket["ticket_number"],
                    "message": msg_record
                })
        else:
            # 5. Check Knowledge Base / FAQ match before opening a new ticket in private chat
            matched_faq = match_faq(text) if (not is_group and not text.startswith("/")) else None
            if matched_faq:
                # Store pending info
                self.pending_faq_messages[user_id] = {
                    "text": text,
                    "msg_id": msg_id,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "full_name": full_name,
                    "username": username,
                    "extracted_phone": extracted_phone,
                    "media_type": media_type,
                    "media_url": media_url,
                    "chat_type": chat_type,
                    "chat_title": chat_title
                }
                
                faq_text = (
                    f"💡 <b>Suggested Resolution: {html.escape(matched_faq['question'])}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{html.escape(matched_faq['answer'])}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"❓ <b>Did this solve your issue?</b>"
                )
                faq_keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Yes, issue solved!", "callback_data": f"faq_solved:{matched_faq['id']}"},
                            {"text": "🎫 Open ticket with technician", "callback_data": f"faq_open:{matched_faq['id']}"}
                        ]
                    ]
                }
                await self.send_message(chat_id, faq_text, reply_markup=faq_keyboard, reply_to_message_id=msg_id)
                return

            # Clear pending FAQ message if user sent another regular message
            self.pending_faq_messages.pop(user_id, None)

            # Create NEW Ticket with auto-detected category
            category = detect_ticket_category(text)
            subject = (text[:60] + "...") if len(text) > 60 else text
            new_ticket = create_ticket(
                telegram_chat_id=chat_id,
                telegram_user_id=user_id,
                user_name=full_name,
                username=username,
                phone_number=extracted_phone,
                chat_type=chat_type,
                chat_title=chat_title,
                subject=subject,
                last_message_id=msg_id,
                category=category
            )
            
            msg_record = add_message(
                ticket_id=new_ticket["id"],
                sender_type="user",
                sender_name=full_name,
                text=text,
                media_type=media_type,
                media_url=media_url,
                telegram_message_id=msg_id
            )
            
            bot_username = self.bot_info.get("username", "IT_Support3_bot")
            user_mention = f"@{username}" if username else html.escape(first_name)
            phone_saved = new_ticket.get("phone_number")

            if is_group:
                # Group reply: Acknowledge ticket and prompt user to start bot in private
                phone_note = f"\n📱 <i>Phone: {phone_saved}</i>" if phone_saved else "\n📲 <i>Please share your phone number so we can contact you.</i>"
                confirm_msg = (
                    f"🎫 <b>New ticket #{new_ticket['ticket_number']} opened</b> for {user_mention}!\n"
                    f"🏷️ Category: <code>{html.escape(category)}</code>\n"
                    f"The IT Support team will assist you via private chat.{phone_note}\n\n"
                    f"👇 <i>Please start private chat with the bot to register your phone and receive direct updates:</i>"
                )
                inline_markup = {
                    "inline_keyboard": [
                        [{"text": "💬 Open Private Chat & Share Phone", "url": f"https://t.me/{bot_username}"}]
                    ]
                }
                await self.send_message(chat_id, confirm_msg, reply_markup=inline_markup, reply_to_message_id=msg_id)
            else:
                # Private chat reply
                reply_keyboard = {
                    "keyboard": [
                        [{"text": "📱 Share Phone Number", "request_contact": True}]
                    ],
                    "resize_keyboard": True,
                    "one_time_keyboard": True
                }
                if phone_saved:
                    confirm_msg = (
                        f"Welcome {html.escape(first_name)}! 👋\n\n"
                        f"🎫 Ticket <b>#{new_ticket['ticket_number']}</b> has been opened successfully.\n"
                        f"🏷️ Category: <code>{html.escape(category)}</code>\n"
                        f"📱 Registered phone: <code>{phone_saved}</code>\n\n"
                        f"The IT Support team is working on your request and will reply shortly."
                    )
                    markup = {"remove_keyboard": True}
                else:
                    confirm_msg = (
                        f"Welcome {html.escape(first_name)}! 👋\n\n"
                        f"🎫 Ticket <b>#{new_ticket['ticket_number']}</b> has been opened successfully.\n"
                        f"🏷️ Category: <code>{html.escape(category)}</code>\n\n"
                        f"📲 <b>Please share your phone number so we can reach you quickly:</b>\n"
                        f"👇 Tap the button below to share your phone number, or type it here in a message:"
                    )
                    markup = reply_keyboard
                await self.send_message(chat_id, confirm_msg, reply_markup=markup, reply_to_message_id=msg_id)
            
            # Send alert to IT team group with Claim Ticket button!
            await self.notify_it_team_new_ticket(new_ticket)

            if self.broadcast:
                ticket_full = get_ticket_details(new_ticket["id"])
                await self.broadcast({
                    "type": "new_ticket",
                    "ticket": ticket_full
                })

    async def _handle_callback_query(self, cb: Dict[str, Any]):
        cb_id = cb.get("id")
        data = cb.get("data", "")
        from_user = cb.get("from", {})
        msg = cb.get("message", {})
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        message_id = msg.get("message_id")

        if data.startswith("rate:"):
            # format: rate:{ticket_id}:{rating_1_to_5}
            parts = data.split(":")
            if len(parts) == 3:
                try:
                    ticket_id = int(parts[1])
                    rating = int(parts[2])

                    # Save rating in database
                    updated_ticket = save_ticket_rating(ticket_id, rating)
                    stars_str = "⭐" * rating

                    # 1. Answer Telegram callback query (shows quick feedback banner)
                    ans_url = f"https://api.telegram.org/bot{self.token}/answerCallbackQuery"
                    await self.client.post(ans_url, json={
                        "callback_query_id": cb_id,
                        "text": f"Thank you! Your rating ({stars_str}) has been recorded. 🌟",
                        "show_alert": False
                    })

                    # 2. Edit original message to show confirmed stars and remove buttons
                    ticket_num = updated_ticket.get("ticket_number", f"TK-{ticket_id}") if updated_ticket else f"TK-{ticket_id}"
                    thank_you_text = (
                        f"✅ <b>Ticket {ticket_num} Resolved & Closed</b>\n\n"
                        f"🙏 <b>Thank you for your rating!</b>\n"
                        f"Your rating: <b>{stars_str}</b> ({rating} of 5)\n\n"
                        f"We are always glad to assist you. Have a great day! 🌸"
                    )
                    edit_url = f"https://api.telegram.org/bot{self.token}/editMessageText"
                    await self.client.post(edit_url, json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": thank_you_text,
                        "parse_mode": "HTML"
                    })

                    # 3. Add system message in ticket log
                    add_message(
                        ticket_id=ticket_id,
                        sender_type="user",
                        sender_name=from_user.get("first_name", "User"),
                        text=f"🌟 Customer Satisfaction Rating: {stars_str} ({rating}/5)"
                    )

                    # 4. Broadcast live update to Dashboard via WebSocket
                    if self.broadcast:
                        await self.broadcast({
                            "type": "ticket_rated",
                            "ticket_id": ticket_id,
                            "ticket_number": ticket_num,
                            "rating": rating,
                            "rated_at": updated_ticket.get("rated_at") if updated_ticket else ""
                        })
                except Exception as e:
                    logger.error(f"Error handling rating callback query: {e}", exc_info=True)

        elif data.startswith("claim:"):
            # format: claim:{ticket_id}
            parts = data.split(":")
            if len(parts) == 2:
                try:
                    ticket_id = int(parts[1])
                    t = get_ticket_details(ticket_id)
                    if not t:
                        await self.client.post(f"https://api.telegram.org/bot{self.token}/answerCallbackQuery", json={
                            "callback_query_id": cb_id,
                            "text": "⚠️ Ticket not found!",
                            "show_alert": True
                        })
                        return

                    if t.get("assigned_to"):
                        await self.client.post(f"https://api.telegram.org/bot{self.token}/answerCallbackQuery", json={
                            "callback_query_id": cb_id,
                            "text": f"⚠️ Ticket is already claimed by: {t['assigned_to']}",
                            "show_alert": True
                        })
                        return

                    # Resolve technician name
                    first_name = from_user.get("first_name", "")
                    last_name = from_user.get("last_name", "")
                    staff_name = f"{first_name} {last_name}".strip()
                    if not staff_name:
                        staff_name = f"@{from_user.get('username', 'Technician')}"
                    staff_name = staff_name.strip()

                    # Assign ticket and set in_progress
                    updated = assign_ticket(ticket_id, staff_name)
                    update_ticket_status(ticket_id, "in_progress")
                    
                    # Answer callback
                    await self.client.post(f"https://api.telegram.org/bot{self.token}/answerCallbackQuery", json={
                        "callback_query_id": cb_id,
                        "text": f"✅ Ticket #{t['ticket_number']} claimed successfully!",
                        "show_alert": False
                    })

                    # Edit group message to show claimed state and remove button
                    orig_text = msg.get("text", "")
                    new_text = orig_text + f"\n\n✅ <b>Claimed by:</b> {html.escape(staff_name)} (In Progress ⚙️)"
                    await self.client.post(f"https://api.telegram.org/bot{self.token}/editMessageText", json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": new_text,
                        "parse_mode": "HTML"
                    })

                    # Add system audit log
                    add_message(
                        ticket_id=ticket_id,
                        sender_type="agent",
                        sender_name=staff_name,
                        text=f"🙋‍♂️ Ticket claimed from Telegram by: {staff_name}"
                    )

                    # Broadcast to dashboard
                    if self.broadcast:
                        await self.broadcast({
                            "type": "ticket_assigned",
                            "ticket_id": ticket_id,
                            "assigned_to": staff_name,
                            "ticket": get_ticket_details(ticket_id)
                        })
                        await self.broadcast({
                            "type": "status_changed",
                            "ticket_id": ticket_id,
                            "status": "in_progress"
                        })
                except Exception as e:
                    logger.error(f"Error handling claim callback query: {e}", exc_info=True)

        elif data.startswith("faq_solved:"):
            # format: faq_solved:{faq_id}
            parts = data.split(":")
            if len(parts) == 2:
                try:
                    faq_id = int(parts[1])
                    increment_faq_helpful(faq_id)
                    await self.client.post(f"https://api.telegram.org/bot{self.token}/answerCallbackQuery", json={
                        "callback_query_id": cb_id,
                        "text": "Glad we could help! 🌟",
                        "show_alert": False
                    })
                    solved_text = (
                        "✅ <b>Great! The issue is resolved.</b>\n\n"
                        "If you need any further assistance, the IT Support team is always here to help. 🙏"
                    )
                    await self.client.post(f"https://api.telegram.org/bot{self.token}/editMessageText", json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": solved_text,
                        "parse_mode": "HTML"
                    })
                    self.pending_faq_messages.pop(from_user.get("id"), None)
                except Exception as e:
                    logger.error(f"Error handling faq_solved callback: {e}", exc_info=True)

        elif data.startswith("faq_open:"):
            # format: faq_open:{faq_id}
            parts = data.split(":")
            if len(parts) == 2:
                try:
                    u_id = from_user.get("id")
                    pending = self.pending_faq_messages.pop(u_id, None)
                    
                    await self.client.post(f"https://api.telegram.org/bot{self.token}/answerCallbackQuery", json={
                        "callback_query_id": cb_id,
                        "text": "Opening an IT support ticket for you... 🎫",
                        "show_alert": False
                    })
                    
                    p_text = pending.get("text", "IT Support Request") if pending else "IT Support Request"
                    p_msg_id = pending.get("msg_id", message_id) if pending else message_id
                    p_user_name = pending.get("full_name") if pending else (from_user.get("first_name", "User"))
                    p_username = pending.get("username") if pending else from_user.get("username", "")
                    p_phone = pending.get("extracted_phone", "") if pending else ""
                    p_media_type = pending.get("media_type", "text") if pending else "text"
                    p_media_url = pending.get("media_url", "") if pending else ""
                    
                    category = detect_ticket_category(p_text)
                    subject = (p_text[:60] + "...") if len(p_text) > 60 else p_text
                    
                    new_ticket = create_ticket(
                        telegram_chat_id=chat_id,
                        telegram_user_id=u_id,
                        user_name=p_user_name,
                        username=p_username,
                        phone_number=p_phone,
                        chat_type="private",
                        chat_title="",
                        subject=subject,
                        last_message_id=p_msg_id,
                        category=category
                    )
                    
                    add_message(
                        ticket_id=new_ticket["id"],
                        sender_type="user",
                        sender_name=p_user_name,
                        text=p_text,
                        media_type=p_media_type,
                        media_url=p_media_url,
                        telegram_message_id=p_msg_id
                    )
                    
                    open_msg = (
                        f"🎫 <b>Ticket #{new_ticket['ticket_number']} opened successfully!</b>\n\n"
                        f"🏷️ Category: <code>{html.escape(category)}</code>\n"
                        f"The IT Support team is working on your request and will reply shortly."
                    )
                    await self.client.post(f"https://api.telegram.org/bot{self.token}/editMessageText", json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": open_msg,
                        "parse_mode": "HTML"
                    })
                    
                    # Notify IT team group
                    await self.notify_it_team_new_ticket(new_ticket)
                    
                    if self.broadcast:
                        ticket_full = get_ticket_details(new_ticket["id"])
                        await self.broadcast({
                            "type": "new_ticket",
                            "ticket": ticket_full
                        })
                except Exception as e:
                    logger.error(f"Error handling faq_open callback: {e}", exc_info=True)

    async def _poll_loop(self):
        offset = 0
        logger.info("Long polling loop started.")
        while self.is_running:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                params = {"offset": offset, "timeout": 25, "allowed_updates": ["message", "edited_message", "callback_query"]}
                res = await self.client.get(url, params=params, timeout=35.0)
                
                if res.status_code == 200:
                    data = res.json()
                    if data.get("ok"):
                        updates = data.get("result", [])
                        for u in updates:
                            update_id = u["update_id"]
                            offset = max(offset, update_id + 1)
                            logger.info(f"Incoming update #{update_id}: {u}")
                            try:
                                if "callback_query" in u:
                                    await self._handle_callback_query(u["callback_query"])
                                elif "message" in u or "edited_message" in u:
                                    await self._handle_update(u)
                            except Exception as e:
                                logger.error(f"Error handling single update: {e}", exc_info=True)
                    else:
                        logger.error(f"Telegram error in getUpdates: {data.get('description')}")
                        await asyncio.sleep(5)
                elif res.status_code == 401 or res.status_code == 404:
                    logger.error("Invalid Bot Token! Polling stopped.")
                    self.is_running = False
                    break
                else:
                    logger.warning(f"Unexpected status from getUpdates: {res.status_code}")
                    await asyncio.sleep(3)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Network hiccup or timeout, wait briefly and retry
                await asyncio.sleep(2)
