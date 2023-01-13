import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Dict

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN: str = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: int = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD: int = 600
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: Dict = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS: Dict = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия токенов."""
    return all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN])


def send_message(bot, message):
    """Отправляет сообщение в чат."""
    try:
        logging.debug('Отправляем сообщение')
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
    except telegram.error.TelegramError as error:
        logging.error('Ошибка отправки')
        raise exceptions.TelegramError(
            f'Не удалось отправить сообщение - {error}')
    else:
        logging.info(f'Сообщение отправлено {message}')


def get_api_answer(timestamp):
    """Получение ответа о статусе домашки."""
    timestamp = int(time.time())
    params_request = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    try:
        logging.info(
            'Запрашиваем: url = {url},'
            'headers = {headers},'
            'params = {params}'.format(**params_request))
        homework_statuses = requests.get(**params_request)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.AccessDenied('Не удалось получить ответ API')
        return homework_statuses.json()
    except Exception as error:
        raise ConnectionError(
            (
                'Во время подключения к эндпоинту {url} произошла'
                ' непредвиденная ошибка: {error}'
                ' headers = {headers}; params = {params};'
            ).format(
                error=error,
                **params_request
            )
        ) from error


def check_response(response):
    """Проверка ответа."""
    logging.info('Проверка ответа')
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является dict')
    if 'homeworks' not in response or 'current_date' not in response:
        raise exceptions.EmptyResponseFromAPI('Пустой ответ API')
    homeworks: list = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('homeworks не является списком')
    return homeworks


def parse_status(homework):
    """Статус проверки домашки."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе отсутствует homework_name')
    homework_name: str = homework.get('homework_name')
    homework_status: str = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        logging.error(f'Неизвестный статус работы - {homework_status}')
        raise ValueError(f'Неизвестный статус работы - {homework_status}')
    verdict: str = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Проверьте наличие всех токенов')
        sys.exit('Отсутствуют необходимые переменные окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp: int = int(time.time())
    start_message: str = 'Привет! Сейчас проверю, что там у нас'
    send_message(bot, start_message)
    current_report: Dict = {
        'name': '',
        'output': ''
    }
    prev_report: Dict = current_report.copy()

    while True:
        try:
            response: Dict = get_api_answer(timestamp)
            timestamp = response.get(
                'current_date', int(time.time())
            )
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                homework: Dict = homeworks[0]
                current_report['name'] = homework.get('homework_name')
                current_report['output'] = homework.get('status')
                send_message(bot, message)
            else:
                current_report['name'] = 'Пусто'
                current_report['output'] = 'Нет изменений.'

            if current_report != prev_report:
                message = (f"{current_report['name']}, "
                           f"{current_report['output']}")
                send_message(bot, message)
                prev_report = current_report.copy()
            else:
                logging.info('Нет изменений статуса проверки')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            send_message(bot, message)
            current_report['output'] = message
            if current_report != prev_report:
                prev_report = current_report.copy()

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO)
    main()
