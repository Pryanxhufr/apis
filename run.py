from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

def read_cart():
    cart_entries = []
    try:
        with open("cart.txt", "r", encoding="utf-8") as file:
            for line in file:
                cart_entries.append(json.loads(line.strip()))
    except FileNotFoundError:
        pass
    return cart_entries

def write_cart(cart_entries):
    with open("cart.txt", "w", encoding="utf-8") as file:
        for entry in cart_entries:
            json.dump(entry, file)
            file.write("\n")

def save_to_cart(ip, product_id, quantity, size=None):
    try:
        cart_entries = read_cart()
        products = read_products()
        
        # Find product to check size selection
        product = next((p for p in products if p.get("product_id") == product_id), None)
        if not product:
            return False
            
        # Only include size if product has size_selection true
        cart_entry = {
            "ip": ip,
            "product_id": product_id,
            "quantity": quantity,
            "timestamp": datetime.now().isoformat()
        }
        
        if product.get("size_selection", False) and size:
            cart_entry["size"] = size

        # Check for existing entry with same IP, product_id and size
        found = False
        for entry in cart_entries:
            if (entry["ip"] == ip and 
                entry["product_id"] == product_id and 
                entry.get("size") == cart_entry.get("size")):
                entry["quantity"] += quantity
                entry["timestamp"] = datetime.now().isoformat()
                found = True
                break

        if not found:
            cart_entries.append(cart_entry)

        write_cart(cart_entries)
        return True
    except Exception:
        return False

def get_cart_items(ip):
    try:
        cart_entries = read_cart()
        products = read_products()

        # Get all cart items for this IP and enrich with product details
        cart_items = []
        for entry in cart_entries:
            if entry["ip"] == ip:
                # Find product details
                product = next((p for p in products if p.get("product_id") == entry["product_id"]), None)
                if product:
                    # Get price without "Rs." prefix and convert to float
                    price_str = product.get("price", "0").replace("Rs.", "").strip()
                    # Handle price ranges (e.g. "Rs.1200-450") by taking first value
                    price = float(price_str.split("-")[0])
                    item_total = price * entry["quantity"]

                    item = {
                        "product_id": entry["product_id"],
                        "name": product.get("name", "Unknown Product"),
                        "quantity": entry["quantity"],
                        "price_per_item": f"Rs.{price:.2f}",
                        "item_total": f"Rs.{item_total:.2f}",
                        "image_url": product.get("image_url", "")
                    }
                    if "size" in entry:
                        item["size"] = entry["size"]
                    cart_items.append(item)

        if not cart_items:
            return {"error": "No items found in cart"}

        # Calculate total cart value
        cart_total = sum(float(item["item_total"].replace("Rs.", "")) for item in cart_items)
        return {"items": cart_items, "total_cart_value": f"Rs.{cart_total:.2f}"}
    except Exception as e:
        print(f"Error getting cart items: {e}")
        return []

def remove_from_cart(ip, product_id, quantity):
    try:
        cart_entries = read_cart()

        # Find the user's item
        for i, entry in enumerate(cart_entries):
            if entry["ip"] == ip and entry["product_id"] == product_id:
                if quantity >= entry["quantity"]:
                    # Remove entire entry if quantity to remove is >= current quantity
                    cart_entries.pop(i)
                    write_cart(cart_entries)
                    return {"removed": True, "message": "Item completely removed from cart"}
                else:
                    # Reduce the quantity
                    entry["quantity"] -= quantity
                    entry["timestamp"] = datetime.now().isoformat()
                    write_cart(cart_entries)
                    return {"removed": True, "message": f"Removed {quantity} items, {entry['quantity']} remaining"}

        return {"removed": False, "message": "Item not found in cart"}
    except Exception as e:
        return {"removed": False, "message": str(e)}

def read_products():
    products = []
    with open("products.txt", "r", encoding="utf-8") as file:
        for line in file:
            try:
                product = json.loads(line.strip())  # Use JSON instead of ast
                products.append(product)
            except json.JSONDecodeError:
                continue
    return products

@app.route("/fetch_product_range/<int:first>_<int:last>", methods=["GET"])
def fetch_products(first, last):
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0]
    print(f"Request from IP: {client_ip}")
    products = read_products()
    filtered_products = [p for p in products if first <= p.get("product_id", 0) <= last]
    return jsonify(filtered_products)

@app.route("/", methods=["GET"])
def fetch_product_by_id():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0]
    print(f"Request from IP: {client_ip}")
    product_id = request.args.get("product_id", type=int)

    if product_id is None:
        return jsonify({"error": "Missing product_id parameter"}), 400

    products = read_products()
    for product in products:
        if product.get("product_id") == product_id:
            return jsonify(product)

    return jsonify({"error": "Product not found"}), 200

@app.route("/add_to_cart/", methods=["POST"])
def add_to_cart():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0]
    print(f"Request from IP: {client_ip}")
    product_id = request.args.get("product_id", type=int)
    quantity = request.args.get("quantity", type=int)
    size = request.args.get("size", "XS")

    if not product_id or not quantity:
        return jsonify({"error": "Missing product_id or quantity"}), 400

    if quantity <= 0:
        return jsonify({"error": "Invalid quantity"}), 400

    # Check if product exists first
    products = read_products()
    product = next((p for p in products if p.get("product_id") == product_id), None)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    # Validate size if product has size_selection
    valid_sizes = ["XS", "S", "M", "L", "XL", "XXL"]
    if product.get("size_selection", False):
        if not size or size.upper() not in valid_sizes:
            return jsonify({"error": "Valid size required for this product"}), 400
        size = size.upper()  # Standardize size to uppercase

    if save_to_cart(client_ip, product_id, quantity, size):
        cart_items = get_cart_items(client_ip)
        return jsonify({
            "message": "Added to cart successfully",
            "cart_items": cart_items
        })
    return jsonify({"error": "Failed to add to cart"}), 500

@app.route("/remove_item/", methods=["POST"])
def remove_item():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0]
    print(f"Request from IP: {client_ip}")

    product_id = request.args.get("product_id", type=int)
    quantity = request.args.get("quantity", type=int)

    if not product_id:
        return jsonify({"error": "Missing product_id"}), 400

    if quantity is not None and quantity <= 0:
        return jsonify({"error": "Invalid quantity"}), 400

    # Check if product exists first
    products = read_products()
    product = next((p for p in products if p.get("product_id") == product_id), None)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    # If quantity is None or "all", remove all items of that product
    if quantity is None or str(quantity).lower() == "all":
        result = remove_from_cart(client_ip, product_id, float('inf'))  # Using infinity to remove all
    else:
        result = remove_from_cart(client_ip, product_id, quantity)
    if result["removed"]:
        cart_items = get_cart_items(client_ip)
        return jsonify({
            "message": result["message"],
            "cart_items": cart_items
        })
    return jsonify({"error": result["message"]}), 404

@app.route("/cart/", methods=["GET"])
def get_cart():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0]
    print(f"Request from IP: {client_ip}")

    cart_items = get_cart_items(client_ip)
    if isinstance(cart_items, dict) and "error" in cart_items:
        return jsonify(cart_items), 404
    return jsonify({"cart_items": cart_items})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
