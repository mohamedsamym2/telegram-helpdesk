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
    get_ticket_details, update_ticket_last_message_id
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

# Regex to detect phone numbers in message text
PHONE_REGEX = re.compile(r'(?:\+?20|0020)?0?1[0125]\d{8}\b|\b(?:\+?\d{1,4}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')

class TelegramBot:
    def __init__(self, broadcast_callback: Optional[Callable[[Dict[str, Any]], Any]] = None):
        self.broadcast = broadcast_callback
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.token = ""
        self.bot_info: Dict[str, Any] = {}
        self.client: Optional[httpx.AsyncClient] = None

    def get_token(self) -> str:
        token = get_setting("telegram_bot_token", "")
        if not token:
            token = os.getenv("TELEGRAM_BOT_TOKEN", "8825356962:AAH-IwHd43WBNSp34un-RVoQD2w3IjKwlbs").strip()
        return token.strip()

    def set_token(self, token: str):
        self.token = token.strip()
        set_setting("telegram_bot_token", self.token)

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
            text = (
                f"✅ <b>Ticket {ticket_num} has been resolved and closed!</b>\n\n"
                f"Thank you for contacting IT Support. If you experience any further issues, "
                f"feel free to send a message anytime to open a new ticket. Have a great day! 🌸"
            )
            await self.send_message(user_id, text, reply_markup={"remove_keyboard": True})
        elif new_status == "in_progress":
            text = (
                f"⚙️ <b>Ticket {ticket_num} Update:</b>\n\n"
                f"Our IT Support team has started working on your request."
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
            active_ticket = get_active_ticket_for_user(user_id)
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
                    f"✅ <b>Thank you {html.escape(first_name)}!</b>\nYour phone number <code>{phone_number}</code> has been saved to ticket <b>{active_ticket['ticket_number']}</b>.",
                    reply_markup={"remove_keyboard": True},
                    reply_to_message_id=msg_id
                )
                if self.broadcast:
                    await self.broadcast({
                        "type": "ticket_updated",
                        "ticket_id": active_ticket["id"],
                        "phone_number": phone_number
                    })
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

        # 3. Detect phone number automatically if user wrote it in the text
        extracted_phone = ""
        match = PHONE_REGEX.search(text)
        if match:
            extracted_phone = match.group(0).strip()

        # 4. Handle commands like /start in private chat
        bot_username = self.bot_info.get("username", "IT_Support3_bot")
        text = text.replace(f"@{bot_username}", "").strip()

        if text.strip() == "/start" and not is_group:
            welcome_text = (
                f"Hello {html.escape(first_name)}! 👋 Welcome to IT Support.\n\n"
                f"Please describe your technical issue here (you can also attach photos/screenshots), and an IT Support ticket will be opened for you immediately! 🎫"
            )
            await self.send_message(chat_id, welcome_text)
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
            if extracted_phone and not active_ticket.get("phone_number"):
                update_ticket_phone(active_ticket["id"], extracted_phone)

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
            ack_text = f"📥 Your message has been added to ticket <b>{active_ticket['ticket_number']}</b>."
            await self.send_message(chat_id, ack_text, reply_to_message_id=msg_id)
            
            if self.broadcast:
                await self.broadcast({
                    "type": "new_message",
                    "ticket_id": active_ticket["id"],
                    "ticket_number": active_ticket["ticket_number"],
                    "message": msg_record
                })
        else:
            # Create NEW Ticket
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
                last_message_id=msg_id
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

            if is_group:
                # Group reply: Acknowledge ticket and prompt user to start bot in private
                phone_note = f"\n📱 <i>Phone detected: {extracted_phone}</i>" if extracted_phone else ""
                confirm_msg = (
                    f"🎫 <b>Ticket #{new_ticket['ticket_number']} Created</b> for {user_mention}!\n"
                    f"Our IT Support team has logged your issue and will reply to you <b>directly in private chat</b>.{phone_note}\n\n"
                    f"👇 <i>Please make sure to start the bot in private to receive our response:</i>"
                )
                inline_markup = {
                    "inline_keyboard": [
                        [{"text": "💬 Open Private Chat with Support", "url": f"https://t.me/{bot_username}"}]
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
                phone_extra = f"\n📱 Phone saved: {extracted_phone}" if extracted_phone else "\n\n👇 <i>Tap below to share your phone number:</i>"
                confirm_msg = (
                    f"Hello {html.escape(first_name)}! 👋\n\n"
                    f"Ticket <b>#{new_ticket['ticket_number']}</b> has been created for your issue. 🎫\n"
                    f"Our IT Support team will reply to you here shortly.{phone_extra}"
                )
                markup = None if extracted_phone else reply_keyboard
                await self.send_message(chat_id, confirm_msg, reply_markup=markup, reply_to_message_id=msg_id)
            
            if self.broadcast:
                ticket_full = get_ticket_details(new_ticket["id"])
                await self.broadcast({
                    "type": "new_ticket",
                    "ticket": ticket_full
                })

    async def _poll_loop(self):
        offset = 0
        logger.info("Long polling loop started.")
        while self.is_running:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                params = {"offset": offset, "timeout": 25, "allowed_updates": ["message", "edited_message"]}
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
