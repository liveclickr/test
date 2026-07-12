import os
import re
import json
import base64
import urllib.parse
import requests

# ক্লাউডফ্লেয়ার এনভায়রনমেন্ট ভ্যারিয়েবলস
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "").strip()
CF_KV_NAMESPACE_ID = os.environ.get("CF_KV_NAMESPACE_ID", "").strip()
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "").strip()

# স্ট্যান্ডার্ড ব্রাউজার রিকোয়েস্ট নিশ্চিত করার জন্য হেডারস
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

def fetch_url_content(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
    return ""

def get_embedded_sources(html):
    # এইচটিএমএল কোডের ভেতর থেকে সমস্ত প্লেয়ার এবং স্ক্রিপ্ট লিঙ্ক খুঁজে বের করা
    urls = re.findall(r'(https?://[^\s"\'><]+)', html)
    valid_urls = []
    player_keywords = ["qzz.io", "trophystream", "lovetier", "deviantart", "grita", "thebosstv", "stream", "player", "embed", "videx", "gomstream"]
    
    for url in urls:
        # লিঙ্ক ক্লিনআপ
        url_clean = url.replace('\\', '').split('"')[0].split("'")[0]
        if any(kw in url_clean.lower() for kw in player_keywords):
            if url_clean not in valid_urls:
                valid_urls.append(url_clean)
    return valid_urls

def extract_m3u8_from_html(html):
    # ইউআরএল ডিকোড করা হচ্ছে যাতে স্ক্রিপ্টটি সহজেই লিঙ্কগুলো রিড করতে পারে
    decoded_html = urllib.parse.unquote(html)
    m3u8_links = re.findall(r'(https?://[^\s"\'><]+\.m3u8(?:\?[^\s"\'><]+)?)', decoded_html)
    return m3u8_links

def update_cloudflare_kv(slug, stream_url):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{slug}"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "text/plain"
    }
    r = requests.put(url, headers=headers, data=stream_url)
    if r.status_code == 200:
        print(f"  [KV SAVED] Key '{slug}' is updated with URL: {stream_url}")
    else:
        print(f"  [KV ERROR] Failed to save '{slug}': {r.text}")

if __name__ == "__main__":
    print("--- Cloudflare Credentials Diagnostic Check ---")
    print(f"Account ID Length: {len(CF_ACCOUNT_ID)} (Should be exactly 32)")
    print(f"KV Namespace ID Length: {len(CF_KV_NAMESPACE_ID)} (Should be exactly 32)")
    print(f"API Token Length: {len(CF_API_TOKEN)}")
    print("------------------------------------------------\n")
    
    if not CF_ACCOUNT_ID or not CF_KV_NAMESPACE_ID or not CF_API_TOKEN:
        print("[CRITICAL] Missing Cloudflare credentials!")
        exit(1)
        
    print("Step 1: Fetching NongorPlay main page content...")
    url = "https://nongorplay.live/watch/fifa-world-cup"
    html = fetch_url_content(url)
    
    if not html:
        print("[CRITICAL] Failed to fetch NongorPlay page content!")
        exit(0)
        
    compiled_html = html
    
    # প্লেয়ার লিঙ্ক ও আইফ্রেম খোঁজা হচ্ছে
    print("Step 2: Scanning for embedded stream players...")
    embeds = get_embedded_sources(html)
    print(f"Found {len(embeds)} potential player links. Fetching them...")
    
    for embed_url in embeds:
        print(f"  -> Fetching embedded player/script: {embed_url}")
        embed_html = fetch_url_content(embed_url)
        if embed_html:
            compiled_html += "\n" + embed_html
            
    # লাইভ .m3u8 লিঙ্ক খোঁজা হচ্ছে
    print("\nStep 3: Searching and extracting .m3u8 stream tokens...")
    m3u8_urls = extract_m3u8_from_html(compiled_html)
    
    found_streams_count = 0
    for m3u8_url in m3u8_urls:
        if any(kw in m3u8_url.lower() for kw in ["hls", "live", "stream", "tracks", "mono", "playlist", "chunks"]):
            
            slug = None
            
            # লিঙ্ক থেকে ডাইনামিকভাবে চ্যানেলের নাম (যেমন: tsn1, tsn3, tsn4) বের করা হচ্ছে
            slug_match = re.search(r'deviantart\.lovetier\.bz/([^/]+)/', m3u8_url)
            if slug_match:
                slug = slug_match.group(1).lower() # এটি হবে "tsn1" অথবা "tsn3"
                
            # যদি নাম খুঁজে না পায় তবে জেনেরিক নাম ব্যবহার করবে
            if not slug:
                slug = f"stream-{found_streams_count + 1}"
                
            print(f"  [FOUND] Active stream found: {m3u8_url}")
            update_cloudflare_kv(slug, m3u8_url)
            found_streams_count += 1
            
    if found_streams_count == 0:
        print("[NOT FOUND] No active streams found on NongorPlay page.")
    else:
        print(f"\n[COMPLETE] Successfully extracted and saved {found_streams_count} streams!")
