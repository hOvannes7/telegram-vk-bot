"""
Configuration module for Telegram VK Bot.
Loads settings from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot configuration."""
    
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    VK_ACCESS_TOKEN: str = os.getenv("VK_ACCESS_TOKEN", "")
    VK_API_VERSION: str = os.getenv("VK_API_VERSION", "5.131")
    TARGET_CHAT_ID: str = os.getenv("TARGET_CHAT_ID", "")
    
    # VK API base URL
    VK_API_URL: str = "https://api.vk.com/method"
    
    # Request timeout
    REQUEST_TIMEOUT: int = 30
    
    # Max posts per request
    MAX_POSTS_COUNT: int = 100
    
    # File download chunk size
    CHUNK_SIZE: int = 8192
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        if not cls.VK_ACCESS_TOKEN:
            raise ValueError("VK_ACCESS_TOKEN is not set")
        return True
