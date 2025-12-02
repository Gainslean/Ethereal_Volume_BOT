import asyncio
import random

import aiohttp
import json
from decimal import Decimal
from ethereal import AsyncRESTClient


with open("private_keys.txt") as f:
    private_key = f.read().strip()


oll_wallet = True # если True то будет фармить на всех приватниках сразу

mhoshitel = 5 # Плечо для сделки, меньше не советую делать,дольше фармить будет

need_random = False # True / False тру если надо выбрать кошельки для работы, фолс если будет все сразу ебашить ))

number_wallets = (0,1) # кошельки с которыми будем работать !!!!!!!!!!!!! НУМЕРАЦИЯ НАЧИНАЕТСЯ С НУЛЯ 0 . ЕСЛИ ВАМ НУЖНО 2 И 3 , ТО УКЗАЫВАЕТЕ 1,2   !!!!!!!!!!!!!!

sleep_from_wallet = 10  # задержка между кошельками  от ceкунды
sleep_to_wallet = 30 # задержка между кошельками до   ceкунды

volume_from = 10001 # объем набив от
volume_to = 10010 # до какого значения крутить объем

sleep_from_end = 10 # задержка между циклом от  ceкунды
sleep_to_end = 30 # задержка между циклом до ceкунды

# ---------------------------------------------------------
# Запись статистики в JSON
# ---------------------------------------------------------
async def update_account_data(address, volume, fees, balance, pnl):

    address = address.lower()

    # 1. Загружаем старый JSON (если нет — создаём пустой словарь)
    try:
        with open("info.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    # 2. Если кошелька ещё нет — создаем новую запись
    if address not in data:
        data[address] = {
            "volume": 0.0,
            "fees": 0.0,
            "balance": 0.0,
            "pnl": 0.0
        }

    # 3. Обновляем данные только для этого кошелька
    data[address]["volume"] += float(volume)
    data[address]["fees"] += float(fees)
    data[address]["balance"] += float(balance)
    data[address]["pnl"] += float(pnl)

    # 4. Записываем ОБНОВЛЁННЫЙ словарь обратно в файл
    with open("info.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"✔ Статистика обновлена для {address}")


async def get_btc_price(): # BTC PRICE
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT") as resp:
            data = await resp.json()
            price = float(data["price"])
            print(f"BTC price = {price}")
            return float(data["price"])



# ---------------------------------------------------------
# Инициализация клиента
# ---------------------------------------------------------
async def init_client(private_key):
    client = await AsyncRESTClient.create({
        "base_url": "https://api.ethereal.trade",
        "chain_config": {
            "rpc_url": "https://rpc.ethereal.trade",
            "private_key": private_key
        }
    })
    return client

async def get_balance(client,sub_id):
    balances = await client.get_subaccount_balances(subaccount_id=sub_id)
    balance = int(balances[0].available)
    print(f"Balcnce {sub_id} {balance}")
    return balance

# ---------------------------------------------------------
# Один MARKET ордер (BUY или SELL)
# side = 0 → LONG, 1 → SHORT
# ---------------------------------------------------------
async def execute_order(client, sub_id, eth_wallet, side,volume):

    # получаем баланс
    balances = await client.get_subaccount_balances(subaccount_id=sub_id)
    balance = float(balances[0].available)

    # создаём маркет-ордер
    order = await client.create_order(
        order_type="MARKET",
        quantity=Decimal(f"{volume}"),
        side=side,
        ticker="BTCUSD",
    )
    print("Order:", order)

    # получаем позиции
    positions = await client.list_positions(subaccount_id=sub_id)
    if not positions:
        print("❗ Позиции нет")
        return

    pos = positions[0].model_dump()

    fees = float(pos["fees_accrued_usd"])
    volume = float(pos["total_increase_notional"])
    pnl = float(pos["realized_pnl"])

    # запись в JSON
    await update_account_data(
        address=eth_wallet,
        volume=volume,
        fees=fees,
        balance=balance,
        pnl=pnl
    )

async def get_volume_info(address):

    address = address.lower()

    with open("info.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    volume = data[address]["volume"]
    print(f"{address} = {volume}")
    return volume



async def close_all_position(client, sub_id, eth_wallet):  ##### закрываем все позиции

    positions = await client.list_positions(subaccount_id=sub_id)

    #print("Все позиции:", positions)

    info = float(positions[0].size)
    if info == 0:
        print(f"Открытых позиций нет")
    else:
        info_close = abs(float(info))

        if info > 0:
            print(f"Найдена лонг позиция на {info}")
            await execute_order(client, sub_id, eth_wallet, side=1, volume=info_close)
        else:
            print(f"Найдена шорт позиция на {info}")
            await execute_order(client, sub_id, eth_wallet, side=0, volume=info_close)


# ---------------------------------------------------------
# Основной цикл
# ---------------------------------------------------------
async def main(wallet):

    btc_price = await get_btc_price()

    client = await init_client(wallet)

    # получаем субаккаунты 1 раз
    subs = await client.subaccounts()
    sub = subs[0]

    sub_id = sub.id
    eth_wallet = sub.account

    print("Работаю с:", eth_wallet)


    target_volume = random.randint(volume_from,volume_to)


    while True:
        balance = await get_balance(client=client,sub_id=sub_id)

        btc_amount = balance/btc_price
        print(btc_amount)

        def round_qty(qty):
            lot = Decimal("0.00001")
            qty = Decimal(str(qty))
            return (qty // lot) * lot



        value = round_qty(btc_amount)*mhoshitel

        await execute_order(client, sub_id, eth_wallet, side=0,volume=value)
        #
        #     # небольшая пауза
        await asyncio.sleep(0.5)
        #
        await execute_order(client, sub_id, eth_wallet, side=1,volume=value)

        await asyncio.sleep(0.5)
        #
        await close_all_position(client, sub_id, eth_wallet)

        volume = await get_volume_info(eth_wallet)

        if volume > target_volume:
            return True
        else:
            print(f"Для счета {eth_wallet} осталось набрать {target_volume - volume}")

        # пауза между циклами
        sleep_end = random.randint(sleep_from_end, sleep_to_end)
        print(f"Жду {sleep_end} сек перед новым циклом")
        await asyncio.sleep(sleep_end)

async def test_main(wallet):
    client = await init_client(wallet)

    # получаем субаккаунты 1 раз
    subs = await client.subaccounts()
    sub = subs[0]

    sub_id = sub.id
    eth_wallet = sub.account

    print("Работаю с:", eth_wallet)



async def test():


    wallet = []

    with open("private_keys.txt") as f:
        for line in f:
            key = line.strip()
            if key:              # пропускаем пустые строки
                wallet.append(key)


    if oll_wallet  == True: # если надо все коши разом прогнать

        task = []

        for wallets in wallet:
             task.append(main(wallet=wallets))
        await asyncio.gather(*task)

    else:

        if need_random == True: # если надо работать с выбраными кошельками

            print(number_wallets)
            target_wallet = [wallet[i] for i in number_wallets]
            print(f"Буду работать с {target_wallet}")
            for wallets in target_wallet:
                await main(wallet=wallets)
                time_sleep = random.randint(sleep_from_wallet,sleep_to_wallet)
                print(f"Ожидаю {time_sleep} перед следующим кошельком")
                await asyncio.sleep(time_sleep)

        else:
            print(f"Буду работать с {wallet}")

            for wallets in wallet:
                await main(wallet=wallets)
                time_sleep = random.randint(sleep_from_wallet,sleep_to_wallet)
                print(f"Ожидаю {time_sleep} перед следующим кошельком")
                await asyncio.sleep(time_sleep)






asyncio.run(test())
