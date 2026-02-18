"""
VK API client for fetching posts with media attachments.
"""

import logging
import requests
from typing import Optional
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


class VKClient:
    """Client for VK API interactions."""
    
    def __init__(self):
        self.token = Config.VK_ACCESS_TOKEN
        self.version = Config.VK_API_VERSION
        self.base_url = Config.VK_API_URL
    
    def _make_request(self, method: str, params: dict, use_token: bool = True) -> Optional[dict]:
        """Make request to VK API."""
        url = f"{self.base_url}/{method}"
        if use_token:
            params.update({
                "access_token": self.token,
                "v": self.version
            })
        else:
            params["v"] = self.version

        try:
            response = requests.get(url, params=params, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                error_msg = data['error'].get('error_msg', 'Unknown error')
                error_code = data['error'].get('error_code', 'Unknown')
                logger.error(f"VK API error [{error_code}]: {error_msg}")
                logger.error(f"Request: {method}, Params: {params}")
                return None

            return data.get("response")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
    
    def get_group_id(self, group_name: str) -> Optional[int]:
        """Get group ID by group name/screen name."""
        group_name = group_name.strip()
        
        # If it's already a numeric ID, return it
        if group_name.isdigit():
            return int(group_name)
        
        # Try different formats for screen names
        variants = [
            group_name,           # e.g., "durov"
            f"club{group_name}",  # e.g., "club123456" for groups
            f"public{group_name}", # e.g., "public123456" for pages
            f"@{group_name}",     # e.g., "@durov"
        ]
        
        for variant in variants:
            params = {"group_id": variant}
            result = self._make_request("groups.getById", params)
            if result and result.get("groups"):
                group_id = result["groups"][0]["id"]
                logger.info(f"Found group ID {group_id} for '{group_name}'")
                return group_id
        
        # Try using wall.get directly to check if the group exists
        # This works for some cases where groups.getById fails
        logger.warning(f"groups.getById failed, trying wall.get fallback for '{group_name}'")
        
        # Try with screen name directly in wall.get
        test_params = {
            "owner_id": group_name,
            "count": 1
        }
        result = self._make_request("wall.get", test_params)
        if result:
            # Extract owner_id from the response
            # For groups, owner_id is negative
            logger.info(f"wall.get succeeded for '{group_name}', using as-is")
            return group_name  # Return as string, will be handled in get_posts
        
        logger.error(f"Could not find group: {group_name}")
        return None
    
    def get_posts(
        self,
        group_id: int | str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        count: int = 100
    ) -> list:
        """
        Get posts from a group within a time range.

        Args:
            group_id: VK group ID (numeric or screen name)
            start_date: Start of time range (inclusive)
            end_date: End of time range (inclusive)
            count: Number of posts to fetch

        Returns:
            List of posts with attachments
        """
        all_posts = []
        offset = 0
        batch_size = min(count, Config.MAX_POSTS_COUNT)

        # Format owner_id: negative for groups, handle both int and str
        if isinstance(group_id, str):
            # For screen names, VK uses negative values for groups
            # Try with minus prefix first
            owner_id = f"-{group_id}" if not group_id.startswith('-') else group_id
        else:
            owner_id = f"-{group_id}"

        logger.info(f"Fetching posts for owner_id: {owner_id}")

        while len(all_posts) < count:
            params = {
                "owner_id": owner_id,
                "offset": offset,
                "count": batch_size,
                "filter": "owner"
            }

            logger.debug(f"Fetching posts: offset={offset}, count={batch_size}")
            
            # Try simple request without extended and attachments first
            result = self._make_request("wall.get", params, use_token=False)
            
            # If that fails, try with token
            if not result:
                logger.info("Trying with token...")
                result = self._make_request("wall.get", params, use_token=True)
            
            # If still fails, try with extended but without attachments
            if not result:
                logger.info("Trying with extended=1...")
                params["extended"] = 1
                result = self._make_request("wall.get", params, use_token=False)
                
            # Last resort: full params with token
            if not result:
                logger.info("Trying with full params and token...")
                params["attachments"] = "photo,video,doc,link,note,poll,article"
                result = self._make_request("wall.get", params, use_token=True)

            if not result or not result.get("items"):
                # Try without the minus prefix (for pages/public pages)
                if owner_id.startswith('-') and isinstance(group_id, str):
                    logger.info(f"Trying without minus prefix: {group_id}")
                    params["owner_id"] = group_id
                    params.pop("extended", None)
                    params.pop("attachments", None)
                    
                    result = self._make_request("wall.get", params, use_token=False)
                    if not result:
                        result = self._make_request("wall.get", params, use_token=True)
                
                if not result or not result.get("items"):
                    break

            posts = result["items"]
            
            logger.info(f"Got {len(posts)} posts, filtering...")

            for post in posts:
                post_date = datetime.fromtimestamp(post["date"])
                logger.debug(f"Post date: {post_date}, text: {post.get('text', '')[:50]}...")

                # Filter by time range
                if start_date and post_date < start_date:
                    # Posts are sorted by date desc, so we can stop
                    logger.info(f"Post date {post_date} < start_date {start_date}, stopping")
                    return all_posts

                if end_date and post_date > end_date:
                    logger.debug(f"Post date {post_date} > end_date {end_date}, skipping")
                    continue

                all_posts.append(post)
                logger.debug(f"Added post from {post_date}")

                if len(all_posts) >= count:
                    break

            offset += batch_size

            # If we got fewer posts than requested, no more posts available
            if len(posts) < batch_size:
                break

        return all_posts
    
    def get_post_media(self, post: dict) -> dict:
        """
        Extract media information from a post.
        
        Returns:
            Dict with photos, videos, and documents info
        """
        media = {
            "photos": [],
            "videos": [],
            "documents": [],
            "links": [],
            "text": post.get("text", "")
        }
        
        attachments = post.get("attachments", [])
        
        for attachment in attachments:
            att_type = attachment.get("type")
            
            if att_type == "photo":
                photo = attachment.get("photo", {})
                # Get the highest resolution photo URL
                sizes = photo.get("sizes", [])
                if sizes:
                    # Sort by size and get the largest
                    sizes.sort(key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)
                    media["photos"].append({
                        "url": sizes[0].get("url"),
                        "width": sizes[0].get("width"),
                        "height": sizes[0].get("height")
                    })
                elif "photo_1280" in photo:
                    media["photos"].append({"url": photo["photo_1280"]})
                elif "photo_807" in photo:
                    media["photos"].append({"url": photo["photo_807"]})
                elif "photo_604" in photo:
                    media["photos"].append({"url": photo["photo_604"]})
            
            elif att_type == "video":
                video = attachment.get("video", {})
                media["videos"].append({
                    "title": video.get("title", "Video"),
                    "description": video.get("description", ""),
                    "player": video.get("player"),
                    "image": video.get("image"),
                    "duration": video.get("duration", 0),
                    "owner_id": video.get("owner_id"),
                    "id": video.get("id")
                })
            
            elif att_type == "doc":
                doc = attachment.get("doc", {})
                media["documents"].append({
                    "title": doc.get("title", "Document"),
                    "url": doc.get("url"),
                    "size": doc.get("size", 0),
                    "ext": doc.get("ext", "")
                })
            
            elif att_type == "link":
                link = attachment.get("link", {})
                media["links"].append({
                    "title": link.get("title", ""),
                    "url": link.get("url", ""),
                    "description": link.get("description", ""),
                    "photo": link.get("photo", {})
                })
        
        return media
