import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
BOT_TOKEN = "9134817516:AAGBfC_v5NkBRO69vkwL6GVpGZix10rRPLU"
ADMIN_ID = 8788949939  # Твой ID (узнать в @userinfobot)

bot = Bot(token=BOT_TOKEN, timeout=60)
dp = Dispatcher(storage=MemoryStorage())

# ==========================================
# 2. БАЗА ДАННЫХ
# ==========================================
db = sqlite3.connect("market.db")
db.execute("""CREATE TABLE IF NOT EXISTS lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER,
    seller_name TEXT,
    item_type TEXT,
    item_name TEXT,
    price INTEGER,
    status TEXT DEFAULT 'active' -- active, pending, sold
)""")
db.commit()

# ==========================================
# 3. СОСТОЯНИЯ (FSM) ДЛЯ ПРОДАЖИ
# ==========================================
class SellState(StatesGroup):
    choosing_type = State()
    entering_name = State()
    entering_price = State()

# ==========================================
# 4. ГЛАВНОЕ МЕНЮ
# ==========================================
@dp.message(CommandStart())
async def start(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Рынок (Купить)", callback_data="open_market")],
        [InlineKeyboardButton(text="💼 Продать товар", callback_data="sell_item")],
        [InlineKeyboardButton(text="📦 Мои лоты", callback_data="my_lots")]
    ])
    await msg.answer("👋 Добро пожаловать на Маркет!\nЗдесь можно купить или продать номерки и вирты.", reply_markup=kb)

# ==========================================
# 5. СОЗДАНИЕ ЛОТА (ПРОДАЖА)
# ==========================================
@dp.callback_query(F.data == "sell_item")
async def sell_start(cb: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔢 Номерок", callback_data="type_Номерок")],
        [InlineKeyboardButton(text="💰 Вирты", callback_data="type_Вирты")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_menu")]
    ])
    await cb.message.edit_text("Что вы хотите продать?", reply_markup=kb)
    await state.set_state(SellState.choosing_type)
    await cb.answer()

@dp.callback_query(SellState.choosing_type, F.data.startswith("type_"))
async def sell_type(cb: types.CallbackQuery, state: FSMContext):
    item_type = cb.data.split("_")[1]
    await state.update_data(item_type=item_type)
    await cb.message.edit_text(f"Вы продаете: {item_type}.\nВведите название или описание товара (например: 'Номер 777' или '10к виртов'):")
    await state.set_state(SellState.entering_name)
    await cb.answer()

@dp.message(SellState.entering_name)
async def sell_name(msg: types.Message, state: FSMContext):
    await state.update_data(item_name=msg.text)
    await msg.answer("Введите цену в ⭐ (только целое число):")
    await state.set_state(SellState.entering_price)

@dp.message(SellState.entering_price)
async def sell_price(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("❌ Ошибка! Введите только число (например: 50).")
    
    base_price = int(msg.text)
    data = await state.get_data()
    item_type = data['item_type']
    item_name = data['item_name']

    # Логика комиссии
    if msg.from_user.id == ADMIN_ID:
        final_price = base_price
        fee = 0
    else:
        fee = int(base_price * 0.05) # 5% комиссия
        final_price = base_price + fee

    # Сохраняем лот
    cur = db.execute("INSERT INTO lots (seller_id, seller_name, item_type, item_name, price) VALUES (?, ?, ?, ?, ?)",
                     (msg.from_user.id, msg.from_user.username or msg.from_user.first_name, item_type, item_name, final_price))
    db.commit()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="На рынок", callback_data="open_market")]])
    
    text = (
        f"✅ **Лот выставлен!**\n\n"
        f"Тип: {item_type}\n"
        f"Название: {item_name}\n"
        f"Цена для покупателя: {final_price} ⭐\n"
    )
    if fee > 0:
        text += f"*(Комиссия рынка: {fee} ⭐. Вы получите: {base_price} ⭐)*"
        
    await msg.answer(text, reply_markup=kb, parse_mode="Markdown")
    await state.clear()

# ==========================================
# 6. ВИТРИНА (РЫНОК)
# ==========================================
@dp.callback_query(F.data == "open_market")
async def open_market(cb: types.CallbackQuery):
    lots = db.execute("SELECT id, item_type, item_name, price, seller_name FROM lots WHERE status='active' ORDER BY id DESC LIMIT 10").fetchall()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if not lots:
        text = "🛒 Рынок пуст. Станьте первым продавцом!"
        kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")])
    else:
        text = "🛒 **Активные лоты:**\n\n"
        for lot in lots:
            lot_id, itype, iname, price, seller = lot
            text += f"📦 {itype}: {iname}\n💰 {price} ⭐ | Продавец: @{seller}\n\n"
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"Купить {iname} за {price} ⭐", callback_data=f"buy_{lot_id}")])
        kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")])
        
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@dp.callback_query(F.data == "back_menu")
async def back_menu(cb: types.CallbackQuery):
    await start(cb.message)
    await cb.answer()

# ==========================================
# 7. ПОКУПКА (ОПЛАТА В STARS)
# ==========================================
@dp.callback_query(F.data.startswith("buy_"))
async def buy_lot_cb(cb: types.CallbackQuery):
    lot_id = int(cb.data.split("_")[1])
    lot = db.execute("SELECT item_name, price, status, seller_id FROM lots WHERE id=?", (lot_id,)).fetchone()
    
    if not lot or lot[2] != 'active':
        return await cb.answer("❌ Этот лот уже куплен или удален.", show_alert=True)
    
    item_name, price, _, seller_id = lot
    if cb.from_user.id == seller_id:
        return await cb.answer("❌ Вы не можете купить свой собственный лот.", show_alert=True)

    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title=f"Покупка: {item_name}",
        description="Средства защищены гарант-ботом.",
        payload=f"deal_{lot_id}",
        provider_token="", 
        currency="XTR",
        prices=[LabeledPrice(label=item_name, amount=price)]
    )
    await cb.answer()

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

# ==========================================
# 8. УСПЕШНАЯ ОПЛАТА И УВЕДОМЛЕНИЯ
# ==========================================
@dp.message(F.successful_payment)
async def successful_payment(msg: types.Message):
    payload = msg.successful_payment.invoice_payload
    lot_id = int(payload.split("_")[1])
    
    lot = db.execute("SELECT seller_id, item_name, price FROM lots WHERE id=?", (lot_id,)).fetchone()
    seller_id, item_name, price = lot
    
    # Меняем статус на "Ожидает выдачи"
    db.execute("UPDATE lots SET status='pending' WHERE id=?", (lot_id,))
    db.commit()

    await msg.answer("✅ Оплата получена! Деньги заморожены.\nОжидайте, пока продавец свяжется с вами.")

    # Уведомляем продавца
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я передал товар", callback_data=f"confirm_{lot_id}")]
    ])
    try:
        await bot.send_message(
            seller_id, 
            f"💰 Покупатель оплатил ваш лот: **{item_name}**!\n\nПередайте товар и нажмите кнопку ниже:", 
            reply_markup=kb, parse_mode="Markdown"
        )
    except:
        pass

    # Уведомляем админа (тебя)
    await bot.send_message(ADMIN_ID, f"🔔 **Сделка #{lot_id} оплачена!**\nТовар: {item_name}\nСумма: {price} ⭐\nОжидайте подтверждения от продавца.", parse_mode="Markdown")

# ==========================================
# 9. ПОДТВЕРЖДЕНИЕ ПЕРЕДАЧИ ТОВАРА
# ==========================================
@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_delivery(cb: types.CallbackQuery):
    lot_id = int(cb.data.split("_")[1])
    db.execute("UPDATE lots SET status='sold' WHERE id=?", (lot_id,))
    db.commit()
    
    await cb.message.edit_text("🎉 Вы подтвердили передачу! Сделка закрыта.")
    
    # Сообщаем админу, что пора выплатить деньги продавцу
    await bot.send_message(ADMIN_ID, f"✅ Продавец подтвердил передачу лота #{lot_id}.\nПора выплатить ему его долю!")
    await cb.answer("Успешно!")

# ==========================================
# 10. МОИ ЛОТЫ (ДЛЯ ПРОДАВЦОВ)
# ==========================================
@dp.callback_query(F.data == "my_lots")
async def my_lots(cb: types.CallbackQuery):
    lots = db.execute("SELECT id, item_name, price, status FROM lots WHERE seller_id=? ORDER BY id DESC LIMIT 5", (cb.from_user.id,)).fetchall()
    if not lots:
        return await cb.answer("У вас пока нет лотов.", show_alert=True)
        
    text = "📦 **Ваши последние лоты:**\n\n"
    for lot in lots:
        status_ru = {"active": "На продаже", "pending": "Ждет выдачи", "sold": "Продан"}
        text += f"ID: {lot[0]} | {lot[1]} | {lot[2]} ⭐ | Статус: {status_ru[lot[3]]}\n"
        
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]]), parse_mode="Markdown")
    await cb.answer()

# ==========================================
# 11. ЗАПУСК
# ==========================================
async def main():
    print("Маркет запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())