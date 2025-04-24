import os
import subprocess
import argparse
import getpass
import json
import sys
import time
from tabulate import tabulate
from datetime import datetime

CONFIG_FILE = "config.json"
LOG_FILE = "logs.txt"


# ------------------------ ADB FUNCTIONS ------------------------
def adb(command):
    try:
        result = subprocess.check_output(f"adb {command}", shell=True, stderr=subprocess.DEVNULL)
        return result.decode().strip()
    except subprocess.CalledProcessError:
        return ""

def check_adb_connection():
    while True:
        devices = adb("devices").splitlines()[1:]
        if devices and any("device" in d for d in devices):
            return True
        print("\nTrying to reconnect ADB...")
        time.sleep(2)

def send_ussd(code):
    adb(f"shell am start -a android.intent.action.CALL -d tel:{code.replace('#', '%23')}")


def capture_screenshot():
    adb("shell screencap -p /sdcard/screen.png")
    adb("pull /sdcard/screen.png screen.png")
    return "screen.png"

def start_screen_record():
    adb("shell screenrecord /sdcard/record.mp4 &")

def stop_screen_record():
    adb("shell killall -9 screenrecord")
    adb("pull /sdcard/record.mp4 record.mp4")


def input_text(text):
    adb(f"shell input text '{text}'")

def tap(x, y):
    adb(f"shell input tap {x} {y}")

# ------------------------ CONFIG ------------------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def reset_config():
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
    print("✅ Config reset.")

# ------------------------ PASSWORD ------------------------
def set_password():
    pw = getpass.getpass("🔐 Set new password: ")
    confirm = getpass.getpass("🔁 Confirm password: ")
    if pw == confirm:
        config = load_config()
        config["password"] = pw
        save_config(config)
        print("✅ Password set.")
    else:
        print("❌ Passwords don't match.")

def verify_password(stored_pw):
    attempt = getpass.getpass("🔐 Enter password: ")
    if attempt != stored_pw:
        print("❌ Incorrect password.")
        return False
    return True

# ------------------------ LOGGING ------------------------
def log_action(action):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{now}] {action}\n")

def show_logs():
    if not os.path.exists(LOG_FILE):
        print("📂 No logs found.")
        return
    with open(LOG_FILE) as f:
        logs = f.readlines()
    print("\n📜 Logs:")
    print("".join(logs))

# ------------------------ TELECOM FEATURES (EGYPT) ------------------------

PROVIDERS = {
    "vodafone": {
        # === Main & Support ===
        "main_menu": "*9#",
        "customer_service": "7001",

        # === PIN Management ===
        "create_pin": "*9*5#",                  # إنشاء رقم سري للمحفظة
        "change_pin": "*9*2#",                  # تغيير الرقم السري
        "forgot_pin": "*9*12#",                 # نسيان الرقم السري

        # === Balance & Recharge ===
        "balance": "*9*13#",                    # الاستعلام عن الرصيد
        "recharge_self": "*9*0*{amount}*{pin}#",        # شحن لرقمي
        "recharge_other": "*9*3*{number}*{amount}*{pin}#", # شحن لرقم آخر
        "fakka_1_5": "*9*150#",                 # كارت فكة 1.5 جنيه
        "fakka_3_5": "*9*350#",                 # كارت فكة 3.5 جنيه

        # === Transfers & Withdrawals ===
        "transfer": "*9*7*{number}*{amount}*{pin}#",     # تحويل لرقم آخر
        "withdraw": "*9*1*{amount}*{pin}#",              # سحب من ATM
        "nearest_branch": "*9*9#",                       # أقرب منفذ سحب/إيداع

        # === Online & Bills ===
        "create_visa": "*9*100#",                # إنشاء فيزا للشراء أونلاين
        "pay_bills": "*9*4*{service_code}*{amount}*{pin}#",  # دفع فواتير
    },

    "etisalat": {
        "main_menu": "*777#",
        "customer_service": "778",
        "balance": "*888#",
        "transfer": "*557*{number}*{amount}*{pin}#",
        "withdraw": "*777*1*{amount}*{pin}#",
        "pay_bills": "*777*2*{service_code}*{amount}*{pin}#",
        "reset_pin": "*888*109*{nid}#"
    },

    "orange": {
        "main_menu": "#100#",
        "customer_service": "110",
        "balance": "#100#",
        "transfer": "#100*2*{number}*{amount}*{pin}#",
        "withdraw": "#100*1*{amount}*{pin}#",
        "pay_bills": "#100*4*{service_code}*{amount}*{pin}#",
        "reset_pin": "#100*5*{nid}#"
    },

    "we": {
        "main_menu": "*322#",
        "customer_service": "111",
        "balance": "#550*",
        "transfer": "*551*{number}*{amount}#",
        "withdraw": "*322*1*{amount}*{pin}#",
        "pay_bills": "*322*4*{service_code}*{amount}*{pin}#",
        "reset_pin": "*322*5*{nid}#"
    }
}

def send_ussd_transfer(number, amount, pin, provider):
    code = PROVIDERS[provider]["transfer"].format(number=number, amount=amount, pin=pin)
    print(f"📤 Sending USSD: {code}")
    send_ussd(code)
    log_action(f"Transfer: {amount} to {number} [{provider}]")

def check_balance(provider):
    code = PROVIDERS[provider]["balance"]
    print(f"📞 Checking balance using {code}")
    send_ussd(code)
    log_action(f"Checked balance [{provider}]")

def reset_pin(provider, nid):
    code = PROVIDERS[provider]["reset_pin"].format(nid=nid)
    print(f"🔁 Resetting PIN using: {code}")
    send_ussd(code)
    log_action(f"Reset PIN using NID [{provider}]")

# ------------------------ ADVANCED FEATURES ------------------------
def get_balance_via_ocr():
    print("🔍 Capturing screen for OCR...")
    img = capture_screenshot()
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(img), lang='eng+ara')
        print("📖 OCR Result:\n", text)
        log_action("OCR balance check")
    except Exception as e:
        print("❌ OCR failed:", e)

def bulk_transfer(file, provider):
    import csv
    with open(file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            send_ussd_transfer(row['number'], row['amount'], row['pin'], provider)
    print("✅ Bulk transfer complete.")
    log_action(f"Bulk transfer from {file} [{provider}]")

def simulate_mode():
    print("🧪 Running in simulation mode (no real USSD calls)...")
    time.sleep(1)
    print("📱 Simulated transfer: 50 EGP to 01012345678 (Vodafone)")
    print("💰 Simulated balance: 120.75 EGP")
    print("🔁 Simulated PIN reset request.")
    log_action("Simulated operations")

def voice_interface():
    print("🎙️ Voice mode coming soon (WIP)...")

# ------------------------ INTERACTIVE CLI ------------------------
def show_interactive_menu():
    options = [
        "Transfer Money",
        "Check Balance",
        "OCR Balance Reader",
        "Voice Command Mode",
        "Bulk Transfer (CSV)",
        "Reset PIN with National ID",
        "Show Logs",
        "Reset Config",
        "Exit"
    ]
    while True:
        print("\n🤖 ADB PowerTool Menu")
        for i, opt in enumerate(options, 1):
            print(f"[{i}] {opt}")
        try:
            choice = int(input("\nSelect an option: "))
            if choice == 1:
                number = input("📞 Recipient number: ")
                amount = input("💸 Amount: ")
                pin = input("🔐 PIN: ")
                provider = input("📡 Provider (vodafone/etisalat/orange/we): ").lower()
                send_ussd_transfer(number, amount, pin, provider)
            elif choice == 2:
                provider = input("📡 Provider: ").lower()
                check_balance(provider)
            elif choice == 3:
                get_balance_via_ocr()
            elif choice == 4:
                voice_interface()
            elif choice == 5:
                file = input("📄 CSV File Path: ")
                provider = input("📡 Provider: ").lower()
                bulk_transfer(file, provider)
            elif choice == 6:
                provider = input("📡 Provider: ").lower()
                nid = input("🆔 National ID: ")
                reset_pin(provider, nid)
            elif choice == 7:
                show_logs()
            elif choice == 8:
                reset_config()
            elif choice == 9:
                print("👋 Exiting...")
                break
            else:
                print("❌ Invalid option.")
        except ValueError:
            print("❌ Please enter a valid number.")

# ------------------------ ARGUMENT PARSER ------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="ADB PowerTool CLI")
    parser.add_argument("--set-password", action="store_true")
    parser.add_argument("--reset-config", action="store_true")
    parser.add_argument("--logs", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--lang", choices=["ar", "en"])
    parser.add_argument("--voice", action="store_true")
    parser.add_argument("--balance", action="store_true")
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--bulk")
    parser.add_argument("--provider", choices=PROVIDERS.keys())
    parser.add_argument("--transfer", nargs=3, metavar=("number", "amount", "pin"))
    parser.add_argument("--reset-pin", nargs=2, metavar=("provider", "nid"))
    return parser.parse_args()

# ------------------------ MAIN ------------------------
def main():
    print(r"""
    ___    ____   ____                 __              ______            __     
   /   |  / __ \ / __ \____ _____     / /_____  ____  / ____/___  ____  / /___ _
  / /| | / / / // /_/ / __ `/ __ \   / __/ __ \/ __ \/ /   / __ \/ __ \/ / __ `/
 / ___ |/ /_/ // _, _/ /_/ / / / /  / /_/ /_/ / / / / /___/ /_/ / /_/ / / /_/ / 
/_/  |_/_____//_/ |_|\__,_/_/ /_/   \__/\____/_/ /_/\____/\____/\____/_/\__,_/  

       ADB PowerTool PRO - Full Android Automation & Cash Services CLI
    """)

    check_adb_connection()

    args = parse_args()
    config = load_config()
    lang = args.lang or config.get("language", "en")

    if config.get("password") and not args.set_password:
        if not verify_password(config["password"]):
            return

    if args.set_password:
        set_password()
    elif args.reset_config:
        reset_config()
    elif args.logs:
        show_logs()
    elif args.simulate:
        simulate_mode()
    elif args.voice:
        voice_interface()
    elif args.balance:
        check_balance(args.provider or config.get("provider", "vodafone"))
    elif args.ocr:
        get_balance_via_ocr()
    elif args.bulk:
        bulk_transfer(args.bulk, args.provider or config.get("provider", "vodafone"))
    elif args.transfer:
        num, amt, pin = args.transfer
        send_ussd_transfer(num, amt, pin, args.provider or config.get("provider", "vodafone"))
    elif args.reset_pin:
        provider, nid = args.reset_pin
        reset_pin(provider, nid)
    else:
        show_interactive_menu()

if __name__ == "__main__":
    main()

