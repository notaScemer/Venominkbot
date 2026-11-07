# VENOM INK backend v1.1

Deploy this folder's contents to the GitHub repository connected to Render (root directory empty).

Build: `pip install -r requirements.txt`
Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Environment variables: BOT_TOKEN, DATABASE_URL, CHANNEL_USERNAME, ADMIN_IDS, WEBHOOK_SECRET.

Features: Telegram Mini App initData validation, PostgreSQL user records, 15 Ink daily login reward, server-side wheel (50 Ink per spin), 1000 Ink order for 15 Stars, admin user list, admin order status. Stars are NOT sent automatically; admins must pay manually in Telegram and mark delivered.

Important: this is a beta starter. The HTML's remaining quest/referral buttons are not all connected to secure server-side rewards yet. Do not launch paid/redeemable rewards until those endpoints and Telegram webhook setup are completed and tested. Set the actual Telegram bot username in the referral URL in app/main.py (YOUR_BOT_USERNAME).
