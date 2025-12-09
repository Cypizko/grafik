import asyncio
import logging
import time
from datetime import datetime
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

async def get_schedule_final(addr):
    print(f"📸 FINAL-MODE (Server): {addr['street']}...")
    
    chrome_options = Options()
    
    # 🔥 НАСТРОЙКИ ДЛЯ СЕРВЕРА (Обязательные!)
    chrome_options.add_argument("--headless=new") # Запуск без окна
    chrome_options.add_argument("--no-sandbox")   # Нужно для Linux/Docker
    chrome_options.add_argument("--disable-dev-shm-usage") # Чтобы не падало от нехватки памяти
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Мобильный режим
    mobile_emulation = { "deviceName": "iPhone XR" }
    chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
    
    # На сервере Linux путь к хрому может отличаться, но webdriver_manager обычно справляется
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 15)
    
    results = [] 
    error_screenshot = "error_debug.png"
    
    try:
        driver.get(DTEK_URL)
        time.sleep(2) 

        # 🔥 ФУНКЦИЯ "ЯДЕРНЫЙ ВЗРЫВ"
        def nuke_everything():
            try:
                driver.execute_script("""
                    document.body.style.overflow = 'visible';
                    document.documentElement.style.overflow = 'visible';
                    var all = document.querySelectorAll('*');
                    for (var i = 0; i < all.length; i++) {
                        var style = window.getComputedStyle(all[i]);
                        if (style.position === 'fixed' || style.position === 'sticky') { all[i].remove(); }
                        if (style.zIndex > 50 && (style.position === 'absolute' || style.position === 'fixed')) { all[i].remove(); }
                    }
                    var bad = document.querySelectorAll('.modal, .modal-backdrop, .popup, .cookie, .cookies, .banner, .overlay, iframe');
                    bad.forEach(el => el.remove());
                """)
            except: pass
        
        nuke_everything()
        time.sleep(0.5)

        # --- ФУНКЦИЯ ЗАПОЛНЕНИЯ ---
        def safe_fill(field_name, text_value):
            nuke_everything() 
            try:
                inp = wait.until(EC.presence_of_element_located((By.NAME, field_name)))
            except:
                print(f"❌ Не нашел поле {field_name}")
                return False

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
            time.sleep(0.2)
            
            # JS INJECTION
            driver.execute_script(f"arguments[0].value = '{text_value}';", inp)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", inp)
            driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", inp)
            
            list_id = field_name + "autocomplete-list"
            time.sleep(0.8)
            
            try:
                # JS Click
                script = f"""
                var list = document.getElementById('{list_id}');
                if (list) {{
                    var items = list.getElementsByTagName('div');
                    if (items.length > 0) {{
                        items[0].click(); 
                        return true;
                    }}
                }}
                return false;
                """
                clicked = driver.execute_script(script)
                if not clicked: inp.send_keys(Keys.ENTER)
            except:
                inp.send_keys(Keys.ENTER)
            
            time.sleep(0.5)
            return True

        # Заполняем
        if not safe_fill("city", addr['city']): raise Exception("Не ввел город")
        if not safe_fill("street", addr['street']): raise Exception("Не ввел улицу")
        
        # Дом
        try:
            nuke_everything()
            inp_house = wait.until(EC.presence_of_element_located((By.NAME, "house_num")))
            driver.execute_script(f"arguments[0].value = '{addr['house']}';", inp_house)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input'));", inp_house)
            time.sleep(0.5)
            inp_house.send_keys(Keys.ENTER)
        except: pass

        # --- СКРИНШОТЫ ---
        print("📸 Жду таблицу...")
        time.sleep(2)
        nuke_everything() 

        # АНАЛИЗ
        current_status_text = "Невідомо"
        current_status_emoji = "❓"
        group_text = "Не знайдено"
        
        try:
            now = datetime.now()
            hour = now.hour
            time_str = f"{hour:02d}-{hour+1:02d}" 
            
            script_status = f"""
            var cells = document.querySelectorAll('td');
            for (var i = 0; i < cells.length; i++) {{
                if (cells[i].innerText.includes('{time_str}')) {{
                    var statusCell = cells[i].nextElementSibling;
                    if (statusCell) {{ return statusCell.className; }}
                }}
            }}
            return 'unknown';
            """
            status_class = driver.execute_script(script_status)
            
            if "cell-scheduled" in status_class: 
                current_status_emoji = "🔴"
                current_status_text = "СВІТЛА НЕМАЄ"
            elif "cell-non-scheduled" in status_class:
                current_status_emoji = "🟢"
                current_status_text = "СВІТЛО Є"
            elif "maybe" in status_class or "half" in status_class:
                current_status_emoji = "🟡"
                current_status_text = "МОЖЛИВЕ ВІДКЛЮЧЕННЯ"
        except: pass

        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            import re
            match = re.search(r"Група\s*([\d\.]+)", body_text)
            if match: group_text = match.group(1)
            elif addr['house'] == "104": group_text = "5.1"
            elif addr['house'] == "77": group_text = "1.1"
        except: pass

        caption_base = f"{current_status_emoji} {current_status_text}\n🏠 {addr['header']}\n⚡️ Група: {group_text}"

        # ФОТО 1
        try:
            target = driver.find_element(By.CLASS_NAME, "table2col")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
            time.sleep(0.5)
            
            path_today = "status_today.png"
            target.screenshot(path_today)
            
            try: date_txt = driver.find_element(By.CSS_SELECTOR, ".date.active span[rel='date']").text
            except: date_txt = "Сьогодні"
            
            results.append((path_today, f"{caption_base}\n📅 {date_txt}"))
        except: pass

        # ФОТО 2
        has_tomorrow = False
        try:
            tomorrow_btn = driver.find_element(By.XPATH, "//div[contains(text(), 'на завтра')]")
            driver.execute_script("arguments[0].click();", tomorrow_btn)
            time.sleep(1.5)
            nuke_everything()

            target_tmr = driver.find_element(By.CLASS_NAME, "table2col")
            if target_tmr.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_tmr)
                path_tmr = "status_tomorrow.png"
                target_tmr.screenshot(path_tmr)
                
                try: date_tmr = tomorrow_btn.find_element(By.CSS_SELECTOR, "span[rel='date']").text
                except: date_tmr = "Завтра"
                
                results.append((path_tmr, f"{caption_base}\n📅 {date_tmr}"))
                has_tomorrow = True
        except: pass

        return results, has_tomorrow, None

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        driver.save_screenshot(error_screenshot)
        return None, False, str(e)
    finally:
        driver.quit()

# --- КЛАВИАТУРА И БОТ ---
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=ADDR_1['btn']))
    builder.add(KeyboardButton(text=ADDR_2['btn']))
    builder.adjust(2) 
    return builder.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("⚡ Бот готовий! (Server Mode)", reply_markup=get_main_kb())

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

async def main():
    print("Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())