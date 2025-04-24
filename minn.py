import os
import json
import getpass
from datetime import datetime

CONFIG_PATH = "config.json"
LOG_PATH = "cash_log.txt"

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    else:
        ip = input("Enter your phone's ADB IP address (e.g. 192.168.1.7): ").strip()
        pin = getpass.getpass("Enter your Vodafone Cash PIN: ").strip()
        config = {"ip": ip, "pin": pin}
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f)
        return config

def connect_adb(ip):
    print(f"[ADB] Connecting to {ip}...")
    os.system(f"adb connect {ip}")

def send_ussd(code):
    safe_code = code.replace("#", "%23")
    command = f'adb shell am start -a android.intent.action.CALL -d tel:{safe_code}'
    os.system(command)

def log_action(action, target=None, amount=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a") as f:
        log_entry = f"[{now}] {action}"
        if target:
            log_entry += f" | Target: {target}"
        if amount:
            log_entry += f" | Amount: {amount} EGP"
        f.write(log_entry + "\n")

def transfer_money(pin):
    phone = input("Recipient phone number (e.g. 01012345678): ").strip()
    amount = input("Amount to transfer (EGP): ").strip()
    confirm = input(f"Confirm transfer of {amount} EGP to {phone}? (y/n): ").lower()
    if confirm == 'y':
        ussd = f"*9*7*{phone}*{amount}*{pin}#"
        send_ussd(ussd)
        log_action("Transfer", phone, amount)
        print("[✔] Transfer request sent.")
    else:
        print("[✘] Transfer canceled.")

def check_balance():
    send_ussd("*868*1#")
    log_action("Balance Check")
    print("[✔] Balance check request sent.")

def change_pin():
    send_ussd("*9*12#")
    log_action("PIN Change")
    print("[✔] PIN change request sent.")

def main():
    config = load_config()
    connect_adb(config["ip"])

    while True:
        print("\n=== Vodafone Cash ADB Controller ===")
        print("1. Transfer money")
        print("2. Check balance")
        print("3. Change PIN")
        print("4. Exit")

        choice = input("Select an option [1-4]: ").strip()

        if choice == "1":
            transfer_money(config["pin"])
        elif choice == "2":
            check_balance()
        elif choice == "3":
            change_pin()
        elif choice == "4":
            print("Exiting. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()

