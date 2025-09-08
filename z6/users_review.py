import os
import re

PASSWORD_FILE = "/etc/passwd"
SHADOW_FILE = "/etc/shadow"
SUDOERS_FILE = "/etc/sudoers"

def review_passwd(users: dict):
    with open(PASSWORD_FILE, "r") as f:
        lines = f.readlines()

    uid0 = []

    for line in lines:
        parts = line.strip().split(":")
        if len(parts) < 7:
            continue

        username, _, uid, _, _, _, shell = parts
        uid = int(uid)

        if uid == 0:
            uid0.append(username)

        has_shell = shell not in ["/bin/false", "/usr/sbin/nologin"]
        users.setdefault(username, {})["has shell"] = f"{str(has_shell):5}"
        users[username]["shell"] = f"{shell:17}"

    print("--- Users with UID 0 ===")
    if uid0:
        for u in uid0:
            print(f" - {u}")
    else:
        print("No suspicious UID 0 users found")

def detect_algorithm(hash_field):
    if not hash_field or hash_field in ["*", "!", "!!"]:
        return "No password / locked"
    if "$" not in hash_field:
        return "DES"
    if hash_field.startswith("$1$"):
        return "MD5"
    elif hash_field.startswith("$2$") or hash_field.startswith("$2a$"):
        return "Blowfish"
    elif hash_field.startswith("$5$"):
        return "SHA-256"
    elif hash_field.startswith("$6$"):
        return "SHA-512"
    else:
        return "Unknown algorithm"
    
def review_shadow(users):
    if not os.path.exists(SHADOW_FILE):
        print("Shadow file not found")
        return
    with open(SHADOW_FILE, "r") as f:
        lines = f.readlines()
    
    for line in lines:
        parts = line.strip().split(":")
        if len(parts) < 2:
            continue
        username, hash_field = parts[0], parts[1]
        algorithm = detect_algorithm(hash_field)
        users.setdefault(username, {})["password algorithm"] = f"{algorithm:20}"

def check_common_password():
    path = "/etc/pam.d/common-password"
    if os.path.exists(path):
        print("\n--- Default Password Algorithm ---")
        with open(path, "r") as f:
            for line in f:
                if "pam_unix.so" in line or "pam_cracklib.so" in line:
                    print(" - " + line.split()[-1])
    else:
        print("Common-password file not found")

def review_sudoers():
    if not os.path.exists(SUDOERS_FILE):
        print("Sudoers file not found")
        return

    print("\n--- Reviewing /etc/sudoers configuration ---")
    with open(SUDOERS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            print(line)

if __name__ == "__main__":
    users = {}
    review_passwd(users)
    review_shadow(users)
    check_common_password()
    review_sudoers()

    print("\n--- Data for each user ---")
    for u in sorted(users.keys()):
        print(f" - {u:20}", end="|")
        for p, v in users[u].items():
            print(f" {p}: {v} ", end="|")