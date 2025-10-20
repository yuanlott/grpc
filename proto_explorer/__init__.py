import subprocess
import os
import sys
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
    app_path = os.path.join(current_dir, 'proto_explorer.py')

    # 2. Build the command: 
    # ['python', '-m', 'streamlit', 'run', '/path/to/app.py', '--', '--load_path=...', ...]
    command = [
        sys.executable,
        '-m', 'streamlit', 'run', app_path,
        '--',  f"--proto_module={args.proto_module}"
    ]
    if args.load_path:
        command.append(f"--load_path={args.load_path}")

    print("Launching Proto Explorer...")
    try:
        # Launch the Streamlit server
        subprocess.run(command, check=True)
    except FileNotFoundError:
        print(f"Error: Could not find 'streamlit'. Ensure it is installed.", file=sys.stderr)
        sys.exit(1)
