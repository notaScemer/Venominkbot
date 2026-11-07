# VENOM INK Backend starter

## Что это
Стартовый сервер FastAPI + PostgreSQL для Telegram Mini App: проверка подписи initData, создание профиля, проверка подписки на @Venominkhh, профиль, реферальные привязки, заявки на фиксированные 15 внутренних единиц и админский просмотр/смена статуса.

**Это серверный каркас, не завершённая интеграция существующего HTML.** Текущий `index.html` нужно отдельно подключить к API: передавать `Telegram.WebApp.initData` в заголовке `Authorization: tma <initData>` и вызывать `/api/me`, `/api/profile`, `/api/orders` и `/api/admin/orders`.

## Безопасность и ограничения
- Не публикуйте BOT_TOKEN и DATABASE_URL.
- ADMIN_IDS должны содержать числовые Telegram ID, а не username.
- Команда `/id` бота показывает ваш ID. Каждый администратор должен написать боту `/id`; внесите оба числа в Render.
- Бот должен быть администратором канала @Venominkhh для надёжной проверки подписки.
- Заказ на 15 здесь списывает 15 внутренних единиц. Это НЕ отправляет Telegram Stars автоматически. Выдачу реальных Stars выполняет администратор отдельно через предусмотренный Telegram процесс; не отмечайте заказ выданным до фактической выдачи.
- Для реферальных начислений и игровых наград нужно добавить серверные правила после согласования экономики. Не доверяйте суммам, присланным браузером.
- В production установите HTTPS URL и задайте webhook через setWebhook, передав secret_token=WEBHOOK_SECRET.
- Установите WEBHOOK_SECRET как длинную случайную строку.

## Размещение
1. Создайте PostgreSQL в Render и скопируйте Internal Database URL.
2. Создайте Web Service из репозитория с этими файлами.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Добавьте переменные из `.env.example` в Environment.
6. Для webhook после публикации вызовите Telegram setWebhook с URL `https://ВАШ-СЕРВЕР.onrender.com/telegram/webhook` и secret_token, совпадающим с WEBHOOK_SECRET.
7. В BotFather укажите Netlify URL как Web App URL.

## Получение Telegram ID
Запустите бота и отправьте `/id`. Добавьте ID обоих администраторов в `ADMIN_IDS`, например `123456789,987654321`, затем перезапустите сервис.
