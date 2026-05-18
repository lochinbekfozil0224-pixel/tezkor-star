# Tezkor Star — Backend

Bot va Web API bir vaqtda ishlaydi. Telegram Mini App va bot ikkalasi ham bir xil database'ga yozadi.

## Lokalda ishga tushirish

```bash
cd backend
pip install -r requirements.txt

# .env yaratish
cp .env.example .env
# .env faylni tahrirlash

python main.py
```

## Railway'ga deploy qilish

### 1. Railway'da yangi loyiha yaratish
1. https://railway.com → New Project → Deploy from GitHub
2. Yoki `railway up` (CLI orqali)

### 2. Environment variables qo'shish
Railway dashboard → Variables:
- `BOT_TOKEN` = `8712600970:AAFFXIwrY1Rg_sVj4GrxXkMaqgEFSh0-J38`
- `ADMIN_ID` = `8135915671`
- `WEBAPP_URL` = (Vercel deploy'dan keyin qo'yiladi)
- `DB_PATH` = `/data/bot.db`

### 3. Volume qo'shish (database persistencе uchun)
1. Service → Settings → Volumes
2. Add Volume → Mount path: `/data`
3. Bu SQLite faylni saqlab turadi (deploy bo'lganda yo'qolmaydi)

### 4. Domain
1. Service → Settings → Networking → Generate Domain
2. URL'ni nusxalang (masalan `https://tezkor-star.up.railway.app`)
3. Bu API URL frontend'da ishlatiladi

## BotFather sozlamalari

Telegram'da @BotFather'ga yozing:

```
/setmenubutton
@tezkor_star_bot
Menu button text: 🌐 Saytni ochish
Menu button URL: https://tezkor-star.vercel.app
```

## Endpoint'lar

- `GET /` — health check
- `GET /api/me` — joriy foydalanuvchi
- `GET /api/packages/stars` — star paketlari
- `GET /api/packages/premium` — premium paketlari
- `POST /api/buy/stars` — star sotib olish (balansdan)
- `POST /api/buy/premium` — premium sotib olish
- `POST /api/topup/request` — balansga to'ldirish so'rovi
- `GET /api/orders` — buyurtmalar tarixi
- `GET /api/transactions` — tranzaksiyalar tarixi
- `GET /api/ratings/spending` — xarid reytingi
- `GET /api/ratings/referrals` — referal reytingi
- `GET /api/admin/*` — admin endpoint'lari (faqat admin'lar uchun)

Har bir API so'rovi `X-Init-Data` header'ida Telegram WebApp `initData`'sini kutadi.
