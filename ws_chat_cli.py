import asyncio
import json
import sys
from pathlib import Path

import websockets

ORIGIN = "http://localhost:8000"
DEFAULT_TOKENS_FILE = "tokens.json"

HELP = """
Commands:
  /m <text>             send message
  /typing on|off        typing indicator
  /read <message_id>    send read receipt (marks read up to this id)
  /join <conv_id>       join conversation (needed if you connect to /ws/chat/ gateway)
  /leave <conv_id>      leave conversation
  /help                 show help
  /quit                 exit
If you just type text without a command, it sends as a message.
""".strip()


def build_ws_url(base: str, conv_id: int | None, token: str, use_gateway: bool) -> str:
    if use_gateway or conv_id is None:
        # Gateway route
        return f"{base}/ws/chat/?token={token}"
    # Conversation alias route (auto-join)
    return f"{base}/ws/chat/conversations/{conv_id}/?token={token}"


def load_token(role: str, tokens_path: str) -> str:
    path = Path(tokens_path)
    if not path.exists():
        raise FileNotFoundError(
            f"tokens file not found: {path.resolve()}  (create {DEFAULT_TOKENS_FILE} next to the project)"
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    if role not in data or not isinstance(data[role], str) or not data[role].strip():
        raise KeyError(
            f"token for role '{role}' not found in {path.resolve()}. "
            f"Available roles: {', '.join(sorted(data.keys()))}"
        )
    return data[role].strip()


async def receiver(ws, name: str):
    while True:
        raw = await ws.recv()
        try:
            msg = json.loads(raw)
        except Exception:
            print(f"\n📩 {name} RAW:", raw)
            continue

        t = msg.get("type")

        if t == "message":
            text = msg.get("text")
            print(
                f"\n📩 {name} MESSAGE: (id={msg.get('id')}) "
                f"from {msg.get('sender_id')} -> {text!r}"
            )
        elif t == "delivered":
            print(
                f"\n✅ {name} DELIVERED: conv={msg.get('conversation_id')} "
                f"user={msg.get('user_id')} up_to_id={msg.get('up_to_id')}"
            )
        elif t == "read":
            print(
                f"\n👁️  {name} READ: conv={msg.get('conversation_id')} "
                f"user={msg.get('user_id') or msg.get('reader_id')} up_to_id={msg.get('up_to_id')}"
            )
        else:
            print(f"\n📩 {name} EVENT:", msg)


async def sender(ws, name: str, conv_id: int | None):
    loop = asyncio.get_event_loop()
    print(HELP)
    while True:
        line = await loop.run_in_executor(None, input, f"✍️  {name}> ")
        line = (line or "").strip()
        if not line:
            continue

        if line in ("/quit", "/exit"):
            await ws.close()
            return

        if line == "/help":
            print(HELP)
            continue

        if line.startswith("/typing "):
            arg = line.split(maxsplit=1)[1].strip().lower()
            is_typing = arg in ("on", "true", "1", "yes")
            if conv_id is None:
                print("⚠️ You must set conversation_id (run with it) or /join first.")
                continue
            await ws.send(json.dumps({"type": "typing", "conversation_id": conv_id, "is_typing": is_typing}))
            continue

        if line.startswith("/read "):
            parts = line.split()
            if len(parts) != 2 or not parts[1].isdigit():
                print("Usage: /read <message_id>")
                continue
            if conv_id is None:
                print("⚠️ You must set conversation_id (run with it) or /join first.")
                continue

            # IMPORTANT: consumer expects "up_to_id", not "message_id"
            await ws.send(
                json.dumps({"type": "read", "conversation_id": conv_id, "up_to_id": int(parts[1])})
            )
            continue

        if line.startswith("/join "):
            parts = line.split()
            if len(parts) != 2 or not parts[1].isdigit():
                print("Usage: /join <conversation_id>")
                continue
            conv_id = int(parts[1])
            await ws.send(json.dumps({"type": "join", "conversation_id": conv_id}))
            continue

        if line.startswith("/leave "):
            parts = line.split()
            if len(parts) != 2 or not parts[1].isdigit():
                print("Usage: /leave <conversation_id>")
                continue
            cid = int(parts[1])
            await ws.send(json.dumps({"type": "leave", "conversation_id": cid}))
            if conv_id == cid:
                conv_id = None
            continue

        # Default: send message
        text = line[3:].strip() if line.startswith("/m ") else line

        if conv_id is None:
            print("⚠️ No conversation_id set. Start with /join <id> or run with conv_id argument.")
            continue

        await ws.send(json.dumps({"type": "message", "conversation_id": conv_id, "text": text}))


async def run(role: str, conv_id: int | None, base: str, tokens_path: str, use_gateway: bool):
    token = load_token(role, tokens_path)
    url = build_ws_url(base, conv_id, token, use_gateway)

    # Origin header helps with AllowedHostsOriginValidator in your ASGI stack
    async with websockets.connect(url, additional_headers={"Origin": ORIGIN}) as ws:
        print(f"✅ {role} connected: {url.split('?')[0]}  (token hidden)")
        await asyncio.gather(receiver(ws, role), sender(ws, role, conv_id))


def parse_args(argv: list[str]):
    if len(argv) < 2:
        print(
            "Usage:\n"
            "  python ws_chat_cli.py <Role> [conversation_id] [--gateway] "
            "[--base ws://host:port] [--tokens tokens.json]\n"
        )
        print("Examples:")
        print("  python ws_chat_cli.py Operator 1")
        print("  python ws_chat_cli.py Customer 1")
        print("  python ws_chat_cli.py Operator --gateway   (then /join 1)")
        sys.exit(1)

    role = argv[1]
    conv_id = None
    use_gateway = False
    base = "ws://localhost:8000"
    tokens_path = DEFAULT_TOKENS_FILE

    i = 2
    while i < len(argv):
        a = argv[i]
        if a.isdigit():
            conv_id = int(a)
        elif a == "--gateway":
            use_gateway = True
        elif a == "--base":
            i += 1
            if i >= len(argv):
                print("Missing value after --base")
                sys.exit(1)
            base = argv[i]
        elif a == "--tokens":
            i += 1
            if i >= len(argv):
                print("Missing value after --tokens")
                sys.exit(1)
            tokens_path = argv[i]
        else:
            print(f"Unknown arg: {a}")
            sys.exit(1)
        i += 1

    return role, conv_id, base, tokens_path, use_gateway


def main():
    role, conv_id, base, tokens_path, use_gateway = parse_args(sys.argv)
    try:
        asyncio.run(run(role, conv_id, base, tokens_path, use_gateway))
    except KeyboardInterrupt:
        print("\n👋 bye")


if __name__ == "__main__":
    main()