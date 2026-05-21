import time
import os
import psutil
import joblib
import pandas as pd
import requests
import colorama
from colorama import Fore, Style
import socket
import re
from concurrent.futures import ThreadPoolExecutor
import msvcrt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import getpass
from datetime import datetime

# Global Configuration for Gmail Alerting (can be configured here or prompted securely)
GMAIL_USER = "shivaniprasadshivaniprasad55@gmail.com"
GMAIL_APP_PASSWORD = "twiv caiy pzok wcet"

# Try to import serial for ESP32 Serial Monitor capability
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    import sys
    import subprocess
    print("Installing pyserial for ESP32 Serial Monitor capability...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyserial"])
        import serial
        import serial.tools.list_ports
    except Exception as e:
        print(f"Could not install pyserial: {e}")
        serial = None

# Initialize colorama for colored terminal output
colorama.init()

def discover_via_mdns():
    try:
        # Try to resolve esp32.local
        ip = socket.gethostbyname("esp32.local")
        return ip
    except socket.gaierror:
        return None

def discover_via_serial():
    if not serial:
        return None
    
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
        
    print(f"{Fore.CYAN}Found active COM ports: {[p.device for p in ports]}. Scanning serial outputs...{Style.RESET_ALL}")
    
    for p in ports:
        desc = p.description.lower()
        # Common ESP32 USB-to-UART bridge keywords
        is_esp_port = any(kwd in desc for kwd in ["silicon", "cp210", "ch340", "usb to uart", "usb-to-uart", "seri"])
        
        try:
            # Try to open the serial port
            ser = serial.Serial(p.device, 115200, timeout=1.0)
            print(f"Reading from port {p.device} (acting as Serial Monitor)...")
            
            # Read lines for up to 3 seconds to see if ESP32 prints its IP on connect
            start_time = time.time()
            while time.time() - start_time < 3.0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"  [Serial Monitor] {line}")
                    # Match IPv4 address
                    match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                    if match:
                        ip = match.group(1)
                        if not ip.startswith("127."):
                            print(f"{Fore.GREEN}ESP32 IP address discovered via Serial Monitor: {ip}{Style.RESET_ALL}")
                            ser.close()
                            return ip
            ser.close()
        except Exception:
            continue
    return None

def scan_ip(ip):
    try:
        # Quick socket port 80 check
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.15)
            result = s.connect_ex((ip, 80))
            if result == 0:
                # Verify web server responds to GET requests
                try:
                    requests.get(f"http://{ip}/", timeout=0.8)
                    return ip
                except requests.RequestException:
                    return ip
    except Exception:
        pass
    return None

def discover_via_subnet_scan():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "192.168.1.1"
        
    if local_ip.startswith("127."):
        return None
        
    print(f"{Fore.CYAN}Local IP detected: {local_ip}. Scanning local subnet for ESP32 web server...{Style.RESET_ALL}")
    parts = local_ip.split('.')
    subnet_prefix = f"{parts[0]}.{parts[1]}.{parts[2]}"
    
    ips_to_scan = [f"{subnet_prefix}.{i}" for i in range(1, 255) if f"{subnet_prefix}.{i}" != local_ip]
    
    with ThreadPoolExecutor(max_workers=60) as executor:
        results = executor.map(scan_ip, ips_to_scan)
        for res in results:
            if res:
                return res
    return None

def find_esp32_ip():
    # 1. Try mDNS
    print(f"{Fore.CYAN}Step 1: Attempting to resolve ESP32 hostname via mDNS (esp32.local)...{Style.RESET_ALL}")
    ip = discover_via_mdns()
    if ip:
        print(f"{Fore.GREEN}ESP32 found at {ip} via mDNS!{Style.RESET_ALL}")
        return ip
        
    # 2. Try Serial Monitor
    print(f"{Fore.CYAN}Step 2: mDNS failed. Attempting to scan active Serial COM ports...{Style.RESET_ALL}")
    ip = discover_via_serial()
    if ip:
        return ip
        
    # 3. Try Network Subnet Scan
    print(f"{Fore.CYAN}Step 3: Serial discovery failed. Scanning local subnet on WiFi...{Style.RESET_ALL}")
    ip = discover_via_subnet_scan()
    if ip:
        print(f"{Fore.GREEN}ESP32 found at {ip} via local network scan!{Style.RESET_ALL}")
        return ip
        
    # 4. Fallback default
    print(f"{Fore.YELLOW}Step 4: Auto-discovery failed. Defaulting to 10.217.179.24.{Style.RESET_ALL}")
    return "10.217.179.24"

def trigger_buzzer(esp32_ip, timeout=5.0, retries=2):
    for attempt in range(retries + 1):
        try:
            # Send HTTP GET request with the specified timeout
            requests.get(f"http://{esp32_ip}/buzz", timeout=timeout)
            return True
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                # Brief pause before retrying
                time.sleep(0.5)
                continue
            # Print warning after final attempt
            print(f"{Fore.YELLOW}[Warning] ESP32 buzzer offline or unreachable at {esp32_ip} (failed after {retries + 1} attempts): {e}{Style.RESET_ALL}")
    return False

def send_email_alert(timestamp, cpu, ram, net_sent, net_recv, gmail_user, gmail_app_password):
    sender_email = gmail_user
    receiver_email = gmail_user # Send to yourself by default
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "ANOMALY DETECTED"
    
    body = f"""
=========================================
WARNING: SYSTEM ANOMALY DETECTED
=========================================
Intrusion detection system has identified anomalous system resource usage.

Details of the event:
-----------------------------------------
Timestamp:            {timestamp}
CPU Usage:            {cpu}%
RAM Usage:            {ram}%
Bytes Sent Delta:     {net_sent} bytes
Bytes Received Delta: {net_recv} bytes
-----------------------------------------
Please inspect your machine's processes immediately.
"""
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_app_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print(f"\n{Fore.GREEN}[Email Alert] Gmail notification successfully sent to {receiver_email}!{Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"\n{Fore.YELLOW}[Warning] Failed to send Gmail alert: {e}{Style.RESET_ALL}")
        return False

def report_to_dashboard(payload):
    try:
        requests.post("http://127.0.0.1:5000/api/report", json=payload, timeout=1.0)
    except Exception:
        pass

# Thread pool executor shared globally for async email and dashboard dispatch
executor = ThreadPoolExecutor(max_workers=5)

def run_detector():
    global GMAIL_USER, GMAIL_APP_PASSWORD
    model_file = "anomaly_model.pkl"
    
    if not os.path.exists(model_file):
        print(f"{Fore.RED}Error: Trained model file '{model_file}' not found.{Style.RESET_ALL}")
        print("Please run train_model.py first to train and save the model.")
        return
        
    # Email alert credentials setup
    if not GMAIL_USER:
        print(f"{Fore.CYAN}--- Gmail Alert Configuration ---{Style.RESET_ALL}")
        GMAIL_USER = input("Enter your Gmail address: ").strip()
    if not GMAIL_APP_PASSWORD:
        GMAIL_APP_PASSWORD = getpass.getpass("Enter your Gmail App Password (hidden): ").strip()
        print("")
        
    # Discover ESP32 IP Address
    esp32_ip = find_esp32_ip()
    print(f"{Fore.CYAN}Target ESP32 IP Address: {esp32_ip}{Style.RESET_ALL}\n")
    
    print(f"{Fore.CYAN}Loading anomaly detection model...{Style.RESET_ALL}")
    try:
        model = joblib.load(model_file)
        print(f"{Fore.GREEN}Model loaded successfully! Starting real-time detection every 3s...{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error loading model: {e}{Style.RESET_ALL}")
        return

    # Warm up CPU usage counter
    psutil.cpu_percent(interval=None)
    
    # Initialize previous network counters
    net_io = psutil.net_io_counters()
    prev_bytes_sent = net_io.bytes_sent
    prev_bytes_recv = net_io.bytes_recv
    
    # Initialize email rate-limiting variables
    last_email_time = 0
    EMAIL_COOLDOWN = 60 # 1 minute cooldown
    
    print(f"{Fore.YELLOW}Manual Test Mode Active: Press 'T' to trigger the ESP32 buzzer immediately for testing, or Ctrl+C to exit.{Style.RESET_ALL}\n")
    try:
        while True:
            # Sleep for 3 seconds, checking for 'T' keypresses every 100ms
            for _ in range(30):
                time.sleep(0.1)
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                    if key == 't':
                        print(f"\n{Fore.YELLOW}[Manual Test] 'T' key pressed! Triggering ESP32 buzzer at {esp32_ip}...{Style.RESET_ALL}")
                        trigger_buzzer(esp32_ip)
            
            # Retrieve metrics
            cpu_pct = psutil.cpu_percent(interval=None)
            ram_pct = psutil.virtual_memory().percent
            
            # Network delta calculation
            net_io = psutil.net_io_counters()
            bytes_sent_delta = net_io.bytes_sent - prev_bytes_sent
            bytes_recv_delta = net_io.bytes_recv - prev_bytes_recv
            
            # Update previous counters for the next iteration
            prev_bytes_sent = net_io.bytes_sent
            prev_bytes_recv = net_io.bytes_recv
            
            # Prepare feature DataFrame matching training columns
            features = pd.DataFrame([{
                "CPU_Usage_Pct": cpu_pct,
                "RAM_Usage_Pct": ram_pct,
                "Bytes_Sent_Delta": bytes_sent_delta,
                "Bytes_Received_Delta": bytes_recv_delta
            }])
            
            # Make prediction using decision_function with a threshold of -0.3
            score = model.decision_function(features)[0]
            prediction = -1 if score < -0.3 else 1
            
            # Formulate report payload and send asynchronously
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload = {
                "timestamp": timestamp,
                "cpu": float(cpu_pct),
                "ram": float(ram_pct),
                "net_sent": int(bytes_sent_delta),
                "net_recv": int(bytes_recv_delta),
                "prediction": int(prediction),
                "score": float(score)
            }
            executor.submit(report_to_dashboard, payload)
            
            if prediction == -1:
                # Print ANOMALY DETECTED in red
                print(f"{Fore.RED}ANOMALY DETECTED{Style.RESET_ALL} (CPU: {cpu_pct}%, RAM: {ram_pct}%, NetSentDelta: {bytes_sent_delta}B, NetRecvDelta: {bytes_recv_delta}B)")
                
                # Send HTTP GET request with retries to ESP32 buzzer
                trigger_buzzer(esp32_ip)
                
                # Send email alert (Rate-limited, dispatched asynchronously to avoid blocking the main thread)
                current_time = time.time()
                if current_time - last_email_time >= EMAIL_COOLDOWN:
                    print(f"{Fore.CYAN}[Email Alert] Dispatching Gmail notification in background...{Style.RESET_ALL}")
                    executor.submit(
                        send_email_alert,
                        timestamp,
                        cpu_pct,
                        ram_pct,
                        bytes_sent_delta,
                        bytes_recv_delta,
                        GMAIL_USER,
                        GMAIL_APP_PASSWORD
                    )
                    last_email_time = current_time
            else:
                # Print Normal in green
                print(f"{Fore.GREEN}Normal{Style.RESET_ALL} (CPU: {cpu_pct}%, RAM: {ram_pct}%, NetSentDelta: {bytes_sent_delta}B, NetRecvDelta: {bytes_recv_delta}B)")
                
    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}Detection stopped manually by user.{Style.RESET_ALL}")

if __name__ == "__main__":
    run_detector()
