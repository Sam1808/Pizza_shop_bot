import json
import os
import requests
import time

from funcy import retry

MOLTIN_TOKEN = None
MOLTIN_TOKEN_EXPIRES_TIME = 0


@retry(tries=3, timeout=1)
def add_product_to_cart(
        api_base_url,
        client_id,
        client_secret,
        cart_id,
        product_id,
        quantity
):
    """
    Добавляет товар в корзину
    :param cart_id: ID корзины
    :param product_id: ID товара
    :param quantity: Количество товара
    :return: Результат (в т.ч. ошибку) как JSON объект
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    data = {
        "data":
            {
                "id": product_id,
                "type": "cart_item",
                "quantity": quantity
            }
    }
    response = requests.post(
        f'{api_base_url}/v2/carts/{cart_id}/items',
        headers=headers,
        data=json.dumps(data)
    )
    response.raise_for_status()
    return response.json()


@retry(tries=3, timeout=1)
def create_a_file(
        api_base_url,
        client_id,
        client_secret,
        folder_name='images'
):
    """
    Загружает файлы в систему CMS.
    Проверяет папку (по умолчанию 'images') и загружает все найденные картинки.
    Загруженные картинки переименовывает в имя_файла.расширение.uploaded
    Возвращает количество загруженных картинок и их список
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {'Authorization': f'Bearer {token}'}

    filenames = os.listdir(folder_name)
    uploaded_files = []
    for filename in filenames:
        if 'uploaded' in filename:
            continue

        filename_path = os.path.join(folder_name, filename)
        files = {
            'file': (filename, open(filename_path, 'rb')),
            'public': (None, 'true'),
        }
        response = requests.post(
            f'{api_base_url}/v2/files',
            headers=headers,
            files=files
        )
        response.raise_for_status()

        uploaded_files.append(filename)
        uploaded_filename_path = os.path.join(
            folder_name,
            f'{filename}.uploaded'
        )
        os.rename(filename_path, uploaded_filename_path)

    return f'Uploaded {len(uploaded_files)} files. Details: {uploaded_files}'


@retry(tries=3, timeout=1)
def create_a_file_from_url(
        api_base_url,
        client_id,
        client_secret,
        url
):
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
    }
    files = {
        'file_location': (None, url),
    }

    response = requests.post(
        f'{api_base_url}/v2/files',
        headers=headers,
        files=files
    )
    response.raise_for_status()
    return response.json()


@retry(tries=3, timeout=1)
def create_a_customer(
        api_base_url,
        client_id,
        client_secret,
        name,
        email
):
    """
    Создает покупателя.
    Поле пароля не предусмотрено
    :param name: Имя покупателя
    :param email: Email покупателя
    :return: Результат (в т.ч. ошибку) как JSON объект
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    data = {
        "data":
            {
                "type": "customer",
                "name": name,
                "email": email
            }
    }
    response = requests.post(
        f'{api_base_url}/v2/customers',
        headers=headers,
        data=json.dumps(data)
    )
    response.raise_for_status()
    return response.json()


@retry(tries=3, timeout=1)
def create_main_image_relationship(
        api_base_url,
        client_id,
        client_secret,
        product_id,
        image_id
):
    """
    Привязывает главную картинку для продукта на основании ID продукта
     и ID картинки.
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    data = {"data": {"type": "main_image", "id": image_id}}

    response = requests.post(
        f'{api_base_url}/v2/products/{product_id}/relationships/main-image',
        headers=headers,
        data=json.dumps(data)
    )
    response.raise_for_status()
    return response.json()


@retry(tries=3, timeout=1)
def get_token(
        api_base_url,
        client_id,
        client_secret
):
    """
    Создает или возвращает актуальный токен,
     т.к. токены имеют свойство _протухать_
    """
    global MOLTIN_TOKEN_EXPIRES_TIME
    global MOLTIN_TOKEN

    current_time = int(time.time())
    if current_time <= MOLTIN_TOKEN_EXPIRES_TIME:
        return MOLTIN_TOKEN

    data = {
        'client_id': client_id,
        'grant_type': 'client_credentials',
        'client_secret': client_secret,
    }
    response = requests.post(
        f'{api_base_url}/oauth/access_token',
        data=data
    )
    response.raise_for_status()
    token_info = response.json()

    MOLTIN_TOKEN_EXPIRES_TIME = token_info['expires']
    MOLTIN_TOKEN = token_info['access_token']
    return MOLTIN_TOKEN


@retry(tries=3, timeout=1)
def get_a_customers(
        api_base_url,
        client_id,
        client_secret,
        customer_id=None
):
    """
    Возвращает список всех покупателей или конкретного покупателя по его ID
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )

    headers = {'Authorization': f'Bearer {token}'}

    url = f'{api_base_url}/v2/customers/'
    if customer_id:
        url += customer_id

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def get_files(
        api_base_url,
        client_id,
        client_secret,
        file_id=None
):
    """
    Возвращает описание всех загруженных файлов или конкретного файла по его ID
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {'Authorization': f'Bearer {token}'}

    url = f'{api_base_url}/v2/files/'
    if file_id:
        url += file_id

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def get_cart_status(
        api_base_url,
        client_id,
        client_secret,
        card_id,
        items=False
):
    """
    Возвращает статус корзины или ее список товаров в ней
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret,
    )
    headers = {'Authorization': f'Bearer {token}'}

    url = f'{api_base_url}/v2/carts/{card_id}'
    if items:
        url += '/items'

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def get_products(
        api_base_url,
        client_id,
        client_secret,
        product_id=None
):
    """
    Возвращает описание всех продуктов
    или описание конкретного продукта по его ID
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {'Authorization': f'Bearer {token}'}

    url = f'{api_base_url}/v2/products/'
    if product_id:
        url += product_id

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def create_a_product(
        api_base_url,
        client_id,
        client_secret,
        product_info,
):
    """
    Создает продукт на основании product_info
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    url = f'{api_base_url}/v2/products/'

    product = {
        "type": "product",
        "name": product_info["name"],
        "slug": f"pizza-{product_info['id']}",
        "sku": f"pizza-{product_info['id']}-sku",
        "manage_stock": False,
        "description": product_info["description"],
        "price": [
            {
                "amount": int(product_info["price"]),
                "currency": "RUB",
                "includes_tax": True
            }
        ],
        "status": "live",
        "commodity_type": "physical"
    }

    data = dict()
    data["data"] = product

    response = requests.post(
        url,
        headers=headers,
        data=json.dumps(data)
    )
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def remove_item_from_cart(
        api_base_url,
        client_id,
        client_secret,
        card_id,
        product_id
):
    """
    Удаляет товар из конкретной корзины (cart_id) по ID-товара
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )

    headers = {'Authorization': f'Bearer {token}'}

    url = f'{api_base_url}/v2/carts/{card_id}/items/{product_id}'

    response = requests.delete(url, headers=headers)
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def create_a_flow(
        api_base_url,
        client_id,
        client_secret,
        flow_name,
        flow_slug,
        flow_description,
        is_enabled=True
):
    """
    Создает новую Flow-модель
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    url = f'{api_base_url}/v2/flows/'
    flow_info = {
        "type": "flow",
        "name": flow_name,
        "slug": flow_slug,
        "description": flow_description,
        "enabled": is_enabled
    }

    data = dict()
    data["data"] = flow_info

    response = requests.post(
        url,
        headers=headers,
        data=json.dumps(data)
    )
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def get_flow(
        api_base_url,
        client_id,
        client_secret,
        flow_id=None
):
    """
    Возвращает список Flow моделей или конкретной модели по ее ID
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
    }

    url = f'{api_base_url}/v2/flows/'
    if flow_id:
        url += flow_id

    response = requests.get(
        url,
        headers=headers,
    )
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def create_field_for_flow(
        api_base_url,
        client_id,
        client_secret,
        **kwargs
):
    """
    Создает полe для Flow
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    url = f'{api_base_url}/v2/fields'
    field_description = {
        "type": "field",
        "name": kwargs["name"],
        "slug": kwargs["slug"],
        "field_type": kwargs["field_type"],
        "description": kwargs["description"],
        "required": kwargs["required"],
        "enabled": kwargs["enabled"]
    }
    field_relationships = {
        "flow": {
            "data": {
                "type": "flow",
                "id": kwargs["flow_id"]
            }
        }
    }
    field_description['relationships'] = field_relationships
    data = dict()
    data["data"] = field_description
    response = requests.post(
        url,
        headers=headers,
        data=json.dumps(data)
    )
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def create_an_entry(
        api_base_url,
        client_id,
        client_secret,
        flow_slug,
        **kwargs
):
    """
    Создает записи в полях Flow
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    url = f'{api_base_url}/v2/flows/{flow_slug}/entries'
    entry_description = {"type": "entry", **kwargs}
    data = dict()
    data["data"] = entry_description
    response = requests.post(
        url,
        headers=headers,
        data=json.dumps(data)
    )
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def update_an_entry(
        api_base_url,
        client_id,
        client_secret,
        flow_slug,
        entry_id,
        **kwargs
):
    """
    Обновляет запись в модели Flow
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    url = f'{api_base_url}/v2/flows/{flow_slug}/entries/{entry_id}'
    entry_description = {
        "id": entry_id,
        "type": "entry",
        **kwargs
    }
    data = dict()
    data["data"] = entry_description
    response = requests.put(
        url,
        headers=headers,
        data=json.dumps(data)
    )
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def get_all_entries(
        api_base_url,
        client_id,
        client_secret,
        flow_slug,
        per_page=75
):
    """
    Отдает список всех Entries в соответствии с Flow slug.
    Количество записей регулируется переменной per_page (default 75)
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
    }
    url = f'{api_base_url}/v2/flows/{flow_slug}/entries'
    payload = {'page': per_page}

    response = requests.get(url, headers=headers, params=payload)
    response.raise_for_status()

    return response.json()


@retry(tries=3, timeout=1)
def get_an_entry(
        api_base_url,
        client_id,
        client_secret,
        flow_slug,
        entry_id
):
    """
    Отдает Entry по ее ID.
    """
    token = get_token(
        api_base_url,
        client_id,
        client_secret
    )
    headers = {
        'Authorization': f'Bearer {token}',
    }
    url = f'{api_base_url}/v2/flows/{flow_slug}/entries/{entry_id}'

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()
