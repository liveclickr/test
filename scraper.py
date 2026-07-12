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

# ব্লগার মোবাইল ভিউ রিকোয়েস্ট নিশ্চিত করার জন্য হেডারস
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
}

def get_post_links():
    links = set()
    home_url = "https://m3uworld4k.blogspot.com/?m=1"
    try:
        r = requests.get(home_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            html = r.text
            # ডিরেক্ট লিঙ্ক খোঁজা হচ্ছে (https://m3uworld4k.blogspot.com/2026/07/post.html)
            pattern1 = r'href=["\'](https://m3uworld4k\.blogspot\.com/\d{4}/\d{2}/[^"\']+\.html)'
            matches1 = re.findall(pattern1, html)
            for m in matches1:
                links.add(m)
                
            # রিলেটিভ লিঙ্ক খোঁজা হচ্ছে (/2026/07/post.html)
            pattern2 = r'href=["\'](/\d{4}/\d{2}/[^"\']+\.html)'
            matches2 = re.findall(pattern2, html)
            for m in matches2:
                links.add("https://m3uworld4k.blogspot.com" + m)
                
            print(f"[SUCCESS] Found {len(links)} unique post links on homepage.")
    except Exception as e:
        print(f"[ERROR] Failed to fetch homepage: {e}")
    return list(links)

def fetch_post_content(post_url):
    # মোবাইল ভার্সন নিশ্চিত করার জন্য m=1 যুক্ত করা হচ্ছে
    if "?m=1" not in post_url and "&m=1" not in post_url:
        post_url += "?m=1"
    try:
        r = requests.get(post_url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print(f"[ERROR] Failed to fetch post content for {post_url}: {e}")
    return ""

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
        print("[CRITICAL] Missing Cloudflare credentials!")
        exit(1)
        
    print("Step 1: Finding individual post links on homepage...")
    posts = get_post_links()
    
    if not posts:
        print("[CRITICAL] Could not find any post links on the homepage!")
        exit(1)
        
    # প্রতিটি পোস্ট পেজের কন্টেন্ট রিড করা হচ্ছে
    print("Step 2: Fetching HTML content of each post page...")
    combined_posts_html = ""
    for post in posts:
        print(f"Opening: {post}")
        html = fetch_post_content(post)
        if html:
            combined_posts_html += "\n" + html
            
    print("Step 3: Searching tokens inside the posts content...")
    for channel_id, base_url in CHANNELS.items():
        print(f"Searching token for {channel_id}...")
        pattern = rf"{channel_id}\.m3u8\?(s=[a-zA-Z0-9_-]+&e=\d+)"
        match = re.search(pattern, combined_posts_html)
        if match:
            fresh_token = match.group(1)
            print(f"[SUCCESS] Found working token for {channel_id}: {fresh_token}")
            update_cloudflare_kv(channel_id, fresh_token, base_url)
        else:
            print(f"[NOT FOUND] Could not find any active token for {channel_id}.")
