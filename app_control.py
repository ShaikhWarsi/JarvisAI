# app_control.py
from pywinauto import Application

def control_notepad(text):
    try:
        app = Application().connect(title='Untitled - Notepad')
        app.UntitledNotepad.Edit.type_keys(text)
        return "Text entered into Notepad."
    except Exception as e:
        return f"Error controlling Notepad: {e}"

# Add more application control functions as needed.