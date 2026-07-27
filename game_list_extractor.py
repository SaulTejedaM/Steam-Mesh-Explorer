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

print("Database path:", db_path)


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
# STEAM APP LIST
# ==============================

def get_app_list(last_appid):


    params = {

        "key": API_KEY,

        "max_results": 200,

        "last_appid": last_appid

    }


    response = requests.get(
        BASE_URL,
        params=params
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
            timeout=10
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


        print(
            f"Player count error AppID {appid}: {e}"
        )


        return 0







# ==============================
# STEAM STORE DETAILS
# ==============================

def get_game_details(appid):


    params = {

        "appids": appid,

        "l": "english"

    }



    response = requests.get(
        DETAIL_URL,
        params=params
    )



    if response.status_code != 200:


        print(
            f"HTTP Error {response.status_code} for AppID {appid}"
        )


        return None




    data = response.json()



    if str(appid) not in data:

        return None




    if not data[str(appid)]["success"]:

        return None




    return data[str(appid)]["data"]







# ==============================
# STEAMSPY DETAILS
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
            timeout=10
        )



        if response.status_code != 200:

            return None




        return response.json()



    except Exception as e:


        print(
            f"SteamSpy error AppID {appid}: {e}"
        )


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



    release_date = data.get(
        "release_date",
        {}
    ).get(
        "date",
        None
    )



    tags = ""



    if steamspy_data:


        steamspy_tags = steamspy_data.get(
            "tags",
            {}
        )


        if isinstance(
            steamspy_tags,
            dict
        ):


            tags = ", ".join(
                steamspy_tags.keys()
            )






    cursor.execute("""


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

    ))



    conn.commit()







# ==============================
# MAIN
# ==============================

def main():


    last_appid = 0


    limit = 200


    processed = 0





    while True:



        print(
            f"\n===== Downloading from AppID {last_appid} ====="
        )



        response = get_app_list(
            last_appid
        )



        apps = response["response"]["apps"]





        for app in apps:



            if processed >= limit:


                print(
                    "\nLimit reached."
                )


                print(
                    f"{processed} games saved."
                )


                conn.close()


                return





            appid = app["appid"]



            print(
                f"\nChecking AppID: {appid}"
            )


            print(
                f"Listed name: {app['name']}"
            )




            active_players = get_active_players(
                appid
            )



            print(
                f"Active players: {active_players}"
            )






            details = get_game_details(
                appid
            )



            if details:



                print(
                    f"✓ Steam information: {details.get('name')}"
                )



                steamspy = get_steamspy_details(
                    appid
                )



                if steamspy:


                    print(
                        "✓ SteamSpy tags obtained"
                    )


                else:


                    print(
                        "✗ No SteamSpy data"
                    )





                save_game(

                    appid,

                    details,

                    steamspy,

                    active_players

                )



                processed += 1





                cursor.execute(
                    "SELECT COUNT(*) FROM steam_games"
                )



                total = cursor.fetchone()[0]



                print(
                    f"✓ Games saved: {processed}/{limit}"
                )


                print(
                    f"✓ Total database records: {total}"
                )



            else:


                print(
                    "✗ API returned no information."
                )




            time.sleep(0.5)







        new_last = response["response"].get(
            "last_appid",
            0
        )




        if new_last == last_appid or new_last == 0:


            print(
                "No more applications available."
            )


            break





        last_appid = new_last






    conn.close()






if __name__ == "__main__":
    main()
    