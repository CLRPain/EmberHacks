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

        self.selected_ta = None   # stays None if the window is closed

        TitleScreen(parent=self, controller=self).pack(fill="both", expand=True)

    def choose(self, ta_name):
        self.selected_ta = ta_name
        self.destroy()            # title screen disappears here


def choose_ta():
    """Show the title screen and return the chosen TA name (or None)."""
    app = TheTAApp()
    app.mainloop()
    return app.selected_ta


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
        self.controller.choose(choice)

    def open_manual(self):
        messagebox.showinfo(
            "Instruction Manual",
            "1. Select your desired TA personality.\n2. Get to work! If the TA detects you getting distracted, they’ll give you a warning.\n3. If you want a break, just tell the TA you want a break.",
        )

    def open_rules(self):
        messagebox.showinfo(
            "Program Description",
            "The Problem: With the ever-degrading attention span of our society, students are having a hard time staying focused on their work. Have you ever sat in front of your laptop for an entire day to work, only to realize at the end of the day, you were mostly staring at your phone?\n\nThe Solution: This program mimics a TA, or supervisor, that monitors you as you work. If it detects that you are distracted (e.g., looking at your phone, falling asleep, etc.), the program will bark at you to focus and get back to work. The program does so by periodically taking and sending a photo of you to Gemini, which determines instances of non-focus, and gives an appropriate response based on what it determines your distraction to be.",
        )



if __name__ == "__main__":
    print(choose_ta())