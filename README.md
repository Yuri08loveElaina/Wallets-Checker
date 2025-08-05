# 🦊 Wallets Checker - Multi-chain Wallet Intelligence Tool

A fast wallet intelligence and checker tool written in Python, supporting **multi-chain** analysis with no API key required.  
Perfect for OSINT, NFT forensics, airdrop hunting, and blockchain data exploration.

---

## ✅ Features

- Check wallet ETH balances across multiple chains
- Detect NFT holdings
- Show token balances
- Export results to CSV/Excel
- Fully CLI-driven, no API key needed
- Fast async mode
- Easy to use — all in one file

---

## 🚀 Usage

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the tool
```bash
python wallet_hunter.py --input wallets.txt --output result.csv --mode all
```

#### Parameters:
| Flag           | Description                                 | Example                     |
|----------------|---------------------------------------------|-----------------------------|
| `--input`      | Path to your wallet list (0x....)           | `--input wallets.txt`       |
| `--output`     | Output CSV or XLSX file                     | `--output output.csv`       |
| `--mode`       | Mode: `balance`, `nft`, `token`, `all`      | `--mode all`                |
| `--format`     | Output format: `csv` or `xlsx`              | `--format csv`              |
| `--threads`    | Number of async workers (default: 10)       | `--threads 20`              |
| `--chain`      | Chain to check: `eth`, `bsc`, `polygon`, `all` | `--chain all`            |

---

## 📦 Input Example (wallets.txt)

```
0x742d35Cc6634C0532925a3b844Bc454e4438f44e
0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0
```

---

## 📤 Output Example (CSV)

| Wallet Address                             | Chain   | ETH Balance | NFTs Found | Tokens Found |
|-------------------------------------------|---------|-------------|------------|---------------|
| 0x742d35Cc6634C0532925a3b844Bc454e4438f44e | Ethereum| 500.23      | 2 BAYC     | 3 Tokens      |
| 0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0 | BSC     | 0.00        | 0          | 1 Token       |

---

## 🛠 Notes

- No API keys are required, all data is scraped or gathered from public sources.
- You can analyze hundreds of wallets simultaneously.
- NFT detection uses heuristics on common contracts.

---

## 📁 License

MIT License
