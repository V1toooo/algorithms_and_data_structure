import pandas as pd
import random
from datetime import datetime, timedelta
from faker import Faker
import json
import re


fake_ru = Faker('ru_RU')

def generate_name(count: int): #генерация ФИО
    names = []
    while len(names) <= count:
        if fake_ru.boolean():
            first_name = fake_ru.first_name_female()
            last_name = fake_ru.last_name_female()
            patronymic = fake_ru.middle_name_female()
        else:
            first_name = fake_ru.first_name_male()
            last_name = fake_ru.last_name_male()
            patronymic = fake_ru.middle_name_male()

        names.append({
            "Фамилия": last_name,
            "Имя": first_name,
            "Отчество": patronymic,
        })
    return names

def generate_passport(count: int): #генерация уникальных паспортов
    passports = set()

    while len(passports) < count:
        c_passport = fake_ru.passport_number().replace(" ", "")
        passport = c_passport[:4] + " " + c_passport[4:]
        passports.add(passport)
    return list(passports)


with open("trains.json", "r", encoding="utf-8") as f:
    trains_data = json.load(f)

PERIOD_START = datetime(2020, 1, 1)
PERIOD_END = datetime.now()

train_state = {}

TURNAROUND_MIN_HOURS = 1 #время на разворот 
TURNAROUND_MAX_HOURS = 3

def get_pair_key(route):     #уникальный идентификатор физического поезда (пара его номеров туда+обратно)
    return tuple(sorted([route["number_there"], route["number_back"]]))

train_state = {}

def generate_ticket(new_departure_probability=0.5): #генерация билета 
    train_type = random.choice(trains_data) #случайный тип поезда 
    route_key = random.choice(list(train_type["routes"].keys())) #случайное направление поезда
    route = train_type["routes"][route_key] #информация о маршруте 
    city_from_base, city_to_base = route_key.split(" - ") #базовое направление маршрута
    pair_key = get_pair_key(route)

    state = train_state.get(pair_key)

    #нужно ли новое отправление? (либо его ещё не было, либо старое распродано) (есть вероятность даже при таких случаях добавить новое)
    need_new_departure = state is None or state.get("sold_out", False) or random.random() < new_departure_probability

    if need_new_departure:
        if state is None:
            state = {"position": city_from_base, "next_time": PERIOD_START}
            train_state[pair_key] = state

        if state["position"] == city_from_base:
            city_from, city_to = city_from_base, city_to_base
            number = route["number_there"]
        else:
            city_from, city_to = city_to_base, city_from_base
            number = route["number_back"]

        travel_time = timedelta(hours=route["time"])
        earliest_departure = state["next_time"]
        if earliest_departure >= PERIOD_END:
            return None

        max_wait_seconds = min(
            int(timedelta(days=7).total_seconds()),
            int((PERIOD_END - earliest_departure).total_seconds())
        )
        departure_time = earliest_departure + timedelta(seconds=random.randint(0, max_wait_seconds))
        arrive_time = departure_time + travel_time
        turnaround = timedelta(hours=random.randint(TURNAROUND_MIN_HOURS, TURNAROUND_MAX_HOURS))

        state["next_time"] = arrive_time + turnaround
        state["position"] = city_to
        state["city_from"] = city_from
        state["city_to"] = city_to
        state["departure_time"] = departure_time
        state["arrival_time"] = arrive_time
        state["number"] = number
        state["occupied"] = set()
        state["sold_out"] = False

    coach_type = random.choice(list(train_type["coaches"].keys())) #случайный тип вагона
    coach = train_type["coaches"][coach_type] #информация о вагоне
    coach_number = random.choice(coach["coach_numbers"]) #случайный номер вагона

    whole_unit_classes = train_type.get("whole_unit_classes", [])

    if coach_type in whole_unit_classes:
        #купе продаётся только целиком
        seats_per_compartment = coach["seats_per_compartment"]
        total_compartments = coach["seats_count"] // seats_per_compartment

        occupied_compartments = {
            c for (ct, cn, c) in state["occupied"] if ct == coach_type and cn == coach_number
        }
        free_compartments = set(range(total_compartments)) - occupied_compartments

        if not free_compartments:
            return None

        compartment_index = random.choice(list(free_compartments))
        state["occupied"].add((coach_type, coach_number, compartment_index))

        first_seat = compartment_index * seats_per_compartment + 1
        seat_number = ",".join(str(s) for s in range(first_seat, first_seat + seats_per_compartment))

    else:
        free_seats = set(range(1, coach["seats_count"] + 1)) - {
            s for (ct, cn, s) in state["occupied"] if ct == coach_type and cn == coach_number
        } #свободные места

        if not free_seats:
            return None

        seat_number = random.choice(list(free_seats))
        state["occupied"].add((coach_type, coach_number, seat_number))

    # если все места во всех вагонах закончились — пометим отправление распроданным
    total_capacity = sum(c["seats_count"] * len(c["coach_numbers"]) for c in train_type["coaches"].values())
    if len(state["occupied"]) >= total_capacity:
        state["sold_out"] = True

    price = round(route["time"] * route["avg_price_per_hour"] * coach["price_multiplier"])
    if coach_type in train_type.get("dining_included", {}):
        price += train_type["dining_included"][coach_type]

    return (
        state["city_from"], state["city_to"],
        state["departure_time"].isoformat(timespec="minutes"),
        state["arrival_time"].isoformat(timespec="minutes"),
        state["number"],
        f"{coach_number}-{seat_number}",
        price,
    )

def luhn_check_digit(number): #для поиска 16 цифры в номере карты
    digits = [int(x) for x in number]
    total = 0

    for i, digit in enumerate(digits):
        if i % 2 == 0:
            digit *= 2

            if digit > 9:
                digit = digit // 10 + digit % 10

        total += digit

    return str((10 - total % 10) % 10)

bank_bins = {
    'sber': {
        'visa': '402333',  
        'mastercard': '230718',  
        'mir': '220220'  
    },
    'alfa': {
        'visa': '479087',  
        'mastercard': '555949',  
        'mir': '220015'  
    },
    'gazprom': {
        'visa': '424976',  
        'mastercard': '526483',  
        'mir': '220056'  
    },
    'tinkoff': {
        'visa': '437784',  
        'mastercard': '548387',  
        'mir': '220070'  
    },
    'vtb': {
        'visa': '438259',  
        'mastercard': '527015',  
        'mir': '220224'  
    },
    'raiffeisen': {
        'visa': '425884',  
        'mastercard': '548164',  
        'mir': '220030'  
    }
}


def input_probabilities(options):
    while True:
        try:
            probabilities = list(map(float, input(
                f"Введите вероятности для {' '.join(options)} соответственно через пробел: "
            ).split()))

            if len(probabilities) != len(options):
                print("Количество вероятностей должно совпадать с количеством вариантов.")
                continue

            if not all(0 <= p <= 1 for p in probabilities):
                print("Все вероятности должны быть от 0 до 1.")
                continue

            if abs(sum(probabilities) - 1) > 1e-9:
                print("Сумма вероятностей должна быть равна 1.")
                continue

            return probabilities

        except ValueError:
            print("Введите только числа через пробел.")



banks = ["sber", "alfa", "gazprom", "tinkoff", "vtb", "raiffeisen"]
payment_systems = ["visa", "mastercard", "mir"]
card_usage = {}

def generate_card(banks: list, payment: list, bank_weights: list, payment_weights: list):
    while True:
        payment_system = random.choices(payment, weights=payment_weights, k=1)[0]
        bank = random.choices(banks, weights=bank_weights, k=1)[0]
        card_bin = bank_bins[bank][payment_system]

        card_without_check = card_bin + fake_ru.numerify("#########")
        card = card_without_check + luhn_check_digit(card_without_check)

        if card_usage.get(card, 0) < 5:
            card_usage[card] = card_usage.get(card, 0) + 1
            return card

def generate_passenger(bank_weights: list, payment_weights: list, count: int):
    list_of_names = generate_name(count)
    list_of_passports = generate_passport(count)

    rows = []

    i = 0

    while i < count:
        ticket = generate_ticket()
        if ticket is None:
            continue

        city_from, city_to, date_before, date_after, flight, seat, price = ticket

        name = list_of_names[i]
        passport = list_of_passports[i]
        card = generate_card(banks, payment_systems, bank_weights, payment_weights)

        rows.append({
            **name,
            "Паспорт": passport,
            "Откуда": city_from,
            "Куда": city_to,
            "Дата отъезда": date_before,
            "Дата приезда": date_after,
            "Рейс": flight,
            "Вагон-Место": seat,
            "Стоимость": f"{price} руб.",
            "Карта оплаты": " ".join(re.findall(r".{1,4}", str(card))),
        })

        i += 1
    return pd.DataFrame(rows)

if __name__ == "__main__":

    bank_weights = input_probabilities(banks)
    payment_system_weights = input_probabilities(payment_systems)

    while True:
        try:
            a = int(input("Введите желаемое количество строк в датасете: "))

            if a < 50_000:
                print("Количество строк не может быть меньше 50000.")
                continue
            break
        except ValueError:
            print("Введите целое число.")

    print("Ожидайте...")
    df = generate_passenger(bank_weights, payment_system_weights, a)
    df.index = range(1, len(df) + 1)
    df.to_excel("tickets_dataset.xlsx", sheet_name='Лист1', index=True)
    print("Генерация завершена. Создан файл tickets_dataset.xlsx")
