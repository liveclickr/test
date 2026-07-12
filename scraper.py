import requests
import re
import json

# আপনার ক্লাউডফ্লেয়ারের ডিটেইলস (এগুলো সিক্রেট হিসেবে থাকবে)
CF_ACCOUNT_ID = "YOUR_CLOUDFLARE_ACCOUNT_ID"
CF_KV_NAMESPACE_ID = "YOUR_KV_NAMESPACE_ID"
CF_API_TOKEN = "YOUR_CLOUDFLARE_API_TOKEN"

# যে চ্যানেলগুলো আপডেট করতে চান তার তালিকা
CHANNELS = {
    "ithh1xe7c01n2": "https://gxqkdba3q70p.48552462.net:8443/hls/",
    "g8yy3cfv128h5": "https://y4mpwzd7.12703830.net:8443/hls/"
}

# সোর্স সাইট বা গিটহাবের পেজ যেখান থেকে টোকেন রিড করতে হবে
# পরীক্ষার জন্য আমরা এমন একটি সোর্স ব্যবহার করব যেখানে এই লিঙ্কগুলো নিয়মিত আপডেট হয়
SOURCE_URL = "https://raw.githubusercontent.com/someuser/somerepo/main/live_links.txt" # এখানে আপনার টার্গেট সোর্স বসাবেন

def fetch_fresh_token(channel_id):
    try:
        response = requests.get(SOURCE_URL, timeout=10)
        if response.status_code == 200:
            content = response.text
            # Regex দিয়ে নির্দিষ্ট চ্যানেলের সচল টোকেনটি খুঁজে বের করা
            pattern = rf"{channel_id}\.m3u8\?(s=[a-zA-Z0-9_-]+&e=\d+)"
            match = re.search(pattern, content)
            if match:
                return match.group(1) # যেমন: s=fCv9PCNMgspC-bGsxHY_hA&e=1783851690
    except Exception as e:
        print(f"Error fetching token for {channel_id}: {e}")
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
    
    response = requests.put(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        print(f"Successfully updated KV for {channel_id}")
    else:
        print(f"Failed to update KV: {response.text}")

# মেইন রানার
for channel_id, base_url in CHANNELS.items():
    fresh_token = fetch_fresh_token(channel_id)
    if fresh_token:
        update_cloudflare_kv(channel_id, fresh_token, base_url)
    else:
        print(f"Could not find active token for {channel_id}")
