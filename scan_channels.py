import os
import json
import requests

# ---------------- CONFIGURATION ----------------
PORTAL_URL = "http://innovationdns.eu:80/c/"
MAC_ADDRESS = "00:1A:79:11:C4:7A"
# আপনার দেওয়া ক্লাউডফ্লেয়ার প্রক্সি URL
PROXY_WORKER_URL = "https://workerreverseproxy.mafejur8990.workers.dev" 
# -----------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
    "X-User-Agent": "Model: MAG250; Link: WiFi",
    "Referer": PORTAL_URL,
    "Cookie": f"mac={MAC_ADDRESS}"
}

def clean_stream_url(cmd_str):
    """স্টকার কমান্ড থেকে রিয়েল স্ট্রিমিং লিঙ্ক আলাদা করে"""
    if not cmd_str:
        return ""
    cleaned = cmd_str.strip()
    if cleaned.startswith("ffrt "):
        cleaned = cleaned[5:]
    elif cleaned.startswith("ffmpeg "):
        cleaned = cleaned[7:]
    return cleaned

def fetch_data():
    print("[*] Initiating handshake with Stalker Portal...")
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # ১. হ্যান্ডশেক এবং টোকেন রিকোয়েস্ট
    handshake_url = f"{PORTAL_URL}server/load.php?type=stb&action=handshake"
    try:
        response = session.get(handshake_url, timeout=15)
        response_data = response.json()
        token = response_data.get("js", {}).get("token")
    except Exception as e:
        print(f"[!] Handshake failed: {e}")
        return

    if not token:
        print("[!] Authorization Token could not be retrieved.")
        return
    print(f"[+] Token generated successfully: {token[:8]}...")

    # ২. ক্যাটাগরি (Genres) ম্যাপ করা
    genres_url = f"{PORTAL_URL}server/load.php?type=itv&action=get_genres&token={token}"
    genres_map = {}
    try:
        g_res = session.get(genres_url, timeout=15).json()
        for genre in g_res.get("js", []):
            genres_map[str(genre.get("id"))] = genre.get("title", "Live TV")
    except Exception:
        pass

    # ৩. চ্যানেলের তালিকা সংগ্রহ করা
    channels_url = f"{PORTAL_URL}server/load.php?type=itv&action=get_ordered_list&token={token}"
    try:
        ch_res = session.get(channels_url, timeout=15).json()
        raw_channels = ch_res.get("js", {}).get("data", []) or ch_res.get("js", [])
    except Exception as e:
        print(f"[!] Failed to get channel list: {e}")
        return

    if not raw_channels:
        print("[!] Channel list is empty.")
        return

    print(f"[+] Retrieved {len(raw_channels)} channels. Generating fresh links...")

    processed_channels = []
    
    # প্রথম ১০০টি মেইন চ্যানেল প্রসেস করার লিমিট
    limit = 100 
    for index, ch in enumerate(raw_channels[:limit]):
        ch_id = ch.get("id")
        name = ch.get("name", "Unknown Channel")
        genre_id = str(ch.get("tv_genre_id", ""))
        category = genres_map.get(genre_id, "Live TV")
        logo = ch.get("logo", "")
        cmd = ch.get("cmd", "")

        if not cmd:
            continue

        # ৪. লাইভ প্লে-এবল লিঙ্ক জেনারেশন
        create_link_url = f"{PORTAL_URL}server/load.php?type=itv&action=create_link&cmd={requests.utils.quote(cmd)}&forced_storage=0&disable_ad=0&token={token}"
        try:
            link_res = session.get(create_link_url, timeout=10).json()
            raw_stream_link = link_res.get("js", {}).get("cmd", "")
            final_stream_url = clean_stream_url(raw_stream_link)
        except Exception:
            final_stream_url = ""

        if not final_stream_url:
            final_stream_url = clean_stream_url(cmd)

        if final_stream_url:
            stalker_headers = {
                "User-Agent": HEADERS["User-Agent"],
                "Cookie": HEADERS["Cookie"]
            }
            headers_param = requests.utils.quote(json.dumps(stalker_headers))
            
            # প্রক্সি ওয়ার্কারের মাধ্যমে লিঙ্ক বিল্ড করা
            proxied_url = f"{PROXY_WORKER_URL}/hls?headers={headers_param}&url={requests.utils.quote(final_stream_url)}"

            processed_channels.append({
                "id": str(ch_id),
                "name": name,
                "url": proxied_url,
                "category": category,
                "logo": logo
            })
            print(f"[{index+1}/{limit}] Processed: {name}")

    # ৫. channels.json ফাইলে ডেটা সেভ করা
    output_data = {"channels": processed_channels}
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print("[+] Database successfully updated in channels.json")

if __name__ == "__main__":
    fetch_data()
