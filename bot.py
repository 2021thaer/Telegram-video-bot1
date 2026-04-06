#!/usr/bin/env python3
"""
بوت تيليجرام لتحميل فيديوهات وسائل التواصل الاجتماعي
يدعم: يوتيوب، تيكتوك، فيسبوك، إنستغرام، تويتر/X، ريديت، فيميو، ديلي موشن، ساوند كلاود، وغيرها
"""

import os
import re
import asyncio
import logging
import glob
import time
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ChatAction

# ─── الإعدادات ───────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/tmp/telegram_video_bot_downloads")
MAX_TG_SIZE = 50 * 1024 * 1024  # 50 ميغابايت - حد تيليجرام
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ─── تهيئة السجل ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── أنماط الروابط المدعومة ─────────────────────────────────
URL_PATTERN = re.compile(
    r'https?://(?:www\.|m\.|vm\.|vt\.|)'
    r'(?:youtube\.com|youtu\.be|tiktok\.com|'
    r'facebook\.com|fb\.watch|fb\.com|'
    r'instagram\.com|'
    r'twitter\.com|x\.com|'
    r'reddit\.com|'
    r'vimeo\.com|'
    r'dailymotion\.com|dai\.ly|'
    r'twitch\.tv|'
    r'soundcloud\.com|'
    r'pinterest\.com|pin\.it|'
    r'linkedin\.com|'
    r'snapchat\.com|'
    r'tumblr\.com|'
    r'bilibili\.com|b23\.tv|'
    r'v\.redd\.it|'
    r'streamable\.com|'
    r'rumble\.com|'
    r'odysee\.com|'
    r'bitchute\.com|'
    r'loom\.com|'
    r'ted\.com|'
    r'ok\.ru|'
    r'vk\.com|'
    r'9gag\.com|'
    r'likee\.video|'
    r'triller\.co|'
    r'kwai\.com|'
    r'threads\.net|'
    r'[a-zA-Z0-9\-]+\.[a-zA-Z]{2,})'
    r'[^\s<>\"\']+'
)

# ─── المنصات المدعومة ────────────────────────────────────────
SUPPORTED_PLATFORMS = """
🎬 **المنصات المدعومة:**

▫️ يوتيوب (YouTube)
▫️ تيك توك (TikTok)
▫️ فيسبوك (Facebook)
▫️ إنستغرام (Instagram)
▫️ تويتر / إكس (Twitter/X)
▫️ ثريدز (Threads)
▫️ ريديت (Reddit)
▫️ فيميو (Vimeo)
▫️ ديلي موشن (Dailymotion)
▫️ تويتش (Twitch)
▫️ بنترست (Pinterest)
▫️ لينكد إن (LinkedIn)
▫️ سناب شات (Snapchat)
▫️ تمبلر (Tumblr)
▫️ بيلي بيلي (Bilibili)
▫️ ستريمابل (Streamable)
▫️ رمبل (Rumble)
▫️ أوديسي (Odysee)
▫️ لووم (Loom)
▫️ تيد (TED)
▫️ في كي (VK)
▫️ أوك (OK.ru)
▫️ وغيرها الكثير...
"""


def cleanup_downloads():
    """تنظيف ملفات التحميل القديمة"""
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
        try:
            if os.path.isfile(f) and (time.time() - os.path.getmtime(f)) > 300:
                os.remove(f)
        except Exception:
            pass


def extract_url(text: str) -> str | None:
    """استخراج الرابط من النص"""
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None


def get_platform_name(url: str) -> str:
    """تحديد اسم المنصة من الرابط"""
    platforms = {
        "youtube.com": "يوتيوب",
        "youtu.be": "يوتيوب",
        "tiktok.com": "تيك توك",
        "facebook.com": "فيسبوك",
        "fb.watch": "فيسبوك",
        "fb.com": "فيسبوك",
        "instagram.com": "إنستغرام",
        "twitter.com": "تويتر",
        "x.com": "إكس",
        "reddit.com": "ريديت",
        "v.redd.it": "ريديت",
        "vimeo.com": "فيميو",
        "dailymotion.com": "ديلي موشن",
        "dai.ly": "ديلي موشن",
        "twitch.tv": "تويتش",
        "pinterest.com": "بنترست",
        "pin.it": "بنترست",
        "linkedin.com": "لينكد إن",
        "snapchat.com": "سناب شات",
        "tumblr.com": "تمبلر",
        "bilibili.com": "بيلي بيلي",
        "b23.tv": "بيلي بيلي",
        "streamable.com": "ستريمابل",
        "rumble.com": "رمبل",
        "odysee.com": "أوديسي",
        "loom.com": "لووم",
        "ted.com": "تيد",
        "ok.ru": "أوك",
        "vk.com": "في كي",
        "threads.net": "ثريدز",
        "9gag.com": "9GAG",
        "likee.video": "لايكي",
        "kwai.com": "كواي",
    }
    url_lower = url.lower()
    for domain, name in platforms.items():
        if domain in url_lower:
            return name
    return "غير معروف"


async def download_video(url: str, chat_id: int) -> dict:
    """
    تحميل الفيديو باستخدام yt-dlp
    يعيد قاموس يحتوي على مسار الملف ومعلومات الفيديو
    """
    cleanup_downloads()
    
    output_template = os.path.join(DOWNLOAD_DIR, f"{chat_id}_%(id)s.%(ext)s")
    
    # المحاولة الأولى: جودة متوسطة تناسب حد تيليجرام
    ydl_opts = {
        "outtmpl": output_template,
        "format": (
            "bestvideo[filesize<50M][ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo[filesize<50M]+bestaudio/"
            "best[filesize<50M][ext=mp4]/"
            "best[filesize<50M]/"
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo[height<=720]+bestaudio/"
            "best[height<=720]/"
            "best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android"],
            }
        },
    }
    
    result = {"success": False, "file_path": None, "title": None, "duration": None, "error": None}
    
    try:
        loop = asyncio.get_event_loop()
        
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # yt-dlp قد يغير الامتداد بعد الدمج
                if not os.path.exists(filename):
                    base = os.path.splitext(filename)[0]
                    for ext in [".mp4", ".mkv", ".webm", ".mp3", ".m4a"]:
                        if os.path.exists(base + ext):
                            filename = base + ext
                            break
                return info, filename
        
        info, filename = await loop.run_in_executor(None, _download)
        
        if not os.path.exists(filename):
            # البحث عن أي ملف تم تحميله
            pattern = os.path.join(DOWNLOAD_DIR, f"{chat_id}_*")
            files = glob.glob(pattern)
            if files:
                filename = max(files, key=os.path.getctime)
            else:
                result["error"] = "لم يتم العثور على الملف بعد التحميل"
                return result
        
        file_size = os.path.getsize(filename)
        
        # إذا كان الملف أكبر من الحد، نحاول بجودة أقل
        if file_size > MAX_TG_SIZE:
            os.remove(filename)
            logger.info("الملف كبير جداً، جاري إعادة التحميل بجودة أقل...")
            
            ydl_opts["format"] = (
                "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=480]+bestaudio/"
                "best[height<=480]/"
                "worst[ext=mp4]/"
                "worst"
            )
            
            info, filename = await loop.run_in_executor(None, _download)
            
            if not os.path.exists(filename):
                pattern = os.path.join(DOWNLOAD_DIR, f"{chat_id}_*")
                files = glob.glob(pattern)
                if files:
                    filename = max(files, key=os.path.getctime)
            
            file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
            
            if file_size > MAX_TG_SIZE:
                os.remove(filename)
                result["error"] = (
                    f"حجم الفيديو ({file_size / (1024*1024):.1f} ميغابايت) أكبر من الحد المسموح "
                    f"في تيليجرام (50 ميغابايت) حتى بأقل جودة."
                )
                return result
        
        result["success"] = True
        result["file_path"] = filename
        result["title"] = info.get("title", "بدون عنوان")
        result["duration"] = info.get("duration")
        result["file_size"] = file_size
        
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Private video" in error_msg or "private" in error_msg.lower():
            result["error"] = "هذا الفيديو خاص ولا يمكن تحميله."
        elif "Sign in" in error_msg or "login" in error_msg.lower():
            result["error"] = "هذا الفيديو يتطلب تسجيل الدخول ولا يمكن تحميله."
        elif "not available" in error_msg.lower() or "unavailable" in error_msg.lower():
            result["error"] = "هذا الفيديو غير متاح أو تم حذفه."
        elif "Unsupported URL" in error_msg:
            result["error"] = "هذا الرابط غير مدعوم. تأكد من صحة الرابط."
        else:
            result["error"] = f"حدث خطأ أثناء التحميل: {error_msg[:200]}"
    except Exception as e:
        result["error"] = f"حدث خطأ غير متوقع: {str(e)[:200]}"
    
    return result


# ─── أوامر البوت ──────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    welcome_msg = (
        "مرحباً بك! 👋\n\n"
        "أنا بوت تحميل الفيديوهات من وسائل التواصل الاجتماعي.\n\n"
        "📌 **طريقة الاستخدام:**\n"
        "فقط أرسل لي رابط أي فيديو وسأقوم بتحميله وإرساله لك مباشرة!\n\n"
        "📋 **الأوامر المتاحة:**\n"
        "/start - بدء البوت\n"
        "/help - المساعدة\n"
        "/platforms - المنصات المدعومة\n\n"
        "🔗 جرّب الآن! أرسل لي رابط فيديو..."
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /help"""
    help_msg = (
        "📖 **دليل الاستخدام:**\n\n"
        "1️⃣ انسخ رابط الفيديو من أي منصة تواصل اجتماعي\n"
        "2️⃣ الصق الرابط وأرسله لي في المحادثة\n"
        "3️⃣ انتظر قليلاً حتى أقوم بتحميل الفيديو\n"
        "4️⃣ سأرسل لك الفيديو مباشرة كوسائط!\n\n"
        "⚠️ **ملاحظات:**\n"
        "• الحد الأقصى لحجم الفيديو هو 50 ميغابايت (حد تيليجرام)\n"
        "• إذا كان الفيديو كبيراً سأحاول تحميله بجودة أقل\n"
        "• بعض الفيديوهات الخاصة لا يمكن تحميلها\n"
        "• تأكد من أن الرابط صحيح وكامل\n\n"
        "💡 أرسل /platforms لعرض جميع المنصات المدعومة"
    )
    await update.message.reply_text(help_msg, parse_mode="Markdown")


async def platforms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /platforms"""
    await update.message.reply_text(SUPPORTED_PLATFORMS, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل الواردة"""
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    url = extract_url(text)
    
    if not url:
        await update.message.reply_text(
            "🔗 أرسل لي رابط فيديو من وسائل التواصل الاجتماعي وسأقوم بتحميله لك!\n\n"
            "💡 أرسل /help للمساعدة أو /platforms لعرض المنصات المدعومة."
        )
        return
    
    platform = get_platform_name(url)
    
    # إرسال رسالة انتظار
    status_msg = await update.message.reply_text(
        f"⏳ جاري تحميل الفيديو من {platform}...\n"
        "يرجى الانتظار قليلاً ⏬"
    )
    
    # إرسال حالة "يرسل فيديو"
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.UPLOAD_VIDEO,
    )
    
    # تحميل الفيديو
    result = await download_video(url, update.effective_chat.id)
    
    if result["success"]:
        file_path = result["file_path"]
        title = result["title"]
        duration = result.get("duration")
        file_size = result.get("file_size", 0)
        size_mb = file_size / (1024 * 1024)
        
        caption = f"📹 {title}\n📦 الحجم: {size_mb:.1f} ميغابايت"
        if duration:
            minutes = int(duration) // 60
            seconds = int(duration) % 60
            caption += f"\n⏱ المدة: {minutes}:{seconds:02d}"
        caption += f"\n🌐 المصدر: {platform}"
        
        try:
            # إرسال حالة رفع الفيديو
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.UPLOAD_VIDEO,
            )
            
            with open(file_path, "rb") as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=caption,
                    supports_streaming=True,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=60,
                )
            
            # حذف رسالة الانتظار
            await status_msg.delete()
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"خطأ في إرسال الفيديو: {error_str}")
            
            # محاولة إرسال كمستند إذا فشل كفيديو
            try:
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id,
                    action=ChatAction.UPLOAD_DOCUMENT,
                )
                with open(file_path, "rb") as doc_file:
                    await update.message.reply_document(
                        document=doc_file,
                        caption=caption,
                        read_timeout=120,
                        write_timeout=120,
                        connect_timeout=60,
                    )
                await status_msg.delete()
            except Exception as e2:
                logger.error(f"خطأ في إرسال المستند: {str(e2)}")
                await status_msg.edit_text(
                    "❌ حدث خطأ أثناء إرسال الفيديو.\n"
                    "قد يكون الملف كبيراً جداً. حاول مرة أخرى."
                )
        finally:
            # تنظيف الملف
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
    else:
        await status_msg.edit_text(f"❌ {result['error']}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء العامة"""
    logger.error(f"خطأ: {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "❌ حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى لاحقاً."
        )


def main():
    """تشغيل البوت"""
    logger.info("جاري تشغيل البوت...")
    
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(120)
        .write_timeout(120)
        .connect_timeout(60)
        .build()
    )
    
    # إضافة الأوامر
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("platforms", platforms_command))
    
    # معالجة الرسائل النصية
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # معالجة الأخطاء
    app.add_error_handler(error_handler)
    
    logger.info("البوت يعمل الآن! اضغط Ctrl+C للإيقاف.")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
