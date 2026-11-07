import os, hmac, hashlib, json, time
from urllib.parse import parse_qsl
from typing import Optional
import asyncpg, httpx
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel, Field

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")
CHANNEL = os.environ.get("CHANNEL_USERNAME", "@Venominkhh")
ADMIN_IDS = {int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

app = FastAPI(title="VENOM INK API", version="1.0.0")
pool: Optional[asyncpg.Pool] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 telegram_id BIGINT PRIMARY KEY, username TEXT, first_name TEXT, nickname TEXT,
 photo_url TEXT, balance NUMERIC(14,3) NOT NULL DEFAULT 0,
 referred_by BIGINT REFERENCES users(telegram_id), created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS orders (
 id BIGSERIAL PRIMARY KEY, order_code TEXT UNIQUE NOT NULL,
 telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
 stars INTEGER NOT NULL CHECK (stars = 15),
 status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','delivered','rejected')),
 created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now(),
 delivered_by BIGINT
);
CREATE TABLE IF NOT EXISTS referrals (
 inviter_id BIGINT NOT NULL REFERENCES users(telegram_id),
 invited_id BIGINT UNIQUE NOT NULL REFERENCES users(telegram_id),
 created_at TIMESTAMPTZ DEFAULT now()
);
"""

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as c:
        await c.execute(SCHEMA)

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()

def verify_init_data(init_data: str) -> dict:
    if not init_data:
        raise HTTPException(401, "Open this app from Telegram.")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        raise HTTPException(401, "Missing Telegram signature.")
    auth_date = int(pairs.get("auth_date", "0"))
    if time.time() - auth_date > 86400:
        raise HTTPException(401, "Telegram session expired. Reopen the app.")
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received):
        raise HTTPException(401, "Invalid Telegram signature.")
    try:
        return {"user": json.loads(pairs["user"]), "start_param": pairs.get("start_param", "")}
    except Exception:
        raise HTTPException(401, "Telegram user data is missing.")

async def current_user(authorization: Optional[str]):
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(401, "Missing Telegram initData.")
    data = verify_init_data(authorization[4:])
    u = data["user"]
    tid = int(u["id"])
    async with pool.acquire() as c:
        row = await c.fetchrow("SELECT * FROM users WHERE telegram_id=$1", tid)
        if not row:
            ref = data["start_param"]
            inviter = None
            if ref.startswith("ref_"):
                try: inviter = int(ref[4:])
                except ValueError: pass
                if inviter == tid: inviter = None
            await c.execute("""
              INSERT INTO users(telegram_id,username,first_name,nickname,referred_by)
              VALUES($1,$2,$3,$3,$4) ON CONFLICT(telegram_id) DO NOTHING
            """, tid, u.get("username"), u.get("first_name","User"), inviter)
            if inviter:
                await c.execute("""
                  INSERT INTO referrals(inviter_id,invited_id) VALUES($1,$2)
                  ON CONFLICT(invited_id) DO NOTHING
                """, inviter, tid)
            row = await c.fetchrow("SELECT * FROM users WHERE telegram_id=$1", tid)
        else:
            await c.execute("UPDATE users SET username=$2, first_name=$3 WHERE telegram_id=$1",
                            tid, u.get("username"), u.get("first_name","User"))
            row = await c.fetchrow("SELECT * FROM users WHERE telegram_id=$1", tid)
    return row

async def tg(method, payload=None):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=payload or {})
        data = r.json()
        if not data.get("ok"):
            raise HTTPException(502, f"Telegram API error: {data.get('description','unknown')}")
        return data["result"]

class ProfileUpdate(BaseModel):
    nickname: str = Field(min_length=2, max_length=32)
    photo_url: str = Field(default="", max_length=500)

class OrderCreate(BaseModel):
    stars: int = Field(ge=15, le=15)

class StatusUpdate(BaseModel):
    status: str

@app.get("/")
async def health():
    return {"ok": True, "service": "VENOM INK API", "version": "1.0.0"}

@app.get("/api/me")
async def me(authorization: Optional[str] = Header(default=None)):
    u = await current_user(authorization)
    async with pool.acquire() as c:
        referrals = await c.fetchval("SELECT count(*) FROM referrals WHERE inviter_id=$1", u["telegram_id"])
        orders = await c.fetch("SELECT order_code,stars,status,created_at FROM orders WHERE telegram_id=$1 ORDER BY id DESC", u["telegram_id"])
    return {"telegram_id": u["telegram_id"], "username": u["username"], "first_name": u["first_name"],
            "nickname": u["nickname"], "photo_url": u["photo_url"], "balance": str(u["balance"]),
            "referrals": referrals, "referral_link": f"https://t.me/YOUR_BOT_USERNAME?start=ref_{u['telegram_id']}",
            "orders": [dict(x) for x in orders]}

@app.put("/api/profile")
async def profile(body: ProfileUpdate, authorization: Optional[str] = Header(default=None)):
    u = await current_user(authorization)
    async with pool.acquire() as c:
        await c.execute("UPDATE users SET nickname=$2,photo_url=$3 WHERE telegram_id=$1",
                        u["telegram_id"], body.nickname, body.photo_url)
    return {"ok": True}

@app.get("/api/subscription")
async def subscription(authorization: Optional[str] = Header(default=None)):
    u = await current_user(authorization)
    try:
        member = await tg("getChatMember", {"chat_id": CHANNEL, "user_id": u["telegram_id"]})
        return {"subscribed": member["status"] in ("creator","administrator","member") or
                (member["status"] == "restricted" and member.get("is_member", False))}
    except HTTPException:
        return {"subscribed": False, "reason": "Could not verify channel membership."}

@app.post("/api/orders")
async def create_order(body: OrderCreate, authorization: Optional[str] = Header(default=None)):
    u = await current_user(authorization)
    async with pool.acquire() as c:
        async with c.transaction():
            row = await c.fetchrow("SELECT balance FROM users WHERE telegram_id=$1 FOR UPDATE", u["telegram_id"])
            if row["balance"] < 15:
                raise HTTPException(400, "Not enough balance. Need 15 internal stars.")
            code = "VI-" + str(int(time.time())) + "-" + str(u["telegram_id"])[-5:]
            await c.execute("UPDATE users SET balance=balance-15 WHERE telegram_id=$1", u["telegram_id"])
            order = await c.fetchrow("""
              INSERT INTO orders(order_code,telegram_id,stars) VALUES($1,$2,15)
              RETURNING order_code,telegram_id,stars,status,created_at
            """, code, u["telegram_id"])
    return dict(order)

@app.get("/api/orders")
async def my_orders(authorization: Optional[str] = Header(default=None)):
    u = await current_user(authorization)
    async with pool.acquire() as c:
        rows = await c.fetch("SELECT order_code,stars,status,created_at FROM orders WHERE telegram_id=$1 ORDER BY id DESC", u["telegram_id"])
    return [dict(x) for x in rows]

@app.get("/api/admin/orders")
async def admin_orders(authorization: Optional[str] = Header(default=None)):
    u = await current_user(authorization)
    if u["telegram_id"] not in ADMIN_IDS: raise HTTPException(403, "Admin only.")
    async with pool.acquire() as c:
        rows = await c.fetch("""
          SELECT o.order_code,o.telegram_id,o.stars,o.status,o.created_at,u.username,u.nickname
          FROM orders o JOIN users u USING(telegram_id) ORDER BY o.id DESC LIMIT 200
        """)
    return [dict(x) for x in rows]

@app.patch("/api/admin/orders/{order_code}")
async def update_order(order_code: str, body: StatusUpdate, authorization: Optional[str] = Header(default=None)):
    u = await current_user(authorization)
    if u["telegram_id"] not in ADMIN_IDS: raise HTTPException(403, "Admin only.")
    if body.status not in ("delivered","rejected"): raise HTTPException(400, "Invalid status.")
    async with pool.acquire() as c:
        row = await c.fetchrow("UPDATE orders SET status=$2,updated_at=now(),delivered_by=$3 WHERE order_code=$1 RETURNING order_code,status",
                               order_code, body.status, u["telegram_id"])
    if not row: raise HTTPException(404, "Order not found.")
    return dict(row)

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: Optional[str] = Header(default=None)):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(403, "Bad webhook secret.")
    update = await request.json()
    msg = update.get("message", {})
    if msg:
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "")
        if text.startswith("/start") and chat_id:
            await tg("sendMessage", {"chat_id": chat_id, "text": "VENOM INK готов. Открой Mini App через кнопку меню бота."})
        elif text == "/id" and chat_id:
            await tg("sendMessage", {"chat_id": chat_id, "text": f"Твой Telegram ID: {chat_id}"})
    return {"ok": True}
