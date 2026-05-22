import os
import csv
import threading
import io
import time
import random
from flask import Flask, render_template, jsonify, send_file, request

app = Flask(__name__)

# Simulator state variables for Demo Mode
use_simulator = True
simulator_active_attack = 0

def simulator_thread_func():
    """Generates realistic mock metrics in a background thread while no real detector is connected."""
    global current_status, use_simulator, simulator_active_attack
    print("Dashboard: Demo Mode Simulator Thread Active.")
    
    while True:
        time.sleep(3.0)
        if not use_simulator:
            continue
            
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Decide if we trigger a simulated attack (approx. once every 2 minutes)
        if simulator_active_attack <= 0:
            if random.random() < 0.025:  # ~2.5% chance per tick
                simulator_active_attack = random.randint(3, 5)  # anomaly lasts 9 to 15 seconds
                print(f"\n[DEMO MODE] Activating simulated cyber-intrusion threat for {simulator_active_attack} ticks!")
        
        if simulator_active_attack > 0:
            # Generate simulated anomaly parameters
            cpu = random.uniform(84.0, 97.5)
            ram = random.uniform(76.5, 91.0)
            net_sent = random.randint(1100000, 7800000)
            net_recv = random.randint(1500000, 9200000)
            prediction = -1
            score = random.uniform(-0.52, -0.31)
            simulator_active_attack -= 1
        else:
            # Generate simulated normal baseline parameters
            cpu = random.uniform(4.5, 23.0)
            ram = random.uniform(32.0, 56.5)
            net_sent = random.randint(120, 4800)
            net_recv = random.randint(300, 8000)
            prediction = 1
            score = random.uniform(0.06, 0.35)
            
        anomaly_active = (prediction == -1)
        
        with data_lock:
            current_status.update({
                "timestamp": timestamp,
                "cpu": round(cpu, 1),
                "ram": round(ram, 1),
                "net_sent": net_sent,
                "net_recv": net_recv,
                "prediction": prediction,
                "score": round(score, 4),
                "anomaly_active": anomaly_active
            })
            
        if anomaly_active:
            log_anomaly(timestamp, round(cpu, 1), round(ram, 1), net_sent, net_recv, score)

# CSV File for logging anomalies
CSV_FILE = "anomaly_history.csv"

# Ensure the CSV file exists and has headers
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "CPU_Usage_Pct", "RAM_Usage_Pct", "Bytes_Sent_Delta", "Bytes_Received_Delta", "Threat_Score"])

# Thread-safe in-memory cache for current live metrics
data_lock = threading.Lock()
current_status = {
    "timestamp": "N/A",
    "cpu": 0.0,
    "ram": 0.0,
    "net_sent": 0,
    "net_recv": 0,
    "prediction": 1,
    "score": 0.0,
    "anomaly_active": False
}

def log_anomaly(timestamp, cpu, ram, net_sent, net_recv, score):
    """Appends a new anomaly record to the persistent CSV file."""
    try:
        with open(CSV_FILE, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, cpu, ram, net_sent, net_recv, round(score, 4)])
    except Exception as e:
        print(f"Error logging anomaly to CSV: {e}")

@app.route("/")
def index():
    """Serves the main SOC dashboard interface."""
    return render_template("index.html")

@app.route("/api/report", methods=["POST"])
def report():
    """Receives live metrics and anomaly status reported by detector.py."""
    global current_status, use_simulator
    
    # Automatically switch off simulation thread as soon as a real detector POSTs
    if use_simulator:
        use_simulator = False
        print("\n[LIVE MONITOR] Received real telemetry reports! Deactivating Demo Mode Simulator.")
        
    payload = request.json
    if not payload:
        return jsonify({"status": "error", "message": "No JSON payload provided"}), 400
    
    timestamp = payload.get("timestamp", "N/A")
    cpu = payload.get("cpu", 0.0)
    ram = payload.get("ram", 0.0)
    net_sent = payload.get("net_sent", 0)
    net_recv = payload.get("net_recv", 0)
    prediction = payload.get("prediction", 1)
    score = payload.get("score", 0.0)
    anomaly_active = (prediction == -1)

    with data_lock:
        current_status.update({
            "timestamp": timestamp,
            "cpu": cpu,
            "ram": ram,
            "net_sent": net_sent,
            "net_recv": net_recv,
            "prediction": prediction,
            "score": score,
            "anomaly_active": anomaly_active
        })

    # Log to CSV if it's an anomaly
    if anomaly_active:
        log_anomaly(timestamp, cpu, ram, net_sent, net_recv, score)

    return jsonify({"status": "success"})

@app.route("/api/data", methods=["GET"])
def get_data():
    """Returns the current real-time state as JSON for dashboard polling."""
    global use_simulator
    with data_lock:
        res_data = current_status.copy()
        res_data["use_simulator"] = use_simulator
        return jsonify(res_data)

@app.route("/api/history", methods=["GET"])
def get_history():
    """Reads all historical anomalies from the CSV and returns them in reverse chronological order."""
    history = []
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, mode='r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    history.append(row)
        except Exception as e:
            print(f"Error reading history CSV: {e}")
    
    # Return in reverse chronological order (newest first)
    return jsonify(history[::-1])

@app.route("/api/export", methods=["GET"])
def export_csv():
    """Streams the full anomaly CSV log file to the user's browser as a download."""
    if os.path.exists(CSV_FILE):
        return send_file(
            CSV_FILE,
            mimetype="text/csv",
            as_attachment=True,
            download_name="anomaly_history_log.csv"
        )
    else:
        # Fallback to empty CSV header if file doesn't exist
        mem_file = io.BytesIO()
        mem_file.write(b"Timestamp,CPU_Usage_Pct,RAM_Usage_Pct,Bytes_Sent_Delta,Bytes_Received_Delta,Threat_Score\n")
        mem_file.seek(0)
        return send_file(
            mem_file,
            mimetype="text/csv",
            as_attachment=True,
            download_name="anomaly_history_log.csv"
        )

# Start simulation thread for Demo Mode
sim_thread = threading.Thread(target=simulator_thread_func, daemon=True)
sim_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("--------------------------------------------------")
    print("  Cybersecurity SOC Dashboard Backend Running     ")
    print(f"  Access dashboard at: http://localhost:{port}/    ")
    print("--------------------------------------------------")
    app.run(host="0.0.0.0", port=port, debug=False)
