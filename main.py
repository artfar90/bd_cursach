from fastapi import FastAPI, HTTPException, Form, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlite3 import Error, connect
import sqlite3
from datetime import datetime
from starlette.middleware.sessions import SessionMiddleware
import secrets
from contextlib import asynccontextmanager
import bcrypt

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключение SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_hex(32),  # Секретный ключ для подписи сессий
    session_cookie="session_cookie"    # Имя cookie для сессии
)

# Функция для получения соединения с базой данных
@asynccontextmanager
async def get_db():
    conn = connect('store.db')
    try:
        yield conn
    finally:
        conn.close()

# Корневая директория сайта ссылается на страницу регистрации
@app.get("/")
def read_root(request: Request):
    return RedirectResponse(url="/register/", status_code=303)

# Регистрация пользователя
@app.get("/register/")
def read_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register/")
async def create_register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    # Хэширование пароля
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    async with db as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password.decode('utf-8')))
            conn.commit()
            
            # Получаем ID только что зарегистрированного пользователя
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            
            if user:
                # Сохраняем user_id в сессии
                request.session["user_id"] = user[0]
                
                # Проверяем, есть ли у пользователя корзина
                cursor.execute("SELECT id FROM carts WHERE user_id = ?", (user[0],))
                cart = cursor.fetchone()
                if not cart:
                    # Если корзины нет, создаем новую
                    cursor.execute("INSERT INTO carts (user_id) VALUES (?)", (user[0],))
                    conn.commit()
            
            return RedirectResponse(url="/catalog/", status_code=303)
        except Error as e:
            raise HTTPException(status_code=400, detail=str(e))

# Вход пользователя
@app.get("/login/")
def read_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login/")
async def create_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    async with get_db() as db:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if user:
            # Проверка пароля
            if bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
                # Сохраняем user_id в сессии
                request.session["user_id"] = user[0]
                
                # Проверяем, есть ли у пользователя корзина
                cursor.execute("SELECT id FROM carts WHERE user_id = ?", (user[0],))
                cart = cursor.fetchone()
                if not cart:
                    # Если корзины нет, создаем новую
                    cursor.execute("INSERT INTO carts (user_id) VALUES (?)", (user[0],))
                    db.commit()
                return RedirectResponse(url="/catalog/", status_code=303)
            else:
                raise HTTPException(status_code=400, detail="Invalid username or password")
        else:
            raise HTTPException(status_code=400, detail="Invalid username or password")
    
# Отображение формы для добавления товара
@app.get("/add_product/")
def read_add_product(request: Request):
    return templates.TemplateResponse("add_product.html", {"request": request})

# Обработка данных формы
@app.post("/add_product/")
async def create_add_product(
    name: str = Form(...),
    price: float = Form(...),
    quantity: int = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    async with db as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO products (name, price, quantity) VALUES (?, ?, ?)",
                (name, price, quantity)
            )
            conn.commit()
            return RedirectResponse(url="/catalog/", status_code=303)
        except Error as e:
            raise HTTPException(status_code=400, detail=str(e))


# Просмотр каталога товаров
@app.get("/catalog/")
async def read_catalog(request: Request, message: str = None, db: sqlite3.Connection = Depends(get_db)):
    async with db as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()
        return templates.TemplateResponse("catalog.html", {"request": request, "products": products, "message": message})

# Просмотр корзины
@app.get("/cart/")
async def read_cart(request: Request, message: str = None, db: sqlite3.Connection = Depends(get_db)):
    async with db as conn:
        cursor = conn.cursor()
        
        # Получаем ID пользователя из сессии
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User  not authenticated")
        
        # Получаем корзину пользователя
        cursor.execute("SELECT id FROM carts WHERE user_id = ?", (user_id,))
        cart = cursor.fetchone()
        if not cart:
            raise HTTPException(status_code=400, detail="Cart not found")
        
        cart_id = cart[0]
        
        # Получаем товары из корзины
        cursor.execute("""
            SELECT cart_items.id, cart_items.product_id, products.name, cart_items.quantity 
            FROM cart_items 
            JOIN products ON cart_items.product_id = products.id 
            WHERE cart_items.cart_id = ?
        """, (cart_id,))
        
        cart_items = cursor.fetchall()
        
        return templates.TemplateResponse("cart.html", {"request": request, "cart": cart_items, "message": message})

# Добавление товара в корзину
@app.post("/add_to_cart/")
async def create_add_to_cart(
    request: Request,
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    async with db as conn:
        cursor = conn.cursor()
        # Получаем ID пользователя из сессии
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        # Получаем корзину пользователя
        cursor.execute("SELECT id FROM carts WHERE user_id = ?", (user_id,))
        cart = cursor.fetchone()
        if not cart:
            raise HTTPException(status_code=400, detail="Cart not found")
        
        cart_id = cart[0]
        
        # Проверяем, есть ли товар уже в корзине
        cursor.execute("SELECT * FROM cart_items WHERE cart_id = ? AND product_id = ?", (cart_id, product_id))
        cart_item = cursor.fetchone()
        if cart_item:
            # Если товар уже есть в корзине, увеличиваем его количество
            new_quantity = cart_item[3] + quantity
            cursor.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (new_quantity, cart_item[0]))
        else:
            # Если товара нет в корзине, добавляем его
            cursor.execute("INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (?, ?, ?)", (cart_id, product_id, quantity))
        conn.commit()
        return RedirectResponse(url="/catalog/?message=Товар успешно добавлен в корзину!", status_code=303)
    
# Удаление товара из корзины
@app.post("/remove_from_cart/")
async def create_remove_from_cart(
    request: Request,
    cart_item_id: int = Form(...),  # Получаем cart_item_id из формы
    db: sqlite3.Connection = Depends(get_db)
):
    async with db as conn:
        cursor = conn.cursor()
        
        # Проверяем, существует ли элемент корзины
        cursor.execute("SELECT * FROM cart_items WHERE id = ?", (cart_item_id,))
        cart_item = cursor.fetchone()
        if not cart_item:
            raise HTTPException(status_code=404, detail="Товар не найден в корзине")
        
        # Удаляем товар из корзины
        cursor.execute("DELETE FROM cart_items WHERE id = ?", (cart_item_id,))
        conn.commit()
        
        return RedirectResponse(url="/cart/?message=Товар успешно удален из корзины!", status_code=303)

# Отображение формы для проверки карты
@app.get("/check_card/")
def read_check_card(request: Request, message: str = None):
    return templates.TemplateResponse("check_card.html", {"request": request, "message": message})

# Проверка валидности карты и осуществление покупки
@app.post("/check_card/")
async def create_check_card(
    request: Request,
    card_number: str = Form(...),
    expiration_date: str = Form(...),
    cvv: str = Form(...),
    db: sqlite3.Connection = Depends(get_db)
):
    try:
        # Простая проверка номера карты (можно использовать более сложные алгоритмы)
        if len(card_number) != 16 or not card_number.isdigit():
            return RedirectResponse(url="/check_card/?message=Неверный номер карты", status_code=303)

        # Проверка срока действия карты
        try:
            expiration_date_parts = expiration_date.split("/")
            expiration_month = int(expiration_date_parts[0])
            expiration_year = int(expiration_date_parts[1])
            if expiration_month < 1 or expiration_month > 12:
                return RedirectResponse(url="/check_card/?message=Неправильный формат срока действия карты", status_code=303)
            if expiration_year < int(str(datetime.now().year)[2:]) or (expiration_year == int(str(datetime.now().year)[2:]) and expiration_month <= datetime.now().month):
                return RedirectResponse(url="/check_card/?message=Срок действия карты истек", status_code=303)  
        except (ValueError, IndexError):
            return RedirectResponse(url="/check_card/?message=Неправильный формат срока действия карты", status_code=303)

        # Проверка CVV
        if len(cvv) != 3 or not cvv.isdigit():
            return RedirectResponse(url="/check_card/?message=Неправильный формат CVV", status_code=303)

        # Если карта валидна, осуществляем покупку
        async with db as conn:
            try:
                cursor = conn.cursor()
                # Получаем ID пользователя из сессии
                user_id = request.session.get("user_id")
                if not user_id:
                    return RedirectResponse(url="/check_card/?message=Пользователь не авторизован", status_code=303)

                # Удаляем все товары из корзины пользователя
                cursor.execute("DELETE FROM cart_items WHERE cart_id IN (SELECT id FROM carts WHERE user_id = ?)", (user_id,))
                conn.commit()

                # Перенаправляем пользователя на страницу проверки карты с сообщением об успехе
                return RedirectResponse(url="/check_card/?message=Покупка успешно завершена!", status_code=303)
            except sqlite3.Error as e:
                # Перенаправляем с сообщением об ошибке
                return RedirectResponse(url=f"/check_card/?message=Ошибка: {str(e)}", status_code=303)
            except Exception as e:
                # Перенаправляем с сообщением об ошибке
                return RedirectResponse(url=f"/check_card/?message=Ошибка: {str(e)}", status_code=303)
    except Exception as e:
        # Перенаправляем с сообщением об ошибке
        return RedirectResponse(url=f"/check_card/?message=Ошибка: {str(e)}", status_code=303)

# Выход пользователя из аккаунта
@app.post("/logout/")
async def create_logout(request: Request):
    # Очищаем сессию пользователя
    request.session.clear()
    # Перенаправляем на страницу входа
    return RedirectResponse(url="/login/", status_code=303)

# Запуск приложения
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)