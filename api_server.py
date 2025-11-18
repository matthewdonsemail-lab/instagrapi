"""
Complete Instagrapi REST API Server
Implements all major endpoints from the instagrapi library
"""
from fastapi import FastAPI, HTTPException, Query, Body, UploadFile, File, Form
from fastapi.responses import FileResponse
from instagrapi import Client
from instagrapi.exceptions import ClientError
from instagrapi.types import Usertag, Location, StoryMention, StoryLink, StoryHashtag
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import os
import tempfile

app = FastAPI(title="Instagrapi REST API", version="1.0.0")

# Initialize client
cl = Client()
sessionid = os.getenv("IG_SESSIONID")
if sessionid:
    cl.login_by_sessionid(sessionid)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def strip_username(username: str) -> str:
    """Strip trailing slashes and @ symbols from username"""
    return username.strip().rstrip('/').lstrip('@')

def convert_user_short(user):
    """Convert UserShort object to dict"""
    return {
        "pk": user.pk,
        "username": user.username,
        "full_name": user.full_name,
        "is_private": user.is_private,
        "profile_pic_url": str(user.profile_pic_url) if user.profile_pic_url else None
    }

def convert_media(media):
    """Convert Media object to dict"""
    return {
        "pk": media.pk,
        "id": media.id,
        "code": media.code,
        "taken_at": media.taken_at.isoformat() if media.taken_at else None,
        "media_type": media.media_type,
        "product_type": media.product_type,
        "thumbnail_url": str(media.thumbnail_url) if media.thumbnail_url else None,
        "location": media.location.dict() if media.location else None,
        "user": convert_user_short(media.user) if media.user else None,
        "comment_count": media.comment_count,
        "like_count": media.like_count,
        "caption_text": media.caption_text,
        "video_url": str(media.video_url) if media.video_url else None,
        "view_count": media.view_count,
        "video_duration": media.video_duration
    }

# ============================================================================
# USER ENDPOINTS
# ============================================================================

@app.get("/user/id_from_username/{username}")
async def user_id_from_username(username: str):
    """Get user_id from username"""
    try:
        username = strip_username(username)
        user_id = cl.user_id_from_username(username)
        return {"user_id": user_id, "username": username}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")

@app.get("/user/username_from_id/{user_id}")
async def username_from_user_id(user_id: int):
    """Get username from user_id"""
    try:
        username = cl.username_from_user_id(user_id)
        return {"user_id": user_id, "username": username}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")

@app.get("/user/info/{user_id}")
async def user_info(user_id: int):
    """Get full user info by user_id"""
    try:
        user = cl.user_info(user_id)
        return user.dict()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/user/info_by_username/{username}")
async def user_info_by_username(username: str):
    """Get full user info by username"""
    try:
        username = strip_username(username)
        user = cl.user_info_by_username(username)
        return user.dict()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

# --- NEW: FOLLOWER COUNT ENDPOINTS ------------------------------------------

@app.get("/user/{user_id}/followers_count")
async def user_followers_count(user_id: int):
    """Get total follower count by user_id"""
    try:
        user = cl.user_info(user_id)
        return {
            "user_id": user_id,
            "username": user.username,
            "follower_count": user.follower_count,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/user/followers_count/by_username/{username}")
async def user_followers_count_by_username(username: str):
    """Get total follower count by username"""
    try:
        username = strip_username(username)
        user = cl.user_info_by_username(username)
        return {
            "user_id": user.pk,
            "username": user.username,
            "follower_count": user.follower_count,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

# ---------------------------------------------------------------------------

@app.get("/user/{user_id}/followers")
async def user_followers(user_id: int, amount: int = Query(0, ge=0, description="0 = all followers")):
    """Get user's followers"""
    try:
        followers = cl.user_followers(user_id, amount)
        return [convert_user_short(user) for user in followers.values()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/user/{user_id}/following")
async def user_following(user_id: int, amount: int = Query(0, ge=0, description="0 = all following")):
    """Get user's following"""
    try:
        following = cl.user_following(user_id, amount)
        return [convert_user_short(user) for user in following.values()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/following/{username}/search")
async def search_following(
    username: str,
    q: str = Query(..., min_length=1, description="Search query"),
    amount: int = Query(50, ge=1, le=1000)
):
    """Search within following of a user"""
    try:
        username = strip_username(username)
        user_id = cl.user_id_from_username(username)
        results = cl.search_following(user_id, q)
        return [convert_user_short(user) for user in results[:amount]]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/followers/{username}/search")
async def search_followers(
    username: str,
    q: str = Query(..., min_length=1, description="Search query"),
    amount: int = Query(50, ge=1, le=1000)
):
    """Search within followers of a user"""
    try:
        username = strip_username(username)
        user_id = cl.user_id_from_username(username)
        results = cl.search_followers(user_id, q)
        return [convert_user_short(user) for user in results[:amount]]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/{user_id}/follow")
async def user_follow(user_id: int):
    """Follow a user"""
    try:
        result = cl.user_follow(user_id)
        return {"success": result, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/{user_id}/unfollow")
async def user_unfollow(user_id: int):
    """Unfollow a user"""
    try:
        result = cl.user_unfollow(user_id)
        return {"success": result, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/{user_id}/remove_follower")
async def user_remove_follower(user_id: int):
    """Remove a follower"""
    try:
        result = cl.user_remove_follower(user_id)
        return {"success": result, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/{user_id}/mute_posts")
async def mute_posts_from_follow(user_id: int):
    """Mute posts from following user"""
    try:
        result = cl.mute_posts_from_follow(user_id)
        return {"success": result, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/{user_id}/unmute_posts")
async def unmute_posts_from_follow(user_id: int):
    """Unmute posts from following user"""
    try:
        result = cl.unmute_posts_from_follow(user_id)
        return {"success": result, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/{user_id}/mute_stories")
async def mute_stories_from_follow(user_id: int):
    """Mute stories from following user"""
    try:
        result = cl.mute_stories_from_follow(user_id)
        return {"success": result, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/{user_id}/close_friend/add")
async def close_friend_add(user_id: int):
    """Add user to close friends list"""
    try:
        result = cl.close_friend_add(user_id)
        return {"success": result, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/{user_id}/close_friend/remove")
async def close_friend_remove(user_id: int):
    """Remove user from close friends list"""
    try:
        result = cl.close_friend_remove(user_id)
        return {"success": result, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MEDIA ENDPOINTS
# ============================================================================

@app.get("/media/pk_from_code/{code}")
async def media_pk_from_code(code: str):
    """Get media_pk from short code"""
    try:
        media_pk = cl.media_pk_from_code(code)
        return {"media_pk": media_pk, "code": code}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/media/pk_from_url")
async def media_pk_from_url(url: str = Query(..., description="Instagram media URL")):
    """Get media_pk from URL"""
    try:
        media_pk = cl.media_pk_from_url(url)
        return {"media_pk": media_pk, "url": url}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/media/info/{media_pk}")
async def media_info(media_pk: int):
    """Get media info"""
    try:
        media = cl.media_info(media_pk)
        return media.dict()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/user/{user_id}/medias")
async def user_medias(user_id: int, amount: int = Query(20, ge=1, le=100)):
    """Get user's medias"""
    try:
        medias = cl.user_medias(user_id, amount)
        return [convert_media(media) for media in medias]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/user/{user_id}/clips")
async def user_clips(user_id: int, amount: int = Query(50, ge=1, le=100)):
    """Get user's clips/reels"""
    try:
        clips = cl.user_clips(user_id, amount)
        return [convert_media(clip) for clip in clips]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/media/{media_pk}/like")
async def media_like(media_pk: int):
    """Like a media"""
    try:
        media_id = cl.media_id(media_pk)
        result = cl.media_like(media_id)
        return {"success": result, "media_pk": media_pk}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/media/{media_pk}/unlike")
async def media_unlike(media_pk: int):
    """Unlike a media"""
    try:
        media_id = cl.media_id(media_pk)
        result = cl.media_unlike(media_id)
        return {"success": result, "media_pk": media_pk}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/media/{media_pk}")
async def media_delete(media_pk: int):
    """Delete a media"""
    try:
        result = cl.media_delete(media_pk)
        return {"success": result, "media_pk": media_pk}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/media/{media_pk}/archive")
async def media_archive(media_pk: int):
    """Archive a media"""
    try:
        media_id = cl.media_id(media_pk)
        result = cl.media_archive(media_id)
        return {"success": result, "media_pk": media_pk}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/media/{media_pk}/unarchive")
async def media_unarchive(media_pk: int):
    """Unarchive a media"""
    try:
        media_id = cl.media_id(media_pk)
        result = cl.media_unarchive(media_id)
        return {"success": result, "media_pk": media_pk}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/media/{media_pk}/likers")
async def media_likers(media_pk: int):
    """Get users who liked a media"""
    try:
        media_id = cl.media_id(media_pk)
        likers = cl.media_likers(media_id)
        return [convert_user_short(user) for user in likers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/media/download/{media_pk}")
async def media_download(media_pk: int):
    """Download media (photo/video)"""
    try:
        media = cl.media_info(media_pk)
        temp_dir = Path(tempfile.mkdtemp())
        
        if media.media_type == 1:  # Photo
            path = cl.photo_download(media_pk, folder=temp_dir)
        elif media.media_type == 2 and media.product_type == "feed":  # Video
            path = cl.video_download(media_pk, folder=temp_dir)
        elif media.media_type == 2 and media.product_type == "igtv":  # IGTV
            path = cl.igtv_download(media_pk, folder=temp_dir)
        elif media.media_type == 2 and media.product_type == "clips":  # Reels
            path = cl.clip_download(media_pk, folder=temp_dir)
        else:
            raise HTTPException(status_code=400, detail="Unsupported media type")
        
        return FileResponse(path, filename=path.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# COMMENT ENDPOINTS
# ============================================================================

@app.get("/media/{media_pk}/comments")
async def media_comments(media_pk: int, amount: int = Query(0, ge=0)):
    """Get comments on a media (0 = all comments)"""
    try:
        media_id = cl.media_id(media_pk)
        comments = cl.media_comments(media_id, amount)
        return [comment.dict() for comment in comments]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CommentCreate(BaseModel):
    text: str
    replied_to_comment_id: Optional[int] = None

@app.post("/media/{media_pk}/comment")
async def media_comment(media_pk: int, comment_data: CommentCreate):
    """Add a comment to media"""
    try:
        media_id = cl.media_id(media_pk)
        comment = cl.media_comment(
            media_id, 
            comment_data.text,
            replied_to_comment_id=comment_data.replied_to_comment_id
        )
        return comment.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/comment/{comment_pk}/like")
async def comment_like(comment_pk: int):
    """Like a comment"""
    try:
        result = cl.comment_like(comment_pk)
        return {"success": result, "comment_pk": comment_pk}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/comment/{comment_pk}/unlike")
async def comment_unlike(comment_pk: int):
    """Unlike a comment"""
    try:
        result = cl.comment_unlike(comment_pk)
        return {"success": result, "comment_pk": comment_pk}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/media/{media_pk}/comments")
async def comment_bulk_delete(media_pk: int, comment_pks: List[int] = Body(...)):
    """Delete multiple comments"""
    try:
        media_id = cl.media_id(media_pk)
        result = cl.comment_bulk_delete(media_id, comment_pks)
        return {"success": result, "deleted_count": len(comment_pks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# DIRECT MESSAGE ENDPOINTS
# ============================================================================

@app.get("/direct/threads")
async def direct_threads(
    amount: int = Query(20, ge=1, le=100),
    selected_filter: str = Query("", description="Filter: '', 'flagged', or 'unread'")
):
    """Get all direct message threads"""
    try:
        threads = cl.direct_threads(amount, selected_filter)
        return [thread.dict() for thread in threads]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/direct/pending")
async def direct_pending_inbox(amount: int = Query(20, ge=1, le=100)):
    """Get pending direct message threads"""
    try:
        threads = cl.direct_pending_inbox(amount)
        return [thread.dict() for thread in threads]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/direct/thread/{thread_id}")
async def direct_thread(thread_id: int, amount: int = Query(20, ge=1)):
    """Get a specific thread with messages"""
    try:
        thread = cl.direct_thread(thread_id, amount)
        return thread.dict()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/direct/thread/{thread_id}/messages")
async def direct_messages(thread_id: int, amount: int = Query(20, ge=1)):
    """Get messages in a thread"""
    try:
        messages = cl.direct_messages(thread_id, amount)
        return [msg.dict() for msg in messages]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DirectMessageSend(BaseModel):
    text: str
    user_ids: List[int] = []
    thread_ids: List[int] = []

@app.post("/direct/send")
async def direct_send(message: DirectMessageSend):
    """Send a direct message to users or threads"""
    try:
        result = cl.direct_send(message.text, message.user_ids, message.thread_ids)
        return result.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/direct/thread/{thread_id}/answer")
async def direct_answer(thread_id: int, text: str = Body(..., embed=True)):
    """Reply to a thread"""
    try:
        result = cl.direct_answer(thread_id, text)
        return result.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/direct/search")
async def direct_search(query: str = Query(..., min_length=1)):
    """Search direct message threads"""
    try:
        results = cl.direct_search(query)
        return [thread.dict() for thread in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/direct/thread/{thread_id}")
async def direct_thread_hide(thread_id: int):
    """Delete (hide) a thread"""
    try:
        result = cl.direct_thread_hide(thread_id)
        return {"success": result, "thread_id": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/direct/thread/{thread_id}/mark_unread")
async def direct_thread_mark_unread(thread_id: int):
    """Mark a thread as unread"""
    try:
        result = cl.direct_thread_mark_unread(thread_id)
        return {"success": result, "thread_id": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/direct/thread/{thread_id}/mute")
async def direct_thread_mute(thread_id: int):
    """Mute a thread"""
    try:
        result = cl.direct_thread_mute(thread_id)
        return {"success": result, "thread_id": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/direct/thread/{thread_id}/unmute")
async def direct_thread_unmute(thread_id: int):
    """Unmute a thread"""
    try:
        result = cl.direct_thread_unmute(thread_id)
        return {"success": result, "thread_id": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/direct/message/{thread_id}/{message_id}")
async def direct_message_delete(thread_id: int, message_id: int):
    """Delete a message from thread"""
    try:
        result = cl.direct_message_delete(thread_id, message_id)
        return {"success": result, "thread_id": thread_id, "message_id": message_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class MediaShare(BaseModel):
    media_id: str
    user_ids: List[int]

@app.post("/direct/share/media")
async def direct_media_share(share: MediaShare):
    """Share a media to users via DM"""
    try:
        result = cl.direct_media_share(share.media_id, share.user_ids)
        return result.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "logged_in": cl.user_id is not None,
        "user_id": cl.user_id if cl.user_id else None
    }

@app.get("/")
async def root():
    """Root endpoint - redirect to docs"""
    return {
        "message": "Instagrapi REST API",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
