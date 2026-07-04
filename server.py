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

@app.route("/version")
def version():
    return "PixelForge relay version: SYNC V3"

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
            "host_connected": False,
            "joiner_connected": False,
            "host_data": "",
            "joiner_data": "",
            "message_id": 0
        }

    return jsonify({"ok": True, "code": code})

@app.route("/join")
def join():
    code = request.args.get("code", "")

    with rooms_lock:
        if code not in rooms:
            return jsonify({"ok": False, "error": "room_not_found"}), 404

        rooms[code]["joiner_ready"] = True
        rooms[code]["message_id"] += 1
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
        rooms[code]["message_id"] += 1

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
            "host_connected": room["host_connected"],
            "joiner_connected": room["joiner_connected"],
            "host_data": room["host_data"],
            "joiner_data": room["joiner_data"],
            "message_id": room["message_id"]
        })


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

        if player == "host":
            rooms[code]["host_connected"] = True
        else:
            rooms[code]["joiner_connected"] = True
            rooms[code]["joiner_ready"] = True

        game = rooms[code]["game"]

    ws.send("OK|" + code)

    if game != "":
        ws.send("GAME|" + game)

    try:
        while True:
            msg = ws.receive()

            if msg is None:
                break

            # Main fast sync message:
            # SYNC|data
            #
            # Host sends full game state.
            # Server replies with latest joiner data.
            #
            # Joiner sends paddle y.
            # Server replies with latest host data.
            if msg.startswith("SYNC|"):
                data = msg[5:]

                with rooms_lock:
                    room = rooms.get(code)

                    if room is None:
                        ws.send("ERR|room_gone")
                        break

                    if player == "host":
                        room["host_data"] = data
                        peer_data = room["joiner_data"]
                    else:
                        room["joiner_data"] = data
                        peer_data = room["host_data"]

                    room["message_id"] += 1
                    message_id = room["message_id"]

                ws.send("PEER|" + str(message_id) + "|" + peer_data)

            elif msg == "PING":
                ws.send("PONG")

            else:
                ws.send("ERR|bad_msg")

    except Exception as e:
        print("WebSocket error:", e)

    finally:
        with rooms_lock:
            room = rooms.get(code)

            if room is not None:
                if player == "host":
                    room["host_connected"] = False
                else:
                    room["joiner_connected"] = False

@app.route("/ws-test")
def ws_test():
    return "WebSocket route should be /ws"
