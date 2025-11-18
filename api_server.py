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
        # Bubble up the actual error message so you can see IG / login issues in the response
        raise HTTPException(status_code=500, detail=str(e))

    out = []
    for pk, user in followers.items():
        # user is a UserShort object – only some fields exist
        out.append(
            {
                "pk": int(pk),
                "username": user.username,
                "full_name": user.full_name,
                # UserShort has profile_pic_url; convert HttpUrl -> str for JSON
                "profile_pic_url": str(user.profile_pic_url) if user.profile_pic_url else None,
                # If you really want verified info, you'd have to call cl.user_info(...) per user,
                # which is way slower – so we skip it here.
            }
        )
    return out
