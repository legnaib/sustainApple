import threading

import PySimpleGUI as sg

from backend_db import Backend
from backend_db import event as backend_event
from backend_db import update_frontend

granted = False
backend = Backend(drop_db=True, timeout_frontend=20)

global window_login
sg.theme("DarkBlue9")


def grant():
    global granted
    granted = True


def login(username, password):
    success = False
    file = open("user_detail.txt", "r")
    for i in file:
        a, b = i.split(",")
        b = b.strip()
        if a == username and b == password:
            success = True
            break
    file.close()
    if success:
        grant()
        backend.login_or_create_new_user(username, password)
    else:
        sg.popup_error("Invalid Username or Password.")
        begin()


def register(username, password):
    file = open("user_detail.txt", "r")
    for i in file:
        a, b = i.split(",")
        if a == username or password == "":
            print(username, password)
            sg.popup_error("Invalid username or password.")
            layout = [
                [sg.Text("Enter your Name and Password to Register")],
                [sg.Text("New Username "), sg.Input()],
                [sg.Text("New Password "), sg.Input()],
                [sg.Button("Continue")],
            ]
            window = sg.Window("sustainApple", layout)
            event, values = window.read()
            username = values[0]
            password = values[1]
            register(username, password)
    file = open("user_detail.txt", "a")
    file.write("\n" + str(username) + "," + str(password))
    grant()
    backend.login_or_create_new_user(username, password)


def access(option):
    global username, window_login
    window_login.close()
    if option == "Log in":
        layout = [[sg.Text("Username "), sg.Input()], [sg.Text("Password "), sg.Input()], [sg.Button("Continue")]]
        window = sg.Window("sustainApple", layout, size=(300, 100))
        event, values = window.read()
        username = values[0]
        password = values[1]
        login(username, password)
    else:
        layout = [
            [sg.Text("Enter your Name and Password to Register")],
            [sg.Text("New Username "), sg.Input()],
            [sg.Text("New Password "), sg.Input()],
            [sg.Button("Continue")],
        ]
        window = sg.Window("sustainApple", layout)
        event, values = window.read()
        username = values[0]
        password = values[1]
        register(username, password)
    if event == sg.WIN_CLOSED:
        window.close()
    window.close()


def begin():
    global option, window_login
    layout = [[sg.Text("")], [sg.Button("Log in"), sg.Button("Register")], [sg.Text("")]]
    window_login = sg.Window("sustainApple", layout, size=(300, 100), element_justification="c")

    event, values = window_login.read()
    option = event
    if event == sg.WIN_CLOSED:
        window_login.close()


begin()
access(option)

while True:
    if granted:
        layout = [[sg.Text("Welcome to SustainApple, " + username + "!")], [sg.Button("Continue")]]
        window = sg.Window("sustainApple", layout)
        event, values = window.read()
        if event == "Continue" or event == sg.WIN_CLOSED:
            window.close()
    import pandas as pd

    our_db = pd.read_csv("OUR DB - Alphabet.csv")
    our_db["Model"] = our_db["Mk"] + " -- " + our_db["Cn"]
    our_db["em"] = our_db["e (g/km)"] / 1000
    # our_db.sort_values(by="Model")
    print(our_db["Model"][:10])
    layout = [
        [sg.Text("Add your car")],
        [sg.Text("Model"), sg.Combo(our_db["Model"].tolist(), key="combo")],
        [sg.Button("Add")],
    ]
    window = sg.Window("sustainApple", layout)
    event, values = window.read()
    if event == "Add":
        idx = 0
        full_model = values["combo"]
        brand, model = full_model.split(" -- ")
        # print(our_db[["Mk", "Cn", "em"]])
        carbon_emission_g_m = list(our_db[our_db["Model"] == full_model]["em"])[0]
        # brand, model, carbon_emission_g_m = our_db[["Mk", "Cn", "em"]].iloc(idx)
        backend.add_car(brand, model, carbon_emission_g_m)
        window.close()

    headings = ["Place", "Name", "carbon emissions (g)"]
    data = backend.get_data()
    layout = [
        [
            sg.Text("Your current car:"),
            sg.Text(full_model),
            sg.Text(" with carbon emissions of "),
            sg.Text(f"{carbon_emission_g_m*1000} g/km.", key="car_em"),
        ],
        [sg.Text("Your current carbon emissions because of transport:"), sg.Text("-", key="carbon_emissions")],
        [sg.Text("Your current mode of transport is:"), sg.Text("standing", key="mode")],
        [sg.Text("Your sustainability score is"), sg.Text("0 apples", key="apples")],
        [sg.Text("")],
        [sg.Text("You traveled on your feet"), sg.Text("-", key="m_by_feet")],
        [sg.Text("You traveled by car"), sg.Text("-", key="m_by_car")],
        [sg.Table(values=data, headings=headings)],
        [sg.Button("Start tracking"), sg.Button("Stop tracking")],
    ]
    window = sg.Window("sustainApple", layout)
    event, values = window.read()
    if event == "Start tracking":
        # backend.start_background_checks()
        fg_thread = threading.Thread(target=update_frontend, args=(backend, window, backend.timeout_frontend))
        fg_thread.start()

        event, values = window.read()
        if event == "Stop tracking":
            backend_event.set()
            fg_thread.join()
        # fg_thread.join()
        # window["carbon_emissions"].update(str(10))
        # perc = 100 * (1 - backend.get_current_percentage_position())
        # window["apples"].update(f"{perc:.0f}/100 apples")

    # layout = [[sg.Button("Start tracking")]]
    # window = sg.Window("sustainApple", layout)

    event, values = window.read()
    if event == "Start tracking":
        update_frontend(backend)
    break

window.close()
