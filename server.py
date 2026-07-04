from flask import Flask, request, jsonify
import random
import time

app = Flask(__name__)

rooms = {}

def make_code():
    return "".join(str(random.randint(0, 9)) for _ in range(5))

@app.route("/")
def home():
    return "PixelForge relay online"

@app.route("/create")
def create():
    code = make_code()

    rooms[code] = {
        "code": code,
        "created": time.time(),
        "host_ready": True,
        "joiner_ready": False,
        "game": "",
        "host_data": "",
        "joiner_data": "",
        "message_id": 0
    }

    return jsonify({"ok": True, "code": code})

@app.route("/join")
def join():
    code = request.args.get("code", "")

    if code not in rooms:
        return jsonify({"ok": False, "error": "room_not_found"}), 404

    rooms[code]["joiner_ready"] = True
    rooms[code]["message_id"] += 1

    return jsonify({
        "ok": True,
        "code": code,
        "game": rooms[code]["game"]
    })

@app.route("/setgame")
def setgame():
    code = request.args.get("code", "")
    game = request.args.get("game", "")

    if code not in rooms:
        return jsonify({"ok": False, "error": "room_not_found"}), 404

    rooms[code]["game"] = game
    rooms[code]["message_id"] += 1

    return jsonify({"ok": True, "game": game})

@app.route("/status")
def status():
    code = request.args.get("code", "")

    if code not in rooms:
        return jsonify({"ok": False, "error": "room_not_found"}), 404

    room = rooms[code]

    return jsonify({
        "ok": True,
        "code": room["code"],
        "host_ready": room["host_ready"],
        "joiner_ready": room["joiner_ready"],
        "game": room["game"],
        "message_id": room["message_id"]
    })

@app.route("/send")
def send():
    code = request.args.get("code", "")
    player = request.args.get("player", "")
    data = request.args.get("data", "")

    if code not in rooms:
        return jsonify({"ok": False, "error": "room_not_found"}), 404

    if player == "host":
        rooms[code]["host_data"] = data
    elif player == "joiner":
        rooms[code]["joiner_data"] = data
    else:
        return jsonify({"ok": False, "error": "bad_player"}), 400

    rooms[code]["message_id"] += 1

    return jsonify({
        "ok": True,
        "message_id": rooms[code]["message_id"]
    })

@app.route("/read")
def read():
    code = request.args.get("code", "")
    player = request.args.get("player", "")

    if code not in rooms:
        return jsonify({"ok": False, "error": "room_not_found"}), 404

    room = rooms[code]

    if player == "host":
        return jsonify({
            "ok": True,
            "data": room["joiner_data"],
            "game": room["game"],
            "joiner_ready": room["joiner_ready"],
            "message_id": room["message_id"]
        })

    if player == "joiner":
        return jsonify({
            "ok": True,
            "data": room["host_data"],
            "game": room["game"],
            "host_ready": room["host_ready"],
            "message_id": room["message_id"]
        })

    return jsonify({"ok": False, "error": "bad_player"}), 400
