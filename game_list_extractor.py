import requests
import sqlite3
import time
import os
import json

# ==============================
# LOAD CONFIG
# ==============================

script_folder = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_folder, "config.json")

if not os.path.exists(config_path):
    raise FileNotFoundError(f"Config file not found: {config_path}")

with open(config_path, "r", encoding="utf-8") as file:
    config = json.load(file)

API_KEY = config["steam_api_key"]

BASE_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
DETAIL_URL = "https://store.steampowered.com/api/appdetails"
STEAMSPY_URL = "https://steamspy.com/api.php"
PLAYER_COUNT_URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"

# ==============================
# DATABASE
# ==============================

db_path = os.path.join(script_folder, "steam.db")

print("Database:", db_path)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS steam_games (
    id INTEGER PRIMARY KEY,
    name TEXT,
    genres TEXT,
    categories TEXT,
    tags TEXT,
    description TEXT,
    developer TEXT,
    publisher TEXT,
    release_date TEXT,
    header_image TEXT,
    background_image TEXT,
    active_players INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

# ==============================
# LAST APPID STORED
# ==============================

def get_last_saved_appid():
    cursor.execute("SELECT MAX(id) FROM steam_games")
    row = cursor.fetchone()

    if row is None:
        return 0

    if row[0] is None:
        return 0

    return int(row[0])

# ==============================
# GET APP LIST
# ==============================

def get_app_list(last_appid):

    params = {
        "key": API_KEY,
        "last_appid": last_appid,
        "max_results": 5000
    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    return response.json()

# ==============================
# ACTIVE PLAYERS
# ==============================

def get_active_players(appid):

    params = {
        "appid": appid
    }

    try:

        response = requests.get(
            PLAYER_COUNT_URL,
            params=params,
            timeout=15
        )

        if response.status_code != 200:
            return 0

        data = response.json()

        return data.get(
            "response",
            {}
        ).get(
            "player_count",
            0
        )

    except Exception as e:

        print(f"Player count error {appid}: {e}")

        return 0

# ==============================
# STORE DETAILS
# ==============================

def get_game_details(appid):

    params = {
        "appids": appid,
        "l": "english"
    }

    try:

        response = requests.get(
            DETAIL_URL,
            params=params,
            timeout=20
        )

        if response.status_code != 200:
            return None

        data = response.json()

        if str(appid) not in data:
            return None

        if not data[str(appid)]["success"]:
            return None

        return data[str(appid)]["data"]

    except Exception as e:

        print(f"Store error {appid}: {e}")

        return None

# ==============================
# STEAMSPY
# ==============================

def get_steamspy_details(appid):

    params = {
        "request": "appdetails",
        "appid": appid
    }

    try:

        response = requests.get(
            STEAMSPY_URL,
            params=params,
            timeout=15
        )

        if response.status_code != 200:
            return None

        return response.json()

    except Exception as e:

        print(f"SteamSpy error {appid}: {e}")

        return None
# ==============================
# SAVE GAME
# ==============================

def save_game(appid, data, steamspy_data, active_players):

    genres = ", ".join(
        genre["description"]
        for genre in data.get(
            "genres",
            []
        )
    )

    categories = ", ".join(
        category["description"]
        for category in data.get(
            "categories",
            []
        )
    )

    developers = ", ".join(
        data.get(
            "developers",
            []
        )
    )

    publishers = ", ".join(
        data.get(
            "publishers",
            []
        )
    )

    release_date = (
        data.get(
            "release_date",
            {}
        ).get(
            "date",
            None
        )
    )

    tags = ""

    if steamspy_data:

        steamspy_tags = steamspy_data.get(
            "tags",
            {}
        )

        if isinstance(steamspy_tags, dict):

            tags = ", ".join(
                steamspy_tags.keys()
            )

    cursor.execute(
        """
        INSERT INTO steam_games (
            id,
            name,
            genres,
            categories,
            tags,
            description,
            developer,
            publisher,
            release_date,
            header_image,
            background_image,
            active_players
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id)
        DO UPDATE SET
            name = excluded.name,
            genres = excluded.genres,
            categories = excluded.categories,
            tags = excluded.tags,
            description = excluded.description,
            developer = excluded.developer,
            publisher = excluded.publisher,
            release_date = excluded.release_date,
            header_image = excluded.header_image,
            background_image = excluded.background_image,
            active_players = excluded.active_players,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            appid,
            data.get("name"),
            genres,
            categories,
            tags,
            data.get("short_description"),
            developers,
            publishers,
            release_date,
            data.get("header_image"),
            data.get("background"),
            active_players
        )
    )

    conn.commit()


# ==============================
# PROCESS ONE GAME
# ==============================

def process_game(appid):

    print("-" * 60)
    print(f"AppID : {appid}")

    active_players = get_active_players(appid)

    print(f"Players : {active_players}")

    details = get_game_details(appid)

    if details is None:

        print("No Steam Store information.")

        return False

    print(f"Game : {details.get('name')}")

    steamspy = get_steamspy_details(appid)

    if steamspy:
        print("SteamSpy OK")
    else:
        print("SteamSpy unavailable")

    save_game(
        appid,
        details,
        steamspy,
        active_players
    )

    print("Saved.")

    return True


# ==============================
# UPDATE DATABASE
# ==============================

def update_database():

    last_saved = get_last_saved_appid()

    print()
    print("=" * 60)
    print(f"Last AppID stored : {last_saved}")
    print("=" * 60)

    total_added = 0

    while True:

        response = get_app_list(last_saved)

        response_data = response.get(
            "response",
            {}
        )

        apps = response_data.get(
            "apps",
            []
        )

        if not apps:

            print("No new applications found.")

            break

        print()
        print(f"Downloaded {len(apps)} new AppIDs")

        for app in apps:

            appid = app["appid"]

            try:

                if process_game(appid):
                    total_added += 1

            except Exception as e:

                print(f"Unexpected error {appid}: {e}")

            time.sleep(0.5)

        new_last = response_data.get(
            "last_appid",
            0
        )

        if new_last == 0:

            print("Steam returned last_appid = 0")

            break

        if new_last == last_saved:

            print("No more new applications.")

            break

        last_saved = new_last

        print()
        print(f"Next request will start from AppID {last_saved}")

    return total_added
# ==============================
# MAIN
# ==============================

def main():

    start = time.time()

    try:

        print()
        print("=" * 60)
        print("STEAM DATABASE UPDATER")
        print("=" * 60)

        added = update_database()

        cursor.execute("SELECT COUNT(*) FROM steam_games")
        total = cursor.fetchone()[0]

        print()
        print("=" * 60)
        print("UPDATE FINISHED")
        print("=" * 60)
        print(f"New games added : {added}")
        print(f"Total games     : {total}")

        cursor.execute("SELECT MAX(id) FROM steam_games")
        last = cursor.fetchone()[0]

        print(f"Last AppID      : {last}")

        elapsed = time.time() - start

        print(f"Elapsed time    : {elapsed:.2f} seconds")

    except KeyboardInterrupt:

        print()
        print("Interrupted by user.")

    except Exception as e:

        print()
        print(f"Fatal error: {e}")

    finally:

        conn.commit()
        conn.close()

        print("Database closed.")


# ==============================
# ENTRY POINT
# ==============================

if __name__ == "__main__":
    main()