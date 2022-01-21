import logging
import os

from moltin_api import add_product_to_cart
from moltin_api import get_cart_status
from moltin_api import get_files
from moltin_api import get_products
from moltin_api import load_environment
from moltin_api import remove_item_from_cart

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler
from telegram.ext import Filters, Updater

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
        keyboard += menu_footer
        update.message.reply_text(text=message, reply_markup=InlineKeyboardMarkup(keyboard))
        update.message.delete()
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

    # if '/pay' == query.data:
    #     return handle_email(update, context)
    if '/back' == query.data:
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
    total_cost = \
        cart_status['data']['meta']['display_price']['with_tax']['formatted'][1:]
    product_message += f'\nИтого цена: {total_cost} рублей'

    keyboard.append(
        [
            InlineKeyboardButton('В меню', callback_data='/back'),
            InlineKeyboardButton('Оплатить', callback_data='/pay')
        ],
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.message.reply_text(text=product_message, reply_markup=reply_markup)
    query.message.delete()

    query.answer()
    return 'HANDLE_CART'


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
        # 'WAITING_EMAIL': handle_email,
    }
    state_handler = states_functions[user_state]

    next_state = state_handler(update, context)

    context.user_data[chat_id] = next_state


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    api_base_url, client_id, client_secret = load_environment()

    updater = Updater(os.environ["TELEGRAM-TOKEN"])

    dispatcher = updater.dispatcher
    dispatcher.bot_data['api_base_url'] = api_base_url
    dispatcher.bot_data['client_id'] = client_id
    dispatcher.bot_data['client_secret'] = client_secret

    dispatcher.add_handler(
        CallbackQueryHandler(handle_users_reply)
    )
    dispatcher.add_handler(
        MessageHandler(Filters.text, handle_users_reply)
    )
    dispatcher.add_handler(
        CommandHandler('start', handle_users_reply)
    )
    dispatcher.add_error_handler(_error)
    updater.start_polling()
    updater.idle()
