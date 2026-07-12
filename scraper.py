import os
import re
import json
import requests

# ক্লাউডফ্লেয়ার এবং গিটহাব এনভায়রনমেন্ট ভ্যারিয়েবল (Secrets থেকে অটোমেটিক লোড হবে)
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
CF_KV_NAMESPACE_ID = os.environ.get("CF_KV_NAMESPACE_ID")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
GH_TOKEN = os.environ.get("GITHUB_TOKEN") # গিটহাব অ্যাকশনের নিজস্ব বিল্ট-ইন টোকেন

# আপনার চ্যানেল আইডি এবং সেগুলোর বেস ইউআরএল (Base URL)
CHANNELS = {
    "ithh1xe7c01n2": "https://gxqkdba3q70p.48552462.net:8443/hls/",
    "g8yy3cfv128h5": "https://y4mpwzd7.12703830.net:8443/hls/",
    "nessgjp115wr8": "https://gxqkdba3q70p.48552462.net:8443/hls/",
    "o9mmstuhtgqjq": "https://gxqkdba3q70p.48552462.net:8443/hls/",
    "ulgk1vzsw8aqr": "https://gxqkdba3q70p.48552462.net:8443/hls/",
    "cd88is8arjavh": "https://gxqkdba3q70p.48552462.net:8443/hls/"
}

def search_github_for_token(channel_id):
    headers = {
        "Accept": "application/vnd.github+json",
    }
    if GH_TOKEN:
        headers["Authorization"] = f"Bearer {GH_TOKEN}"
        
    # গিটহাবে ইউনিক চ্যানেল আইডি দিয়ে কোড সার্চ কুয়েরি করা হচ্ছে
    query = f"{channel_id}.m3u8"
    url = f"https://api.github.com/search/code?q={query}"
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            for item in items[:5]:  # সেরা ৫টি সার্চ রেজাল্ট চেক করা হবে
                raw_url = item.get("html_url", "").replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                raw_r = requests.get(raw_url, timeout=10)
                if raw_r.status_code == 200:
                    content = raw_r.text
                    # লিঙ্ক থেকে s=... এবং e=... প্যারামিটারটি খোঁজা হচ্ছে
                    pattern = rf"{channel_id}\.m3u8\?(s=[a-zA-Z0-9_-]+&e=\d+)"
                    match = re.search(pattern, content)
                    if match:
                        potential_token = match.group(1)
                        
                        # টোকেনটি সচল কি না তা সার্ভারে রিকোয়েস্ট পাঠিয়ে নিশ্চিত করা হচ্ছে
                        test_url = f"{CHANNELS[channel_id]}{channel_id}.m3u8?{potential_token}"
                        try:
                            head_r = requests.head(test_url, timeout=5)
                            if head_r.status_code == 200:
                                print(f"[SUCCESS] verified working token for {channel_id}: {potential_token}")
                                return potential_token
                        except Exception:
                            pass
        else:
            print(f"[API ERROR] GitHub Search returned status {r.status_code} for {channel_id}.")
    except Exception as e:
        print(f"[ERROR] Searching failed for {channel_id}: {e}")
    return None

def update_cloudflare_kv(channel_id, token, base_url):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{channel_id}"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "token": token,
        "base_url": base_url
    }
    r = requests.put(url, headers=headers, data=json.dumps(data))
    if r.status_code == 200:
        print(f"[KV SAVED] {channel_id} is successfully updated in Cloudflare!")
    else:
        print(f"[KV ERROR] Failed to save {channel_id}: {r.text}")

if __name__ == "__main__":
    if not CF_ACCOUNT_ID or not CF_KV_NAMESPACE_ID or not CF_API_TOKEN:
        print("[CRITICAL] Missing Cloudflare credentials in environment variables!")
        exit(1)
        
    for channel_id, base_url in CHANNELS.items():
        print(f"Searching token for {channel_id}...")
        token = search_github_for_token(channel_id)
        if token:
            update_cloudflare_kv(channel_id, token, base_url)
        else:
            print(f"Could not find any working token for {channel_id}.")
