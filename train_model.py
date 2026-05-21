import os
import joblib
import numpy as np
import pandas as pd
import warnings
from sklearn.model_selection import train_test_split
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM
from sklearn.metrics import accuracy_score
import colorama
from colorama import Fore, Style

# Suppress sklearn/user warnings
warnings.filterwarnings('ignore')

# Initialize colorama
colorama.init()

def train_anomaly_model():
    csv_file = "normal_data.csv"
    model_file = "anomaly_model.pkl"
    
    if not os.path.exists(csv_file):
        print(f"{Fore.RED}Error: {csv_file} does not exist. Please collect data first.{Style.RESET_ALL}")
        return
    
    # Load dataset
    df = pd.read_csv(csv_file)
    
    # Features to train on
    features = ["CPU_Usage_Pct", "RAM_Usage_Pct", "Bytes_Sent_Delta", "Bytes_Received_Delta"]
    
    # Check if all required features exist in the CSV
    missing_features = [feat for feat in features if feat not in df.columns]
    if missing_features:
        print(f"{Fore.RED}Error: Missing columns in CSV: {missing_features}{Style.RESET_ALL}")
        return
    
    # Select feature columns
    X = df[features]
    
    # Split baseline normal data: 80% for training, 20% for validation
    X_train, X_val_normal = train_test_split(X, test_size=0.2, random_state=42)
    
    # Generate Synthetic Anomalies for validation (representing active network intrusions)
    num_anomalies = len(X_val_normal)
    np.random.seed(42)
    X_val_anomaly = X_val_normal.copy().reset_index(drop=True)
    
    # Inject extreme outlier resource consumption signatures
    # CPU: 90% to 100%
    X_val_anomaly["CPU_Usage_Pct"] = np.random.uniform(90.0, 100.0, num_anomalies)
    # RAM: 90% to 100%
    X_val_anomaly["RAM_Usage_Pct"] = np.random.uniform(90.0, 100.0, num_anomalies)
    # Network traffic deltas: 1MB to 10MB
    X_val_anomaly["Bytes_Sent_Delta"] = np.random.randint(1000000, 10000000, num_anomalies)
    X_val_anomaly["Bytes_Received_Delta"] = np.random.randint(1000000, 10000000, num_anomalies)
    
    # Combine normal validation samples (label 1) and synthetic anomalies (label -1)
    X_val = pd.concat([X_val_normal, X_val_anomaly], axis=0).reset_index(drop=True)
    y_val = np.array([1] * len(X_val_normal) + [-1] * num_anomalies)
    
    # Define models
    # LOF novelty=True is required to allow predicting on unseen validation points
    models = {
        "Isolation Forest": IsolationForest(n_estimators=100, contamination=0.05, random_state=42),
        "Local Outlier Factor": LocalOutlierFactor(n_neighbors=20, contamination=0.05, novelty=True),
        "One-Class SVM": OneClassSVM(nu=0.05, kernel='rbf', gamma='scale')
    }
    
    results = {}
    fitted_models = {}
    
    print(f"\n{Fore.CYAN}Training and evaluating 3 anomaly detection models...{Style.RESET_ALL}")
    
    for name, model in models.items():
        try:
            # Fit model on training normal dataset
            model.fit(X_train)
            fitted_models[name] = model
            
            # Predict labels on validation dataset (predict outputs 1 or -1)
            y_pred = model.predict(X_val)
            acc = accuracy_score(y_val, y_pred)
            results[name] = acc
            print(f"  Fitted and evaluated {Fore.GREEN}{name}{Style.RESET_ALL}...")
        except Exception as e:
            print(f"  {Fore.RED}Failed to train {name}: {e}{Style.RESET_ALL}")
            results[name] = 0.0
            
    # Auto-select the model with the highest validation accuracy
    best_model_name = max(results, key=results.get)
    best_model = fitted_models[best_model_name]
    
    # Save the best model
    joblib.dump(best_model, model_file)
    
    # Print comparison table
    print("\n" + "="*60)
    print(f" {Fore.CYAN}CYBERSECURITY MODEL BENCHMARK COMPARISON{Style.RESET_ALL} ")
    print("="*60)
    print(f"| {'Model Algorithm':<22} | {'Validation Accuracy':<19} | {'Status':<11} |")
    print("|" + "-"*24 + "|" + "-"*21 + "|" + "-"*13 + "|")
    for name, score in results.items():
        status = "[CHAMPION]" if name == best_model_name else "Benchmarked"
        color = Fore.GREEN if name == best_model_name else Fore.YELLOW
        print(f"| {name:<22} | {color}{score:>18.2%}{Style.RESET_ALL} | {color}{status:<11}{Style.RESET_ALL} |")
    print("="*60)
    print(f"{Fore.GREEN}SUCCESS:{Style.RESET_ALL} Selected {Fore.YELLOW}{best_model_name}{Style.RESET_ALL} as champion and saved as '{model_file}'!\n")

if __name__ == "__main__":
    train_anomaly_model()
