# bank_simulator.py
# A simple Flask web application to simulate a bank for testing purposes.
# It uses a PostgreSQL database to store account information and pre-populates
# it with mock data on first run.

import os
import psycopg2
from flask import Flask, request, jsonify

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Database Configuration ---
# It's recommended to use environment variables for database credentials.
# Example:
# export DB_NAME="bank_db"
# export DB_USER="bank_user"
# export DB_PASSWORD="your_password"
# export DB_HOST="localhost"
# export DB_PORT="5432"

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname="bank_db",
            user="bank_user",
            password="your_password",
            host=os.environ.get("DB_HOST", "localhost"),
            port=os.environ.get("DB_PORT", "5432")
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to PostgreSQL database. Please check credentials and connection. Details: {e}")
        return None

def init_db():
    """
    Initializes the database:
    1. Creates the 'accounts' table if it doesn't exist.
    2. Populates the table with mock accounts if it's empty.
    """
    conn = get_db_connection()
    if not conn:
        print("Database connection failed. Aborting database initialization.")
        return

    try:
        with conn.cursor() as cur:
            # Step 1: Create table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id SERIAL PRIMARY KEY,
                    account_number VARCHAR(255) UNIQUE NOT NULL,
                    balance NUMERIC(15, 2) NOT NULL CHECK (balance >= 0)
                );
            """)
            print("Database table 'accounts' is present.")

            # Step 2: Check if table is empty
            cur.execute("SELECT COUNT(*) FROM accounts;")
            count = cur.fetchone()[0]

            # Step 3: Populate with mock data if empty
            if count == 0:
                print("No accounts found. Populating with mock data...")
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
                print(f"{len(mock_accounts)} mock accounts have been created.")
            else:
                print("Database already contains accounts. Skipping mock data insertion.")

            conn.commit()
    except psycopg2.Error as e:
        print(f"Error during database initialization: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


# --- API Endpoints ---

@app.route('/account', methods=['POST'])
def create_account():
    """
    Creates a new bank account.
    Expects a JSON payload: {"account_number": "...", "initial_balance": ...}
    Returns: JSON response and HTTP status code.
    """
    data = request.get_json()
    if not data or 'account_number' not in data or 'initial_balance' not in data:
        return jsonify({"error": "Missing account_number or initial_balance"}), 400

    account_number = data['account_number']
    try:
        initial_balance = float(data['initial_balance'])
        if initial_balance < 0:
             return jsonify({"error": "Initial balance cannot be negative"}), 400
    except ValueError:
        return jsonify({"error": "Invalid format for initial_balance"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO accounts (account_number, balance) VALUES (%s, %s)",
                (account_number, initial_balance)
            )
            conn.commit()
            return jsonify({"message": "Account created successfully", "account_number": account_number}), 201
    except psycopg2.IntegrityError:
        return jsonify({"error": f"Account with number {account_number} already exists"}), 409
    except psycopg2.Error as e:
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/account/<string:account_number>', methods=['GET'])
def get_account(account_number):
    """
    Retrieves account details for a given account number.
    Returns: JSON response and HTTP status code.
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT account_number, balance FROM accounts WHERE account_number = %s", (account_number,))
            account = cur.fetchone()
            if account:
                return jsonify({"account_number": account[0], "balance": str(account[1])})
            else:
                return jsonify({"error": "Account not found"}), 404
    except psycopg2.Error as e:
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/deposit', methods=['POST'])
def deposit():
    """
    Deposits funds into a bank account.
    Expects a JSON payload: {"account_number": "...", "amount": ...}
    Amount must be positive.
    Returns: JSON response and HTTP status code.
    """
    data = request.get_json()
    if not data or 'account_number' not in data or 'amount' not in data:
        return jsonify({"error": "Missing account_number or amount"}), 400

    account_number = data['account_number']
    try:
        amount = float(data['amount'])
        if amount <= 0:
            return jsonify({"error": "Deposit amount must be positive"}), 400
    except ValueError:
        return jsonify({"error": "Invalid format for amount"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cur:
            # Lock the row for update to prevent race conditions
            cur.execute(
                "SELECT balance FROM accounts WHERE account_number = %s FOR UPDATE",
                (account_number,)
            )
            account = cur.fetchone()

            if not account:
                return jsonify({"error": "Account not found"}), 404

            current_balance = float(account[0])
            new_balance = current_balance + amount

            cur.execute(
                "UPDATE accounts SET balance = %s WHERE account_number = %s",
                (new_balance, account_number)
            )
            conn.commit()

            print(f"[Deposit] Account: {account_number}, Old Balance: {current_balance:.2f}, Amount: {amount:.2f}, New Balance: {new_balance:.2f}")

            return jsonify({
                "message": "Deposit successful",
                "account_number": account_number,
                "new_balance": str(new_balance)
            }), 200

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        return jsonify({"error": f"Database transaction failed: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/withdrawal', methods=['POST'])
def withdrawal():
    """
    Withdraws funds from a bank account.
    Expects a JSON payload: {"account_number": "...", "amount": ...}
    Amount must be positive.
    Returns: JSON response and HTTP status code.
    """
    data = request.get_json()
    if not data or 'account_number' not in data or 'amount' not in data:
        return jsonify({"error": "Missing account_number or amount"}), 400

    account_number = data['account_number']
    try:
        amount = float(data['amount'])
        if amount <= 0:
            return jsonify({"error": "Withdrawal amount must be positive"}), 400
    except ValueError:
        return jsonify({"error": "Invalid format for amount"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cur:
            # Lock the row for update to prevent race conditions
            cur.execute(
                "SELECT balance FROM accounts WHERE account_number = %s FOR UPDATE",
                (account_number,)
            )
            account = cur.fetchone()

            if not account:
                return jsonify({"error": "Account not found"}), 404

            current_balance = float(account[0])
            new_balance = current_balance - amount # Subtract for withdrawal

            if new_balance < 0:
                return jsonify({"error": "Insufficient funds for this withdrawal"}), 400

            cur.execute(
                "UPDATE accounts SET balance = %s WHERE account_number = %s",
                (new_balance, account_number)
            )
            conn.commit()

            print(f"[Withdrawal] Account: {account_number}, Old Balance: {current_balance:.2f}, Amount: {amount:.2f}, New Balance: {new_balance:.2f}")


            return jsonify({
                "message": "Withdrawal successful",
                "account_number": account_number,
                "new_balance": str(new_balance)
            }), 200

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        return jsonify({"error": f"Database transaction failed: {e}"}), 500
    finally:
        if conn:
            conn.close()

# --- Main Execution ---
if __name__ == '__main__':
    print("Starting bank simulator...")
    init_db()
    # Runs the Flask app. Use host='0.0.0.0' to make it accessible
    # from other containers/machines on the same network.
    app.run(host='0.0.0.0', port=5001, debug=True)