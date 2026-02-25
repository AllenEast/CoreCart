# Pro Chat (Karzinka)

Bu paketda chat **realtime** ishlaydi (Django Channels + Redis) va quyidagi "pro" featurelar bor:

- ✅ Realtime message
- ✅ Typing indicator (`type=typing`)
- ✅ Presence (online user id lar) (`type=presence`)
- ✅ Read receipts (2-sided: user/staff)
- ✅ Pagination (`type=fetch` yoki REST orqali)

## 1) Redis ishga tushirish

### Variant A: docker compose

```bash
docker compose -f docker-compose.redis.yml up -d
```

### Variant B: local

Redis o'rnating va 6379 portda ishga tushiring.

## 2) .env

`karzina/settings/base.py` Redis URL ni shundan oladi:

```env
REDIS_URL=redis://127.0.0.1:6379/0
```

Dockerda bo'lsa:

```env
REDIS_URL=redis://redis:6379/0
```

## 3) Install + migrate

```bash
pip install -r requirements.txt
python manage.py migrate
```

## 4) Websocket ulanish

JWT access token query orqali yuboriladi:

```txt
ws://localhost:8000/ws/chat/<room_id>/?token=<ACCESS_TOKEN>
```

### Client -> server

```json
{ "type": "message", "text": "salom" }
{ "type": "typing", "is_typing": true }
{ "type": "read", "up_to_id": 123 }
{ "type": "fetch", "before_id": 200, "limit": 30 }
```

### Server -> client

```json
{ "type": "meta", "room_id": 1, "unread": 5 }
{ "type": "message", "id": 1, "room_id": 1, "sender_id": 10, "text": "salom", "created_at": "...", "read_by_user": true, "read_by_staff": false }
{ "type": "typing", "room_id": 1, "user_id": 10, "is_typing": true }
{ "type": "presence", "room_id": 1, "online": [10, 2] }
{ "type": "read", "room_id": 1, "up_to_id": 123, "reader_id": 10 }
{ "type": "messages", "room_id": 1, "items": [ ... ] }
```

## 5) REST API

`/api/chat/`:

- `GET /api/chat/rooms/` (staff: hammasi, user: o'ziniki)
- `POST /api/chat/rooms/` (user uchun: o'ziga room create/get)
- `GET /api/chat/rooms/<room_id>/messages/?before_id=&limit=`
- `POST /api/chat/rooms/<room_id>/read/` body: `{ "up_to_id": 123 }`
