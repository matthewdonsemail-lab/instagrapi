from fastapi import FastAPI, HTTPException
from instagrapi import Client
import os

app = FastAPI(title="Instagrapi Followers API")

# --- Instagrapi client bootstrap ---

cl = Client()

SESSIONID = os.getenv("IG_SESSIONID")
if not SESSIONID:
    raise RuntimeError("IG_SESSIONID env var must be set")

# Login using sessionid to avoid interactive challenge
cl.login_by_sessionid(SESSIONID)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/followers/{username}")
def get_followers(username: str, amount: int = 50):
    """
    Return up to `amount` followers for the given username.
    """
    try:
        user_id = cl.user_id_from_username(username)
        followers = cl.user_followers(user_id, amount=amount)
    except Exception as e:
        # Bubble up the error so you can see it in the response if IG/login fails
        raise HTTPException(status_code=500, detail=str(e))

    out = []
    for pk, user in followers.items():
        out.append(
            {
                "pk": int(pk),
                "username": user.username,
                "full_name": user.full_name,
                "is_private": user.is_private,
                "profile_pic_url": str(user.profile_pic_url) if user.profile_pic_url else None,
            }
        )
    return out
