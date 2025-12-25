
from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, messagebox


def ask_password(parent: tk.Tk, title: str, prompt: str) -> str:
    return simpledialog.askstring(title, prompt, parent=parent, show="*") or ""


def info(parent: tk.Tk, title: str, msg: str) -> None:
    messagebox.showinfo(title, msg, parent=parent)


def error(parent: tk.Tk, title: str, msg: str) -> None:
    messagebox.showerror(title, msg, parent=parent)
