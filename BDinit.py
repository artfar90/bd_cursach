import sqlite3

# Функция для создания таблиц в базе данных
def initialize_database(db_path='store.db'):
    try:
        # Подключение к базе данных (если файла нет, он будет создан)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Создание таблицы пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        ''')

        # Создание таблицы товаров
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL
            )
        ''')

        # Создание таблицы корзин
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS carts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Создание таблицы элементов корзины
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cart_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                FOREIGN KEY (cart_id) REFERENCES carts(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')

        # Сохранение изменений и закрытие соединения
        conn.commit()
        conn.close()
        print("База данных успешно инициализирована!")

    except sqlite3.Error as e:
        print(f"Ошибка при инициализации базы данных: {e}")

# Запуск инициализации базы данных
if __name__ == "__main__":
    initialize_database()