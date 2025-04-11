# app.py
from flask import Flask, render_template, request, redirect
from ib_comm.client.web_client import IBKRWebClient
import time
import os

app = Flask(__name__)

# Initialize IBKR client
client = IBKRWebClient(
    base_url="https://localhost:5055/v1/api",
    cert_path="webapp/cacert.pem",  # Adjust path as needed
    account_id=os.getenv('IBKR_ACCOUNT_ID')
)

@app.template_filter('ctime')
def timectime(s):
    return time.ctime(s/1000)

@app.route("/")
def dashboard():
    try:
        accounts = client.get_accounts()
        account = accounts[1]  # Adjust index as needed
        summary = client.get_account_summary()
        return render_template("dashboard.html", account=account, summary=summary)
    except ConnectionError as e:
        return f'Authentication error. Please <a href="https://localhost:5055">Log in</a>. Error: {e}'

@app.route("/lookup")
def lookup():
    symbol = request.args.get('symbol')
    stocks = []
    if symbol:
        stocks = client.search_contracts(symbol)
    return render_template("lookup.html", stocks=stocks)

@app.route("/contract/<contract_id>/<period>")
def contract(contract_id, period='5d', bar='1d'):
    contract_id = int(contract_id)
    price_history = client.get_market_history(contract_id, period, bar)
    
    # Get contract details
    data = {"conids": [contract_id]}
    contract = client._request('POST', 'trsrv/secdef', json=data)['secdef'][0]
    
    return render_template("contract.html", price_history=price_history, contract=contract)

@app.route("/orders")
def orders():
    orders = client.get_orders()
    return render_template("orders.html", orders=orders)

@app.route("/order", methods=['POST'])
def place_order():
    try:
        client.place_order(
            contract_id=int(request.form.get('contract_id')),
            price=float(request.form.get('price')),
            quantity=int(request.form.get('quantity')),
            side=request.form.get('side')
        )
        return redirect("/orders")
    except Exception as e:
        return f"Order placement failed: {e}", 400

@app.route("/orders/<order_id>/cancel")
def cancel_order(order_id):
    return client.cancel_order(order_id)

@app.route("/portfolio")
def portfolio():
    positions = client.get_positions()
    return render_template("portfolio.html", positions=positions)

@app.route("/watchlists")
def watchlists():
    watchlists = client.get_watchlists()
    return render_template("watchlists.html", watchlists=watchlists)

@app.route("/watchlists/<int:id>")
def watchlist_detail(id):
    watchlist = client._request('GET', f'iserver/watchlist?id={id}')
    return render_template("watchlist.html", watchlist=watchlist)

@app.route("/watchlists/<int:id>/delete")
def watchlist_delete(id):
    client.delete_watchlist(id)
    return redirect("/watchlists")

@app.route("/watchlists/create", methods=['POST'])
def create_watchlist():
    data = request.get_json()
    symbols = [s.strip() for s in data['symbols'].split(",") if s.strip()]
    client.create_watchlist(data['name'], symbols)
    return redirect("/watchlists")