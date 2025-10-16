import re

MAP = {
    "twitter.com": "x", "x.com": "x",
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube", "youtu.be": "youtube",
    "linkedin.com": "linkedin",
    "github.com": "github",
}

def infer_icon_key(url: str) -> str:
    m = re.search(r"https?://([^/]+)", url or "")
    host = (m.group(1).lower() if m else "").replace("www.", "")
    return MAP.get(host, "other")