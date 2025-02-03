import requests
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz  # Для работы с часовыми поясами

# Замените на токен вашего Telegram-бота
TOKEN = '7876708159:AAE5wutIy1k-qU0qPw8m_mTm_5f9dLXUWkw'

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Параметры группы и топика
GROUP_ID = -1002080353046  # ID вашей закрытой группы
TOPIC_ID = 34445           # ID топика в группе

# Состояние отправки вакансий
is_live = False
last_sent_vacancy_id = None

def get_max_salary_vacancy():
    """Получаем вакансию с максимальной зарплатой через API HeadHunter"""
    url = 'https://api.hh.ru/vacancies'

    # Вычисляем дату "вчера" (для поиска вакансий за последний день)
    yesterday = datetime.now() - timedelta(days=1)
    date_from = yesterday.strftime('%Y-%m-%d')
    params = {
        'text': 'экскурсовод',  # Ищем только экскурсоводов
        'area': 1,             # Москва (ID региона)
        'per_page': 10,        # Количество вакансий на странице
        'page': 0,             # Номер страницы
        'date_from': date_from # Фильтр по дате публикации
    }
    try:
        logger.info("Отправляем запрос к API HeadHunter...")
        response = requests.get(url, params=params)
        data = response.json()
        if 'items' not in data or not data['items']:
            logger.warning("Нет вакансий в ответе API.")
            return None, None
        max_salary = None
        best_vacancy = None
        best_vacancy_id = None
        for item in data['items']:
            title = item['name'].strip()
            link = item['alternate_url']
            company = item['employer']['name'] if item['employer'] else 'Не указано'
            salary = item['salary']
            vacancy_id = item['id']
            # Проверяем, что вакансия действительно для Москвы
            area = item.get('area', {}).get('name', '').lower()
            if 'москва' not in area:
                logger.info(f"Вакансия {title} не для Москвы. Пропускаем.")
                continue
            # Исключаем вакансии с удалённым форматом работы
            schedule = item.get('schedule', {}).get('name', '').lower()
            if 'удалённо' in schedule or 'remote' in schedule:
                logger.info(f"Вакансия {title} с удалённым форматом работы. Пропускаем.")
                continue
            # Проверяем, что в названии вакансии только одно слово "экскурсовод"
            if title.lower() != 'экскурсовод':
                logger.info(f"Вакансия {title} не содержит ТОЛЬКО слово 'экскурсовод'. Пропускаем.")
                continue
            salary_value = 0
            salary_text = "Зарплата не указана"
            if salary:
                salary_value = salary.get('to', 0) or salary.get('from', 0)
                salary_text = f"{salary.get('from', '')} - {salary.get('to', '')} {salary.get('currency', '')}"
            if salary_value > (max_salary or 0):
                max_salary = salary_value
                best_vacancy = f"💼 {title}\n🏢 {company}\n💰 {salary_text}\n🔗 {link}\n"
                best_vacancy_id = vacancy_id
        return best_vacancy, best_vacancy_id
    except Exception as e:
        logger.error(f"Ошибка при получении данных через API: {e}")
        return None, None

async def send_daily_vacancy():
    """Отправляет вакансию в группу раз в сутки"""
    global last_sent_vacancy_id
    if not is_live:
        logger.info("Автоматическая отправка вакансий отключена.")
        return
    logger.info("Получаем вакансию для отправки в группу...")
    vacancy, vacancy_id = get_max_salary_vacancy()
    if not vacancy:
        logger.info("Нет подходящих вакансий для отправки.")
        return
    if vacancy_id == last_sent_vacancy_id:
        logger.info("Эта вакансия уже была отправлена ранее. Пропускаем.")
        return
    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=TOPIC_ID,
            text=vacancy
        )
        logger.info(f"Вакансия отправлена в группу: {vacancy}")
        last_sent_vacancy_id = vacancy_id
    except Exception as e:
        logger.error(f"Ошибка при отправке вакансии в группу: {e}")

@dp.message(Command("start"))
async def start(message: Message):
    """Обработка команды /start"""
    logger.info("Команда /start получена")
    await message.answer("Привет! Я помогу найти вакансию с максимальной зарплатой для экскурсоводов в Москве.")

@dp.message(Command("okmne"))
async def send_best_vacancy(message: Message):
    """Обработка команды /okmne"""
    logger.info("Команда /okmne получена")
    await message.answer("Ищу вакансию с максимальной зарплатой за последний день...")
    vacancy, _ = get_max_salary_vacancy()
    if vacancy:
        await message.answer(vacancy)
    else:
        await message.answer("Нет подходящих вакансий.")

@dp.message(Command("live"))
async def enable_live(message: Message):
    """Обработка команды /live"""
    global is_live
    is_live = True
    logger.info("Автоматическая отправка вакансий включена.")
    await message.answer("Бот теперь будет отправлять вакансии в группу раз в сутки в 10:00.")
    # Отправляем текущую вакансию в группу
    vacancy, _ = get_max_salary_vacancy()
    if vacancy:
        try:
            await bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=TOPIC_ID,
                text=vacancy
            )
            await message.answer("Текущая вакансия отправлена в группу.")
        except Exception as e:
            logger.error(f"Ошибка при отправке вакансии в группу: {e}")
            await message.answer("Не удалось отправить вакансию в группу.")
    else:
        await message.answer("Нет подходящих вакансий для отправки.")

@dp.message(Command("nolive"))
async def disable_live(message: Message):
    """Обработка команды /nolive"""
    global is_live
    is_live = False
    logger.info("Автоматическая отправка вакансий отключена.")
    await message.answer("Бот больше не будет отправлять вакансии в группу.")

@dp.message(Command("mnelive"))
async def send_best_vacancy_to_group(message: Message):
    """Обработка команды /mnelive"""
    logger.info("Команда /mnelive получена")
    await message.answer("Ищу вакансию с максимальной зарплатой и отправляю её в группу...")

    # Получаем лучшую вакансию
    vacancy, vacancy_id = get_max_salary_vacancy()
    if not vacancy:
        await message.answer("Нет подходящих вакансий для отправки.")
        return

    # Проверяем, что эта вакансия не была отправлена ранее
    global last_sent_vacancy_id
    if vacancy_id == last_sent_vacancy_id:
        await message.answer("Эта вакансия уже была отправлена ранее.")
        return

    try:
        # Отправляем вакансию в группу
        await bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=TOPIC_ID,
            text=vacancy
        )
        logger.info(f"Вакансия отправлена в группу: {vacancy}")
        last_sent_vacancy_id = vacancy_id
        await message.answer("Вакансия успешно отправлена в группу!")
    except Exception as e:
        logger.error(f"Ошибка при отправке вакансии в группу: {e}")
        await message.answer("Не удалось отправить вакансию в группу.")

async def main():
    """Запуск бота"""
    logger.info("Запуск бота...")
    # Настройка планировщика
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))  # Указываем часовой пояс
    scheduler.add_job(send_daily_vacancy, 'cron', hour=10, minute=0)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())