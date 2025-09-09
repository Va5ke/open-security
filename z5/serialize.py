import sys
import base64
import pickle

class Log:
    def __init__(self, f, m):
        self.f = f
        self.m = m

    def __del__(self):
        with open(self.f, "a") as file:
            file.write(self.m)

if len(sys.argv) != 3:
    print("Usage: python serialize.py <filename> <base64_message>")
    sys.exit(1)
f = sys.argv[1]
m = base64.urlsafe_b64decode(sys.argv[2]).decode("utf-8")
log = Log(f, m)
print(pickle.dumps(log))