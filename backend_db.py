import json
import queue
import sqlite3
import threading
import time

import geopy.distance
import numpy as np
import requests

# Q q
# SustainAPPle

add_dummy_values = """INSERT INTO user (name, password, total_carbon_emissions, sustainability_points)
    VALUES ("Mourad2", "afds", 9369, 9369),
    ("Peter10", "afds", 6315, 6315),
    ("Hans", "afds", 6315, 6315),
    ("Omar1", "afds", 6315, 6315),
    ("Omar2", "afds", 6315, 6315),
    ("Omar3", "afds", 6315, 6315),
    ("Omar4", "afds", 6315, 6315),
    ("Hans2", "afds", 5196, 5196),
    ("Hans3", "afds", 5196, 5196),
    ("Hans4", "afds", 5196, 5196),
    ("Peter2", "afds", 4374, 4374),
    ("Peter3", "afds", 3172, 3172),
    ("Peter4", "afds", 2376, 2800),
    ("Peter4", "afds", 2376, 2500),
    ("Peter4", "afds", 2376, 1702),
    ("Peter4", "afds", 2376, 1584),
    ("Peter4", "afds", 2376, 1358),
    ("Peter4", "afds", 2376, 1129),
    ("Peter4", "afds", 2376, 1030),
    ("Peter4", "afds", 2376, 950),
    ("Peter5", "afds", 867, 760),
    ("Peter6", "afds", 597, 560),
    ("Peter7", "afds", 434, 400),
    ("Peter8", "afds", 356, 300),
    ("Omar5", "afds", 271, 100),
    ("Omar5", "afds", 271, 90),
    ("Omar5", "afds", 271, 80),
    ("Omar5", "afds", 271, 70),
    ("Omar5", "afds", 271, 60),
    ("Omar5", "afds", 271, 50),
    ("Omar5", "afds", 271, 40),
    ("Omar5", "afds", 271, 30),
    ("Omar5", "afds", 271, 20),
    ("Omar5", "afds", 271, 10),
    ("Omar2", "afds", 290, -1),
    ("Omar3", "afds", 275, -2),
    ("Omar4", "afds", 273, -3),
    ("Omar5", "afds", 271, -4),
    ("Donald", "afds", 250, -5),
    ("Olaf", "afds", 238, -10),
    ("Elon", "afds", 178, -23),
    ("Omar", "afds", 174, -135),
    ("Peter", "afds", 101, -1123),
    ("Mourad", "afds", 69, -1780)
    """  # 328

create_user_table = """CREATE TABLE IF NOT EXISTS user (
    id integer PRIMARY KEY,
    name text NOT NULL,
    password text NOT NULL,
    total_carbon_emissions real NOT NULL DEFAULT 0,
    velocity real NOT NULL default 0,
    transport_type text NOT NULL default "standing",
    m_by_feet real NOT NULL default 0,
    m_by_car real NOT NULL default 0,
    sustainability_points real NOT NULL DEFAULT 0);
    """

create_car_table = """CREATE TABLE IF NOT EXISTS cars (
    id integer PRIMARY KEY,
    user_id integer NOT NULL,
    brand text NOT NULL,
    model text NOT NULL,
    carbon_emission_g_m int NOT NULL);
    """

create_user = """INSERT INTO user (name, password)
    VALUES ("{0}", "{1}")
    """

add_car_to_user = """INSERT INTO cars (user_id, brand, model, carbon_emission_g_m)
    VALUES ({0}, "{1}", "{2}", {3})
    """

get_better_users = """SELECT count(id) FROM user WHERE sustainability_points <=
    (SELECT sustainability_points FROM user WHERE id={0})
    """

get_all_users = """SELECT count(id) FROM user
    """

get_car_id = """SELECT cars.id, cars.carbon_emission_g_m FROM cars INNER JOIN user ON user.id=cars.user_id
    WHERE user.id={0} AND cars.brand="{1}" and cars.model="{2}"
    """

update_emission = """UPDATE user SET total_carbon_emissions=
    (SELECT total_carbon_emissions FROM user WHERE user.id={0})+{1}
    WHERE user.id={0}
    """

update_sustainability_score = """UPDATE user SET sustainability_points=
    (SELECT sustainability_points FROM user WHERE user.id={0})+{1}
    WHERE user.id={0}
    """

update_velocity = """UPDATE user SET velocity={1} WHERE id={0}
    """

get_transport_type = """SELECT transport_type FROM user WHERE id={0}
    """

update_transport_type = """UPDATE user SET transport_type = CASE
    WHEN velocity < 2 THEN "standing"
    WHEN velocity < 10 THEN "walking"
    WHEN velocity < 30 THEN "running"
    WHEN velocity < 250 THEN "car"
    ELSE "plane"
    END WHERE id={0}
    """

update_feet = """UPDATE user SET m_by_feet =
    (SELECT m_by_feet FROM user WHERE user.id={0})+{1}
    WHERE user.id={0}
    """
update_car = """UPDATE user SET m_by_car =
    (SELECT m_by_car FROM user WHERE user.id={0})+{1}
    WHERE user.id={0}
    """

lock = threading.Lock()
event = threading.Event()


def get_distance(loc1, loc2):
    return geopy.distance.geodesic(loc1, loc2).m


def make_call():
    url = "https://api.radar.io/v1/users/ea8c84cb0724d057"
    headers = {
        "content-type": "application/json",
        "Authorization": "prj_test_sk_cb456d8c4743097abf573615ee9606cb2d275052",
    }
    resp = requests.get(url, headers=headers)
    return resp.json()["user"]["location"]["coordinates"]


version = "real_time"
# version = "car_simulated"
# version = "running_simulated"


def background_position_loop(q, timeout=0.5, version=False):
    coords = None
    data = []
    while not event.is_set():
        if version in ["car_simulated", "running_simulated"]:
            if coords is None or len(data) == 0:
                if version == "car_simulated":
                    data = json.load(open("positions_car_real.json", "rb"))
                elif version == "running_simulated":
                    data = json.load(open("positions_myself.json", "rb"))
                coords = data[0]
            new_coords = data[0]
            data.pop(0)
        else:
            new_coords = make_call()
            if coords is None:
                coords = new_coords
        dist = get_distance(new_coords, coords)
        coords = new_coords
        print(f"Update dist {dist}")
        if q.full():
            q.get_nowait()
        q.put_nowait(dist)
        time.sleep(timeout)


class Backend:
    def __init__(self, db_name="main.db", drop_db=False, timeout_bg=0.5, timeout_frontend=30):
        self.db_name = db_name
        self.queue = queue.Queue(maxsize=int(timeout_frontend / timeout_bg))
        self.bg_thread = None
        self.transport_type = "standing"
        self.m_by_feet = self.m_by_car = 0
        self.init_db(drop_db)

        self.__dict__.update(locals())

    def drop_tables(self):
        self.cursor.execute("DROP TABLE IF EXISTS user")
        self.cursor.execute("DROP TABLE IF EXISTS cars")
        self.conn.commit()

    def init_db(self, drop_db=False):
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()

        if drop_db:
            self.drop_tables()

        # init both tables
        self.cursor.execute(create_user_table)
        self.cursor.execute(create_car_table)
        nr_names = self.cursor.execute("SELECT count(id) FROM user").fetchone()[0]
        if nr_names <= 1:
            self.cursor.execute(add_dummy_values)
        self.conn.commit()

    def login_or_create_new_user(self, name, password):
        # see if user already exists
        nr_users = self.cursor.execute(f"SELECT * FROM user WHERE name='{name}'").fetchall()
        nr_users_w_pw = self.cursor.execute(
            f"SELECT * FROM user WHERE name='{name}' AND password='{password}'"
        ).fetchall()
        if len(nr_users) == 0:
            self.create_new_user(name, password)
            return 200, "Created new user"
        elif len(nr_users) == len(nr_users_w_pw) == 1:
            self.current_user = nr_users[0][0]  # save id
            return 200, "Logged in"
        else:
            return 404, "User already exists or password is wrong"

    def start_background_checks(self):
        if self.bg_thread is not None:
            event.set()
            self.bg_thread.join()
            while not self.queue.empty():
                self.queue.get_nowait()
            event.clear()
        self.bg_thread = threading.Thread(target=background_position_loop, args=(self.queue,))
        self.bg_thread.start()

    def select_car(self, brand, model):
        self.car_id, self.carbon_emission_g_m = self.cursor.execute(
            get_car_id.format(self.current_user, brand, model)
        ).fetchone()

    def update_carbon_emission(self):
        dists = []
        while not self.queue.empty():
            dists.append(self.queue.get_nowait())
        total_dist = np.sum(dists)
        add_emission = total_dist * self.carbon_emission_g_m
        velocity = total_dist / self.timeout_frontend * 3.6
        self.cursor.execute(update_velocity.format(self.current_user, velocity))
        self.cursor.execute(
            update_transport_type.format(
                self.current_user,
            )
        )
        transport_type = self.cursor.execute(get_transport_type.format(self.current_user)).fetchone()[0]
        multiplier = 1
        if transport_type == "standing":
            multiplier = 0
        elif transport_type == "walking":
            multiplier = -0.3
        elif transport_type == "running":
            multiplier = -0.6
        elif transport_type == "car":
            multiplier = 1
        multiplier *= 2
        self.transport_type = transport_type
        if transport_type in ["walking", "running"]:
            self.m_by_feet += total_dist
            self.cursor.execute(update_feet.format(self.current_user, total_dist))
        if transport_type == "car":
            self.m_by_car += total_dist
            self.cursor.execute(update_car.format(self.current_user, total_dist))
        if transport_type == "car":
            self.cursor.execute(update_emission.format(self.current_user, add_emission))
        self.cursor.execute(update_sustainability_score.format(self.current_user, add_emission * multiplier))

    def create_new_user(self, name, password):
        self.cursor.execute(create_user.format(name, password))
        self.conn.commit()
        self.current_user = self.cursor.lastrowid

    def add_car(self, brand, model, carbon_emission_g_m=1):
        self.carbon_emission_g_m = carbon_emission_g_m
        self.cursor.execute(add_car_to_user.format(self.current_user, brand, model, self.carbon_emission_g_m))
        self.conn.commit()
        self.start_background_checks()

    def get_current_percentage_position(self):
        nr_users = self.cursor.execute(get_all_users).fetchone()[0]
        nr_better_users = self.cursor.execute(get_better_users.format(self.current_user)).fetchone()[0]
        return nr_better_users / nr_users

    def get_data(self):
        data = self.cursor.execute(
            "SELECT id, name, total_carbon_emissions, sustainability_points FROM user ORDER BY sustainability_points ASC"
        ).fetchall()
        data = data[:10]
        for i in range(len(data)):
            data[i] = list(data[i])
            data[i][0] = i + 1
            # data[i][3] = f"{data[i][3]} \u127822"
        return data

    def get_carbon_emission(self):
        return self.cursor.execute(f"SELECT total_carbon_emissions FROM user WHERE id={self.current_user}").fetchone()[
            0
        ]


def update_frontend(backend, window, timeout=30):
    while not event.is_set():
        if backend.queue.empty():
            event.set()
            print(backend.get_data())
            break
        print("Big update")
        backend.update_carbon_emission()

        window["carbon_emissions"].update(f"{backend.get_carbon_emission():.1f}g")
        perc = 100 * (1 - backend.get_current_percentage_position())
        window["apples"].update(f"{perc:.0f}/100 apples")
        window["mode"].update(backend.transport_type)
        window["m_by_car"].update(f"{backend.m_by_car/1000:.2f}km")
        window["m_by_feet"].update(f"{backend.m_by_feet:.1f}m")
        time.sleep(timeout)


if __name__ == "__main__":
    backend = Backend(drop_db=True, timeout_frontend=20)
    print(backend.login_or_create_new_user("Fabian", "Password"))
    print(backend.login_or_create_new_user("Felix", "Password2"))
    print(backend.login_or_create_new_user("Fabian", "p3"))
    print(backend.login_or_create_new_user("Fabian", "Password"))
    backend.add_car("Tesla", "Y")
    print(backend.cursor.execute("SELECT * FROM user").fetchall())
    print(backend.cursor.execute("SELECT * FROM cars").fetchall())
    print(backend.select_car("Tesla", "Y"))

    fg_thread = threading.Thread(target=update_frontend, args=(backend, backend.timeout_frontend))
    fg_thread.start()
    fg_thread.join()

    print(backend.get_current_percentage_position())
    # print(backend.update_carbon_emission())
    # print(backend.cursor.execute("SELECT * FROM user").fetchall())
    # print(backend.cursor.execute("SELECT * FROM cars").fetchall())
    # print(backend.__dict__)
