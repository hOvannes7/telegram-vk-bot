"""
Telegram Bot for copying VK posts.
Main bot implementation with command handlers.
"""

import logging
import json
from datetime import datetime
from typing import Optional
from pathlib import Path
from telegram import Update, Bot
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
SETCHAT_WAIT_ID = 100  # State for waiting chat ID

# File to store target chat ID
TARGET_CHAT_FILE = Path("target_chat.json")


class VKTelegramBot:
    """Main bot class."""

    def __init__(self):
        self.vk_client = VKClient()
        self.bot: Optional[Bot] = None
        self.media_handler: Optional[MediaHandler] = None
        self.user_data = {}
        self.setchat_user = None  # User ID waiting for chat ID input

    def _get_target_chat_id(self) -> Optional[str]:
        """Get target chat ID from file or config."""
        # First check if we have saved chat ID
        if TARGET_CHAT_FILE.exists():
            try:
                with open(TARGET_CHAT_FILE, 'r') as f:
                    data = json.load(f)
                    chat_id = data.get('chat_id')
                    if chat_id:
                        return str(chat_id)
            except Exception as e:
                logger.error(f"Error reading target chat file: {e}")
        
        # Fall back to config
        return Config.TARGET_CHAT_ID or None

    def _save_target_chat_id(self, chat_id: str) -> None:
        """Save target chat ID to file."""
        try:
            with open(TARGET_CHAT_FILE, 'w') as f:
                json.dump({'chat_id': chat_id}, f)
            logger.info(f"Saved target chat ID: {chat_id}")
        except Exception as e:
            logger.error(f"Error saving target chat ID: {e}")

    def _clear_target_chat_id(self) -> None:
        """Clear saved target chat ID."""
        try:
            if TARGET_CHAT_FILE.exists():
                TARGET_CHAT_FILE.unlink()
            logger.info("Cleared target chat ID")
        except Exception as e:
            logger.error(f"Error clearing target chat ID: {e}")

    async def set_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /setchat command - start waiting for chat ID."""
        # Only allow in private chat
        if update.effective_chat.type != 'private':
            await update.message.reply_text(
                "❌ Эта команда работает только в личном чате с ботом."
            )
            return ConversationHandler.END
        
        # Set user as waiting for chat ID
        self.setchat_user = update.effective_user.id
        
        # Get current target chat info
        current_chat_id = self._get_target_chat_id()
        current_info = f"Текущий чат: <code>{current_chat_id}</code>\n\n" if current_chat_id else ""
        
        await update.message.reply_text(
            f"📍 <b>Настройка целевого чата</b>\n\n"
            f"{current_info}"
            f"<b>Отправьте ID чата следующим сообщением.</b>\n\n"
            f"Как узнать ID чата:\n"
            f"1. Добавьте бота @userinfobot в ваш канал/группу\n"
            f"2. Он покажет ID (например: -1001234567890)\n"
            f"3. Скопируйте ID и отправьте мне\n\n"
            f"Или используйте:\n"
            f"/cancel - отменить\n"
            f"/getchat - показать текущий чат",
            parse_mode=ParseMode.HTML
        )
        
        return SETCHAT_WAIT_ID

    async def receive_chat_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive chat ID from user."""
        user_id = update.effective_user.id
        
        # Check if this user is waiting for chat ID
        if user_id != self.setchat_user:
            return ConversationHandler.END
        
        chat_id_text = update.message.text.strip()
        
        # Validate chat ID (should be like -1001234567890 or 123456789)
        if not chat_id_text.lstrip('-').isdigit():
            await update.message.reply_text(
                "❌ Неверный формат ID.\n\n"
                "ID должен быть числом, например: -1001234567890\n"
                "Попробуйте ещё раз или /cancel для отмены."
            )
            return SETCHAT_WAIT_ID
        
        # Save chat ID
        self._save_target_chat_id(chat_id_text)
        self.setchat_user = None
        
        await update.message.reply_text(
            f"✅ <b>Целевой чат установлен!</b>\n\n"
            f"ID: <code>{chat_id_text}</code>\n\n"
            f"Теперь все посты будут копироваться в этот чат.\n\n"
            f"Команды:\n"
            f"/getchat - Показать текущий чат\n"
            f"/clearchat - Сбросить настройки\n"
            f"/setchat - Изменить чат",
            parse_mode=ParseMode.HTML
        )
        
        return ConversationHandler.END

    async def cancel_setchat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel setchat operation."""
        user_id = update.effective_user.id
        
        if user_id == self.setchat_user:
            self.setchat_user = None
        
        await update.message.reply_text(
            "❌ Отменено.\n\n"
            f"/setchat - начать настройку заново"
        )
        
        return ConversationHandler.END

    async def get_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /getchat command - show current target chat."""
        target_chat_id = self._get_target_chat_id()
        
        if target_chat_id:
            await update.message.reply_text(
                f"📍 <b>Текущий целевой чат:</b>\n\n"
                f"ID: <code>{target_chat_id}</code>\n\n"
                f"Команды:\n"
                f"/setchat - Изменить чат\n"
                f"/clearchat - Сбросить настройки",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "ℹ️ <b>Целевой чат не настроен.</b>\n\n"
                f"Посты будут копироваться в тот чат, где отправлена команда <code>/copy</code>.\n\n"
                f"Команды:\n"
                f"/setchat - Установить целевой чат\n"
                f"/getchat - Показать текущий чат",
                parse_mode=ParseMode.HTML
            )

    async def clear_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clearchat command - clear target chat settings."""
        self._clear_target_chat_id()
        
        await update.message.reply_text(
            "✅ <b>Настройки сброшены!</b>\n\n"
            f"Теперь посты будут копироваться в тот чат, где отправлена команда <code>/copy</code>.\n\n"
            f"Команды:\n"
            f"/setchat - Установить целевой чат\n"
            f"/getchat - Показать текущий чат",
            parse_mode=ParseMode.HTML
        )
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        await update.message.reply_text(
            "👋 <b>Добро пожаловать в VK to Telegram Bot!</b>\n\n"
            "Этот бот копирует посты из сообществ ВКонтакте в Telegram.\n\n"
            "<b>Команды:</b>\n"
            "/copy - Начать копирование постов\n"
            "/help - Показать справку\n"
            "/status - Проверить статус бота",
            parse_mode=ParseMode.HTML
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        await update.message.reply_text(
            "📖 <b>Справка</b>\n\n"
            "<b>Как использовать:</b>\n"
            "1. Используйте /copy для начала копирования\n"
            "2. Введите название или ID группы VK\n"
            "3. Укажите начальную дату (ГГГГ-ММ-ДД)\n"
            "4. Укажите конечную дату (ГГГГ-ММ-ДД)\n"
            "5. Введите количество постов (1-100)\n\n"
            "<b>Примечания:</b>\n"
            "- Все медиа (фото, видео, документы) будут скопированы\n"
            "- Посты копируются в хронологическом порядке\n"
            "- Копирование больших объёмов может занять время",
            parse_mode=ParseMode.HTML
        )

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        await update.message.reply_text(
            "✅ <b>Статус бота: Онлайн</b>\n\n"
            f"Версия VK API: {Config.VK_API_VERSION}\n"
            f"Готов к копированию постов!",
            parse_mode=ParseMode.HTML
        )
    
    async def copy_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start the copy process."""
        await update.message.reply_text(
            "📋 <b>Копирование постов из VK</b>\n\n"
            "Введите название или ID группы VK.\n"
            "Примеры: <code>durov</code>, <code>123456</code>",
            parse_mode=ParseMode.HTML
        )
        return SELECT_GROUP

    async def group_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process selected group."""
        group_name = update.message.text.strip()
        context.user_data["group_name"] = group_name

        # Validate group
        await update.message.reply_text(f"⏳ Проверка группы: <code>{group_name}</code>...")

        group_id = self.vk_client.get_group_id(group_name)
        if not group_id:
            await update.message.reply_text(
                "❌ Группа не найдена. Попробуйте ещё раз или введите /cancel для отмены.",
                parse_mode=ParseMode.HTML
            )
            return SELECT_GROUP

        context.user_data["group_id"] = group_id
        await update.message.reply_text(
            f"✅ Группа найдена!\n\n"
            f"Теперь введите <b>начальную дату</b> (ГГГГ-ММ-ДД):\n"
            f"Пример: <code>2024-01-01</code>",
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
                "❌ Неверный формат даты. Используйте формат ГГГГ-ММ-ДД.\n"
                "Пример: <code>2024-01-01</code>",
                parse_mode=ParseMode.HTML
            )
            return SELECT_START_DATE

        await update.message.reply_text(
            f"✅ Начальная дата: <code>{date_str}</code>\n\n"
            f"Теперь введите <b>конечную дату</b> (ГГГГ-ММ-ДД):\n"
            f"Пример: <code>2024-12-31</code>",
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
                    "❌ Конечная дата должна быть позже начальной.\n"
                    "Попробуйте ещё раз.",
                    parse_mode=ParseMode.HTML
                )
                return SELECT_END_DATE

            context.user_data["end_date"] = end_date
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты. Используйте формат ГГГГ-ММ-ДД.",
                parse_mode=ParseMode.HTML
            )
            return SELECT_END_DATE

        await update.message.reply_text(
            f"✅ Конечная дата: <code>{date_str}</code>\n\n"
            f"Сколько постов скопировать? (1-100)\n"
            f"По умолчанию: <code>50</code>",
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

        # Use target chat ID from file/config or current chat
        chat_id = self._get_target_chat_id() or str(update.effective_chat.id)

        await update.message.reply_text(
            f"🚀 <b>Запуск процесса копирования...</b>\n\n"
            f"Группа: <code>{group_name}</code>\n"
            f"Период: <code>{start_date.strftime('%Y-%m-%d')}</code> - "
            f"<code>{end_date.strftime('%Y-%m-%d')}</code>\n"
            f"Постов: <code>{count}</code>\n"
            f"Чат назначения: <code>{chat_id}</code>\n\n"
            f"⏳ Это может занять некоторое время...",
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
                "⚠️ Посты не найдены за указанный период.",
                parse_mode=ParseMode.HTML
            )
            return

        # Reverse to post in chronological order
        posts.reverse()

        await update.message.reply_text(
            f"📊 Найдено <code>{len(posts)}</code> постов. Начинаю копирование...",
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
                        f"📈 Прогресс: {progress} - скопировано {success_count}/{i} постов"
                    )

            except Exception as e:
                logger.error(f"Error copying post {i}: {e}")
                continue

        await update.message.reply_text(
            f"✅ <b>Копирование завершено!</b>\n\n"
            f"Успешно скопировано: <code>{success_count}/{len(posts)}</code> постов",
            parse_mode=ParseMode.HTML
        )

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the current operation."""
        await update.message.reply_text(
            "❌ Операция отменена.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        logger.error(f"Update {update} caused error: {context.error}")

        if update and update.effective_message:
            await update.effective_message.reply_text(
                f"❌ Произошла ошибка: <code>{context.error}</code>",
                parse_mode=ParseMode.HTML
            )
    
    def run(self) -> None:
        """Run the bot."""
        # Validate config
        Config.validate()

        # Create application
        application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        self.bot = application.bot

        # Add conversation handler for copy
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
        
        # Add conversation handler for setchat
        setchat_handler = ConversationHandler(
            entry_points=[CommandHandler("setchat", self.set_chat)],
            states={
                SETCHAT_WAIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_chat_id)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_setchat)],
        )

        # Add handlers
        application.add_handler(conv_handler)
        application.add_handler(setchat_handler)
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("status", self.status))
        application.add_handler(CommandHandler("cancel", self.cancel))
        application.add_handler(CommandHandler("getchat", self.get_chat))
        application.add_handler(CommandHandler("clearchat", self.clear_chat))

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
