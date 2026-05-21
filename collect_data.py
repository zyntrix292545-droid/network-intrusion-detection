import time
import csv
import os
from datetime import datetime

# Import psutil, try to install it if not present
try:
    import psutil
except ImportError:
    import sys
    import subprocess
    print("psutil not found. Attempting to install it...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
    import psutil

def collect_system_metrics(duration_minutes=15, interval_seconds=2):
    csv_file = "normal_data.csv"
    
    # Check if we need to write the header
    file_exists = os.path.exists(csv_file)
    
    print(f"Starting metric collection for {duration_minutes} minutes...")
    print(f"Data will be saved to {os.path.abspath(csv_file)}")
    print("Collecting data (each dot represents a saved reading every 2s):")
    
    # Get initial network counters for delta calculation
    initial_net = psutil.net_io_counters()
    prev_bytes_sent = initial_net.bytes_sent
    prev_bytes_recv = initial_net.bytes_recv
    
    total_seconds = duration_minutes * 60
    end_time = time.time() + total_seconds
    
    # Open CSV in append mode, line-buffered
    with open(csv_file, mode='a', newline='') as f:
        writer = csv.writer(f)
        
        # Write header if file is new
        if not file_exists:
            writer.writerow([
                "Timestamp",
                "CPU_Usage_Pct",
                "RAM_Usage_Pct",
                "Bytes_Sent_Delta",
                "Bytes_Received_Delta"
            ])
            f.flush()
        
        # Make a measurement right away or wait one interval to get a good CPU percent reading
        # psutil.cpu_percent(interval=None) on first call can return 0.0, so we call it once here
        psutil.cpu_percent(interval=None)
        
        try:
            while time.time() < end_time:
                time.sleep(interval_seconds)
                
                # Fetch metrics
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cpu_pct = psutil.cpu_percent(interval=None)
                ram_pct = psutil.virtual_memory().percent
                
                # Network metrics
                net_io = psutil.net_io_counters()
                bytes_sent = net_io.bytes_sent
                bytes_recv = net_io.bytes_recv
                
                bytes_sent_delta = bytes_sent - prev_bytes_sent
                bytes_recv_delta = bytes_recv - prev_bytes_recv
                
                # Update previous counters
                prev_bytes_sent = bytes_sent
                prev_bytes_recv = bytes_recv
                
                # Write to CSV
                writer.writerow([
                    timestamp,
                    cpu_pct,
                    ram_pct,
                    bytes_sent_delta,
                    bytes_recv_delta
                ])
                f.flush()
                
                # Print a dot to console
                print(".", end="", flush=True)
                
        except KeyboardInterrupt:
            print("\nCollection stopped manually by user.")
            return
            
    print("\nCollection completed successfully!")

if __name__ == "__main__":
    # Run for 15 minutes (900 seconds)
    collect_system_metrics(duration_minutes=15, interval_seconds=2)
