class TelegramError(Exception):
    """Ошибка отправки сообщения в Telegram"""
    pass


class AccessDenied(Exception):
    """Запрашиваемая информация недоступна"""
    pass


class EmptyResponseFromAPI(Exception):
    """Пустой ответ API"""
    pass
