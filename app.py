"""Бот, который парсит сайты по продаже зюзюбликов и сохраняет их в базу"""

import os
import requests
from lxml import html
import pandas as pd
import sqlite3
from urllib.parse import urlparse
import datetime
import telebot
from config import TOKEN

DATABASE = os.path.join('base.db')  # Путь к нашей БД (текущая папка)
bot = telebot.TeleBot(TOKEN)


def get_price(url, xpath):
    """Вытягиваем цену со страницы по url-ссылке товара"""
    response = requests.get(url)
    response.raise_for_status()  # Проверяем запрос (код 200 - успех)
    tree = html.fromstring(response.content)
    price_element = tree.xpath(xpath)  # Ищем цену по пути xpath
    price_v1 = price_element[0].text.strip()  # Возвращаем текст с ценой
    price_v2 = ''
    for i in price_v1:  # Отсеиваем лишние знаки в цене, оставляем цифры
        if i.isdigit():
            price_v2 += i
    price_v3 = int(price_v2)
    return price_v3  # Возвращаем цену со страницы


@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Приветствие"""
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    upload_button = telebot.types.KeyboardButton("Загрузить файл")  # Создаём кнопку
    keyboard.add(upload_button)  # Добавляем кнопку
    bot.send_message(message.chat.id, "Нажми кнопку 'Загрузить файл' и прикрепи Excel документ.", reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text == "Загрузить файл")
def handle_upload_button(message):
    """Действие по нажатию на кнопку Загрузить"""
    bot.send_message(message.chat.id, "Прикрепите Excel документ к сообщению")


@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Загрузка файла. Сохранение данных в базу"""
    conn = sqlite3.connect(DATABASE)  # Устанавливаем соединение с БД
    db_cur = conn.cursor()
    chat_id = message.chat.id
    document = message.document  # Ссылаемся на прикрепленный документ
    if document.file_name.endswith((".xlsx", ".xls")):  # Проверяем, расширение файла
        tm = datetime.datetime.now().strftime("%m%d%Y_%H%M%S")  # Текущее время для имени файла
        file_id = document.file_id
        file_info = bot.get_file(file_id)  # Загружаем файл
        file = bot.download_file(file_info.file_path)  # Указываем путь
        file_path = os.path.join(str(tm)+document.file_name)  # Даём имя файлу
        with open(file_path, 'wb') as saved_file:
            saved_file.write(file)    # Сохраняем файл
        """Работа с базой данных"""
        df = pd.read_excel(saved_file.name, sheet_name=0)  # Считываем таблицу с первой страницы
        for index, row in df.iterrows():  # Парсим ячейки
            url_domain = urlparse(row["url"]).netloc  # Доменное имя главной страницы сайта
            db_cur.execute('SELECT url FROM books WHERE url = ?', (row["url"],))  # Выбираем url-ы ссылок на товары
            url_coind = db_cur.fetchone()
            if url_coind:
                db_cur.execute('UPDATE books SET price = ? WHERE url = ?',
                               (get_price(row["url"], row["xpath"]), row["url"],))
                # Записываем в БД инфу о товарах: имя, ссылка, цена (обновляем цену, если такой url уже есть)
            else:
                db_cur.execute('INSERT INTO books VALUES(?, ?, ?, ?)',
                               (row["title"], row["url"], get_price(row["url"], row["xpath"]), url_domain,))
                # Записываем в БД инфу о товарах: имя, ссылка, цена
            bot.send_message(chat_id, f'Книга {row["title"]}, магазин {row["url"]}, цена '
                                      f'{get_price(row["url"], row["xpath"])} р.')
            # Отправляем пользователю полученую инфу из таблицы: имя, ссылка, цена
        db_cur.execute('SELECT url_dom, ROUND(AVG(price)) FROM books GROUP BY url_dom')
        # Вытягиваем всю инфу с таблицы для вычисления средней цены
        avg_price = db_cur.fetchall()
        for el in avg_price:
            bot.send_message(chat_id, 'Средняя цена зюзюблика на маркетплейсе, руб.: ')
            for i in el:
                bot.send_message(chat_id, i)
        os.remove(saved_file.name)  # Удаляем сохраненный файл за ненадобностью
    else:
        bot.reply_to(message, "Не Excel документ")


if __name__ == '__main__':
    print("Бот запустился...")
    bot.infinity_polling()
