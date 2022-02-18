### Подготавливаем данные в [Elastic Path](https://www.elasticpath.com) для работы магазина

Методы для работы с API от Elastic Path в файле `moltin_api.py`.  

#### Как пользоваться:   
Создайте `py` файл, импортируйте необходимые функции из `moltin_api.py`.  
В первую очередь импортируйте и запустите `load_environment()`, 
которая отдает `api_base_url`, `client_id`, `client_secret` необходимые для получения рабочего **TOKENа**.  
Ниже кратко указаны существующие функции, при этом передача переменных для получения токена опущена, 
потому что передавать их надо **обязательно** в каждой функции.  
Т.об., например, функция:  
```python
add_product_to_cart(
    cart_id=098765,
    product_id=123-45345-6546,
    quantity=5
)
```
должна запускаться как:

```python
add_product_to_cart(
    api_base_url,
    client_id,
    client_secret,
    cart_id=098765,
    product_id=123-45345-6546,
    quantity=5
)
```
т.к. наличие токета - необходимость.

<hr>

Для чего все это пришлось сделать описано [здесь](../README.md).

- `add_product_to_cart(cart_id=098765, product_id=123-45345-6546, quantity=5)` 

Добавляет *существующий* товар в корзину с определенным id, на основании id товара и необходимого количества.

- `create_a_file(folder_name='images')`

Загружает файлы из папки `images` в систему Elastic Path, загруженные файлы помечает как `.uploaded`. Вы можете указать другую папку с файлами.
Возвращает строку с указанием количества загруженных файлов и их списком.
- `create_a_customer(name=Jimm Smith, email=js@hismail.com)`.
 
Создает покупателя в базе данных Elastic Path, присваевает ему id. 
Поля для пароля не предусмотрено, но его можно легко дописать согласно [документации](https://documentation.elasticpath.com/commerce-cloud/docs/api/customers-and-accounts/customers/create-a-customer.html).
- `create_main_image_relationship(product_id=123-45687-456, image_id=987523-123123)`.

Привязывает к *существующему* товару *существующую* (ранее загруженную как файл) картинку, как основное изображение товара.
- `get_actual_token()`.

Функция получения актуального токена для работы с методами, основывается на `CLIENT_ID` и `CLIENT_SECRET`.
- `get_a_customers(customer_id=None)`

Функция для получения списка всех существующих покупателей, или описания конкретного покупателя согласно его id, т.об. `get_a_customers(customer_id=025245-4156456-454)`
- `get_files(file_id=None)`

Метод получения списка всех загруженных файлов или описания конкретного файла по его ID
- `get_cart_status(card_id, items=False)`

Получаем статус корзины по ее ID. Если необходимо, получаем корзину и список товаров в ней, т.об.`get_cart_status(card_id, items=True)`
- `get_products(product_id=None)`

Получаем список всех товаров или конкретного товара по его id. 
- `remove_item_from_cart(card_id=45646-46546, product_id=1341563-4546)`

Удаление из конкретной корзины (на основе ее id), конкретного товара.

- `create_a_flow(flow_name, flow_slug, flow_description, is_enabled=True)`

Создаем новую **Flow** модель .Обязательные поля `flow_name`, `flow_slug`, `flow_description`.

- `create_field_for_flow(**kwargs)`

Создаем поле для Flow-модели. [Документация](https://documentation.elasticpath.com/commerce-cloud/docs/api/advanced/custom-data/fields/create-a-field.html).
Обязательные элементы поля: 
```python
        kwargs["name"] # Имя поля
        kwargs["slug"] # Слаг поля
        kwargs["field_type"] # Тип поля
        kwargs["description"] # Описание поля
        kwargs["required"] # Является ли поле обязательным
        kwargs["enabled"] # Включено ли поле
        kwargs["flow_id"] # ID Flow модели к которой относится поле 
```


- `create_an_entry(flow_slug, **kwargs)`  

Создаем запись в выбранной Flow-модели. [Документация](https://documentation.elasticpath.com/commerce-cloud/docs/api/advanced/custom-data/entries/create-an-entry.html).
Обязательные элементы: 
```python
        flow_slug # Слаг Flow модели в которой делаем запись
        # Запаковываем в **kwargs значения всех обязательных полей модели по slug поля, например:
        latitude=53.01234567,
        address='Москва, Кремль', 
```
- `get_all_entries(flow_slug, per_page=75)`  

Получаем все записи Flow модели по ее Slug, с указанием максимального количества записей  ответе (по умолчанию 75)

- `get_an_entry(flow_slug, entry_id)`  

Получаем конкретную запись Flow модели(aka Entry) по ее ID.

- `update_an_entry(flow_slug, entry_id, **kwargs)`  

Обновляем конкретную запись Flow модели(aka Entry) по ее ID. Опции обновления указываются `**kwags`.
Пример:  
```python
        update_an_entry(
            api_base_url,
            client_id,
            client_secret,
            flow_slug='your_model_slug',
            entry_id=12345679,  #  ID записи данной модели
            exist_field=new_value
        )
```

<hr>

Все методы возвращают JSON данные, если явно не указано другое.  
Логгирование не предусмотрено, возможно *пока*.  
Методы задекорированы как `@retry`, на 3 попытки с перерывом в 1 секунду. API все-таки притормаживают.