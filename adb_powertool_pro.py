import os
import subprocess
import argparse
import getpass
import json
import sys
import time
import re
import hashlib
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
        hashed_pw = hashlib.sha256(pw.encode()).hexdigest()
        config = load_config()
        config["password"] = hashed_pw
        save_config(config)
        print("✅ Password set.")
    else:
        print("❌ Passwords don't match.")

def verify_password(stored_pw):
    attempt = getpass.getpass("🔐 Enter password: ")
    if hashlib.sha256(attempt.encode()).hexdigest() != stored_pw:
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

# ------------------------ TELECOM FEATURES ------------------------
PROVIDERS = {
    "vodafone": {
        "balance": "*868#",
        "transfer": "*868*{number}*{amount}*{pin}#",
        "reset_pin": "*868*09*{nid}#"
    },
    "etisalat": {
        "balance": "*888#",
        "transfer": "*557*{number}*{amount}*{pin}#",
        "reset_pin": "*888*109*{nid}#"
    },
    "orange": {
        "balance": "#100#",
        "transfer": "*100*{number}*{amount}*{pin}#",
        "reset_pin": "*100*5*{nid}#"
    },
    "we": {
        "balance": "*322#",
        "transfer": "*322*{number}*{amount}*{pin}#",
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
        cleaned = re.sub(r'[^\dEGP\.\n]+', ' ', text)
        print("📖 OCR Result:\n", cleaned)
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
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        mic = sr.Microphone()

        print("🎙️ Say a command (e.g., 'check balance', 'transfer 50 to 01012345678')...")

        with mic as source:
            recognizer.adjust_for_ambient_noise(source)
            print("🔊 Listening...")
            audio = recognizer.listen(source)

        command = recognizer.recognize_google(audio)
        print(f"🗣️ You said: {command}")

        if "check balance" in command:
            check_balance("vodafone")
        elif "transfer" in command:
            words = command.split()
            amount = next(word for word in words if word.isdigit())
            number = next(word for word in words if word.startswith("01"))
            pin = input("🔐 Enter PIN: ")
            send_ussd_transfer(number, amount, pin, "vodafone")
        else:
            print("🤷 Unknown voice command.")

    except Exception as e:
        print("❌ Voice recognition failed:", e)

# ------------------------ INTERACTIVE CLI ------------------------
def show_interactive_menu():
    options = [
        "Transfer Money",
        "Check Balance",
        "OCR Balance Reader",
        "Voice Command Mode",
        "Bulk Transfer (CSV)",
        "Reset PIN with National ID",
        "Set Default Provider",
        "Show Logs",
        "Reset Config",
        "Exit"
    ]
    config = load_config()
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
                provider = config.get("provider", "vodafone")
                send_ussd_transfer(number, amount, pin, provider)
            elif choice == 2:
                provider = config.get("provider", "vodafone")
                check_balance(provider)
            elif choice == 3:
                get_balance_via_ocr()
            elif choice == 4:
                voice_interface()
            elif choice == 5:
                file = input("📄 CSV File Path: ")
                provider = config.get("provider", "vodafone")
                bulk_transfer(file, provider)
            elif choice == 6:
                provider = config.get("provider", "vodafone")
                nid = input("🆔 National ID: ")
                reset_pin(provider, nid)
            elif choice == 7:
                new_provider = input("🔁 Enter new default provider: ").lower()
                if new_provider in PROVIDERS:
                    config["provider"] = new_provider
                    save_config(config)
                    print(f"✅ Default provider set to {new_provider}.")
                else:
                    print("❌ Invalid provider name.")
            elif choice == 8:
                show_logs()
            elif choice == 9:
                reset_config()
            elif choice == 10:
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

