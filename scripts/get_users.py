# Gets all Akatsuki relax users and adds it to users.json file, will only add new users who aren't in the list
# This is also used for search players QUERY - Database not implement and just using .json files.

import asyncio
import aiohttp
import ujson as json
from datetime import datetime
import os

BASE_URL = "https://akatsuki.gg/api/v1/users"
LIMIT = 100
BATCH_SIZE = 10
MAX_RETRIES = 3
OUTPUT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "users.json"))

def load_existing_users():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            print("⚠ Failed to read users.json — starting fresh.")
    return []

def save_users(users):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    users.sort(key=lambda x: datetime.strptime(x["registered_on"], "%Y-%m-%dT%H:%M:%SZ"))
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

async def fetch_page(session, page, attempt=1):
    url = f"{BASE_URL}?p={page}&l={LIMIT}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                return page, data.get("users", [])
            else:
                print(f"❌ Page {page} failed (status {response.status})")
    except Exception as e:
        print(f"❌ Exception on page {page} (attempt {attempt}): {e}")
    return page, None

async def fetch_all_users():
    all_users = load_existing_users()
    seen_ids = {u["id"] for u in all_users}
    page = len(all_users) // LIMIT + 1
    failed_pages = set()
    finished = False

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=100)) as session:
        while not finished:
            tasks = [fetch_page(session, page + i) for i in range(BATCH_SIZE)]
            results = await asyncio.gather(*tasks)

            any_full = False
            for pg, users in results:
                if users is None:
                    failed_pages.add(pg)
                    continue
                new_users = [u for u in users if u["id"] not in seen_ids]
                if new_users:
                    all_users.extend(new_users)
                    seen_ids.update(u["id"] for u in new_users)
                    print(f"✅ Page {pg}: {len(new_users)} new users")
                if len(users) == LIMIT:
                    any_full = True

            save_users(all_users)

            if not any_full:
                print("🛑 No more full pages. Assuming end reached.")
                finished = True
            else:
                page += BATCH_SIZE

        # Retry failed pages
        if failed_pages:
            print(f"🔁 Retrying {len(failed_pages)} failed pages...")
            retries = 0
            while failed_pages and retries < MAX_RETRIES:
                retry_tasks = [fetch_page(session, pg, retries + 1) for pg in list(failed_pages)]
                results = await asyncio.gather(*retry_tasks)

                for pg, users in results:
                    if users is not None:
                        new_users = [u for u in users if u["id"] not in seen_ids]
                        if new_users:
                            all_users.extend(new_users)
                            seen_ids.update(u["id"] for u in new_users)
                            print(f"✅ Retried page {pg}: {len(new_users)} new users")
                        failed_pages.discard(pg)

                save_users(all_users)
                retries += 1

            if failed_pages:
                print(f"❌ Gave up on pages: {sorted(failed_pages)}")

    print(f"🎉 Done! Total users saved: {len(all_users)}")

if __name__ == "__main__":
    asyncio.run(fetch_all_users())
