from flask import Flask, request, jsonify
from flask_sock import Sock
import random
import time
import threading

app = Flask(__name__)
sock = Sock(app)

rooms = {}
rooms_lock = threading.Lock()

def make_code():
    return "".join(str(random.randint(0, 9)) for _ in range(5))

@app.route("/")
def home():
    return "PixelForge WebSocket relay online"

@app.route("/create")
def create():
    code = make_code()

    with rooms_lock:
        rooms[code] = {
            "code": code,
            "created": time.time(),
            "game": "",
            "host_ready": True,
            "joiner_ready": False,
            "host_ws": None,
            "joiner_ws": None,
            "host_data": "",
            "joiner_data": ""
        }

    return jsonify({"ok": True, "code": code})

@app.route("/join")
def join():
    code = request.args.get("code", "")

    with rooms_lock:
        if code not in rooms:
            return jsonify({"ok": False, "error": "room_not_found"}), 404

        rooms[code]["joiner_ready"] = True
        game = rooms[code]["game"]

    return jsonify({"ok": True, "code": code, "game": game})

@app.route("/setgame")
def setgame():
    code = request.args.get("code", "")
    game = request.args.get("game", "")

    with rooms_lock:
        if code not in rooms:
            return jsonify({"ok": False, "error": "room_not_found"}), 404

        rooms[code]["game"] = game
        host_ws = rooms[code].get("host_ws")
        joiner_ws = rooms[code].get("joiner_ws")

    # Tell connected players which game was picked.
    msg = "GAME|" + game

    for ws in [host_ws, joiner_ws]:
        if ws is not None:
            try:
                ws.send(msg)
            except:
                pass

    return jsonify({"ok": True, "game": game})

@app.route("/status")
def status():
    code = request.args.get("code", "")

    with rooms_lock:
        if code not in rooms:
            return jsonify({"ok": False, "error": "room_not_found"}), 404

        room = rooms[code]

        return jsonify({
            "ok": True,
            "code": room["code"],
            "game": room["game"],
            "host_ready": room["host_ready"],
            "joiner_ready": room["joiner_ready"],
            "host_connected": room["host_ws"] is not None,
            "joiner_connected": room["joiner_ws"] is not None
        })

@sock.route("/ws")
def websocket(ws):
    code = request.args.get("code", "")
    player = request.args.get("player", "")

    if player not in ["host", "joiner"]:
        ws.send("ERR|bad_player")
        return

    with rooms_lock:
        if code not in rooms:
            ws.send("ERR|room_not_found")
            return

        room = rooms[code]

        if player == "host":
            room["host_ws"] = ws
        else:
            room["joiner_ws"] = ws
            room["joiner_ready"] = True

        game = room["game"]

    ws.send("OK|" + code)

    if game != "":
        ws.send("GAME|" + game)

    try:
        while True:
            msg = ws.receive()

            if msg is None:
                break

            # Message format:
            # DATA|whatever
            # Server forwards it to the other player.
            if msg.startswith("DATA|"):
                with rooms_lock:
                    room = rooms.get(code)

                    if room is None:
                        break

                    if player == "host":
                        room["host_data"] = msg
                        other_ws = room.get("joiner_ws")
                    else:
                        room["joiner_data"] = msg
                        other_ws = room.get("host_ws")

                if other_ws is not None:
                    try:
                        other_ws.send(msg)
                    except:
                        pass

            elif msg == "PING":
                ws.send("PONG")

    except Exception as e:
        print("WebSocket error:", e)

    finally:
        with rooms_lock:
            room = rooms.get(code)

            if room is not None:
                if player == "host" and room.get("host_ws") is ws:
                    room["host_ws"] = None

                if player == "joiner" and room.get("joiner_ws") is ws:
                    room["joiner_ws"] = None
