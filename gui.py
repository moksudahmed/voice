import tkinter as tk
from tkinter import messagebox
import threading

# ================================
# GLOBAL CONTROL
# ================================
app_running = False
worker_thread = None

# ================================
# START FUNCTION
# ================================
def start_script():
    global app_running, worker_thread

    if app_running:
        messagebox.showwarning("Warning", "Script already running!")
        return

    # Get user inputs
    crex_url = url_entry.get()
    team1 = team1_entry.get()
    team2 = team2_entry.get()
    title = title_entry.get()
    output = output_entry.get()

    if not crex_url or not team1 or not team2:
        messagebox.showerror("Error", "Please fill all required fields!")
        return

    # Inject into your existing variables
    global CREX_URL, TEAM1, TEAM2, match_title, OUTPUT_FILE
    CREX_URL = crex_url
    TEAM1 = team1
    TEAM2 = team2
    match_title = title
    OUTPUT_FILE = output

    app_running = True

    # Run your main() in background thread
    worker_thread = threading.Thread(target=run_main)
    worker_thread.daemon = True
    worker_thread.start()

    status_label.config(text="🟢 Running...")


# ================================
# STOP FUNCTION
# ================================
def stop_script():
    global app_running
    app_running = False
    status_label.config(text="🔴 Stopped")


# ================================
# WRAPPER FOR MAIN LOOP
# ================================
def run_main():
    try:
        main()
    except Exception as e:
        messagebox.showerror("Error", str(e))


# ================================
# GUI DESIGN
# ================================
root = tk.Tk()
root.title("Cricket Commentary Bot")
root.geometry("500x400")
root.configure(bg="#1e1e1e")

# Title
tk.Label(root, text="🏏 Cricket Live Commentary Bot",
         font=("Arial", 16, "bold"),
         fg="white", bg="#1e1e1e").pack(pady=10)

# CREX URL
tk.Label(root, text="CREX URL", fg="white", bg="#1e1e1e").pack()
url_entry = tk.Entry(root, width=60)
url_entry.pack(pady=5)

# Team 1
tk.Label(root, text="Team 1 Name", fg="white", bg="#1e1e1e").pack()
team1_entry = tk.Entry(root, width=40)
team1_entry.pack(pady=5)

# Team 2
tk.Label(root, text="Team 2 Name", fg="white", bg="#1e1e1e").pack()
team2_entry = tk.Entry(root, width=40)
team2_entry.pack(pady=5)

# Match Title
tk.Label(root, text="Match Title", fg="white", bg="#1e1e1e").pack()
title_entry = tk.Entry(root, width=50)
title_entry.pack(pady=5)

# Output File
tk.Label(root, text="Output JSON Path", fg="white", bg="#1e1e1e").pack()
output_entry = tk.Entry(root, width=60)
output_entry.pack(pady=5)
output_entry.insert(0, "C:/cricket_voices/score.json")

# Buttons
btn_frame = tk.Frame(root, bg="#1e1e1e")
btn_frame.pack(pady=20)

tk.Button(btn_frame, text="▶ Start",
          command=start_script,
          bg="green", fg="white", width=12).grid(row=0, column=0, padx=10)

tk.Button(btn_frame, text="⏹ Stop",
          command=stop_script,
          bg="red", fg="white", width=12).grid(row=0, column=1, padx=10)

# Status
status_label = tk.Label(root, text="⚪ Idle",
                        fg="white", bg="#1e1e1e",
                        font=("Arial", 12))
status_label.pack(pady=10)

# Run GUI
root.mainloop()