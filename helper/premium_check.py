import logging

from pyrogram import raw

logger = logging.getLogger(__name__)


async def get_session_info(session_client):
    """Ask Telegram directly (raw API) who the STRING_SESSION account is and
    whether it has Premium. Falls back to get_me() if the raw call fails.

    Returns a dict: id, name, username, premium (bool), source.
    """
    raw_user = None
    try:
        res = await session_client.invoke(
            raw.functions.users.GetUsers(id=[raw.types.InputUserSelf()])
        )
        if res:
            raw_user = res[0]
    except Exception as e:
        logger.warning(f"Raw users.GetUsers failed, falling back to get_me(): {e}")

    if raw_user is not None:
        name = " ".join(filter(None, [getattr(raw_user, "first_name", None), getattr(raw_user, "last_name", None)])) or "Unknown"
        info = {
            "id": getattr(raw_user, "id", None),
            "name": name,
            "username": getattr(raw_user, "username", None),
            "premium": bool(getattr(raw_user, "premium", False)),
            "source": "raw",
        }
    else:
        me = await session_client.get_me()
        info = {
            "id": me.id,
            "name": me.first_name or "Unknown",
            "username": me.username,
            "premium": bool(getattr(me, "is_premium", False)),
            "source": "get_me",
        }

    if info["premium"]:
        try:
            # keep the cached self.me in sync (fast_mtproto reads me.is_premium)
            me = await session_client.get_me()
            me.is_premium = True
            session_client.me = me
        except Exception:
            pass
    return info


def describe(info):
    uname = f"@{info['username']}" if info.get("username") else "no username"
    return f"{info['name']} ({uname}, id {info['id']})"
