import os
import sys
import json
import csv
import time
import random
import sqlite3
import asyncio
import platform
from typing import List, Dict
from mnemonic import Mnemonic
from web3 import Web3, HTTPProvider
from eth_account import Account
from eth_utils import to_checksum_address
from solana.rpc.async_api import AsyncClient as SolanaClient
from solana.keypair import Keypair as SolanaKeypair
from solana.publickey import PublicKey as SolanaPublicKey
from aptos_sdk.account import Account as AptosAccount
from aptos_sdk.client import RestClient as AptosRestClient
import openpyxl

ETH_RPC_DEFAULT = "https://cloudflare-eth.com"
PROXY_LIST = []
DB_FILE = "wallets.db"
os.makedirs("wallets/live", exist_ok=True)

mnemo = Mnemonic("english")

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
]

def clear():
    os.system("cls" if platform.system() == "Windows" else "clear")

def save_csv(filename, data: List[Dict]):
    if not data:
        return
    keys = data[0].keys()
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(data)

def save_xlsx(filename, data: List[Dict]):
    wb = openpyxl.Workbook()
    ws = wb.active
    if not data:
        wb.save(filename)
        return
    ws.append(list(data[0].keys()))
    for row in data:
        ws.append(list(row.values()))
    wb.save(filename)

def db_init():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS wallets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chain TEXT,
        address TEXT UNIQUE,
        private_key TEXT,
        mnemonic TEXT,
        balance REAL,
        token_balances TEXT,
        ens_name TEXT,
        nft_data TEXT,
        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    con.commit()
    return con, cur

def levenshtein_distance(a, b):
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)
    previous_row = range(len(b) + 1)
    for i, c1 in enumerate(a):
        current_row = [i + 1]
        for j, c2 in enumerate(b):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def fix_mnemonic(mnemonic):
    words = mnemonic.strip().split()
    corrected = []
    for w in words:
        if mnemo.check(w):
            corrected.append(w)
        else:
            close_word = min(mnemo.wordlist, key=lambda x: levenshtein_distance(x, w))
            corrected.append(close_word)
    return " ".join(corrected)

def get_random_proxy():
    if PROXY_LIST:
        return random.choice(PROXY_LIST)
    return None

def create_w3_with_proxy(proxy=None):
    provider = HTTPProvider(ETH_RPC_DEFAULT)
    w3 = Web3(provider)
    return w3

def generate_eth_wallet(mnemonic=None):
    if mnemonic is None:
        mnemonic = mnemo.generate(strength=128)
    acct = Account.from_mnemonic(mnemonic)
    return {"chain": "ETH", "mnemonic": mnemonic, "address": acct.address, "private_key": acct.key.hex()}

def generate_solana_wallet():
    keypair = SolanaKeypair.generate()
    return {"chain": "SOL", "mnemonic": None, "address": str(keypair.public_key), "private_key": list(keypair.secret_key)}

def generate_aptos_wallet():
    account = AptosAccount.generate()
    return {"chain": "APTOS", "mnemonic": None, "address": account.address(), "private_key": account.private_key.hex()}

def check_eth_wallet(w3, address):
    try:
        balance_wei = w3.eth.get_balance(address)
        balance_eth = w3.fromWei(balance_wei, "ether")
    except Exception:
        return None, {}
    tokens = {
        "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
        "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
    }
    token_balances = {}
    for taddr, symbol in tokens.items():
        try:
            contract = w3.eth.contract(address=to_checksum_address(taddr), abi=ERC20_ABI)
            bal = contract.functions.balanceOf(address).call()
            dec = contract.functions.decimals().call()
            token_balances[symbol] = bal / (10 ** dec)
        except Exception:
            token_balances[symbol] = 0
    return balance_eth, token_balances

async def check_solana_balance(address):
    client = SolanaClient("https://api.mainnet-beta.solana.com")
    try:
        resp = await client.get_balance(SolanaPublicKey(address))
        await client.close()
        if "result" in resp:
            lamports = resp["result"]["value"]
            return lamports / 1e9
    except Exception:
        return None

async def check_aptos_balance(address):
    client = AptosRestClient("https://fullnode.testnet.aptoslabs.com/v1")
    try:
        resources = await client.account_resources(address)
        for r in resources:
            if r["type"] == "0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>":
                balance = int(r["data"]["coin"]["value"])
                return balance / 1_000_000
        return 0
    except Exception:
        return None

def export_wallet_metamask(wallet_data, filename):
    meta_json = {
        "version": 1,
        "id": wallet_data["address"],
        "address": wallet_data["address"][2:].lower(),
        "crypto": {"private_key": wallet_data["private_key"]},
        "mnemonic": wallet_data["mnemonic"],
    }
    with open(filename, "w") as f:
        json.dump(meta_json, f, indent=4)

def db_upsert_wallet(cur, wallet):
    cur.execute("""
    INSERT OR IGNORE INTO wallets(address, chain, private_key, mnemonic, balance, token_balances, ens_name, nft_data)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    (
        wallet["address"], wallet["chain"], wallet["private_key"], wallet["mnemonic"],
        wallet.get("balance", 0), json.dumps(wallet.get("token_balances", {})),
        wallet.get("ens_name", ""), json.dumps(wallet.get("nft_data", {}))
    ))

def print_wallet(wallet):
    print(f"Chain: {wallet['chain']}")
    print(f"Address: {wallet['address']}")
    print(f"Balance: {wallet.get('balance', 'N/A')}")
    print(f"Tokens: {wallet.get('token_balances', {})}")
    print(f"ENS: {wallet.get('ens_name', 'N/A')}")
    print(f"NFTs: {wallet.get('nft_data', 0)}")
    print("-" * 40)

def check_ens_name(w3, address):
    try:
        ens = w3.ens
        name = ens.name(address)
        return name
    except Exception:
        return None

def check_nft_demo(address):
    return random.randint(0, 5)

def main():
    con, cur = db_init()
    while True:
        clear()
        print("1) Generate Wallet (ETH/SOL/APTOS)")
        print("2) Load Leak Wallets JSON File")
        print("3) Check Wallets Balances")
        print("4) Export Live Wallets CSV + Excel")
        print("5) Fix Mnemonic Phrase (Offline AI)")
        print("6) Exit")
        choice = input("Select: ").strip()
        if choice == "1":
            chain = input("Chain (ETH/SOL/APTOS): ").strip().upper()
            if chain == "ETH":
                wallet = generate_eth_wallet()
                w3 = create_w3_with_proxy(get_random_proxy())
                balance, tokens = check_eth_wallet(w3, wallet["address"])
                wallet["balance"] = balance
                wallet["token_balances"] = tokens
                wallet["ens_name"] = check_ens_name(w3, wallet["address"])
                wallet["nft_data"] = check_nft_demo(wallet["address"])
                print_wallet(wallet)
                db_upsert_wallet(cur, wallet)
                con.commit()
                export_wallet_metamask(wallet, f"wallets/live/{wallet['address']}.json")
            elif chain == "SOL":
                wallet = generate_solana_wallet()
                balance = asyncio.run(check_solana_balance(wallet["address"]))
                wallet["balance"] = balance
                wallet["token_balances"] = {}
                wallet["ens_name"] = ""
                wallet["nft_data"] = check_nft_demo(wallet["address"])
                print_wallet(wallet)
                db_upsert_wallet(cur, wallet)
                con.commit()
            elif chain == "APTOS":
                wallet = generate_aptos_wallet()
                balance = asyncio.run(check_aptos_balance(wallet["address"]))
                wallet["balance"] = balance
                wallet["token_balances"] = {}
                wallet["ens_name"] = ""
                wallet["nft_data"] = check_nft_demo(wallet["address"])
                print_wallet(wallet)
                db_upsert_wallet(cur, wallet)
                con.commit()
            else:
                pass
            input()
        elif choice == "2":
            filename = input("File path: ").strip()
            if not os.path.isfile(filename):
                time.sleep(1)
                continue
            with open(filename, "r", encoding="utf-8") as f:
                try:
                    wallets = json.load(f)
                except:
                    time.sleep(1)
                    continue
            for w in wallets:
                db_upsert_wallet(cur, w)
            con.commit()
            input()
        elif choice == "3":
            cur.execute("SELECT * FROM wallets")
            wallets = cur.fetchall()
            if not wallets:
                input()
                continue
            for row in wallets:
                wallet = {"id": row[0], "chain": row[1], "address": row[2], "private_key": row[3], "mnemonic": row[4]}
                if wallet["chain"] == "ETH":
                    w3 = create_w3_with_proxy(get_random_proxy())
                    bal, toks = check_eth_wallet(w3, wallet["address"])
                    ens = check_ens_name(w3, wallet["address"])
                    nft = check_nft_demo(wallet["address"])
                    wallet.update({"balance": bal, "token_balances": toks, "ens_name": ens, "nft_data": nft})
                elif wallet["chain"] == "SOL":
                    bal = asyncio.run(check_solana_balance(wallet["address"]))
                    wallet.update({"balance": bal, "token_balances": {}, "ens_name": "", "nft_data": check_nft_demo(wallet["address"])})
                elif wallet["chain"] == "APTOS":
                    bal = asyncio.run(check_aptos_balance(wallet["address"]))
                    wallet.update({"balance": bal, "token_balances": {}, "ens_name": "", "nft_data": check_nft_demo(wallet["address"])})
                else:
                    continue
                db_upsert_wallet(cur, wallet)
                con.commit()
                print_wallet(wallet)
            input()
        elif choice == "4":
            cur.execute("SELECT chain,address,balance,token_balances,ens_name,nft_data FROM wallets")
            rows = cur.fetchall()
            data = []
            for r in rows:
                data.append({"chain": r[0], "address": r[1], "balance": r[2], "token_balances": r[3], "ens_name": r[4], "nft_data": r[5]})
            save_csv("wallets/live_wallets.csv", data)
            save_xlsx("wallets/live_wallets.xlsx", data)
            input()
        elif choice == "5":
            phrase = input("Mnemonic: ").strip()
            fixed = fix_mnemonic(phrase)
            print(fixed)
            input()
        elif choice == "6":
            break
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()
