import requests
import subprocess
import threading
import os
import sys
import time
from .proto_explorer import parse_args


def cli_entry_point():
    """
    Launches the Streamlit app using the 'streamlit run' command
    and passes all custom arguments. This is the console script entry point
    registered by Poetry.
    """

    try:
        args = parse_args()
    except ValueError as e:
        print(f"Argument error: {e}", file=sys.stderr)
        sys.exit(1)

    # 1. Find the absolute path to app.py relative to this file
    # This ensures the script is found reliably after installation.
    current_dir = os.path.dirname(__file__)
    app_path = os.path.join(current_dir, "proto_explorer.py")

    # 2. Build the command:
    # ['python', '-m', 'streamlit', 'run', '/path/to/app.py', '--', '--load_path=...', ...]
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_path,
        "--server.headless",
        "true",
        "--logger.level",
        "error",
        # '--server.address', 'localhost',
        "--",
        f"--proto_module={args.proto_module}",
    ]
    if args.load_path:
        command.append(f"--load_path={args.load_path}")

    print("Launching Proto Explorer...")
    # Start Streamlit server
    proc = subprocess.Popen(command)

    def wait_for_streamlit():
        for _ in range(20):  # timeout of (0.25 + 0.1) * 20 = 7 seconds
            try:
                requests.get("http://localhost:8501", timeout=0.25)
                return True
            except requests.exceptions.ConnectionError:
                time.sleep(0.1)
        return False

    # Wait until Streamlit is up before printing quit instructions
    if wait_for_streamlit():
        color_yellow = "\033[93m"
        color_reset = "\033[0m"
        print(f"\n{color_yellow}Press 'q' then Enter to quit Proto Explorer.")
        print(f"{color_reset}\n")
    else:
        print("\n(Warning) Streamlit may not have started yet.\n")

    # Watcher thread for user Quit
    def quit_watcher():
        while proc.poll() is None:
            user_input = input().strip().lower()
            if user_input == "q":
                print("Shutting down Proto Explorer...")
                proc.terminate()
                break

    watcher_thread = threading.Thread(target=quit_watcher, daemon=True)
    watcher_thread.start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
