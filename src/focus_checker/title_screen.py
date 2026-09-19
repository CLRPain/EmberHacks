import os
import tkinter as tk
from tkinter import messagebox

# Path to your PNG image (Must be in the same directory)
# Make sure this PNG is pre-resized to fit your frame!
IMAGE_PATH = "./yellingTA.png"


class TheTAApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("The TA")
        self.geometry("1280x720")
        self.minsize(800, 500)
        self.configure(bg="#f4f4f5")

        self.current_ta = tk.StringVar(value="None")

        self.container = tk.Frame(self, bg="#f4f4f5")
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for PageClass in (TitleScreen, AppScreen):
            page_name = PageClass.__name__
            frame = PageClass(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.show_frame("TitleScreen")

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        if hasattr(frame, "on_show"):
            frame.on_show()
        frame.tkraise()


class TitleScreen(tk.Frame):

    def __init__(self, parent, controller):
        super().__init__(parent, bg="#ffffff")
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------------- LEFT SIDE IMAGE PANEL ----------------
        left_panel = tk.Frame(self, bg="#1e1e24")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)

        # Standard Tkinter PNG loading (No external libraries required)
        if os.path.exists(IMAGE_PATH):
            try:
                # Store image reference on 'self' to avoid garbage collection
                self.ta_png = tk.PhotoImage(file=IMAGE_PATH)

                img_label = tk.Label(
                    left_panel, image=self.ta_png, bg="#1e1e24"
                )
                img_label.place(relx=0.5, rely=0.5, anchor="center")
            except Exception as e:
                self.show_error(
                    left_panel, f"Error loading PNG:\n{e}\n\nUse a valid PNG!"
                )
        else:
            self.show_error(
                left_panel,
                f"Image file not found:\n'{IMAGE_PATH}'\n\nPlace PNG in same folder.",
            )

        # ---------------- RIGHT SIDE CANVAS ----------------
        right_panel = tk.Frame(self, bg="#ffffff")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=30, pady=20)

        title_label = tk.Label(
            right_panel,
            text="The TA",
            font=("Comic Sans MS", 38, "bold"),
            bg="#ffffff",
            fg="#111111",
        )
        title_label.pack(anchor="nw", pady=(10, 0))

        subtitle_label = tk.Label(
            right_panel,
            text="Choose your backseater!",
            font=("Comic Sans MS", 14),
            bg="#ffffff",
            fg="#555555",
        )
        subtitle_label.pack(anchor="nw", pady=(0, 20))

        ta_options = [
            ("The Termtestinator", "The Termtestinator"),
            ("Mr. President", "Mr. President"),
            ("The Torontonian", "The Torontonian"),
            ("John Resident", "John Resident"),
        ]

        for text, choice in ta_options:
            btn = tk.Button(
                right_panel,
                text=text,
                font=("Arial", 11, "bold"),
                bg="#f0f0f0",
                fg="#222222",
                activebackground="#007acc",
                activeforeground="#ffffff",
                relief="groove",
                bd=2,
                pady=8,
                command=lambda c=choice: self.select_ta(c),
            )
            btn.pack(fill="x", pady=6)

        bottom_frame = tk.Frame(right_panel, bg="#ffffff")
        bottom_frame.pack(fill="x", side="bottom", pady=(20, 10))

        btn_manual = tk.Button(
            bottom_frame,
            text="Instruction Manual",
            font=("Arial", 9, "bold"),
            bg="#e1e1e1",
            relief="flat",
            padx=10,
            pady=5,
            command=self.open_manual,
        )
        btn_manual.pack(side="left", padx=(0, 5))

        btn_rules = tk.Button(
            bottom_frame,
            text="Program Description",
            font=("Arial", 9, "bold"),
            bg="#e1e1e1",
            relief="flat",
            padx=10,
            pady=5,
            command=self.open_rules,
        )
        btn_rules.pack(side="left")

        version_label = tk.Label(
            bottom_frame,
            text="Version 1984",
            font=("Comic Sans MS", 10, "bold"),
            bg="#ffffff",
            fg="#333333",
        )
        version_label.pack(side="right")

    def show_error(self, parent_frame, text):
        err_label = tk.Label(
            parent_frame,
            text=text,
            font=("Arial", 10),
            fg="#ff5555",
            bg="#1e1e24",
            justify="center",
        )
        err_label.place(relx=0.5, rely=0.5, anchor="center")

    def select_ta(self, choice):
        self.controller.current_ta.set(choice)
        self.controller.show_frame("AppScreen")

    def open_manual(self):
        messagebox.showinfo(
            "Instruction Manual",
            "1. Select your desired TA personality.\nGet to work! If the TA detects you getting distracted, they’ll give you a warning.\nIf you want a break, just tell the TA you want a break.",
        )

    def open_rules(self):
        messagebox.showinfo(
            "Program Description",
            "The Problem: With the ever-degrading attention span of our society, students are having a hard time staying focused on their work. Have you ever sat in front of your laptop for an entire day to work, only to realize at the end of the day, you were mostly staring at your phone?\n\nThe Solution: This program mimics a TA, or supervisor, that monitors you as you work. If it detects that you are distracted (e.g., looking at your phone, falling asleep, etc.), the program will bark at you to focus and get back to work. The program does so by periodically taking and sending a photo of you to Gemini, which determines instances of non-focus, and gives an appropriate response based on what it determines your distraction to be.",
        )


class AppScreen(tk.Frame):

    def __init__(self, parent, controller):
        super().__init__(parent, bg="#18181b")
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top_bar = tk.Frame(self, bg="#27272a", height=50)
        top_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 0))

        self.info_label = tk.Label(
            top_bar,
            text="",
            font=("Arial", 12, "bold"),
            bg="#27272a",
            fg="#ffffff",
        )
        self.info_label.pack(side="left", padx=15, pady=10)

        btn_back = tk.Button(
            top_bar,
            text="← Change TA",
            font=("Arial", 9, "bold"),
            bg="#3f3f46",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=4,
            command=lambda: self.controller.show_frame("TitleScreen"),
        )
        btn_back.pack(side="right", padx=15)

        self.canvas = tk.Canvas(self, bg="#09090b", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)

    def on_show(self):
        active_ta = self.controller.current_ta.get()
        self.info_label.config(text=f"Active Backseater: {active_ta}")
        self.draw_ta_graphic(active_ta)

    def draw_ta_graphic(self, ta_name):
        self.canvas.delete("all")
        self.update_idletasks()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w <= 1 or h <= 1:
            return

        if ta_name == "The Termtestinator":
            self.canvas.create_rectangle(
                w // 2 - 100,
                h // 2 - 80,
                w // 2 + 100,
                h // 2 + 80,
                fill="#7f1d1d",
                outline="#ef4444",
                width=3,
            )
            self.canvas.create_text(
                w // 2,
                h // 2 - 20,
                text="[ STRICT MODE ACTIVE ]",
                fill="#ffffff",
                font=("Courier", 14, "bold"),
            )
            self.canvas.create_text(
                w // 2,
                h // 2 + 20,
                text="'-5 points for missing semicolon'",
                fill="#fca5a5",
                font=("Arial", 10, "italic"),
            )

        elif ta_name == "Mr. President":
            self.canvas.create_oval(
                w // 2 - 90,
                h // 2 - 90,
                w // 2 + 90,
                h // 2 + 90,
                fill="#065f46",
                outline="#10b981",
                width=3,
            )
            self.canvas.create_text(
                w // 2,
                h // 2 - 10,
                text="[ CHILL MODE ]",
                fill="#ffffff",
                font=("Arial", 14, "bold"),
            )
            self.canvas.create_text(
                w // 2,
                h // 2 + 20,
                text="'Looking good, take a coffee break.'",
                fill="#a7f3d0",
                font=("Arial", 10),
            )

        elif ta_name == "The Torontonian":
            self.canvas.create_rectangle(
                w // 2 - 120,
                h // 2 - 60,
                w // 2 + 120,
                h // 2 + 60,
                fill="#1e293b",
                outline="#64748b",
                width=2,
            )
            self.canvas.create_text(
                w // 2,
                h // 2,
                text="... (Watching you code) ...",
                fill="#94a3b8",
                font=("Georgia", 13, "italic"),
            )

        elif ta_name == "John Resident":
            self.canvas.create_polygon(
                w // 2,
                h // 2 - 100,
                w // 2 + 100,
                h // 2 + 80,
                w // 2 - 100,
                h // 2 + 80,
                fill="#581c87",
                outline="#c084fc",
                width=3,
            )
            self.canvas.create_text(
                w // 2,
                h // 2 + 10,
                text="⚠️ CHAOS MODE ⚠️",
                fill="#ffffff",
                font=("Impact", 16),
            )


if __name__ == "__main__":
    app = TheTAApp()
    app.mainloop()