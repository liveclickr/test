import os
import json
import requests
import time

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
    # flush=True ব্যবহারের কারণে গিটহাবে লগ সাথে সাথে প্রিন্ট হবে
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

    # ৩. পেজিনেশন (Pagination) লুপের মাধ্যমে সব চ্যানেল সংগ্রহ করা
    print("[*] Fetching channel list across all pages...", flush=True)
    raw_channels = []
    seen_channel_ids = set()
    page = 1
    total_items = 9999  
    
    while len(raw_channels) < total_items:
        # standard stalker api requirements: p parameter and JsHttpRequest
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
                
                # ডুপ্লিকেট চেকার: যদি এই পেজের সব চ্যানেল আগেই লোড হয়ে থাকে, তবে লুপ ভেঙে দেবে
                new_added = 0
                for ch in page_data:
                    ch_id = str(ch.get("id"))
                    if ch_id not in seen_channel_ids:
                        seen_channel_ids.add(ch_id)
                        raw_channels.append(ch)
                        new_added += 1
                
                print(f"[+] Page {page}: Processed {len(page_data)} channels (New added: {new_added}, Total: {len(raw_channels)}/{total_items})", flush=True)
                
                # যদি নতুন কোনো চ্যানেল এড না হয় বা পেজে সর্বোচ্চ আইটেমের চেয়ে কম ডাটা থাকে
                if new_added == 0 or len(page_data) < max_page_items or total_items == 0:
                    break
            elif isinstance(js_data, list):
                raw_channels = js_data
                break
            else:
                break
                
            page += 1
            time.sleep(0.5) # পোর্টাল ওভারলোড এড়ানোর জন্য সামান্য বিরতি
        except Exception as e:
            print(f"[!] Failed to fetch page {page}: {e}", flush=True)
            break

    if not raw_channels:
        print("[!] Channel list is empty.", flush=True)
        return

    print(f"[+] Successfully retrieved {len(raw_channels)} channels from portal. Processing stream links...", flush=True)

    processed_channels = []
    
    # স্ক্র্যাপ করার সর্বোচ্চ চ্যানেল সংখ্যা (পোর্টাল ব্যান এড়াতে প্রথম ১৫০টি রাখা হয়েছে, চাইলে বাড়াতে পারেন)
    limit = 150 
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
        create_link_url = f"{PORTAL_URL}server/load.php?type=itv&action=create_link&cmd={requests.utils.quote(cmd)}&forced_storage=0&disable_ad=0&JsHttpRequest=1-xml&token={token}"
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
            
            proxied_url = f"{PROXY_WORKER_URL}/hls?headers={headers_param}&url={requests.utils.quote(final_stream_url)}"

            processed_channels.append({
                "id": str(ch_id),
                "name": name,
                "url": proxied_url,
                "category": category,
                "logo": logo
            })
            print(f"[{index+1}/{min(len(raw_channels), limit)}] Processed: {name}", flush=True)

    # ৫. channels.json ফাইলে ডেটা সেভ করা
    output_data = {"channels": processed_channels}
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"[+] Database successfully updated with {len(processed_channels)} channels.", flush=True)

if __name__ == "__main__":
    fetch_data()
