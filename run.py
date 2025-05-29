from flask import Flask, request, jsonify
import json
import os
import requests

app = Flask(__name__)

CART_FILE = "cart.json"

TELEGRAM_CHAT_ID = "-4735749233"
TELEGRAM_BOT_TOKEN = "7906033152:AAE74DpuF_vqFXZe2yJ5TiHfNyLRtNZMBtE"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def read_cart():
    if not os.path.exists(CART_FILE):
        return []
    with open(CART_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return []

def write_cart(cart_data):
    with open(CART_FILE, "w") as f:
        json.dump(cart_data, f, indent=2)

def get_cart_items(ip):
    cart_data = read_cart()
    items = [item for item in cart_data if item["ip"] == ip]
    if not items:
        return {"error": "No items found for IP."}

    total_cart_value = sum(float(item["item_total"].replace("₹", "").strip()) for item in items)
    return {
        "ip": ip,
        "items": items,
        "total_cart_value": f"₹{total_cart_value:.2f}"
    }

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    data = request.get_json()
    required = ["name", "quantity", "price_per_item", "item_total"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing data"}), 400

    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0]

    cart_entry = {
        "ip": client_ip,
        "name": data["name"],
        "quantity": data["quantity"],
        "price_per_item": data["price_per_item"],
        "item_total": data["item_total"]
    }

    if "size" in data:
        cart_entry["size"] = data["size"]

    cart_data = read_cart()
    cart_data.append(cart_entry)
    write_cart(cart_data)

    return jsonify({"message": "Item added to cart"}), 200

@app.route("/order_success/", methods=["POST"])
def order_success():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0]
    print(f"Order placed by IP: {client_ip}")

    try:
        cart_data = get_cart_items(client_ip)
        if isinstance(cart_data, dict) and "error" in cart_data:
            return jsonify({"error": "No items found in cart"}), 200

        items = cart_data["items"]
        total = cart_data["total_cart_value"]

        message_lines = ["🛒 *Order received* 🛒", "", "🧾 *Order Details:*"]
        for item in items:
            line = f"• {item['name']} x{item['quantity']} - {item['price_per_item']}"
            if "size" in item:
                line += f" (Size: {item['size']})"
            line += f"\n  Total: {item['item_total']}"
            message_lines.append(line)
        message_lines.append(f"\n💰 *Cart Total:* {total}")

        message = "\n".join(message_lines)

        # Send Telegram message
        requests.post(TELEGRAM_API_URL, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)

        # Clear the cart
        cart_entries = read_cart()
        new_cart = [entry for entry in cart_entries if entry["ip"] != client_ip]
        write_cart(new_cart)

        return jsonify({"message": "Order received"}), 200

    except Exception as e:
        return jsonify({"error": f"Failed to process order"}), 500

if __name__ == "__main__":
    app.run(debug=True)
