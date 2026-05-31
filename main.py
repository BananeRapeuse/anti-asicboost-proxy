import socket
import threading
import json
from datetime import datetime

HOST = "0.0.0.0"
PORT = 3333

POOL_HOST = "fenixpool.com"
POOL_PORT = 5555

stats = {"acc":0, "rej":0, "low":0}

def log(x):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {x}")

def safe_json(data):
    try:
        return json.loads(data)
    except:
        return None


# 🔒 FORCE DISABLE VERSION ROLLING (CORE FIX)
def patch_notify(msg):
    if msg.get("method") != "mining.notify":
        return msg

    try:
        params = msg.get("params", [])

        # mining.notify → index 6 = version mask (selon stratum)
        if len(params) > 6:
            old = params[6]

            # 🔥 FORCE SAFE MASK (no rolling bits)
            params[6] = "1a000000"

            msg["params"] = params

            log(f"🔧 version mask patched {old} → {params[6]}")

    except:
        pass

    return msg


def patch_config(msg):
    if msg.get("method") == "mining.configure":
        log("⚙️ mining.configure detected (forcing no ASICBoost)")
        try:
            msg["params"] = msg.get("params", {})
            if isinstance(msg["params"], dict):
                msg["params"]["version-rolling"] = False
        except:
            pass
    return msg


def pipe(src, dst, direction):
    buf = ""

    while True:
        try:
            data = src.recv(8192)
            if not data:
                break

            buf += data.decode(errors="ignore")

            while "\n" in buf:
                line, buf = buf.split("\n", 1)

                msg = safe_json(line)
                if not msg:
                    continue

                # MINER → POOL
                if direction == "c2p":
                    msg = patch_config(msg)
                    msg = patch_notify(msg)

                # POOL → MINER
                else:
                    if msg.get("result") is True:
                        stats["acc"] += 1
                        log("✔ ACCEPT")
                    elif msg.get("result") is False:
                        stats["rej"] += 1
                        log(f"❌ REJECT {msg.get('error')}")

                dst.sendall((json.dumps(msg) + "\n").encode())

        except Exception as e:
            log(f"pipe error {e}")
            break


def handle(c):
    s = socket.socket()
    s.connect((POOL_HOST, POOL_PORT))

    threading.Thread(target=pipe, args=(c,s,"c2p"), daemon=True).start()
    threading.Thread(target=pipe, args=(s,c,"p2c"), daemon=True).start()


def main():
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(10)

    log("🚀 proxy V2 LCC anti-ASICBoost running")

    while True:
        c, addr = sock.accept()
        log(f"miner {addr}")
        threading.Thread(target=handle, args=(c,), daemon=True).start()


if __name__ == "__main__":
    main()