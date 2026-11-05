# LumoNews Telegram Bot

نسخه تلگرام ربات LumoNews برای هاست (FadeHost / Laplace و مشابه).

## اجرا روی FadeHost
1. نوع هاست: **Telegram bot**
2. **Upload your code** و همین ZIP را آپلود کن
3. Entry / start command معمولاً:
   ```
   python main.py
   ```
4. اگر فیلد Token جدا خواست، همین توکن را هم آنجا بگذار (داخل کد هم هست)

## اولین راه‌اندازی
1. در تلگرام به ربات `/start` بزن
2. `/setadmin` بزن تا ادمین اصلی شوی (فقط وقتی لیست ادمین خالی است)
3. `/id` شناسه عددی‌ات را نشان می‌دهد

## دستورهای مهم
- `/stock` `/values` `/fruits` `/permanent` `/limiteds` `/gamepasses`
- `/services` — خدمات بلاکس فروت + جدول کندی
- `/broadcast متن` — پیام سراسری (ادمین)
- `/servicereply شماره متن` — پاسخ به درخواست خدمات

## فایل‌ها
- `main.py` — نقطه شروع
- `telegram_bot.py` — منطق ربات
- `core.py` — استاک و ولیو
- `telegram_data.json` — بعد از اجرا ساخته می‌شود
