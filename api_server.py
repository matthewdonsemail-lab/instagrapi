import os
import threading
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from instagrapi import Client
from instagrapi.exceptions import (
    UserNotFound,
    PrivateAccount,
    DirectThreadNotFound,
    DirectMessageNotFound,
)

# Read session id from environment (set this in Railway)
INSTAGRAM_SESSION_ID = os.environ.get("INSTAGRAM_SESSION_ID")

_client: Optional[Client] = None
_client_lock = threading.Lock()


def get_client() -> Client:
    """
    Lazily initialise a single Client instance using INSTAGRAM_SESSION_ID.
    """
    global _client

    if _client is not None:
        return _client

    if not INSTAGRAM_SESSION_ID:
        raise RuntimeError(
            "INSTAGRAM_SESSION_ID environment variable is not set. "
            "Set it in your Railway project variables."
        )

    with _client_lock:
        if _client is not None:
            return _client

        cl = Client()
        # Login using session id (recommended way from docs)
        cl.login_by_sessionid(INSTAGRAM_SESSION_ID)
        _client = cl
        return cl


app = FastAPI(
    title="Instagrapi API",
    version="0.2.1",
    description="REST API around instagrapi for followers/following, user stats and Direct messages.",
)


# ---------- Pydantic models ----------

class UserShortOut(BaseModel):
    pk: int
    username: str
    full_name: str
    is_private: Optional[bool] = None
    profile_pic_url: Optional[str] = None


class UserOut(BaseModel):
    pk: int
    username: str
    full_name: str
    is_private: bool
    profile_pic_url: Optional[str] = None
    is_verified: Optional[bool] = None
    media_count: Optional[int] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    biography: Optional[str] = None
    external_url: Optional[str] = None
    is_business: Optional[bool] = None


class UserStatsOut(BaseModel):
    """
    Lightweight view that lets you very quickly know
    how big an account is without pulling all followers.
    """
    pk: int
    username: str
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    media_count: Optional[int] = None
    is_private: Optional[bool] = None
    is_business: Optional[bool] = None


class DirectSendRequest(BaseModel):
    text: str
    usernames: Optional[List[str]] = None
    user_ids: Optional[List[int]] = None
    thread_ids: Optional[List[int]] = None


class DirectReplyRequest(BaseModel):
    text: str


class BlockResponse(BaseModel):
    username: str
    user_id: int
    blocked: bool


# ---------- Health ----------

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------- Followers / Following / User info ----------

@app.get("/followers/{username}", response_model=List[UserShortOut])
def get_followers(
    username: str,
    amount: int = Query(
        10,
        ge=0,
        le=10000,
        description="How many followers to return. 0 = ALL followers (slow on big accounts!)",
    ),
):
    """
    Return up to `amount` followers for the given username.

    Uses cl.user_followers() which returns Dict[int, UserShort].

    NOTE:
    - amount=0 means "all followers" per instagrapi docs.
      This is naturally slower for large accounts because it has to paginate.
    """
    cl = get_client()

    try:
        user_id = cl.user_id_from_username(username)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        followers = cl.user_followers(user_id, amount=amount or 0)
    except PrivateAccount:
        raise HTTPException(status_code=403, detail="Account is private")

    result: List[UserShortOut] = []
    for pk, user in followers.items():
        result.append(
            UserShortOut(
                pk=pk,
                username=user.username,
                full_name=user.full_name,
                is_private=getattr(user, "is_private", None),
                profile_pic_url=str(user.profile_pic_url)
                if getattr(user, "profile_pic_url", None)
                else None,
            )
        )
    return result


@app.get("/following/{username}", response_model=List[UserShortOut])
def get_following(
    username: str,
    amount: int = Query(
        10,
        ge=0,
        le=10000,
        description="How many accounts to return. 0 = ALL following (slow on big accounts!)",
    ),
):
    """
    Return up to `amount` accounts this user is following.
    Uses cl.user_following().
    """
    cl = get_client()

    try:
        user_id = cl.user_id_from_username(username)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        following = cl.user_following(user_id, amount=amount or 0)
    except PrivateAccount:
        raise HTTPException(status_code=403, detail="Account is private")

    result: List[UserShortOut] = []
    for pk, user in following.items():
        result.append(
            UserShortOut(
                pk=pk,
                username=user.username,
                full_name=user.full_name,
                is_private=getattr(user, "is_private", None),
                profile_pic_url=str(user.profile_pic_url)
                if getattr(user, "profile_pic_url", None)
                else None,
            )
        )
    return result


@app.get("/followers/{username}/search", response_model=List[UserShortOut])
def search_followers(
    username: str,
    q: str = Query(..., min_length=1),
    amount: int = Query(50, ge=1, le=1000),
):
    """
    Search within followers of a user using cl.search_followers().

    This does NOT fetch all followers first – it uses the built-in search
    which is much faster when you only care about matches for a query
    like 'factory'.
    """
    cl = get_client()

    try:
        user_id = cl.user_id_from_username(username)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found")

    followers = cl.search_followers(user_id=user_id, query=q)
    followers = followers[:amount]

    result: List[UserShortOut] = []
    for user in followers:
        result.append(
            UserShortOut(
                pk=user.pk,
                username=user.username,
                full_name=user.full_name,
                is_private=getattr(user, "is_private", None),
                profile_pic_url=str(user.profile_pic_url)
                if getattr(user, "profile_pic_url", None)
                else None,
            )
        )
    return result


@app.get("/following/{username}/search", response_model=List[UserShortOut])
def search_following(
    username: str,
    q: str = Query(..., min_length=1),
    amount: int = Query(50, ge=1, le=1000),
):
    """
    Search within following of a user using cl.search_following().
    """
    cl = get_client()

    try:
        user_id = cl.user_id_from_username(username)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found")

    following = cl.search_following(user_id=user_id, query=q)
    following = following[:amount]

    result: List[UserShortOut] = []
    for user in following:
        result.append(
            UserShortOut(
                pk=user.pk,
                username=user.username,
                full_name=user.full_name,
                is_private=getattr(user, "is_private", None),
                profile_pic_url=str(user.profile_pic_url)
                if getattr(user, "profile_pic_url", None)
                else None,
            )
        )
    return result


@app.get("/users/{username}", response_model=UserOut)
def get_user(username: str):
    """
    Full user profile info using cl.user_info_by_username().

    Use this when you want follower_count / following_count etc,
    but you do NOT need the full follower list.
    """
    cl = get_client()

    try:
        user = cl.user_info_by_username(username)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found")

    return UserOut(
        pk=user.pk,
        username=user.username,
        full_name=user.full_name,
        is_private=user.is_private,
        profile_pic_url=str(user.profile_pic_url)
        if getattr(user, "profile_pic_url", None)
        else None,
        is_verified=getattr(user, "is_verified", None),
        media_count=getattr(user, "media_count", None),
        follower_count=getattr(user, "follower_count", None),
        following_count=getattr(user, "following_count", None),
        biography=getattr(user, "biography", None),
        external_url=str(user.external_url)
        if getattr(user, "external_url", None)
        else None,
        is_business=getattr(user, "is_business", None),
    )


@app.get("/users/{username}/stats", response_model=UserStatsOut)
def get_user_stats(username: str):
    """
    Super-lightweight stats endpoint.

    This calls cl.user_info_by_username() once and only returns the fields
    you usually care about for sizing an account:
    follower_count, following_count, media_count, is_private, is_business.
    """
    cl = get_client()

    try:
        user = cl.user_info_by_username(username)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found")

    return UserStatsOut(
        pk=user.pk,
        username=user.username,
        follower_count=getattr(user, "follower_count", None),
        following_count=getattr(user, "following_count", None),
        media_count=getattr(user, "media_count", None),
        is_private=getattr(user, "is_private", None),
        is_business=getattr(user, "is_business", None),
    )


# ---------- Direct: threads, messages, send, reply, unsend ----------

@app.get("/direct/threads")
def list_threads(
    amount: int = Query(10, ge=1, le=100),
    thread_message_limit: int = Query(10, ge=0, le=200),
):
    """
    List Direct threads using cl.direct_threads().
    """
    cl = get_client()
    threads = cl.direct_threads(
        amount=amount,
        thread_message_limit=thread_message_limit,
    )
    return jsonable_encoder([t.dict() for t in threads])


@app.get("/direct/threads/{thread_id}")
def get_thread(
    thread_id: int,
    amount: int = Query(20, ge=1, le=200),
):
    """
    Get a single Direct thread with last `amount` messages.
    """
    cl = get_client()

    try:
        thread = cl.direct_thread(thread_id, amount=amount)
    except DirectThreadNotFound:
        raise HTTPException(status_code=404, detail="Thread not found")

    return jsonable_encoder(thread.dict())


@app.get("/direct/threads/{thread_id}/messages")
def get_thread_messages(
    thread_id: int,
    amount: int = Query(20, ge=1, le=200),
):
    """
    List messages in a Direct thread using cl.direct_messages().
    """
    cl = get_client()

    try:
        messages = cl.direct_messages(thread_id, amount=amount)
    except DirectThreadNotFound:
        raise HTTPException(status_code=404, detail="Thread not found")

    return jsonable_encoder([m.dict() for m in messages])


@app.post("/direct/send")
def send_direct_message(payload: DirectSendRequest):
    """
    Send a text Direct message.

    Maps to cl.direct_send(text, user_ids=[...], thread_ids=[...])

    - You can pass:
      * usernames: list of Instagram usernames
      * user_ids: list of numeric user IDs
      * thread_ids: list of existing thread IDs (to send into a thread)
    """
    cl = get_client()

    user_ids: List[int] = []
    if payload.user_ids:
        user_ids.extend(payload.user_ids)

    if payload.usernames:
        for username in payload.usernames:
            try:
                uid = cl.user_id_from_username(username)
            except UserNotFound:
                raise HTTPException(
                    status_code=404,
                    detail=f"User not found: {username}",
                )
            user_ids.append(uid)

    if not user_ids and not payload.thread_ids:
        raise HTTPException(
            status_code=400,
            detail="You must provide at least one username/user_id or a thread_ids list.",
        )

    message = cl.direct_send(
        payload.text,
        user_ids=user_ids or None,
        thread_ids=payload.thread_ids or None,
    )

    # direct_send returns DirectMessage
    return jsonable_encoder(message.dict())


@app.post("/direct/threads/{thread_id}/reply")
def reply_to_thread(
    thread_id: int,
    payload: DirectReplyRequest,
):
    """
    Reply into an existing Direct thread using cl.direct_answer().
    """
    cl = get_client()

    try:
        message = cl.direct_answer(thread_id, payload.text)
    except DirectThreadNotFound:
        raise HTTPException(status_code=404, detail="Thread not found")

    return jsonable_encoder(message.dict())


@app.delete("/direct/threads/{thread_id}/messages/{message_id}")
def unsend_message(thread_id: int, message_id: int):
    """
    Unsend (delete) a Direct message using cl.direct_message_delete().
    """
    cl = get_client()

    try:
        ok = cl.direct_message_delete(thread_id, message_id)
    except DirectMessageNotFound:
        raise HTTPException(status_code=404, detail="Message not found")

    return {"success": bool(ok)}


# ---------- Block / Unblock ----------

@app.post("/users/{username}/block", response_model=BlockResponse)
def block_user(username: str):
    """
    Block a user.
    Uses cl.user_block(user_id) if available in this instagrapi version.
    """
    cl = get_client()

    try:
        user_id = cl.user_id_from_username(username)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found")

    block_fn = getattr(cl, "user_block", None)
    if not callable(block_fn):
        raise HTTPException(
            status_code=501,
            detail="This instagrapi version does not expose user_block().",
        )

    blocked = bool(block_fn(user_id))
    return BlockResponse(username=username, user_id=user_id, blocked=blocked)


@app.post("/users/{username}/unblock", response_model=BlockResponse)
def unblock_user(username: str):
    """
    Unblock a user.
    Uses cl.user_unblock(user_id) if available in this instagrapi version.
    """
    cl = get_client()

    try:
        user_id = cl.user_id_from_username(username)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found")

    unblock_fn = getattr(cl, "user_unblock", None)
    if not callable(unblock_fn):
        raise HTTPException(
            status_code=501,
            detail="This instagrapi version does not expose user_unblock().",
        )

    unblocked = bool(unblock_fn(user_id))
    # `blocked` field is inverse of unblocked
    return BlockResponse(username=username, user_id=user_id, blocked=not unblocked)


# ---------- Local dev entrypoint (Railway will ignore this) ----------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        reload=False,
    )
