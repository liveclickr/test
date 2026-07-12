import os
import re
import urllib.parse
import requests

# ক্লাউডফ্লেয়ার এনভায়রনমেন্ট ভ্যারিয়েবল
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
CF_KV_NAMESPACE_ID = os.environ.get("CF_KV_NAMESPACE_ID")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")

# স্ট্যান্ডার্ড ব্রাউজার রিকোয়েস্ট নিশ্চিত করার জন্য হেডারস
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
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

def fetch_url_content(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
    return ""

def get_iframe_sources(html):
    # এইচটিএমএল এর ভেতর থাকা সমস্ত প্লেয়ার লিঙ্ক খুঁজে বের করা
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
    # ইউআরএল ডিকোড করা হচ্ছে (যাতে URL-encoded .m3u8 লিঙ্কগুলোও ধরা পড়ে)
    decoded_html = urllib.parse.unquote(html)
    # যেকোনো .m3u8 লিঙ্ক খুঁজে বের করার প্যাটার্ন
    m3u8_links = re.findall(r'(https?://[^\s"\'><]+\.m3u8(?:\?[^\s"\'><]+)?)', decoded_html)
    return m3u8_links

def update_cloudflare_kv(slug, stream_url):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{slug}"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "text/plain" # সরাসরি টেক্সট ফরমেটে ফুল লিঙ্কটি রাইট করা হচ্ছে
    }
    r = requests.put(url, headers=headers, data=stream_url)
    if r.status_code == 200:
        print(f"[KV SAVED] Key '{slug}' is updated with URL: {stream_url}")
    else:
        print(f"[KV ERROR] Failed to save '{slug}': {r.text}")

if __name__ == "__main__":
    if not CF_ACCOUNT_ID or not CF_KV_NAMESPACE_ID or not CF_API_TOKEN:
        print("[CRITICAL] Missing Cloudflare credentials!")
        exit(1)
        
    print("Step 1: Finding post links on homepage...")
    posts = get_post_links()
    
    if not posts:
        print("[CRITICAL] Could not find any post links on the homepage!")
        exit(1)
        
    print("Step 2: Processing each post dynamically...")
    for post in posts:
        # পোস্ট লিঙ্ক থেকে স্লাগ (যেমন: tsn-4 বা somoy) আলাদা করা হচ্ছে
        slug_match = re.search(r'/([^/]+)\.html', post)
        if not slug_match:
            continue
        slug = slug_match.group(1)
        print(f"\nProcessing post: '{slug}' ({post})")
        
        # পোস্টের কন্টেন্ট রিড করা হচ্ছে
        post_html = fetch_url_content(post)
        if not post_html:
            continue
            
        compiled_html = post_html
        iframes = get_iframe_sources(post_html)
        for iframe_url in iframes:
            print(f"  -> Fetching embedded player: {iframe_url}")
            iframe_html = fetch_url_content(iframe_url)
            if iframe_html:
                compiled_html += "\n" + iframe_html
                
        # সম্পূর্ণ কন্টেন্ট থেকে .m3u8 লিঙ্ক খোঁজা হচ্ছে
        m3u8_urls = extract_m3u8_from_html(compiled_html)
        
        found_stream = False
        for m3u8_url in m3u8_urls:
            # বিজ্ঞাপন এড়াতে রিয়াল লাইভ স্ট্রিমের কিওয়ার্ড ফিল্টার
            if any(kw in m3u8_url.lower() for kw in ["hls", "live", "stream", "tracks", "mono", "playlist", "chunks"]):
                print(f"  [FOUND] Working stream for '{slug}': {m3u8_url}")
                update_cloudflare_kv(slug, m3u8_url)
                found_stream = True
                break # ১ম ওয়ার্কিং লিঙ্কটি পাওয়ামাত্র লুপ ব্রেক করা হচ্ছে
                
        if not found_stream:
            print(f"  [NOT FOUND] No active stream found inside '{slug}' post.")
