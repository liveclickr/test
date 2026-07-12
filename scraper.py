import os
import re
import json
import base64
import urllib.parse
import requests

# ক্লাউডফ্লেয়ার এনভায়রনমেন্ট ভ্যারিয়েবল (ডট স্ট্রিপ করা হয়েছে যাতে কোনো স্পেসের কারণে ৭০০৩ এরর না আসে)
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "").strip()
CF_KV_NAMESPACE_ID = os.environ.get("CF_KV_NAMESPACE_ID", "").strip()
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "").strip()

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
                
            # রিলেティブ লিঙ্ক খোঁজা হচ্ছে (/2026/07/post.html)
            pattern2 = r'href=["\'](/\d{4}/\d{2}/[^"\']+\.html)'
            matches2 = re.findall(pattern2, html)
            for m in matches2:
                links.add("https://m3uworld4k.blogspot.com" + m)
                
            print(f"[SUCCESS] Found {len(links)} unique post links on homepage.")
    except Exception as e:
        print(f"[ERROR] Failed to fetch homepage: {e}")
    return list(links)

def fetch_url_content(url):
    # সোর্স পেজের মোবাইল ভিউ লেআউট নিশ্চিত করার জন্য শেষে ?m=1 যুক্ত করা হচ্ছে
    if "blogspot.com" in url and "?m=1" not in url and "&m=1" not in url:
        if "?" in url:
            url += "&m=1"
        else:
            url += "?m=1"
            
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
    return ""

def get_embedded_sources(html):
    # ১. আইফ্রেম সোর্স খোঁজা হচ্ছে
    iframe_urls = re.findall(r'<iframe[^>]+src=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
    # ২. জাভাস্ক্রিপ্ট স্ক্রিপ্ট সোর্স খোঁজা হচ্ছে
    script_urls = re.findall(r'<script[^>]+src=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
    # ৩. পেজের ভেতর থাকা সমস্ত নরমাল ইউআরএল
    raw_urls = re.findall(r'(https?://[^\s"\'><]+)', html)
    
    valid_urls = []
    # স্ট্রিমিং প্লেয়ারের কমন ডোমেন কিওয়ার্ড ফিল্টার
    player_keywords = ["qzz.io", "trophystream", "lovetier", "deviantart", "grita", "thebosstv", "stream", "player", "embed", "videx", "gomstream"]
    
    all_found = iframe_urls + script_urls + raw_urls
    for url in all_found:
        url_clean = url.replace('\\', '').split('"')[0].split("'")[0]
        if any(kw in url_clean.lower() for kw in player_keywords):
            if url_clean not in valid_urls:
                valid_urls.append(url_clean)
    return valid_urls

def decode_base64_in_html(html_content):
    # পেজে যদি কোনো বেস-৬৪ এনক্রিপ্ট করা স্ট্রিং থাকে তবে তা খুঁজে বের করা হচ্ছে
    b64_pattern = r'[a-zA-Z0-9+/]{24,}'
    matches = re.findall(b64_pattern, html_content)
    decoded_content = ""
    for m in matches:
        try:
            padded_m = m + "=" * ((4 - len(m) % 4) % 4)
            decoded = base64.b64decode(padded_m).decode("utf-8", errors="ignore")
            if "http" in decoded or "m3u8" in decoded:
                decoded_content += "\n" + decoded
        except Exception:
            pass
    return decoded_content

def extract_m3u8_from_html(html):
    # ইউআরএল ডিকোড করা হচ্ছে
    decoded_html = urllib.parse.unquote(html)
    # যেকোনো .m3u8 লিঙ্ক খুঁজে বের করার প্যাটার্ন
    m3u8_links = re.findall(r'(https?://[^\s"\'><]+\.m3u8(?:\?[^\s"\'><]+)?)', decoded_html)
    return m3u8_links

def update_cloudflare_kv(slug, stream_url):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{slug}"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "text/plain" # সরাসরি টেক্সট হিসেবে ফুল লিঙ্ক সেভ করা হচ্ছে
    }
    r = requests.put(url, headers=headers, data=stream_url)
    if r.status_code == 200:
        print(f"  [KV SAVED] Key '{slug}' is updated with URL: {stream_url}")
    else:
        print(f"  [KV ERROR] Failed to save '{slug}': {r.text}")

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
        slug_match = re.search(r'/([^/]+)\.html', post)
        if not slug_match:
            continue
        slug = slug_match.group(1)
        print(f"\nProcessing post: '{slug}' ({post})")
        
        post_html = fetch_url_content(post)
        if not post_html:
            continue
            
        compiled_html = post_html
        
        # ১. প্লেয়ার এবং জাভাস্ক্রিপ্ট আইফ্রেম সোর্স পেজ সংগ্রহ করা হচ্ছে
        embedded_sources = get_embedded_sources(post_html)
        for embed_url in embedded_sources:
            print(f"  -> Fetching embedded player/script: {embed_url}")
            embed_html = fetch_url_content(embed_url)
            if embed_html:
                compiled_html += "\n" + embed_html
                
        # ২. পেজের ভেতর থাকা বেস-৬৪ ডিকোড করা হচ্ছে
        b64_decoded = decode_base64_in_html(post_html)
        if b64_decoded:
            print("  -> Decoded base64 data found.")
            compiled_html += "\n" + b64_decoded
                
        # ৩. সম্পূর্ণ সংকলিত কন্টেন্ট থেকে .m3u8 লিঙ্ক খোঁজা হচ্ছে
        m3u8_urls = extract_m3u8_from_html(compiled_html)
        
        found_stream = False
        for m3u8_url in m3u8_urls:
            if any(kw in m3u8_url.lower() for kw in ["hls", "live", "stream", "tracks", "mono", "playlist", "chunks"]):
                print(f"  [FOUND] Working stream for '{slug}': {m3u8_url}")
                update_cloudflare_kv(slug, m3u8_url)
                found_stream = True
                break
                
        if not found_stream:
            print(f"  [NOT FOUND] No active stream found inside '{slug}' post.")
