"""
Telegram Bot for copying VK posts.
Main bot implementation with command handlers.
"""

import logging
import json
from datetime import datetime
from typing import Optional
from telegram import Update, Bot, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from config import Config
from vk_client import VKClient
from media_handler import MediaHandler

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log",
    filemode="a"
)
logger = logging.getLogger(__name__)

# Conversation states
SELECT_GROUP, SELECT_START_DATE, SELECT_END_DATE, SELECT_COUNT = range(4)

# Mini App URL - URL вашего развёрнутого Mini App
MINI_APP_URL = "https://hOvannes7.github.io/telegram-vk-bot/webapp/"


class VKTelegramBot:
    """Main bot class."""
    
    def __init__(self):
        self.vk_client = VKClient()
        self.bot: Optional[Bot] = None
        self.media_handler: Optional[MediaHandler] = None
        self.user_data = {}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        # Create keyboard with Mini App button
        keyboard = [
            [KeyboardButton("📋 Открыть панель управления", web_app=WebAppInfo(url=MINI_APP_URL))]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "👋 <b>Добро пожаловать в VK to Telegram Bot!</b>\n\n"
            "Этот бот копирует посты из сообществ ВКонтакте в Telegram.\n\n"
            "<b>Команды:</b>\n"
            "/copy - Начать копирование постов\n"
            "/webapp - Открыть панель управления\n"
            "/help - Показать справку\n"
            "/status - Проверить статус бота\n\n"
            "Нажмите кнопку ниже, чтобы открыть удобную панель управления! 🎉",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    
    async def webapp_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /webapp command - open Mini App."""
        keyboard = [
            [KeyboardButton("📋 Открыть панель управления", web_app=WebAppInfo(url=MINI_APP_URL))]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "📱 <b>Панель управления</b>\n\n"
            "Нажмите кнопку ниже, чтобы открыть веб-интерфейс для настройки копирования постов.",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    
    async def handle_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle data received from Mini App."""
        try:
            data = json.loads(update.message.web_app_data.data)
            
            if data.get('action') != 'copy_posts':
                return
            
            # Extract data
            group_id = data.get('groupId')
            start_date_str = data.get('startDate')
            end_date_str = data.get('endDate')
            count = data.get('count', 10)
            
            if not all([group_id, start_date_str, end_date_str]):
                await update.message.reply_text("❌ Неверные данные от Mini App")
                return
            
            # Parse dates
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            end_date = end_date.replace(hour=23, minute=59, second=59)
            
            chat_id = update.effective_chat.id
            
            await update.message.reply_text(
                f"🚀 <b>Запуск процесса копирования...</b>\n\n"
                f"Группа: <code>{group_id}</code>\n"
                f"Период: <code>{start_date_str}</code> - <code>{end_date_str}</code>\n"
                f"Постов: <code>{count}</code>\n\n"
                f"⏳ Пожалуйста, подождите...",
                parse_mode=ParseMode.HTML
            )
            
            # Get posts from VK
            posts = self.vk_client.get_posts(
                group_id=group_id,
                start_date=start_date,
                end_date=end_date,
                count=count
            )
            
            if not posts:
                await update.message.reply_text(
                    "⚠️ Посты не найдены за указанный период."
                )
                return
            
            # Reverse for chronological order
            posts.reverse()
            
            await update.message.reply_text(
                f"📊 Найдено <code>{len(posts)}</code> постов. Начинаю копирование..."
            )
            
            # Initialize media handler
            self.media_handler = MediaHandler(self.bot)
            
            # Copy each post
            success_count = 0
            for i, post in enumerate(posts, 1):
                try:
                    media = self.vk_client.get_post_media(post)
                    
                    # Create caption
                    caption = None
                    if media["text"]:
                        caption = media["text"][:1000]
                    
                    # Send media
                    if await self.media_handler.send_message_with_media(
                        chat_id=chat_id,
                        media=media,
                        caption=caption
                    ):
                        success_count += 1
                    
                    # Progress update every 5 posts
                    if i % 5 == 0 or i == len(posts):
                        await update.message.reply_text(
                            f"📈 Прогресс: {i}/{len(posts)} - скопировано {success_count} постов"
                        )
                        
                except Exception as e:
                    logger.error(f"Error copying post {i}: {e}")
                    continue
            
            await update.message.reply_text(
                f"✅ <b>Копирование завершено!</b>\n\n"
                f"Успешно скопировано: <code>{success_count}/{len(posts)}</code> постов",
                parse_mode=ParseMode.HTML
            )
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON from Mini App")
        except Exception as e:
            logger.error(f"Error handling Mini App data: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        await update.message.reply_text(
            "📖 <b>Help Guide</b>\n\n"
            "<b>How to use:</b>\n"
            "1. Use /copy to start the copying process\n"
            "2. Enter the VK group name or ID\n"
            "3. Specify the start date (YYYY-MM-DD)\n"
            "4. Specify the end date (YYYY-MM-DD)\n"
            "5. Enter the number of posts to copy\n\n"
            "<b>Notes:</b>\n"
            "- All media (photos, videos, documents) will be copied\n"
            "- Posts are copied in chronological order\n"
            "- Large batches may take some time",
            parse_mode=ParseMode.HTML
        )
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        await update.message.reply_text(
            "✅ <b>Bot Status: Online</b>\n\n"
            f"VK API Version: {Config.VK_API_VERSION}\n"
            f"Ready to copy posts!",
            parse_mode=ParseMode.HTML
        )
    
    async def copy_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start the copy process."""
        await update.message.reply_text(
            "📋 <b>Copy VK Posts</b>\n\n"
            "Please enter the VK group name or ID.\n"
            "Examples: <code>durov</code>, <code>123456</code>",
            parse_mode=ParseMode.HTML
        )
        return SELECT_GROUP
    
    async def group_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process selected group."""
        group_name = update.message.text.strip()
        context.user_data["group_name"] = group_name
        
        # Validate group
        await update.message.reply_text(f"⏳ Checking group: <code>{group_name}</code>...")
        
        group_id = self.vk_client.get_group_id(group_name)
        if not group_id:
            await update.message.reply_text(
                "❌ Group not found. Please try again or enter /cancel to abort.",
                parse_mode=ParseMode.HTML
            )
            return SELECT_GROUP
        
        context.user_data["group_id"] = group_id
        await update.message.reply_text(
            f"✅ Group found!\n\n"
            f"Now enter the <b>start date</b> (YYYY-MM-DD):\n"
            f"Example: <code>2024-01-01</code>",
            parse_mode=ParseMode.HTML
        )
        return SELECT_START_DATE
    
    async def start_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process start date."""
        date_str = update.message.text.strip()
        
        try:
            start_date = datetime.strptime(date_str, "%Y-%m-%d")
            context.user_data["start_date"] = start_date
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid date format. Please use YYYY-MM-DD format.\n"
                "Example: <code>2024-01-01</code>",
                parse_mode=ParseMode.HTML
            )
            return SELECT_START_DATE
        
        await update.message.reply_text(
            f"✅ Start date: <code>{date_str}</code>\n\n"
            f"Now enter the <b>end date</b> (YYYY-MM-DD):\n"
            f"Example: <code>2024-12-31</code>",
            parse_mode=ParseMode.HTML
        )
        return SELECT_END_DATE
    
    async def end_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process end date."""
        date_str = update.message.text.strip()
        start_date = context.user_data.get("start_date")

        try:
            end_date = datetime.strptime(date_str, "%Y-%m-%d")
            # Set end_date to end of day (23:59:59)
            end_date = end_date.replace(hour=23, minute=59, second=59)
            
            if start_date and end_date < start_date:
                await update.message.reply_text(
                    "❌ End date must be after start date.\n"
                    "Please try again.",
                    parse_mode=ParseMode.HTML
                )
                return SELECT_END_DATE
            
            context.user_data["end_date"] = end_date
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid date format. Please use YYYY-MM-DD format.",
                parse_mode=ParseMode.HTML
            )
            return SELECT_END_DATE
        
        await update.message.reply_text(
            f"✅ End date: <code>{date_str}</code>\n\n"
            f"How many posts to copy? (1-100)\n"
            f"Default: <code>50</code>",
            parse_mode=ParseMode.HTML
        )
        return SELECT_COUNT
    
    async def count_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process post count and start copying."""
        try:
            count = int(update.message.text.strip())
            if count < 1 or count > 100:
                raise ValueError()
        except ValueError:
            count = 50  # Default
        
        context.user_data["count"] = count
        
        # Start copying
        await self.process_copy(update, context)
        
        return ConversationHandler.END
    
    async def process_copy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process the actual copy operation."""
        group_id = context.user_data["group_id"]
        group_name = context.user_data["group_name"]
        start_date = context.user_data["start_date"]
        end_date = context.user_data["end_date"]
        count = context.user_data["count"]
        
        # Use TARGET_CHAT_ID from config if set, otherwise use current chat
        chat_id = Config.TARGET_CHAT_ID or str(update.effective_chat.id)

        await update.message.reply_text(
            f"🚀 <b>Starting copy process...</b>\n\n"
            f"Group: <code>{group_name}</code>\n"
            f"Period: <code>{start_date.strftime('%Y-%m-%d')}</code> - "
            f"<code>{end_date.strftime('%Y-%m-%d')}</code>\n"
            f"Max posts: <code>{count}</code>\n"
            f"Target chat: <code>{chat_id}</code>\n\n"
            f"⏳ This may take a while...",
            parse_mode=ParseMode.HTML
        )

        # Get posts from VK
        posts = self.vk_client.get_posts(
            group_id=group_id,
            start_date=start_date,
            end_date=end_date,
            count=count
        )
        
        if not posts:
            await update.message.reply_text(
                "⚠️ No posts found for the specified period.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Reverse to post in chronological order
        posts.reverse()
        
        await update.message.reply_text(
            f"📊 Found <code>{len(posts)}</code> posts. Starting to copy...",
            parse_mode=ParseMode.HTML
        )
        
        # Initialize media handler
        self.media_handler = MediaHandler(self.bot)
        
        # Copy each post
        success_count = 0
        for i, post in enumerate(posts, 1):
            progress = f"({i}/{len(posts)})"
            
            try:
                media = self.vk_client.get_post_media(post)
                
                # Create caption
                caption = None
                if media["text"]:
                    caption = media["text"][:1000]  # Telegram caption limit
                
                # Send media
                if await self.media_handler.send_message_with_media(
                    chat_id=chat_id,
                    media=media,
                    caption=caption
                ):
                    success_count += 1
                
                # Progress update every 10 posts
                if i % 10 == 0 or i == len(posts):
                    await update.message.reply_text(
                        f"📈 Progress: {progress} - {success_count}/{i} posts copied"
                    )
                
            except Exception as e:
                logger.error(f"Error copying post {i}: {e}")
                continue
        
        await update.message.reply_text(
            f"✅ <b>Copy completed!</b>\n\n"
            f"Successfully copied: <code>{success_count}/{len(posts)}</code> posts",
            parse_mode=ParseMode.HTML
        )
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the current operation."""
        await update.message.reply_text(
            "❌ Operation cancelled.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        logger.error(f"Update {update} caused error: {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                f"❌ An error occurred: <code>{context.error}</code>",
                parse_mode=ParseMode.HTML
            )
    
    def run(self) -> None:
        """Run the bot."""
        # Validate config
        Config.validate()

        # Create application
        application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        self.bot = application.bot

        # Add conversation handler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("copy", self.copy_start)],
            states={
                SELECT_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.group_selected)],
                SELECT_START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.start_date_selected)],
                SELECT_END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.end_date_selected)],
                SELECT_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.count_selected)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

        # Add handlers
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("webapp", self.webapp_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("status", self.status))
        application.add_handler(CommandHandler("cancel", self.cancel))
        
        # Handler for Mini App data
        application.add_handler(MessageHandler(
            filters.StatusUpdate.WEB_APP_DATA, 
            self.handle_webapp_data
        ))

        # Error handler
        application.add_error_handler(self.error_handler)

        logger.info("Bot started!")
        print("🤖 Bot is running... Press Ctrl+C to stop.")

        # Run the bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point."""
    bot = VKTelegramBot()
    bot.run()


if __name__ == "__main__":
    main()
