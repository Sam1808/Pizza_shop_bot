import logging
import os
import redis

from bot_utils import fetch_coordinates
from bot_utils import get_min_distance

from dotenv import load_dotenv
from functools import partial

from moltin_api import add_product_to_cart
from moltin_api import create_entry
from moltin_api import get_all_entries
from moltin_api import get_entry
from moltin_api import get_cart_status
from moltin_api import get_files
from moltin_api import get_items_in_cart
from moltin_api import get_products
from moltin_api import remove_item_from_cart

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import LabeledPrice, Update

from telegram.ext import CallbackContext, CallbackQueryHandler
from telegram.ext import CommandHandler, MessageHandler
from telegram.ext import Filters, PreCheckoutQueryHandler, Updater

from textwrap import dedent


def _error(_, context):
    """Собираем ошибки"""
    logging.info('Bot catch some exception. Need your attention.')
    logging.exception(context.error)


def start(update, context):
    """
    Функция start - запуск бота (функция handle_users_reply)
    и переход в состояние HANDLE_MENU.
    """

    keyboard = list()
    if not context.user_data.get('products'):
        products_catalog = get_products(
            context.bot_data['api_base_url'],
            context.bot_data['client_id'],
            context.bot_data['client_secret'],
        )
        context.user_data['products'] = products_catalog

    products = context.user_data['products']
    for product in products['data']:
        product_id = str(product['id'])
        keyboard.append(
            [
                InlineKeyboardButton(product['name'], callback_data=product_id)
            ]
        )
    total_products = len(products['data'])
    if not context.user_data.get('menu_from'):
        context.user_data['menu_from'] = 0
        context.user_data['menu_to'] = 8
        # Количество отображаемых товаров: 8 шт.

    menu_from = context.user_data['menu_from']
    if menu_from < 0:
        context.user_data['menu_from'] = 0
        menu_from = 0
        context.user_data['menu_to'] = 8

    menu_to = context.user_data['menu_to']
    if menu_to > total_products:
        context.user_data['menu_from'] = total_products - 8
        menu_from = total_products - 8
        context.user_data['menu_to'] = total_products
        menu_to = total_products

    keyboard = keyboard[menu_from:menu_to]

    menu_footer = [
        [
            InlineKeyboardButton('<', callback_data='<'),
            InlineKeyboardButton('>', callback_data='>')
        ],
        [InlineKeyboardButton('Корзина', callback_data='/cart')]
    ]

    message = 'Список предложений:'
    if update.message:
        update.message.delete()
        keyboard += menu_footer
        update.message.reply_text(
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        update.callback_query.message.delete()
        keyboard += menu_footer
        update.callback_query.message.reply_text(
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return "HANDLE_MENU"


def handle_menu(update, context):
    """Предложение и выбор товара"""

    query = update.callback_query
    if query.data == '>':
        context.user_data['menu_from'] += 8
        context.user_data['menu_to'] += 8
        return start(update, context)

    if query.data == '<':
        context.user_data['menu_from'] -= 8
        context.user_data['menu_to'] -= 8
        return start(update, context)

    if query.data == '/cart':
        return handle_cart(update, context)

    product_details = get_products(
        context.bot_data['api_base_url'],
        context.bot_data['client_id'],
        context.bot_data['client_secret'],
        product_id=query.data
    )['data']

    unit_price = \
        product_details['meta']['display_price']['with_tax']['formatted'][1:]
    message = f'''\
    {product_details['name']}
    Описание: {product_details['description']}
    Цена: {unit_price} рублей за штуку'''

    file_id = product_details['relationships']['main_image']['data']['id']
    file_description = get_files(
        context.bot_data['api_base_url'],
        context.bot_data['client_id'],
        context.bot_data['client_secret'],
        file_id=file_id
    )
    file_url = file_description['data']['link']['href']

    keyboard = [
        [InlineKeyboardButton('В корзинку!', callback_data=query.data)],
        [InlineKeyboardButton('Назад', callback_data='/back')],

    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.delete()
    query.message.reply_photo(
        photo=file_url,
        caption=dedent(message),
        reply_markup=reply_markup
    )
    query.answer()

    return "HANDLE_DESCRIPTION"


def handle_description(update, context):
    """Добавление определенного кол-ва товара в корзину"""

    query = update.callback_query

    if '/back' == query.data:
        return start(update, context)

    purchase_id = str(query.data)
    purchase_quantity = 1

    chat_id = update.effective_message.chat_id
    add_product_to_cart(
        context.bot_data['api_base_url'],
        context.bot_data['client_id'],
        context.bot_data['client_secret'],
        chat_id,
        purchase_id,
        purchase_quantity
    )

    keyboard = [
        [InlineKeyboardButton('Назад', callback_data='/back')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    product_description = get_products(
        context.bot_data['api_base_url'],
        context.bot_data['client_id'],
        context.bot_data['client_secret'],
        product_id=purchase_id
    )['data']

    message = f'''\
    В корзину добавлен товар:
    {product_description['name']}.
    Количество: {purchase_quantity} штука'''

    query.message.delete()
    query.message.reply_text(text=dedent(message), reply_markup=reply_markup)
    query.answer()
    return "HANDLE_DESCRIPTION"


def handle_cart(update, context):
    """Работа с корзиной"""

    chat_id = update.effective_message.chat_id
    query = update.callback_query

    if '/pay' == query.data:
        return handle_waiting(update, context)
    elif '/back' == query.data:
        return start(update, context)
    elif 'delete>' in query.data:
        product_id = str(query.data).split('>')[1]
        remove_item_from_cart(
            context.bot_data['api_base_url'],
            context.bot_data['client_id'],
            context.bot_data['client_secret'],
            chat_id,
            product_id
        )

    context.user_data['order_description'] = None
    order_description = dict()

    cart_status = get_cart_status(
        context.bot_data['api_base_url'],
        context.bot_data['client_id'],
        context.bot_data['client_secret'],
        chat_id
    )
    cart_status_items = get_items_in_cart(
        context.bot_data['api_base_url'],
        context.bot_data['client_id'],
        context.bot_data['client_secret'],
        chat_id,
    )

    product_message = ''
    keyboard = list()

    for product in cart_status_items['data']:
        price = product['meta']['display_price']['with_tax']

        unit_price = price['unit']['formatted'][1:]
        total_price = price['value']['formatted'][1:]

        product_message += dedent(f'''
        {product['name']}
        {product['description']}
        Цена за штуку: {unit_price} рублей
        Количество: {product['quantity']} шт.
        Всего цена: {total_price} рублей
        ''')

        keyboard.append(
            [
                InlineKeyboardButton(
                    f"Удалить: {product['name']}",
                    callback_data=f"delete>{product['id']}"
                )
            ]
        )

        order_description[product['name']] = product['quantity']

    cart_cost = cart_status['data']['meta']['display_price']['with_tax']
    total_cost = cart_cost['formatted'][1:]

    product_message += f'\nИтого цена: {total_cost} рублей'

    context.user_data['total_cost'] = total_cost
    context.user_data['order_description'] = order_description

    keyboard.append(
        [
            InlineKeyboardButton('В меню', callback_data='/back'),
            InlineKeyboardButton('Оплатить', callback_data='/pay')
        ],
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.message.delete()
    query.message.reply_text(text=product_message, reply_markup=reply_markup)

    query.answer()
    return 'HANDLE_CART'


def handle_waiting(update, context):
    """Функция ожидает/определяет локацию клиента.
    Считает расстояние до пиццерии, запускает доставку (handle_delivery),
    если необходимо.
    """

    if update.message:
        current_position = None
        message = None

        if update.message.location:
            position = (
                str(update.message.location.latitude),
                str(update.message.location.longitude),
            )
            current_position = position

        if not current_position:
            current_position = fetch_coordinates(
                apikey=context.bot_data['yandex_key'],
                address=update.message.text
            )

        if not current_position:  # Яндекс (fetch_coordinates) вернул None
            update.message.delete()
            message = '''Мы не смогли определить Ваше местоположение.
            Попробуйте уточнить, пожалуйста!'''
            update.message.reply_text(text=dedent(message))
            return 'HANDLE_WAITING'

        context.user_data['current_position'] = current_position

        all_organization = get_all_entries(
            context.bot_data['api_base_url'],
            context.bot_data['client_id'],
            context.bot_data['client_secret'],
            flow_slug='pizza-shop'
        )
        nearest_org = get_min_distance(
            current_position,
            all_organization['data']
        )
        context.user_data['nearest_pizzeria'] = nearest_org
        distance_to_org = float(nearest_org['distance'])

        keyboard = [
            [
                InlineKeyboardButton('Доставка', callback_data='/delivery')
            ],
            [
                InlineKeyboardButton('Заберу сам', callback_data='/self')
            ],
        ]

        if distance_to_org <= 0.5:
            message = dedent(f'''
            Может, заберете заказ из нашей пиццерии неподалеку?
            Она всего в {distance_to_org} км от Вас.
            А можем и бесплатно доставить, Вы только скажите!
            ''')
        elif distance_to_org <= 5:
            message = dedent(f'''
            Заберете сами? Мы в {distance_to_org}км от Вас.
            Можем и доставить за дополнительные 100 рублей к стоимости заказа.
            ''')
        elif distance_to_org <= 20:
            message = dedent(f'''
            Заберете сами? Мы в {distance_to_org}км от Вас.
            Можем и доставить за дополнительные 300 рублей к стоимости заказа.
            ''')
        elif distance_to_org > 20:
            message = dedent(f'''
            Так далеко мы не сможем доставить, уж лучше Вы к нам!
            Мы в {distance_to_org}км от Вас.
            ''')
            keyboard = [
                [
                    InlineKeyboardButton('В меню', callback_data='/back'),
                ],
            ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.delete()
        update.message.reply_text(text=message, reply_markup=reply_markup)

    else:
        message = 'Пожалуйста, пришлите ваш адрес или геолокацию.'
        query = update.callback_query

        if '/delivery' in query.data:
            username = query.message.from_user['username']
            user_lat, user_lon = context.user_data['current_position']
            order_entry = create_entry(
                context.bot_data['api_base_url'],
                context.bot_data['client_id'],
                context.bot_data['client_secret'],
                flow_slug='customer_address',
                customer_name=username,
                customer_latitude=user_lat,
                customer_longitude=user_lon,
            )
            context.user_data['order_entry_id'] = order_entry['data']['id']
            return handle_delivery(update, context)
        elif '/self' in query.data:
            query.message.delete()
            nearest_org = context.user_data['nearest_pizzeria']
            nearest_org_address = nearest_org['pizza_Address']
            message = f'''
                Отлично! Ваш заказ будет готов по адресу:
                {nearest_org_address}
                Уже ждём Вас!
            '''
        elif '/back' == query.data:
            return start(update, context)

        query.message.reply_text(text=dedent(message))
        query.answer()
    return 'HANDLE_WAITING'


def handle_delivery(update, context):
    """Функция запускает доставку для конкретного заказа
    Шлет сообщение курьеру
    Формирует счет и проверяет оплату"""

    nearest_org_courier = context.user_data['nearest_pizzeria']['courier_id']
    order_entry_id = context.user_data['order_entry_id']

    address_entry = get_entry(
        context.bot_data['api_base_url'],
        context.bot_data['client_id'],
        context.bot_data['client_secret'],
        flow_slug='customer_address',
        entry_id=order_entry_id
    )

    customer_latitude = address_entry['data']['customer_latitude']
    customer_longitude = address_entry['data']['customer_longitude']

    message = 'Доставка\n'
    order_description = context.user_data['order_description']
    for key in order_description.keys():
        message += f'{key}: {order_description[key]} шт.\n'

    update.callback_query.message.bot.send_message(
        chat_id=nearest_org_courier,
        text=message
    )
    update.callback_query.message.bot.send_location(
        chat_id=nearest_org_courier,
        latitude=customer_latitude,
        longitude=customer_longitude
    )
    pay_invoice(update, context)
    run_timer(update, context)


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


def handle_users_reply(
        update,
        context,
        db_connection,
):
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db_connection.get(chat_id).decode("utf-8")

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'HANDLE_WAITING': handle_waiting,
    }
    state_handler = states_functions[user_state]

    next_state = state_handler(update, context)

    db_connection.set(chat_id, next_state)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    api_base_url = os.environ.get('API_BASE_URL', 'https://api.moltin.com')

    updater = Updater(os.environ['TELEGRAM-TOKEN'])

    dispatcher = updater.dispatcher
    dispatcher.bot_data['api_base_url'] = api_base_url
    dispatcher.bot_data['client_id'] = os.environ["CLIENT_ID"]
    dispatcher.bot_data['client_secret'] = os.environ["CLIENT_SECRET"]
    dispatcher.bot_data['yandex_key'] = os.environ['YANDEX_KEY']
    dispatcher.bot_data['payment_token'] = os.environ['PAYMENT_TOKEN']

    db_connection = redis.Redis(
        host=os.environ["REDIS-BASE"],
        port=int(os.environ["REDIS-PORT"]),
        password=os.environ["REDIS-PASSWORD"]
    )

    partial_handle_users_reply = partial(
        handle_users_reply,
        db_connection=db_connection,
    )

    dispatcher.add_handler(
        MessageHandler(Filters.location, handle_waiting)
    )

    dispatcher.add_handler(
        CallbackQueryHandler(partial_handle_users_reply)
    )
    dispatcher.add_handler(
        MessageHandler(Filters.text, partial_handle_users_reply)
    )
    dispatcher.add_handler(
        CommandHandler('start', partial_handle_users_reply)
    )
    dispatcher.add_handler(
        PreCheckoutQueryHandler(precheckout_callback)
    )
    dispatcher.add_handler(
        MessageHandler(Filters.successful_payment, successful_payment_callback)
    )
    dispatcher.add_error_handler(_error)
    updater.start_polling()
    updater.idle()
