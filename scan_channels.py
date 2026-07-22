import os
import json
import requests
import time

# ---------------- CONFIGURATION ----------------
PORTAL_URL = "http://innovationdns.eu:80/c/"
MAC_ADDRESS = "00:1A:79:11:C4:7A"
# আপনার দেওয়া ক্লাউডফ্লেয়ার প্রক্সি URL
PROXY_WORKER_URL = "https://workerreverseproxy.mafejur8990.workers.dev" 
# আপনি সর্বোচ্চ কতটি সচল চ্যানেল লোড করতে চান
CHANNEL_LIMIT = 150 
# -----------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
    "X-User-Agent": "Model: MAG250; Link: WiFi",
    "Referer": PORTAL_URL,
    "Cookie": f"mac={MAC_ADDRESS}"
}

def fetch_data():
    print("[*] Initiating handshake with Stalker Portal...", flush=True)
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # ১. হ্যান্ডশেক এবং টোকেন রিকোয়েস্ট
    handshake_url = f"{PORTAL_URL}server/load.php?type=stb&action=handshake&JsHttpRequest=1-xml"
    try:
        response = session.get(handshake_url, timeout=15)
        response_data = response.json()
        token = response_data.get("js", {}).get("token")
    except Exception as e:
        print(f"[!] Handshake failed: {e}", flush=True)
        return

    if not token:
        print("[!] Authorization Token could not be retrieved.", flush=True)
        return
    print(f"[+] Token generated successfully: {token[:8]}...", flush=True)

    # ২. ক্যাটাগরি (Genres) ম্যাপ করা
    genres_url = f"{PORTAL_URL}server/load.php?type=itv&action=get_genres&JsHttpRequest=1-xml&token={token}"
    genres_map = {}
    try:
        g_res = session.get(genres_url, timeout=15).json()
        for genre in g_res.get("js", []):
            genres_map[str(genre.get("id"))] = genre.get("title", "Live TV")
    except Exception:
        pass

    # ৩. পেজিনেশন (Pagination) লুপের মাধ্যমে লিমিট অনুযায়ী চ্যানেল সংগ্রহ করা
    print("[*] Fetching channel list across pages...", flush=True)
    raw_channels = []
    seen_channel_ids = set()
    page = 1
    total_items = 9999  
    
    while len(raw_channels) < total_items:
        if len(raw_channels) >= CHANNEL_LIMIT:
            print(f"[*] Reached target limit of {CHANNEL_LIMIT} channels. Stopping page fetch.", flush=True)
            break

        channels_url = f"{PORTAL_URL}server/load.php?type=itv&action=get_ordered_list&p={page}&JsHttpRequest=1-xml&token={token}"
        try:
            ch_res = session.get(channels_url, timeout=15).json()
            js_data = ch_res.get("js", {})
            
            if isinstance(js_data, dict):
                page_data = js_data.get("data", [])
                total_items = int(js_data.get("total_items", 0))
                max_page_items = int(js_data.get("max_page_items", 14))
                
                if not page_data:
                    break
                
                new_added = 0
                for ch in page_data:
                    ch_id = str(ch.get("id"))
                    if ch_id not in seen_channel_ids:
                        seen_channel_ids.add(ch_id)
                        raw_channels.append(ch)
                        new_added += 1
                
                print(f"[+] Page {page}: Processed {len(page_data)} channels (New added: {new_added}, Total: {len(raw_channels)}/{total_items})", flush=True)
                
                if new_added == 0 or len(page_data) < max_page_items or total_items == 0:
                    break
            elif isinstance(js_data, list):
                raw_channels = js_data
                break
            else:
                break
                
            page += 1
            time.sleep(0.1)
        except Exception as e:
            print(f"[!] Failed to fetch page {page}: {e}", flush=True)
            break

    if not raw_channels:
        print("[!] Channel list is empty.", flush=True)
        return

    raw_channels = raw_channels[:CHANNEL_LIMIT]
    print(f"[+] Successfully retrieved {len(raw_channels)} channels. Structuring play URLs...", flush=True)

    processed_channels = []
    
    for index, ch in enumerate(raw_channels):
        ch_id = str(ch.get("id"))
        name = ch.get("name", "Unknown Channel")
        genre_id = str(ch.get("tv_genre_id", ""))
        category = genres_map.get(genre_id, "Live TV")
        logo = ch.get("logo", "")

        # 💡 [IP-Binding এবং টোকেন বাইপাস সলিউশন]:
        # গিটহাব রানার আইপিতে জেনারেট করা টোকেন অন্য কোথাও চলে না।
        # তাই আমরা সরাসরি পোর্টালের স্ট্যান্ডার্ড ডিরেক্ট লিঙ্ক জেনারেট করব যা ক্লাউডফ্লেয়ার ওয়ার্কারের মাধ্যমে অন-ডিমান্ড প্লে হবে।
        final_stream_url = f"{PORTAL_URL}play/live.php?mac={MAC_ADDRESS}&stream={ch_id}&extension=m3u8"

        stalker_headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Cookie": HEADERS["Cookie"]
        }
        headers_param = requests.utils.quote(json.dumps(stalker_headers))
        
        proxied_url = f"{PROXY_WORKER_URL}/hls?headers={headers_param}&url={requests.utils.quote(final_stream_url)}"

        processed_channels.append({
            "id": ch_id,
            "name": name,
            "url": proxied_url,
            "category": category,
            "logo": logo
        })
        print(f"[{index+1}/{len(raw_channels)}] Formatted: {name}", flush=True)

    # ৫. channels.json ফাইলে ডেটা সেভ করা
    output_data = {"channels": processed_channels}
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"[+] Database successfully updated with {len(processed_channels)} channels.", flush=True)

if __name__ == "__main__":
    fetch_data()
