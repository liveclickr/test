import os
import re
import json
import requests

# ক্লাউডফ্লেয়ার এনভায়রনমেন্ট ভ্যারিয়েবল (Secrets থেকে অটোমেটিক লোড হবে)
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
CF_KV_NAMESPACE_ID = os.environ.get("CF_KV_NAMESPACE_ID")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")

# আপনার চ্যানেল আইডি এবং সেগুলোর বেস ইউআরএল (Base URL)
CHANNELS = {
    "ithh1xe7c01n2": "https://gxqkdba3q70p.48552462.net:8443/hls/",
    "g8yy3cfv128h5": "https://y4mpwzd7.12703830.net:8443/hls/",
    "nessgjp115wr8": "https://gxqkdba3q70p.48552462.net:8443/hls/",
    "o9mmstuhtgqjq": "https://gxqkdba3q70p.48552462.net:8443/hls/",
    "ulgk1vzsw8aqr": "https://gxqkdba3q70p.48552462.net:8443/hls/",
    "cd88is8arjavh": "https://gxqkdba3q70p.48552462.net:8443/hls/"
}

def get_blogspot_content():
    combined_content = ""
    
    # ১. ব্লগস্পট ফিড ফেচ করা (সবচেয়ে নির্ভরযোগ্য সোর্স - এটি হিডেন পোস্টও রিড করতে পারে)
    feed_url = "https://m3uworld4k.blogspot.com/feeds/posts/default?alt=json"
    try:
        r = requests.get(feed_url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            entries = data.get("feed", {}).get("entry", [])
            for entry in entries:
                content = entry.get("content", {}).get("$t", "")
                summary = entry.get("summary", {}).get("$t", "")
                title = entry.get("title", {}).get("$t", "")
                combined_content += f"\n{title}\n{content}\n{summary}"
            print("[FEED SUCCESS] Successfully fetched Blogspot posts feed.")
    except Exception as e:
        print(f"[FEED ERROR] Failed to fetch Blogger feed: {e}")
        
    # ২. ব্লগস্পট হোমপেইজ HTML ফেচ করা (ব্যাকআপ হিসেবে)
    home_url = "https://m3uworld4k.blogspot.com/?m=1"
    try:
        r = requests.get(home_url, timeout=10)
        if r.status_code == 200:
            combined_content += "\n" + r.text
            print("[HTML SUCCESS] Successfully fetched Blogspot homepage HTML.")
    except Exception as e:
        print(f"[HTML ERROR] Failed to fetch homepage HTML: {e}")
        
    return combined_content

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
        
    print("Fetching Blogspot content...")
    raw_blogspot_data = get_blogspot_content()
    
    if not raw_blogspot_data:
        print("[CRITICAL] Could not fetch any data from Blogspot!")
        exit(1)
        
    for channel_id, base_url in CHANNELS.items():
        print(f"Searching token for {channel_id}...")
        # Regex প্যাটার্ন দিয়ে টোকেন (s=...&e=...) অংশটি আলাদা করা হচ্ছে
        pattern = rf"{channel_id}\.m3u8\?(s=[a-zA-Z0-9_-]+&e=\d+)"
        match = re.search(pattern, raw_blogspot_data)
        if match:
            fresh_token = match.group(1)
            print(f"[SUCCESS] Found working token for {channel_id}: {fresh_token}")
            update_cloudflare_kv(channel_id, fresh_token, base_url)
        else:
            print(f"[NOT FOUND] Could not find any active token for {channel_id}.")
