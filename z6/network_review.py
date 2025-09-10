import subprocess
from datetime import datetime
import os

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        return result.stdout.strip() if result.stdout else result.stderr.strip()
    except Exception as e:
        return f"Error running {cmd}: {e}"

def print_section(title):
    print("\n" + "="*60)
    print(f"[ {title} ]")
    print("="*60)

def network_review():
    print_section("NETWORK REVIEW REPORT")
    print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print_section("Network Interfaces (ifconfig -a)")
    print(run_cmd("ifconfig -a"))

    print_section("Routing Table (route -n)")
    print(run_cmd("route -n"))

    print_section("DNS Configuration (/etc/resolv.conf)")
    if os.path.exists("/etc/resolv.conf"):
        print(run_cmd("cat /etc/resolv.conf"))
    else:
        print("/etc/resolv.conf not found.")

    print_section("Hosts File (/etc/hosts)")
    if os.path.exists("/etc/hosts"):
        print(run_cmd("cat /etc/hosts"))
    else:
        print("/etc/hosts not found.")

    print_section("Firewall Rules (iptables -L -v)")
    print(run_cmd("sudo iptables -L -v"))

if __name__ == "__main__":
    network_review()
