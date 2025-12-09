import asyncio
import logging
import time
import os
from datetime import datetime
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8567662350:AAGZ_bNPC3eJIVs_33yPPbEqfVYbaolQjx0"
DTEK_URL = "https://www.dtek-dnem.com.ua/ua/shutdowns"

ADDR_1 = {
    "btn": "🏠 Новомиколаївка", 
    "header": "с-ще Новомиколаївка, вул. Степова, 77",
    "city": "с-ще Новомиколаївка", 
    "street": "вул. Степова", 
    "house": "77"
}

ADDR_2 = {
    "btn": "🏢 Дніпро", 
    "header": "м. Дніпро, вул. Севастопольська, 16",
    "city": "м. Дніпро", 
    "street": "вул. Севастопольська", 
    "house": "16"
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ФУНКЦИЯ ПАРСИНГА ---
async def get_schedule_final(addr):
    print(f"📸 SERVER-MODE: {addr['street']}...")
    
    chrome_options = Options()
    
    # 🔥 НАСТРОЙКИ ДЛЯ RENDER (ОБЯЗАТЕЛЬНО!)
    chrome_options.add_argument("--headless=new") # Работа без графического интерфейса
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Эмуляция iPhone (для красивой вертикальной таблицы)
    mobile_emulation = { "deviceName": "iPhone XR" }
    chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 20)
    
    results = [] 
    error_screenshot = "error_debug.png"
    
    try:
        driver.get(DTEK_URL)
        time.sleep(2) 

        # --- ФУНКЦИЯ: УДАЛЕНИЕ МУСОРА ---
        def nuke_everything():
            try:
                driver.execute_script("""
                    document.body.style.overflow = 'visible';
                    document.documentElement.style.overflow = 'visible';
                    
                    // Удаляем всё, что имеет fixed позицию (баннеры, шапки)
                    var all = document.querySelectorAll('*');
                    for (var i = 0; i < all.length; i++) {
                        var style = window.getComputedStyle(all[i]);
                        if (style.position === 'fixed' || style.position === 'sticky') {
                            all[i].remove();
                        }
                    }
                    // Удаляем стандартные классы рекламы
                    var bad = document.querySelectorAll('.modal, .modal-backdrop, .popup, .cookie, .cookies, .banner, .overlay, iframe, .feed-back-btn');
                    bad.forEach(el => el.remove());
                """)
            except: pass
        
        nuke_everything()
        time.sleep(0.5)

        # --- ФУНКЦИЯ: ЗАПОЛНЕНИЕ ПОЛЕЙ ---
        def safe_fill(field_name, text_value):
            nuke_everything() 
            try:
                inp = wait.until(EC.presence_of_element_located((By.NAME, field_name)))
            except: return False

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
            time.sleep(0.2)
            
            # JS Ввод (обходит блокировки)
            driver.execute_script(f"arguments[0].value = '{text_value}';", inp)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", inp)
            driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", inp)
            
            list_id = field_name + "autocomplete-list"
            time.sleep(0.8)
            
            try:
                # JS Клик по первому элементу списка
                script = f"""
                var list = document.getElementById('{list_id}');
                if (list) {{
                    var items = list.getElementsByTagName('div');
                    if (items.length > 0) {{ items[0].click(); return true; }}
                }}
                return false;
                """
                if not driver.execute_script(script): 
                    inp.send_keys(Keys.ENTER)
            except: 
                inp.send_keys(Keys.ENTER)
            
            time.sleep(0.5)
            return True

        # 1. Заполняем адрес
        if not safe_fill("city", addr['city']): raise Exception("Не ввел город")
        if not safe_fill("street", addr['street']): raise Exception("Не ввел улицу")
        
        try:
            nuke_everything()
            inp_house = wait.until(EC.presence_of_element_located((By.NAME, "house_num")))
            driver.execute_script(f"arguments[0].value = '{addr['house']}';", inp_house)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input'));", inp_house)
            time.sleep(0.5)
            inp_house.send_keys(Keys.ENTER)
        except: pass

        # --- АНАЛИЗ ГРУППЫ И СТАТУСА ---
        print("📸 Жду таблицу...")
        time.sleep(2)
        nuke_everything() 

        # Поиск группы
        group_text = "Не знайдено"
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            import re
            match = re.search(r"Група\s*([\d\.]+)", page_text)
            if match: group_text = match.group(1)
            elif addr['house'] == "16": group_text = "Unknown"
            elif addr['house'] == "77": group_text = "1.1"
            elif addr['house'] == "104": group_text = "5.1"
        except: pass

        # Определение статуса по цвету ячейки
        def get_status_text():
            try:
                now = datetime.now()
                hour = now.hour
                time_str = f"{hour:02d}-{hour+1:02d}"
                
                script = f"""
                var tds = document.querySelectorAll('td');
                for (var i = 0; i < tds.length; i++) {{
                    if (tds[i].innerText.includes('{time_str}')) {{
                        var next = tds[i].nextElementSibling;
                        if (next) return next.className;
                    }}
                }}
                return '';
                """
                cls = driver.execute_script(script)
                if "cell-scheduled" in cls: return "🔴 СВІТЛА НЕМАЄ"
                if "cell-non-scheduled" in cls: return "🟢 СВІТЛО Є"
                if "maybe" in cls or "half" in cls: return "🟡 МОЖЛИВЕ ВІДКЛЮЧЕННЯ"
                return "❓ Статус невідомий"
            except: return "❓ Статус невідомий"

        base_caption = f"🏠 {addr['header']}\n⚡️ Група: {group_text}"

        # --- ФОТО 1: СЕГОДНЯ ---
        try:
            target = driver.find_element(By.CLASS_NAME, "table2col")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
            time.sleep(0.5)
            
            path_today = "status_today.png"
            target.screenshot(path_today)
            
            try: date_txt = driver.find_element(By.CSS_SELECTOR, ".date.active span[rel='date']").text
            except: date_txt = datetime.now().strftime("%d.%m.%y")
            
            status_now = get_status_text()
            results.append((path_today, f"{status_now}\n{base_caption}\n📅 {date_txt}"))
        except: pass

        # --- ФОТО 2: ЗАВТРА ---
        has_tomorrow = False
        print("👉 Ищу кнопку 'На завтра'...")
        
        try:
            # ЛОГИКА: Находим все даты и кликаем ту, у которой НЕТ класса active
            script_click_tomorrow = """
            var dates = document.querySelectorAll('.date');
            for (var i = 0; i < dates.length; i++) {
                if (!dates[i].classList.contains('active')) {
                    dates[i].click();
                    return true;
                }
            }
            return false;
            """
            clicked = driver.execute_script(script_click_tomorrow)
            
            if clicked:
                time.sleep(2)
                nuke_everything() # Чистим мусор снова

                target_tmr = driver.find_element(By.CLASS_NAME, "table2col")
                if target_tmr.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_tmr)
                    path_tmr = "status_tomorrow.png"
                    target_tmr.screenshot(path_tmr)
                    
                    # Пытаемся достать дату из активной вкладки
                    try: 
                        date_tmr = driver.find_element(By.CSS_SELECTOR, ".date.active span[rel='date']").text
                    except: 
                        date_tmr = "Завтра"
                    
                    results.append((path_tmr, f"ℹ️ Графік на завтра\n{base_caption}\n📅 {date_tmr}"))
                    has_tomorrow = True
            else:
                print("⚠️ Вторая вкладка с датой не найдена.")

        except Exception as e:
            print(f"Ошибка получения завтра: {e}")

        return results, has_tomorrow, None

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        driver.save_screenshot(error_screenshot)
        return None, False, str(e)
    finally:
        driver.quit()

# --- КЛАВИАТУРА ---
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=ADDR_1['btn']))
    builder.add(KeyboardButton(text=ADDR_2['btn']))
    builder.adjust(2) 
    return builder.as_markup(resize_keyboard=True)

# --- БОТ ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("⚡ Бот готовий! Оберіть адресу:", reply_markup=get_main_kb())

@dp.message(F.text == ADDR_1['btn'])
async def process_addr1(message: types.Message):
    await process_request(message, ADDR_1)

@dp.message(F.text == ADDR_2['btn'])
async def process_addr2(message: types.Message):
    await process_request(message, ADDR_2)

async def process_request(message, addr):
    load_msg = await message.answer(f"🐢 Заходжу на сайт для: {addr['street']}...")
    results, has_tomorrow, error = await get_schedule_final(addr)
    await load_msg.delete()
    
    if results:
        for photo_path, caption in results:
            await message.answer_photo(FSInputFile(photo_path), caption=caption)
        if not has_tomorrow:
            await message.answer("ℹ️ На завтра графіка немає.")
    elif error:
        await message.answer(f"❌ Помилка: {error}")
        try: await message.answer_photo(FSInputFile("error_debug.png"), caption="Debug")
        except: pass
    else:
        await message.answer("🤷‍♂️ Графік не знайдено.")

# --- ВЕБ-СЕРВЕР (Для Render & UptimeRobot) ---
async def health_check(request):
    return web.Response(text="Bot is alive!", status=200)

async def start_dummy_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080)) # Render передаст порт сюда
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 Web server started on port {port}")

async def main():
    print("🚀 Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем параллельно: Бот + Веб-сервер
    await asyncio.gather(
        dp.start_polling(bot),
        start_dummy_server()
    )

if __name__ == '__main__':
    asyncio.run(main())
