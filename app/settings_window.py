"""Settings dialog: microphone, system-audio device, transcription model
size, and calls storage folder. Opened on demand from the tray menu -- runs
its own Tk() instance in a dedicated thread rather than sharing a mainloop
with pystray."""

import tkinter as tk
from tkinter import ttk, filedialog

from audio_capture import list_mic_devices, list_system_audio_devices

MODEL_OPTIONS = ["tiny", "base", "small", "medium", "large-v3"]
MODEL_HINT = {
    "tiny": "Fastest, least accurate. Good for quick tests.",
    "base": "Fast, low accuracy.",
    "small": "Good balance for short/simple calls.",
    "medium": "Recommended default -- strong accuracy, still fast on this GPU.",
    "large-v3": "Best accuracy, slower to load, uses more VRAM (quantized automatically to fit).",
}

SYSTEM_DEFAULT_LABEL = "System Default"


def open_settings_window(current_config: dict, on_save):
    """Blocks until the window is closed. Call this in its own thread.
    on_save(new_config: dict) is called only if the user clicks Save."""

    root = tk.Tk()
    root.title("Ascolto Settings")
    root.resizable(False, False)

    mic_devices = list_mic_devices()
    sys_devices = list_system_audio_devices()

    mic_labels = [SYSTEM_DEFAULT_LABEL] + [name for _, name in mic_devices]
    mic_index_by_label = {SYSTEM_DEFAULT_LABEL: None, **{name: idx for idx, name in mic_devices}}

    sys_labels = [SYSTEM_DEFAULT_LABEL] + [name for _, name in sys_devices]
    sys_index_by_label = {SYSTEM_DEFAULT_LABEL: None, **{name: idx for idx, name in sys_devices}}

    frame = ttk.Frame(root, padding=16)
    frame.grid(row=0, column=0, sticky="nsew")

    row = 0

    ttk.Label(frame, text="Microphone:").grid(row=row, column=0, sticky="w", pady=4)
    mic_var = tk.StringVar()
    mic_combo = ttk.Combobox(frame, textvariable=mic_var, values=mic_labels, state="readonly", width=40)
    current_mic_name = next((name for idx, name in mic_devices if idx == current_config.get("mic_device_index")), SYSTEM_DEFAULT_LABEL)
    mic_var.set(current_mic_name)
    mic_combo.grid(row=row, column=1, pady=4)
    row += 1

    ttk.Label(frame, text="System audio (what you hear):").grid(row=row, column=0, sticky="w", pady=4)
    sys_var = tk.StringVar()
    sys_combo = ttk.Combobox(frame, textvariable=sys_var, values=sys_labels, state="readonly", width=40)
    current_sys_name = next((name for idx, name in sys_devices if idx == current_config.get("system_device_index")), SYSTEM_DEFAULT_LABEL)
    sys_var.set(current_sys_name)
    sys_combo.grid(row=row, column=1, pady=4)
    row += 1

    ttk.Label(frame, text="Transcription model:").grid(row=row, column=0, sticky="w", pady=4)
    model_var = tk.StringVar(value=current_config.get("model_size", "medium"))
    model_combo = ttk.Combobox(frame, textvariable=model_var, values=MODEL_OPTIONS, state="readonly", width=40)
    model_combo.grid(row=row, column=1, pady=4)
    row += 1

    hint_label = ttk.Label(frame, text=MODEL_HINT.get(model_var.get(), ""), foreground="#555555", wraplength=320)
    hint_label.grid(row=row, column=1, sticky="w")
    row += 1

    def on_model_change(event=None):
        hint_label.config(text=MODEL_HINT.get(model_var.get(), ""))

    model_combo.bind("<<ComboboxSelected>>", on_model_change)

    ttk.Label(frame, text="Calls folder:").grid(row=row, column=0, sticky="w", pady=4)
    folder_var = tk.StringVar(value=current_config.get("calls_root", ""))
    folder_entry = ttk.Entry(frame, textvariable=folder_var, width=32, state="readonly")
    folder_entry.grid(row=row, column=1, sticky="w", pady=4)
    row += 1

    def browse_folder():
        chosen = filedialog.askdirectory(initialdir=folder_var.get() or str(root))
        if chosen:
            folder_var.set(chosen)

    ttk.Button(frame, text="Browse...", command=browse_folder).grid(row=row, column=1, sticky="w")
    row += 1

    note = ttk.Label(
        frame,
        text="Device and folder changes apply to your next recording.\nChanging the model reloads it in the background.",
        foreground="#555555",
    )
    note.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
    row += 1

    button_frame = ttk.Frame(frame)
    button_frame.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))

    def do_save():
        new_config = {
            "mic_device_index": mic_index_by_label.get(mic_var.get()),
            "system_device_index": sys_index_by_label.get(sys_var.get()),
            "model_size": model_var.get(),
            "calls_root": folder_var.get(),
        }
        on_save(new_config)
        root.destroy()

    def do_cancel():
        root.destroy()

    ttk.Button(button_frame, text="Cancel", command=do_cancel).pack(side="right", padx=(4, 0))
    ttk.Button(button_frame, text="Save", command=do_save).pack(side="right")

    root.mainloop()
