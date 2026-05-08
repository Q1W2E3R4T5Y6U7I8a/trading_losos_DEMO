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
VIEWER_PORT = 8765

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
                        print(f"  🔧 Freed port {port} (PID: {pid})")
                        time.sleep(0.5)
        else:
            subprocess.run(f'fuser -k {port}/tcp', shell=True, capture_output=True)
            time.sleep(0.5)
    except:
        pass

def stop_processes(processes):
    """Gracefully stop all running processes"""
    for name, proc in processes:
        if proc.poll() is None:
            print(f"  ⏹️  Stopping {name}...")
            if sys.platform == "win32":
                proc.terminate()
            else:
                proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

def main():
    print("=" * 70)
    print("  TRADING SYSTEM - HISTORICAL SIMULATION MODE")
    print("  NO REAL ORDERS - Using cached MT5 historical data")
    print("=" * 70)
    
    # Ask for simulation duration
    print("\n  Hours to simulate (default 24, max 168):")
    try:
        hours_input = input("  > ").strip()
        sim_hours = int(hours_input) if hours_input else 24
        sim_hours = max(1, min(168, sim_hours))
    except ValueError:
        sim_hours = 24
        print("  ⚠️  Invalid input, using default: 24 hours")
    
    # Kill any existing process on viewer port
    kill_process_on_port(VIEWER_PORT)
    
    # Set environment variable for strategies
    env = os.environ.copy()
    env["SIMULATION_HOURS"] = str(sim_hours)
    
    print(f"\n  ⏱️  Simulating {sim_hours} hours of trading")
    print(f"  📊 Both strategies will run simultaneously")
    print(f"  🌐 Viewer will open at http://localhost:{VIEWER_PORT}\n")
    
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    processes = []
    
    try:
        # Launch strategies
        print("  Launching MA Crossover Strategy...")
        ma_proc = subprocess.Popen(
            [sys.executable, os.path.join(COMPONENTS_DIR, "MA_strategy.py")],
            env=env
        )
        processes.append(("MA Strategy", ma_proc))
        time.sleep(2)
        
        print("  Launching RSI Mean Reversion Strategy...")
        rsi_proc = subprocess.Popen(
            [sys.executable, os.path.join(COMPONENTS_DIR, "RSI_strategy.py")],
            env=env
        )
        processes.append(("RSI Strategy", rsi_proc))
        time.sleep(2)
        
        print("  Launching 3D Viewer...")
        viewer_proc = subprocess.Popen(
            [sys.executable, os.path.join(COMPONENTS_DIR, "Viewer.py")]
        )
        processes.append(("Viewer", viewer_proc))
        
        # Status display
        print("\n  ┌" + "─" * 68 + "┐")
        print("  │  SIMULATION RUNNING - Historical Data Mode              │")
        for name, proc in processes:
            print(f"  │  {name:<12} PID: {proc.pid:<42}│")
        print("  ├" + "─" * 68 + "┤")
        print("  │  🔷 NO REAL TRADING - Using cached MT5 data             │")
        print(f"  │  ⏱️  Simulating {sim_hours} hours of past data              │")
        print(f"  │  📡 Viewer: http://localhost:{VIEWER_PORT}                      │")
        print("  │                                                        │")
        print("  │  Press Ctrl+C to stop simulation early                 │")
        print("  └" + "─" * 68 + "┘")
        print("\n  Waiting for simulations to complete...\n")
        
        # Wait for strategies (viewer runs indefinitely)
        ma_proc.wait()
        rsi_proc.wait()
        
        print("\n  ✅ Both simulations completed!")
        print(f"  🌐 Viewer still running at http://localhost:{VIEWER_PORT}")
        print("  Press Ctrl+C to stop the viewer and exit...")
        
        # Keep running until user interrupts (viewer is still alive)
        try:
            while viewer_proc.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
    except KeyboardInterrupt:
        print("\n\n  🛑 Simulation interrupted by user")
        
    finally:
        # Clean shutdown
        stop_processes(processes)
        kill_process_on_port(VIEWER_PORT)
        
        print("\n  ✅ All processes stopped")
        print(f"  📁 Simulation data saved to: {DATA_DIR}")


if __name__ == "__main__":
    main()