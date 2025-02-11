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

# Client ID и Client Secret для API HH (не используются в текущем коде)
HH_CLIENT_ID = "NJK9I7I86SHNDQGU0EFC48C3J29U453TOS91F7NSQPHCHBAEIFDAHNOBBQ03NH0M"
HH_CLIENT_SECRET = "T078KE2BT3H2AO95EI04IAU5KAD67ULEN8BUUDO00CU8724V2R9O2K7KUO2LP820"

def get_top_vacancies(count=10):
    """Получаем топ вакансий через API HeadHunter"""
    url = 'https://api.hh.ru/vacancies'
    yesterday = datetime.now() - timedelta(days=1)
    date_from = yesterday.strftime('%Y-%m-%d')
    params = {
        'text': 'экскурсовод OR гид OR "экскурсовод гид"',  # Добавляем ключевые слова
        'area': 1,          # Москва (ID региона)
        'per_page': 100,    # Количество вакансий на странице
        'page': 0,          # Номер страницы
        'date_from': date_from  # Фильтр по дате публикации
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if 'items' not in data or not data['items']:
            return []
        
        vacancies_with_salary = []  # Вакансии с указанной зарплатой
        vacancies_without_salary = []  # Вакансии без указанной зарплаты
        
        required_keywords = {"экскурсовод", "гид", "экскурсовод гид"}  # Требуемые ключевые слова
        
        for item in data['items']:
            title = item['name'].strip().lower()  # Приводим название к нижнему регистру для проверки
            link = item['alternate_url']
            company = item['employer']['name'] if item['employer'] else 'Не указано'
            salary = item['salary']
            vacancy_id = item['id']
            area = item.get('area', {}).get('name', '').lower()
            schedule = item.get('schedule', {}).get('name', '').lower()
            
            # Проверяем, что вакансия действительно для Москвы
            if 'москва' not in area:
                continue
            # Исключаем вакансии с удалённым форматом работы
            if 'удалённо' in schedule or 'remote' in schedule:
                continue
            # Проверяем, что название вакансии содержит одно из требуемых слов
            if not any(keyword in title for keyword in required_keywords):
                continue
            
            # Обработка зарплаты
            salary_value = 0
            salary_text = "Зарплата не указана"
            if salary:
                currency = salary.get('currency', '').upper()
                if currency == 'RUR' or currency == 'RUB':  # Заменяем RUR/RUB на символ рубля
                    currency = '₽'
                from_value = salary.get('from', None)
                to_value = salary.get('to', None)
                if from_value and to_value:
                    salary_text = f"{from_value} - {to_value} {currency}"
                    salary_value = to_value
                elif from_value:
                    salary_text = f"От {from_value} {currency}"
                    salary_value = from_value
                elif to_value:
                    salary_text = f"До {to_value} {currency}"
                    salary_value = to_value
            
            # Создаем словарь для вакансии
            vac = {
                'id': vacancy_id,
                'title': item['name'],  # Сохраняем оригинальное название
                'company': company,
                'salary': salary_text,
                'link': link,
                'salary_value': salary_value
            }
            
            if salary_value > 0:  # Если есть зарплата, добавляем в список с зарплатой
                vacancies_with_salary.append(vac)
            else:  # Иначе добавляем в список без зарплаты
                vacancies_without_salary.append(vac)
        
        # Сортируем вакансии с зарплатой по убыванию
        vacancies_with_salary.sort(key=lambda x: x['salary_value'], reverse=True)
        
        # Объединяем списки: сначала с зарплатой, затем без зарплаты
        all_vacancies = vacancies_with_salary + vacancies_without_salary
        
        # Возвращаем первые count вакансий
        return all_vacancies[:count]
    
    except Exception as e:
        logger.error(f"Ошибка при получении данных через API: {e}")
        return []

@dp.message(Command("okmne"))
async def send_top_vacancies(message: Message):
    """Обработка команды /okmne"""
    logger.info("Команда /okmne получена")
    await message.answer("Ищу топ-10 вакансий за последний день...")
    vacancies = get_top_vacancies(10)  # Получаем 10 вакансий
    if not vacancies:
        await message.answer("Нет подходящих вакансий.")
        return
    response = ""
    for idx, vac in enumerate(vacancies, start=1):
        response += f"{idx}. 💼 {vac['title']}\n🏢 {vac['company']}\n💰 {vac['salary']}\n🔗 {vac['link']}\n\n"
    await message.answer(response)

@dp.message(Command("1", "2", "3", "4", "5", "6", "7", "8", "9", "10"))
async def send_specific_vacancy(message: Message):
    """Обработка команды /1, /2, ..., /10"""
    cmd = message.text[1:]
    idx = int(cmd)
    logger.info(f"Команда /{cmd} получена")
    vacancies = get_top_vacancies(10)  # Получаем 10 вакансий
    if not vacancies:
        await message.answer("Нет подходящих вакансий.")
        return
    if 1 <= idx <= len(vacancies):
        vac = vacancies[idx - 1]
        vacancy_text = f"💼 {vac['title']}\n🏢 {vac['company']}\n💰 {vac['salary']}\n🔗 {vac['link']}"
        try:
            await bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=TOPIC_ID,
                text=vacancy_text
            )
            await message.answer(f"Вакансия №{idx} успешно отправлена в группу!")
        except Exception as e:
            logger.error(f"Ошибка при отправке вакансии в группу: {e}")
            await message.answer("Не удалось отправить вакансию в группу.")
    else:
        await message.answer("Неверный номер вакансии.")

async def main():
    """Запуск бота"""
    logger.info("Запуск бота...")
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())