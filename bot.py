import asyncio
import os
import signal
import sys
from datetime import datetime, time
from typing import Optional

import pytz
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import Database
from task_scanner import TaskScanner
from config import Config  # Ваш конфиг с токеном и ID админа

# Инициализация
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher()
db = Database()
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))

# Команда /start - регистрация чата
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    chat = message.chat
    db.add_chat(
        chat_id=chat.id,
        chat_type=chat.type,
        chat_name=chat.title or chat.username or f"{chat.first_name} {chat.last_name}"
    )
    
    await message.answer(
        "✅ Бот активирован!\n"
        f"Чат ID: {chat.id}\n"
        "Ежедневно в 10:00 (по Москве) я буду присылать случайную задачу ШАД.\n"
        "Используйте /task для немедленного получения задачи.\n" 
    )

# Команда /task - получить задачу сейчас
@dp.message(Command("task"))
async def cmd_task(message: types.Message):
    await send_daily_task_to_chat(message.chat.id, manual=True)

# Админская команда для сканирования задач
@dp.message(Command("scan_tasks"))
async def cmd_scan_tasks(message: types.Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.answer("Только для администраторов")
        return
    
    await message.answer("Начинаю сканирование задач...")
    
    scanner = TaskScanner()
    scanner.scan_and_load_tasks()
    scanner.print_stats()
    
    await message.answer("Задачи загружены в БД")

# Основная функция отправки задачи
async def send_daily_task_to_chat(chat_id: int, manual: bool = False):
    """Отправляет случайную задачу в указанный чат"""
    try:
        # Получаем случайную задачу
        task = db.get_random_task(chat_id)
        if not task:
            await bot.send_message(chat_id, "Задачи не найдены в БД")
            return
        
        # Отправляем фото с условием задачи
        photo = FSInputFile(task['file_path'])
        
        # Формируем подпись
        caption = (
            f"🎯 *Задача ШАД*\n"
            f"Год: {task['year']}\n"
            f"Вариант: {task['variant']}\n"
            f"Позиция: {task['position']}\n\n"
            f"{'🔔 Ежедневная рассылка' if not manual else '🔄 Запрос вручную'}"
        )
        
        if task.get('solution_url'):
            caption += f"\n\n[Ссылка на решение]({task['solution_url']})"
        
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Отмечаем задачу как отправленную
        db.mark_task_sent(chat_id, task['id'])
        
        print(f" Задача отправлена в чат {chat_id}: {task['year']} вариант {task['variant']} позиция {task['position']}")
        
    except Exception as e:
        print(f" Ошибка при отправке задачи в чат {chat_id}: {e}")
        try:
            await bot.send_message(chat_id, "❌ Произошла ошибка при отправке задачи")
        except:
            print(f" Не удалось отправить сообщение об ошибке в чат {chat_id}")

# Задача для планировщика - отправка по расписанию
async def scheduled_daily_tasks():
    """Отправляет задачи всем активным чатам по расписанию"""
    try:
        print(f"⏰ Запуск ежедневной отправки задач в {datetime.now(pytz.timezone('Europe/Moscow')).strftime('%H:%M')}")
        
        # Получаем все активные чаты
        conn = db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.chat_id, s.send_time 
            FROM chats c
            JOIN schedules s ON c.chat_id = s.chat_id
            WHERE c.is_active = 1 AND s.is_enabled = 1
        ''')
        
        active_chats = cursor.fetchall()
        conn.close()
        
        current_time = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%H:%M')
        
        print(f"📋 Найдено активных чатов: {len(active_chats)}")
        
        for chat_id, send_time in active_chats:
            if send_time == current_time or send_time == 'test':  # 'test' для тестовой отправки
                print(f"Отправляю задачу в чат {chat_id}...")
                await send_daily_task_to_chat(chat_id)
                
    except Exception as e:
        print(f"Ошибка в scheduled_daily_tasks: {e}")

# Тестовая функция - отправка задачи через 30 секунд
async def test_send_after_start():
    """Тестовая отправка задачи через 30 секунд после старта"""
    await asyncio.sleep(30)  # Ждем 30 секунд
    
    print("🧪 Запускаю тестовую отправку через 30 секунд...")
    
    # Получаем все активные чаты
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id FROM chats WHERE is_active = 1')
    active_chats = cursor.fetchall()
    conn.close()
    
    if not active_chats:
        print("Нет активных чатов для тестовой отправки")
        return
    
    # Отправляем задачу в первый активный чат
    chat_id = active_chats[0][0]
    print(f" Тестовая отправка в чат {chat_id}")
    await send_daily_task_to_chat(chat_id, manual=True)

# Настройка и запуск планировщика
def setup_scheduler():
    """Настраивает ежедневную отправку в 10:00 по Москве"""
    try:
        # Основная задача - ежедневно в 10:00
        scheduler.add_job(
            scheduled_daily_tasks,
            CronTrigger(
                hour=10,
                minute=0,
                timezone='Europe/Moscow'
            ),
            id='daily_shad_tasks',
            replace_existing=True
        )
        
        print(" Планировщик настроен на ежедневную отправку в 10:00 МСК")
        
    except Exception as e:
        print(f"Ошибка при настройке планировщика: {e}")

# Обработчик сигналов завершения
def setup_signal_handlers():
    """Настраивает обработку сигналов завершения"""
    def signal_handler(sig, frame):
        print("\n Получен сигнал завершения. Останавливаю бота...")
        scheduler.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

# Основная функция запуска
async def main():
    """Основная функция запуска бота"""
    print("🤖 Бот ШАД задач запускается...")
    
    # Настройка обработки сигналов
    setup_signal_handlers()
    
    try:
        # Первоначальное сканирование задач
        scanner = TaskScanner()
        print("Сканирую задачи...")
        scanner.scan_and_load_tasks()
        scanner.print_stats()
        
        # Настройка планировщика
        print("Настраиваю планировщик...")
        setup_scheduler()
        scheduler.start()
        
        # debug Запуск тестовой отправки через 30 секунд
        #print("⏳ Запускаю тестовую отправку через 30 секунд...")
        #asyncio.create_task(test_send_after_start())
        
        # Добавляем чат админа по умолчанию (если нужно)
        if hasattr(Config, 'DEFAULT_CHAT_ID') and Config.DEFAULT_CHAT_ID:
            db.add_chat(chat_id=Config.DEFAULT_CHAT_ID, chat_type="private", chat_name="Admin")
            print(f"✅ Чат админа добавлен: {Config.DEFAULT_CHAT_ID}")
        
        print("Бот успешно запущен и готов к работе!")
        print(" Доступные команды:")
        print("   /start - активировать бота в чате")
        print("   /task - получить задачу немедленно")
        print("   /scan_tasks - пересканировать задачи (админ)")
        
        # Запуск поллинга бота с обработкой ошибок
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f" Критическая ошибка при запуске бота: {e}")
        print("Попытка перезапуска через 10 секунд...")
        
        # Попытка перезапуска через 10 секунд
        await asyncio.sleep(10)
        await main()  # Рекурсивный перезапуск
        
    finally:
        print("Завершение работы...")
        scheduler.shutdown()
        await bot.session.close()

# Запуск бота с обработкой ошибок
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Бот остановлен пользователем")
    except Exception as e:
        print(f" Непредвиденная ошибка: {e}")
        sys.exit(1)