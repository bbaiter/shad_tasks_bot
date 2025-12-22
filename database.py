import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self, db_path: str = 'shad_bot.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация таблиц БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица задач
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                variant INTEGER NOT NULL,
                position INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                solution_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, variant, position)
            )
        ''')
        
        # Таблица пользователей/чатов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                chat_type TEXT NOT NULL,  -- 'private', 'group', 'supergroup'
                chat_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                last_active TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица отправленных задач (чтобы не повторялись)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats(chat_id),
                FOREIGN KEY (task_id) REFERENCES tasks(id),
                UNIQUE(chat_id, task_id)
            )
        ''')
        
        # Таблица расписаний
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedules (
                chat_id INTEGER PRIMARY KEY,
                send_time TEXT DEFAULT '10:00',  -- Время в формате HH:MM (МСК)
                last_sent DATE,
                is_enabled BOOLEAN DEFAULT 1,
                FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_task(self, year: int, variant: int, position: int, file_path: str, solution_url: Optional[str] = None):
        """Добавление задачи в БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            #debug
            print(f"    🗄️    Пытаюсь добавить: {year} вариант {variant} позиция {position}")
            print(f"    📁 Файл: {file_path}")
            print(f"    🔗 Решение: {solution_url}")
            cursor.execute('''
                INSERT OR IGNORE INTO tasks (year, variant, position, file_path, solution_url)
                VALUES (?, ?, ?, ?, ?)
            ''', (year, variant, position, file_path, solution_url))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def get_random_task(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Получить случайную непосланную задачу для чата"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Получаем все задачи, которые еще не отправлялись в этот чат
        cursor.execute('''
            SELECT t.* FROM tasks t
            WHERE NOT EXISTS (
                SELECT 1 FROM sent_tasks st 
                WHERE st.chat_id = ? AND st.task_id = t.id
            )
            ORDER BY RANDOM()
            LIMIT 1
        ''', (chat_id,))
        
        task = cursor.fetchone()
        
        # Если все задачи уже отправлены, сбрасываем историю
        if not task:
            cursor.execute('DELETE FROM sent_tasks WHERE chat_id = ?', (chat_id,))
            conn.commit()
            
            # Пробуем снова
            cursor.execute('''
                SELECT * FROM tasks 
                ORDER BY RANDOM()
                LIMIT 1
            ''')
            task = cursor.fetchone()
        
        conn.close()
        return dict(task) if task else None
    
    def mark_task_sent(self, chat_id: int, task_id: int):
        """Отметить задачу как отправленную"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO sent_tasks (chat_id, task_id)
            VALUES (?, ?)
        ''', (chat_id, task_id))
        
        # Обновляем время последней активности чата
        cursor.execute('''
            UPDATE chats 
            SET last_active = CURRENT_TIMESTAMP 
            WHERE chat_id = ?
        ''', (chat_id,))
        
        conn.commit()
        conn.close()
    def _get_connection(self):
      """Возвращает соединение с БД (для внутреннего использования)"""
      return sqlite3.connect(self.db_path)

    def add_chat(self, chat_id: int, chat_type: str, chat_name: Optional[str] = None):
        """Добавить чат в БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO chats (chat_id, chat_type, chat_name, last_active)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (chat_id, chat_type, chat_name))
        
        # Создаем расписание по умолчанию
        cursor.execute('''
            INSERT OR REPLACE INTO schedules (chat_id)
            VALUES (?)
        ''', (chat_id,))
        
        conn.commit()
        conn.close()