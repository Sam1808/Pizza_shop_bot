import requests

from geopy import distance
from funcy import retry

from telegram import LabeledPrice, Update
from telegram.ext import CallbackContext

from textwrap import dedent


@retry(tries=3, timeout=1)
def fetch_coordinates(apikey, address):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    answer = response.json()
    found_places = answer['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lat, lon


@retry(tries=3, timeout=1)
def get_min_distance(client_position, org_catalog: list):
    for organization in org_catalog:
        org_position = (
            str(organization['pizza_latitude']),
            str(organization['pizza_longitude'])
        )
        organization['distance'] = round(distance.distance(
            client_position, org_position
        ).km, 2)

    return min(
        org_catalog,
        key=lambda org: org['distance']
    )


def run_timer(update: Update, context: CallbackContext):
    timeout = 30  # Таймаут для сообщения "Приятного аппетита" в секундах
    context.job_queue.run_once(
        send_bon_appetit,
        timeout,
        context=update.effective_message.chat_id
    )


def send_bon_appetit(context: CallbackContext):
    text = f'''
    Приятного аппетита! *место для рекламы*
    *сообщение что делать если пицца не пришла*
    '''
    context.bot.send_message(
        chat_id=context.job.context,
        text=dedent(text)
    )


def pay_invoice(update, context):
    chat_id = update.effective_message.chat_id
    title = "Счет"
    description = "Детали заказа: "
    order_description = context.user_data['order_description']
    for key in order_description.keys():
        description += f'{key}({order_description[key]} шт.);'

    payload = "Custom-Payload"
    provider_token = context.bot_data['payment_token']
    currency = "RUB"
    total_cost = str(context.user_data['total_cost']).replace(',', '')
    price = int(total_cost)
    prices = [LabeledPrice("Pizza", price * 100)]
    update.callback_query.message.bot.sendInvoice(
        chat_id,
        title,
        description,
        payload,
        provider_token,
        currency,
        prices
    )


def precheckout_callback(update: Update, context: CallbackContext):
    query = update.pre_checkout_query
    if query.invoice_payload != 'Custom-Payload':
        context.bot.answer_pre_checkout_query(
            pre_checkout_query_id=query.id,
            ok=False,
            error_message="Something went wrong..."
        )
    else:
        context.bot.answer_pre_checkout_query(
            pre_checkout_query_id=query.id,
            ok=True
        )


def successful_payment_callback(update, _):
    update.message.reply_text(
        "Успешная оплата. Спасибо за то, что выбрали нас"
    )
