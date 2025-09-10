import os
import subprocess
from datetime import datetime

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

def system_review():
    print_section("SYSTEM REVIEW REPORT")
    print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print_section("Operating System")
    debian_ver = run_cmd("cat /etc/debian_version")
    ubuntu_ver = run_cmd("lsb_release -a 2>/dev/null")
    print("Debian version:\n", debian_ver)
    print("Ubuntu release:\n", ubuntu_ver)

    print_section("Kernel & Uptime")
    print("Kernel info:\n", run_cmd("uname -a"))
    print("Uptime:\n", run_cmd("uptime"))

    print_section("Time Management")
    print("Timezone:\n", run_cmd("cat /etc/timezone 2>/dev/null"))
    print("NTP service check:\n", run_cmd("ps -edf | grep ntp | grep -v grep"))
    print("NTP peers:\n", run_cmd("ntpq -p -n 2>/dev/null"))

    print_section("Installed Packages (Debian)")
    print("Use this list to check for unnecessary or vulnerable packages:")
    print(run_cmd("dpkg -l | head -n 20"))

    print_section("Logging")
    print("rsyslog process:\n", run_cmd("ps -edf | grep syslog | grep -v grep"))
    print("rsyslog config (first 20 lines):\n", run_cmd("head -n 20 /etc/rsyslog.conf 2>/dev/null"))

if __name__ == "__main__":
    system_review()
