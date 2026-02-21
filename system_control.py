# system_control.py
import subprocess
import os
import pyautogui

def launch_app(app_path):
    try:
        subprocess.Popen([app_path])
        return f"Launched: {app_path}"
    except Exception as e:
        return f"Error launching {app_path}: {e}"

def shutdown_pc():
    try:
        subprocess.run(['shutdown', '/s', '/t', '1'])
        return "Shutting down..."
    except Exception as e:
        return f"Error: {e}"

def control_volume(percentage):
    try:
        pyautogui.press(['volumeup'] * percentage) # example.
        return f"Volume set to {percentage}%"
    except Exception as e:
        return f'Error: {e}'

# Add more system control functions as needed.