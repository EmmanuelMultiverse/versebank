# bank_simulator.py
# A simple Flask web application to simulate a bank for testing purposes.
# It uses a PostgreSQL database to store account information and pre-populates
# it with mock data on first run.

import os
import psycopg2
from flask import Flask, request, jsonify

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Global Request Logging (logs all incoming requests) ---
@app.before_request
def log_request_info():
    """Logs details of every incoming HTTP request before it's processed by a route."""
    print(f"[Versebank Incoming Request] Method: {request.method}, Path: {request.path}", flush=True)
    # Log headers for debugging, but be cautious with sensitive info in production
    # print(f"  Headers: {request.headers}", flush=True)
    if request.is_json:
        try:
            # Use silent=True to avoid errors if JSON is malformed
            json_data = request.get_json(silent=True)
            print(f"  JSON Data: {json_data}", flush=True)
        except Exception as e:
            print(f"  Error parsing JSON data: {e}", flush=True)
    elif request.form:
        print(f"  Form Data: {request.form}", flush=True)


def get_db_connection():
    """Establishes a connection to the PostgreSQL database using environment variables, with no default values."""
    try:
        conn = psycopg2.connect(
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"]
        )
        print("Database connection established.", flush=True)
        return conn
    except KeyError as e:
        print(f"Error: Missing environment variable: {e}. Please ensure all DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, and DB_PORT are set.", flush=True)
        return None
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to PostgreSQL database. Please check credentials and connection. Details: {e}", flush=True)
        return None

def init_db():
    """
    Initializes the database:
    1. Creates the 'accounts' table if it doesn't exist.
    2. Populates the table with mock accounts if it's empty.
    """
    conn = get_db_connection()
    if not conn:
        print("Database connection failed during initialization. Aborting.", flush=True)
        return

    try:
        with conn.cursor() as cur:
            print("Attempting to create 'accounts' table if not exists...", flush=True)
            # Step 1: Create table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id SERIAL PRIMARY KEY,
                    account_number VARCHAR(255) UNIQUE NOT NULL,
                    balance NUMERIC(15, 2) NOT NULL CHECK (balance >= 0)
                );
            """)
            print("Database table 'accounts' presence checked.", flush=True)

            # Step 2: Check if table is empty
            cur.execute("SELECT COUNT(*) FROM accounts;")
            count = cur.fetchone()[0]
            print(f"Current number of accounts: {count}", flush=True)

            # Step 3: Populate with mock data if empty
            if count == 0:
                print("No accounts found. Populating with mock data...", flush=True)
                mock_accounts = [
                    ('1234567890', 5000.75),
                    ('0987654321', 10250.00),
                    ('5555555555', 732.10),
                    ('1122334455', 25000.00)
                ]
                # Use executemany for efficient batch insertion
                cur.executemany(
                    "INSERT INTO accounts (account_number, balance) VALUES (%s, %s)",
                    mock_accounts
                )
                print(f"{len(mock_accounts)} mock accounts have been created.", flush=True)
            else:
                print("Database already contains accounts. Skipping mock data insertion.", flush=True)

            conn.commit()
            print("Database initialization complete.", flush=True)
    except psycopg2.Error as e:
        print(f"Error during database initialization: {e}", flush=True)
        if conn:
            conn.rollback()
            print("Database initialization: Transaction rolled back.", flush=True)
    finally:
        if conn:
            conn.close()
            print("Database connection closed after initialization.", flush=True)

with app.app_context():
    init_db()

# --- API Endpoints ---

@app.route('/account', methods=['POST'])
def create_account():
    """
    Creates a new bank account.
    Expects a JSON payload: {"account_number": "...", "initial_balance": ...}
    Returns: JSON response and HTTP status code.
    """
    # The @app.before_request decorator already logs the basic request info.
    # This specific print confirms the request entered this route handler.
    print(f"[Create Account] Processing request to create account.", flush=True)
    data = request.get_json()
    if not data or 'account_number' not in data or 'initial_balance' not in data:
        print("[Create Account] Error: Missing account_number or initial_balance in request.", flush=True)
        return jsonify({"error": "Missing account_number or initial_balance"}), 400

    account_number = data['account_number']
    try:
        initial_balance = float(data['initial_balance'])
        if initial_balance < 0:
             print(f"[Create Account] Error: Initial balance cannot be negative ({initial_balance}).", flush=True)
             return jsonify({"error": "Initial balance cannot be negative"}), 400
    except ValueError:
        print(f"[Create Account] Error: Invalid format for initial_balance ({data['initial_balance']}).", flush=True)
        return jsonify({"error": "Invalid format for initial_balance"}), 400

    conn = get_db_connection()
    if not conn:
        print("[Create Account] Error: Database connection failed.", flush=True)
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cur:
            print(f"[Create Account] Inserting new account: {account_number}, balance: {initial_balance}", flush=True)
            cur.execute(
                "INSERT INTO accounts (account_number, balance) VALUES (%s, %s)",
                (account_number, initial_balance)
            )
            conn.commit()
            print(f"[Create Account] Account {account_number} created successfully.", flush=True)
            return jsonify({"message": "Account created successfully", "account_number": account_number}), 201
    except psycopg2.IntegrityError:
        print(f"[Create Account] Error: Account with number {account_number} already exists.", flush=True)
        return jsonify({"error": f"Account with number {account_number} already exists"}), 409
    except psycopg2.Error as e:
        print(f"[Create Account] Database error: {e}", flush=True)
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()
            print("[Create Account] Database connection closed.", flush=True)

@app.route('/account/<string:account_number>', methods=['GET'])
def get_account(account_number):
    """
    Retrieves account details for a given account number.
    Returns: JSON response and HTTP status code.
    """
    # The @app.before_request decorator already logs the basic request info.
    print(f"[Get Account] Processing request to retrieve account {account_number}.", flush=True)
    conn = get_db_connection()
    if not conn:
        print("[Get Account] Error: Database connection failed.", flush=True)
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cur:
            print(f"[Get Account] Querying for account_number: {account_number}", flush=True)
            cur.execute("SELECT account_number, balance FROM accounts WHERE account_number = %s", (account_number,))
            account = cur.fetchone()
            if account:
                print(f"[Get Account] Account {account_number} found. Balance: {account[1]}", flush=True)
                return jsonify({"account_number": account[0], "balance": str(account[1])})
            else:
                print(f"[Get Account] Account {account_number} not found.", flush=True)
                return jsonify({"error": "Account not found"}), 404
    except psycopg2.Error as e:
        print(f"[Get Account] Database error: {e}", flush=True)
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()
            print("[Get Account] Database connection closed.", flush=True)

@app.route('/deposit', methods=['POST'])
def deposit():
    """
    Deposits funds into a bank account.
    Expects a JSON payload: {"account_number": "...", "amount": ...}
    Amount must be positive.
    Returns: JSON response and HTTP status code.
    """
    # The @app.before_request decorator already logs the basic request info.
    print(f"[Deposit] Processing request to deposit funds.", flush=True)
    data = request.get_json()
    if not data or 'account_number' not in data or 'amount' not in data:
        print("[Deposit] Error: Missing account_number or amount in request.", flush=True)
        return jsonify({"error": "Missing account_number or amount"}), 400

    account_number = data['account_number']
    try:
        amount = float(data['amount'])
        if amount <= 0:
            print(f"[Deposit] Error: Deposit amount must be positive ({amount}).", flush=True)
            return jsonify({"error": "Deposit amount must be positive"}), 400
    except ValueError:
        print(f"[Deposit] Error: Invalid format for amount ({data['amount']}).", flush=True)
        return jsonify({"error": "Invalid format for amount"}), 400

    conn = get_db_connection()
    if not conn:
        print("[Deposit] Error: Database connection failed.", flush=True)
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cur:
            print(f"[Deposit] Attempting to lock account {account_number} for update...", flush=True)
            # Lock the row for update to prevent race conditions
            cur.execute(
                "SELECT balance FROM accounts WHERE account_number = %s FOR UPDATE",
                (account_number,)
            )
            account = cur.fetchone()

            if not account:
                print(f"[Deposit] Account {account_number} not found.", flush=True)
                return jsonify({"error": "Account not found"}), 404

            current_balance = float(account[0])
            new_balance = current_balance + amount
            print(f"[Deposit] Account {account_number} found. Old Balance: {current_balance:.2f}, Deposit Amount: {amount:.2f}, Calculated New Balance: {new_balance:.2f}", flush=True)

            print(f"[Deposit] Updating balance for account {account_number}...", flush=True)
            cur.execute(
                "UPDATE accounts SET balance = %s WHERE account_number = %s",
                (new_balance, account_number)
            )
            conn.commit()
            print(f"[Deposit] Balance updated and transaction committed for account {account_number}. New Balance: {new_balance:.2f}", flush=True)

            return jsonify({
                "message": "Deposit successful",
                "account_number": account_number,
                "new_balance": str(new_balance)
            }), 200

    except psycopg2.Error as e:
        print(f"[Deposit] Database transaction failed for account {account_number}: {e}", flush=True)
        if conn:
            conn.rollback()
            print(f"[Deposit] Transaction rolled back for account {account_number}.", flush=True)
        return jsonify({"error": f"Database transaction failed: {e}"}), 500
    finally:
        if conn:
            conn.close()
            print("[Deposit] Database connection closed.", flush=True)

@app.route('/withdrawal', methods=['POST'])
def withdrawal():
    """
    Withdraws funds from a bank account.
    Expects a JSON payload: {"account_number": "...", "amount": ...}
    Amount must be positive.
    Returns: JSON response and HTTP status code.
    """
    # The @app.before_request decorator already logs the basic request info.
    print(f"[Withdrawal] Processing request to withdraw funds.", flush=True)
    data = request.get_json()
    if not data or 'account_number' not in data or 'amount' not in data:
        print("[Withdrawal] Error: Missing account_number or amount in request.", flush=True)
        return jsonify({"error": "Missing account_number or amount"}), 400

    account_number = data['account_number']
    try:
        amount = float(data['amount'])
        if amount <= 0:
            print(f"[Withdrawal] Error: Withdrawal amount must be positive ({amount}).", flush=True)
            return jsonify({"error": "Withdrawal amount must be positive"}), 400
    except ValueError:
        print(f"[Withdrawal] Error: Invalid format for amount ({data['amount']}).", flush=True)
        return jsonify({"error": "Invalid format for amount"}), 400

    conn = get_db_connection()
    if not conn:
        print("[Withdrawal] Error: Database connection failed.", flush=True)
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cur:
            print(f"[Withdrawal] Attempting to lock account {account_number} for update...", flush=True)
            # Lock the row for update to prevent race conditions
            cur.execute(
                "SELECT balance FROM accounts WHERE account_number = %s FOR UPDATE",
                (account_number,)
            )
            account = cur.fetchone()

            if not account:
                print(f"[Withdrawal] Account {account_number} not found.", flush=True)
                return jsonify({"error": "Account not found"}), 404

            current_balance = float(account[0])
            new_balance = current_balance - amount # Subtract for withdrawal
            print(f"[Withdrawal] Account {account_number} found. Old Balance: {current_balance:.2f}, Withdrawal Amount: {amount:.2f}, Calculated New Balance: {new_balance:.2f}", flush=True)


            if new_balance < 0:
                print(f"[Withdrawal] Error: Insufficient funds for withdrawal from {account_number}. Current: {current_balance:.2f}, Attempted: {amount:.2f}", flush=True)
                return jsonify({"error": "Insufficient funds for this withdrawal"}), 400

            print(f"[Withdrawal] Updating balance for account {account_number}...", flush=True)
            cur.execute(
                "UPDATE accounts SET balance = %s WHERE account_number = %s",
                (new_balance, account_number)
            )
            conn.commit()
            print(f"[Withdrawal] Balance updated and transaction committed for account {account_number}. New Balance: {new_balance:.2f}", flush=True)


            return jsonify({
                "message": "Withdrawal successful",
                "account_number": account_number,
                "new_balance": str(new_balance)
            }), 200

    except psycopg2.Error as e:
        print(f"[Withdrawal] Database transaction failed for account {account_number}: {e}", flush=True)
        if conn:
            conn.rollback()
            print(f"[Withdrawal] Transaction rolled back for account {account_number}.", flush=True)
        return jsonify({"error": f"Database transaction failed: {e}"}), 500
    finally:
        if conn:
            conn.close()
            print("[Withdrawal] Database connection closed.", flush=True)

# --- Main Execution ---
if __name__ == '__main__':
    print("Starting bank simulator...", flush=True)
    # The init_db() call is now at the module level within the app context
    # Runs the Flask app. Use host='0.0.0.0' to make it accessible
    # from other containers/machines on the same network.
    app.run(host='0.0.0.0', port=5001, debug=True)

