import re
from pathlib import Path
import sqlite3
from database import Database

class TaskScanner:
    def __init__(self, base_path: str = "data/shad"):
        self.base_path = Path(base_path)
        self.db = Database()
    
    def scan_and_load_tasks(self):
        """Эффективное сканирование папок и загрузка задач в БД"""
        print(f"🔍 Сканирую {self.base_path}")
        
        for year_dir in self.base_path.iterdir():
            if not year_dir.is_dir(): continue
            
            try:
                year = int(year_dir.name)
            except:
                continue
            
            print(f"📁 {year}")
            
            for variant_dir in year_dir.iterdir():
                if not variant_dir.is_dir(): continue
                
                # Извлекаем номер варианта
                match = re.search(r'var[_-]?(\d+)', variant_dir.name, re.I)
                if not match: continue
                variant = int(match.group(1))
                
                # Читаем ссылку на решения
                solver_file = variant_dir / "solver.txt"
                solution_url = None
                if solver_file.exists():
                    with open(solver_file, 'r', encoding='utf-8') as f:
                        solution_url = f.read().strip() or None
                
                print(f"  📂 Вариант {variant}" + (f" | 📎 {solution_url[:30]}..." if solution_url else ""))
                
                # Сканируем JPG файлы
                for task_file in variant_dir.glob("*.jpg"):
                    # Парсим имя файла: 21_2_1.jpg -> (21, 2, 1)
                    match = re.search(r'(\d+)_(\d+)_(\d+)', task_file.stem)
                    if not match: continue
                    
                    file_year, file_variant, position = map(int, match.groups())
                    
                    # Нормализуем год (21 -> 2021)
                    file_year = 2000 + file_year if file_year < 100 else file_year
                    
                    # Используем год из папки как основной
                    final_year = year if year >= 2000 else file_year
                    absolute_path = task_file.resolve()
                    
                    # Добавляем в БД
                    self.db.add_task(
                        year=final_year,
                        variant=variant,
                        position=position,
                        file_path=str(absolute_path),
                        solution_url=solution_url
                    )
                    print(f"     Задача {position} добавлена")
    
    def print_stats(self):
        """Краткая статистика"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*), COUNT(DISTINCT year), COUNT(DISTINCT variant) FROM tasks')
        total, years, variants = cursor.fetchone()
        
        print(f"\nСтатистика:")
        print(f"   Всего задач: {total}")
        print(f"   Лет: {years}")
        
        conn.close()