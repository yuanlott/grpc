import subprocess
import os
import sys

def cli_entry_point():
    """
    Launches the Streamlit app using the 'streamlit run' command 
    and passes all custom arguments. This is the console script entry point 
    registered by Poetry.
    """
    
    # 1. Find the absolute path to app.py relative to this file
    # This ensures the script is found reliably after installation.
    current_dir = os.path.dirname(__file__)
    app_path = os.path.join(current_dir, 'proto_explorer.py')
    
    # 2. Build the command: 
    # ['python', '-m', 'streamlit', 'run', '/path/to/app.py', '--', '--load_path=...', ...]
    command = [
        sys.executable,  # Use the python interpreter from the current environment
        '-m', 'streamlit', 'run', 
        app_path, 
        '--',
        *sys.argv[1:]      # Pass all user-provided arguments after 'proto_explorer'
    ]
    
    # 3. Execute the command
    print("Launching Proto Explorer...")
    try:
        # Launch the Streamlit server
        subprocess.run(command, check=True)
    except FileNotFoundError:
        print(f"Error: Could not find 'streamlit'. Ensure it is installed.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error launching Streamlit application: {e}", file=sys.stderr)
        sys.exit(1)
