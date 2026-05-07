"""
Trading System Launcher - Historical Simulation Mode
NO REAL TRADING - All strategies run on cached historical data
"""

import subprocess
import sys
import time
import os
import signal

# Get the root directory
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
COMPONENTS_DIR = os.path.join(ROOT_DIR, "src", "components")
DATA_DIR = os.path.join(ROOT_DIR, "data")

def kill_process_on_port(port):
    """Kill any process using the specified port"""
    try:
        if sys.platform == "win32":
            result = subprocess.run(f'netstat -ano | findstr :{port}', shell=True, capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    pid = parts[-1]
                    if pid.isdigit():
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                        print(f"  Killed process on port {port} (PID: {pid})")
                        time.sleep(1)
        else:
            subprocess.run(f'fuser -k {port}/tcp', shell=True, capture_output=True)
    except:
        pass

def main():
    print("=" * 70)
    print("  TRADING SYSTEM - HISTORICAL SIMULATION MODE")
    print("  NO REAL ORDERS - Using cached MT5 historical data")
    print("=" * 70)
    
    # Ask for simulation duration
    print("\n  Hours to simulate (default 24, max 168):")
    hours_input = input("  > ").strip()
    sim_hours = int(hours_input) if hours_input else 24
    sim_hours = max(1, min(168, sim_hours))
    
    # Kill any existing process on port 8765
    kill_process_on_port(8765)
    
    # Set environment variable
    env = os.environ.copy()
    env["SIMULATION_HOURS"] = str(sim_hours)
    
    print(f"\n  ⏱️  Simulating {sim_hours} hours of trading")
    print("  📊 Both strategies will run simultaneously")
    print("  🌐 Viewer will open at http://localhost:8765\n")
    
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    processes = []
    
    try:
        # Launch MA Strategy
        print("  Launching MA Crossover Strategy...")
        ma_strategy = subprocess.Popen(
            [sys.executable, os.path.join(COMPONENTS_DIR, "MA_strategy.py")],
            env=env
        )
        processes.append(("MA Strategy", ma_strategy))
        time.sleep(2)
        
        # Launch RSI Strategy
        print("  Launching RSI Mean Reversion Strategy...")
        rsi_strategy = subprocess.Popen(
            [sys.executable, os.path.join(COMPONENTS_DIR, "RSI_strategy.py")],
            env=env
        )
        processes.append(("RSI Strategy", rsi_strategy))
        time.sleep(2)
        
        # Launch Viewer
        print("  Launching 3D Viewer...")
        viewer = subprocess.Popen(
            [sys.executable, os.path.join(COMPONENTS_DIR, "Viewer.py")]
        )
        processes.append(("Viewer", viewer))
        
        print("\n  ┌" + "─" * 68 + "┐")
        print("  │  SIMULATION RUNNING - Historical Data Mode              │")
        for name, proc in processes:
            print(f"  │  {name:<12} PID: {proc.pid:<42}│")
        print("  ├" + "─" * 68 + "┤")
        print("  │  🔷 NO REAL TRADING - Using cached MT5 data             │")
        print(f"  │  ⏱️  Simulating {sim_hours} hours of past data              │")
        print("  │  📡 Viewer: http://localhost:8765                      │")
        print("  │                                                        │")
        print("  │  Press Ctrl+C to stop simulation early                 │")
        print("  └" + "─" * 68 + "┘")
        print("\n  Waiting for simulations to complete...\n")
        
        # Wait for both strategies to finish
        ma_strategy.wait()
        rsi_strategy.wait()
        
        print("\n  ✅ Both simulations completed!")
        
        print("\n  Press Enter to stop the viewer and exit...")
        input()
        
    except KeyboardInterrupt:
        print("\n\n  Shutting down simulation...")
        
    finally:
        for name, proc in processes:
            if proc.poll() is None:
                print(f"  Stopping {name}...")
                proc.terminate()
                time.sleep(1)
                if proc.poll() is None:
                    proc.kill()
        
        # Final cleanup of port
        kill_process_on_port(8765)
        
        print("\n  All processes stopped.")
        print("  ✅ Simulation complete!")
        print(f"  📁 Data saved to: {DATA_DIR}")


if __name__ == "__main__":
    main()