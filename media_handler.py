"""
Media handler for downloading and uploading files to Telegram.
"""

import logging
import aiohttp
import io
from typing import Optional, List
from telegram import Bot, InputMediaPhoto
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class MediaHandler:
    """Handles media download and upload operations."""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def download_file(self, url: str) -> Optional[bytes]:
        """Download file from URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    response.raise_for_status()
                    return await response.read()
        except aiohttp.ClientError as e:
            logger.error(f"Failed to download {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading {url}: {e}")
            return None

    async def send_media_group(
        self,
        chat_id: str,
        photos: List[dict],
        caption: Optional[str] = None
    ) -> bool:
        """
        Send multiple photos as a single media group (album).
        Telegram allows up to 10 photos in one album.
        """
        try:
            if not photos:
                return False

            # Telegram allows max 10 photos per album
            # Split into chunks of 10
            chunk_size = 10
            all_success = True

            for i in range(0, len(photos), chunk_size):
                photo_chunk = photos[i:i + chunk_size]
                media_list = []

                for j, photo_data in enumerate(photo_chunk):
                    url = photo_data.get("url")
                    if not url:
                        continue

                    photo_bytes = await self.download_file(url)
                    if not photo_bytes:
                        continue

                    # First photo gets the caption
                    photo_caption = caption if j == 0 and i == 0 else None

                    input_media = InputMediaPhoto(
                        media=io.BytesIO(photo_bytes),
                        caption=photo_caption,
                        parse_mode=ParseMode.HTML if photo_caption else None
                    )
                    media_list.append(input_media)

                if media_list:
                    await self.bot.send_media_group(
                        chat_id=chat_id,
                        media=media_list
                    )

            return all_success
        except Exception as e:
            logger.error(f"Failed to send media group: {e}")
            return False

    async def send_photo(
        self,
        chat_id: str,
        photo_data: dict,
        caption: Optional[str] = None
    ) -> bool:
        """Send single photo to Telegram chat."""
        try:
            url = photo_data.get("url")
            if not url:
                return False

            photo_bytes = await self.download_file(url)
            if not photo_bytes:
                return False

            await self.bot.send_photo(
                chat_id=chat_id,
                photo=io.BytesIO(photo_bytes),
                caption=caption,
                parse_mode=ParseMode.HTML
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")
            return False

    async def send_document(
        self,
        chat_id: str,
        doc_data: dict,
        caption: Optional[str] = None
    ) -> bool:
        """Send document to Telegram chat."""
        try:
            url = doc_data.get("url")
            if not url:
                return False

            doc_bytes = await self.download_file(url)
            if not doc_bytes:
                return False

            filename = doc_data.get("title", f"file.{doc_data.get('ext', 'bin')}")

            await self.bot.send_document(
                chat_id=chat_id,
                document=io.BytesIO(doc_bytes),
                filename=filename,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            return False

    async def send_video(
        self,
        chat_id: str,
        video_data: dict,
        caption: Optional[str] = None
    ) -> bool:
        """
        Send video with thumbnail.
        Note: VK videos often require special handling.
        """
        try:
            title = video_data.get("title", "Video")
            description = video_data.get("description", "")

            caption_text = f"🎬 <b>{title}</b>\n"
            if description:
                caption_text += f"<i>{description[:500]}</i>"

            # Try to get video thumbnail
            image_url = video_data.get("image")
            if image_url:
                image_bytes = await self.download_file(image_url)
                if image_bytes:
                    await self.bot.send_photo(
                        chat_id=chat_id,
                        photo=io.BytesIO(image_bytes),
                        caption=caption_text,
                        parse_mode=ParseMode.HTML
                    )
                    return True

            # Fallback: send text with video info
            await self.bot.send_message(
                chat_id=chat_id,
                text=caption_text,
                parse_mode=ParseMode.HTML
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send video: {e}")
            return False

    async def send_message_with_media(
        self,
        chat_id: str,
        media: dict,
        caption: Optional[str] = None
    ) -> bool:
        """
        Send message with all attached media.
        Multiple photos are sent as an album.

        Args:
            chat_id: Target Telegram chat ID
            media: Media dict from VKClient.get_post_media()
            caption: Optional caption for the message

        Returns:
            True if at least one media item was sent successfully
        """
        success = False

        # Send text if no media
        if not media["photos"] and not media["videos"] and not media["documents"]:
            if media["text"]:
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=media["text"],
                        parse_mode=ParseMode.HTML
                    )
                    return True
                except Exception as e:
                    logger.error(f"Failed to send message: {e}")
                    return False

        # Send photos as album if multiple, or single photo
        if media["photos"]:
            if len(media["photos"]) > 1:
                # Send as album
                if await self.send_media_group(chat_id, media["photos"], caption):
                    success = True
            else:
                # Send single photo
                if await self.send_photo(chat_id, media["photos"][0], caption):
                    success = True

        # Send videos
        for video in media["videos"]:
            if await self.send_video(chat_id, video, caption):
                success = True

        # Send documents
        for doc in media["documents"]:
            if await self.send_document(chat_id, doc, caption):
                success = True

        # Send links
        for link in media["links"]:
            link_text = f"🔗 <a href=\"{link['url']}\">{link['title']}</a>"
            if link.get("description"):
                link_text += f"\n<i>{link['description'][:200]}</i>"
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=link_text,
                    parse_mode=ParseMode.HTML
                )
                success = True
            except Exception as e:
                logger.error(f"Failed to send link: {e}")

        return success
