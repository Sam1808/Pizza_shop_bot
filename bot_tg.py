import logging
import os

from bot_utils import fetch_coordinates
from bot_utils import get_min_distance

from moltin_api import add_product_to_cart
from moltin_api import create_an_entry
from moltin_api import get_all_entries
from moltin_api import get_an_entry
from moltin_api import get_cart_status
from moltin_api import get_files
from moltin_api import get_products
from moltin_api import load_environment
from moltin_api import remove_item_from_cart

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler
from telegram.ext import Filters, PreCheckoutQueryHandler, Updater

from textwrap import dedent

import telegram


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

    menu_from = context.user_data['menu_from']  #TODO:Optimaze it!
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
        [InlineKeyboardButton('<', callback_data='<'), InlineKeyboardButton('>', callback_data='>')],
        [InlineKeyboardButton('Корзина', callback_data='/cart')]
    ]

    message = 'Список предложений:'
    if update.message:
        update.message.delete()
        keyboard += menu_footer
        update.message.reply_text(text=message, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        keyboard += menu_footer
        update.callback_query.message.reply_text(
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        update.callback_query.message.delete()
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

    product_description = get_products(
        context.bot_data['api_base_url'],
        context.bot_data['client_id'],
        context.bot_data['client_secret'],
        product_id=query.data
    )['data']

    unit_price = \
        product_description['meta']['display_price']['with_tax']['formatted'][1:]
    message = f'''\
    {product_description['name']}
    Описание: {product_description['description']}
    Цена: {unit_price} рублей за штуку'''

    file_id = product_description['relationships']['main_image']['data']['id']
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
    query.message.reply_photo(
        photo=file_url,
        caption=dedent(message),
        reply_markup=reply_markup
    )
    query.message.delete()

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

    query.message.reply_text(text=dedent(message), reply_markup=reply_markup)
    query.message.delete()

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
    cart_status_items = get_cart_status(
        context.bot_data['api_base_url'],
        context.bot_data['client_id'],
        context.bot_data['client_secret'],
        chat_id,
        items=True
    )

    product_message = ''
    keyboard = list()

    for product in cart_status_items['data']:
        unit_price = \
            product['meta']['display_price']['with_tax']['unit']['formatted'][1:]
        total_price = \
            product['meta']['display_price']['with_tax']['value']['formatted'][1:]
        product_message += dedent(f'''
        {product['name']}
        {product['description']}
        Цена за штуку(шт): {unit_price} рублей
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

    total_cost = \
        cart_status['data']['meta']['display_price']['with_tax']['formatted'][1:]
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
    """Здесь описание"""

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

        if not current_position:  # Не смогли найти координаты
            update.message.delete()
            message = 'Мы не смогли определить Ваше местоположение. Попробуйте уточнить, пожалуйста!'
            update.message.reply_text(text=message)
            return 'HANDLE_WAITING'

        context.user_data['current_position'] = current_position

        all_organization = get_all_entries(
            context.bot_data['api_base_url'],
            context.bot_data['client_id'],
            context.bot_data['client_secret'],
            flow_slug='pizza-shop'
        )
        nearest_org = get_min_distance(current_position, all_organization['data'])
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
            order_entry = create_an_entry(
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

        query.message.delete()
        query.message.reply_text(text=dedent(message))
        query.answer()
    return 'HANDLE_WAITING'


def handle_delivery(update, context):
    """Здесь описание"""

    nearest_org_courier = context.user_data['nearest_pizzeria']['courier_id']
    order_entry_id = context.user_data['order_entry_id']

    address_entry = get_an_entry(
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
    prices = [telegram.LabeledPrice("Pizza", price * 100)]
    update.callback_query.message.bot.sendInvoice(
        chat_id,
        title,
        description,
        payload,
        provider_token,
        currency,
        prices
    )


def precheckout_callback(update: telegram.Update, context: telegram.ext.CallbackContext):
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
    update.message.reply_text("Thank you for your payment!")


def send_bon_appetit(context: telegram.ext.CallbackContext):
    text = f'''
    Приятного аппетита! *место для рекламы*

    *сообщение что делать если пицца не пришла*
    '''
    context.bot.send_message(
        chat_id=context.job.context,
        text=dedent(text)
    )


def run_timer(update: telegram.Update, context: telegram.ext.CallbackContext):
    timeout = 30
    context.job_queue.run_once(
        send_bon_appetit,
        timeout,
        context=update.effective_message.chat_id
    )


def handle_users_reply(
        update,
        context,
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
        user_state = context.user_data[chat_id]

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'HANDLE_WAITING': handle_waiting,
    }
    state_handler = states_functions[user_state]

    next_state = state_handler(update, context)

    context.user_data[chat_id] = next_state


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    api_base_url, client_id, client_secret = load_environment()

    updater = Updater(os.environ['TELEGRAM-TOKEN'])

    dispatcher = updater.dispatcher
    dispatcher.bot_data['api_base_url'] = api_base_url
    dispatcher.bot_data['client_id'] = client_id
    dispatcher.bot_data['client_secret'] = client_secret
    dispatcher.bot_data['yandex_key'] = os.environ['YANDEX_KEY']
    dispatcher.bot_data['payment_token'] = os.environ['PAYMENT_TOKEN']

    dispatcher.add_handler(
        MessageHandler(Filters.location, handle_waiting)
    )

    dispatcher.add_handler(
        CallbackQueryHandler(handle_users_reply)
    )
    dispatcher.add_handler(
        MessageHandler(Filters.text, handle_users_reply, pass_job_queue=True)
    )
    dispatcher.add_handler(
        CommandHandler('start', handle_users_reply)
    )
    dispatcher.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dispatcher.add_handler(MessageHandler(Filters.successful_payment, successful_payment_callback))
    dispatcher.add_error_handler(_error)
    updater.start_polling()
    updater.idle()
