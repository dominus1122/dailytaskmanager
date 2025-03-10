import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog, scrolledtext
from tkcalendar import DateEntry
from datetime import datetime, timedelta
import json
import os
import logging
import traceback
import threading
import time
import platform
import subprocess
from tkinter import font
from tkinter import VERTICAL, HORIZONTAL
from ttkthemes import ThemedTk
from tkinter import StringVar
from ttkthemes import THEMES
from tkinter import PhotoImage
import copy  # Import the copy module


try:
    from plyer import notification
except ImportError:
    print("Plyer not installed. Notifications will not be available.")

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename='task_manager.log',
                    filemode='w')  # Overwrite log file each run


class ConfigManager:
    def __init__(self):
        self.config_file = "app_config.json"
        self.default_config = {
            "theme": "plastik",  # Default theme
            "last_window_size": "1024x768",
            "last_window_position": None
        }
        self.config = self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            return self.default_config.copy()
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.default_config.copy()

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_setting(self, key):
        return self.config.get(key, self.default_config.get(key))

    def set_setting(self, key, value):
        self.config[key] = value
        self.save_config()

class Task:
    def __init__(self, title, description, priority, due_date, completed=False, category="General", reminders=None, notes=""):
        self.title = title
        self.description = description
        self.priority = priority
        self.due_date = due_date
        self.completed = completed
        self.category = category
        self.reminders = reminders if reminders is not None else []  # List of reminder datetimes
        self.notes = notes

    def to_dict(self):
        return {
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'due_date': self.due_date,
            'completed': self.completed,
            'category': self.category,
            'reminders': [r.isoformat() for r in self.reminders],  # Store reminders as ISO format strings
            'notes': self.notes
        }

    @staticmethod
    def from_dict(data):
        reminders = [datetime.fromisoformat(r) for r in data.get('reminders', [])] # Parse ISO format strings back to datetime
        return Task(
            data['title'],
            data['description'],
            data['priority'],
            data['due_date'],
            data['completed'],
            data.get('category', "General"),
            reminders,
            data.get('notes', "")
        )

class Action:
    def __init__(self, action_type, task_index, old_state, new_state):
        self.action_type = action_type
        self.task_index = task_index
        self.old_state = old_state
        self.new_state = new_state

class DailyTaskManager:
    def __init__(self, root):
        self.root = root
        self.config_manager = ConfigManager() #Initialize configuration
        self.root.title("Daily Task Manager")

        # Initial style configuration
        style = ttk.Style()
        style.configure(".", font=('Arial', 10))  # Set default font
        style.configure("Treeview", rowheight=25)  # Consistent row height
        style.configure("TButton", padding=6)      # Consistent button padding

        #load save window size or use default
        window_size = self.config_manager.get_setting("last_window_size")
        self.root.geometry(window_size)
        self.root.minsize(800, 600)

        self.tasks = []
        self.task_file = "tasks.json"

        # Undo/Redo Stack
        self.undo_stack = []
        self.redo_stack = []

        # Load Tasks before defining GUI elements
        self.load_tasks()

        # Initialize Status Bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Define Icons
        self.icons = {
            "add": self.load_icon("add.png"),
            "edit": self.load_icon("edit.png"),
            "delete": self.load_icon("delete.png"),
            "reminder": self.load_icon("reminder.png"),
            "clear": self.load_icon("clear.png"),
            "completed": self.load_icon("completed.png"),
            "pending": self.load_icon("pending.png"),
            "search": self.load_icon("search.png"),
            "reset": self.load_icon("reset.png"),
            "backup": self.load_icon("backup.png"),
            "undo": self.load_icon("undo.png"),
            "redo": self.load_icon("redo.png"),
            "duplicate": self.load_icon("duplicate.png"),
            "userguide": self.load_icon("userguide.png"),
            "feedback": self.load_icon("feedback.png"),
            "fileopen": self.load_icon("fileopen.png"),
            "filter": self.load_icon("filter.png"),
            "save": self.load_icon("save.png")
        }

        self.create_widgets()
        self.setup_bindings()
        self.update_task_list()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)  # Handle window close
        self.reminder_thread = threading.Thread(target=self.check_reminders, daemon=True)  # Daemon thread
        self.reminder_thread.start()

        # Initial Theme Setup
        # self.set_theme("darkly") # moved theme setting to main function

    def load_icon(self, filename):
        try:
            filepath = os.path.join("icons", filename)
            return PhotoImage(file=filepath)
        except tk.TclError as e:
            logging.error(f"Error loading icon {filename}: {e}")
            return None
        
    def reset_to_default_theme(self):
        """Reset the theme to default plastik theme"""
        self.set_theme("plastik")
        self.config_manager.set_setting("theme", "plastik")

    def update_widget_styles(self):
        """Update widget styles based on current theme"""
        style = ttk.Style()
        
        # Determine if current theme is dark
        is_dark_theme = self.current_theme in ["equilux", "black"]
        
        # Configure main frame padding
        style.configure("TFrame", padding=5)
        
        # Configure labels
        style.configure("TLabel",
            padding=2,
            font=('Arial', 10)
        )
        
        # Configure buttons
        style.configure("TButton",
            padding=6,
            width=8
        )
        
        # Configure entry fields
        style.configure("TEntry",
            padding=5,
            fieldbackground="white" if not is_dark_theme else "#2d2d2d"
        )
        
        # Configure combobox
        style.configure("TCombobox",
            padding=5,
            fieldbackground="white" if not is_dark_theme else "#2d2d2d"
        )
        
        # Update scrollbar style
        style.configure("Vertical.TScrollbar",
            background="#404040" if is_dark_theme else "#f0f0f0",
            troughcolor="#2d2d2d" if is_dark_theme else "white"
        )

    def maintain_widget_layout(self):
        """Maintain consistent widget layout across themes"""
        # Configure grid weights
        self.basic_info_frame.grid_columnconfigure(1, weight=1)
        self.advanced_options_frame.grid_columnconfigure(1, weight=1)
        
        # Update padding for all frames
        for frame in [self.basic_info_frame, self.advanced_options_frame, 
                    self.button_frame, self.search_frame]:
            frame.configure(padding="10")

        # Ensure consistent spacing between widgets
        for widget in self.basic_info_frame.winfo_children():
            widget.grid_configure(padx=5, pady=5)
        
        for widget in self.advanced_options_frame.winfo_children():
            widget.grid_configure(padx=5, pady=5)

    def create_widgets(self):
        # --- Main PanedWindow ---
        self.main_paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Left Panel: Task List ---
        self.left_frame = ttk.Frame(self.main_paned_window)

        # Search Bar
        self.search_var = tk.StringVar()
        self.search_frame = ttk.Frame(self.left_frame)
        self.search_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.search_entry = ttk.Entry(self.search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self.filter_tasks)

        if self.icons["search"]:
            self.search_button = ttk.Button(self.search_frame, image=self.icons["search"], command=lambda: self.filter_tasks(), width=2)
        else:
            self.search_button = ttk.Button(self.search_frame, text="Search", command=lambda: self.filter_tasks(), width=2)
        self.search_button.pack(side=tk.LEFT, padx=2)

        # Filter Button
        if self.icons["filter"]:
            self.filter_button = ttk.Button(self.search_frame, image=self.icons["filter"], command=self.show_filter_panel, width=2)
        else:
            self.filter_button = ttk.Button(self.search_frame, text="Filters", command=self.show_filter_panel)
        self.filter_button.pack(side=tk.LEFT, padx=2)

        # Task Treeview
        self.task_tree = ttk.Treeview(self.left_frame, columns=("Status", "Title", "Priority", "Due Date", "Category"), show="headings", selectmode="extended")
        self.task_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Define Columns
        self.task_tree.heading("Status", text="Status")
        self.task_tree.heading("Title", text="Title")
        self.task_tree.heading("Priority", text="Priority")
        self.task_tree.heading("Due Date", text="Due Date")
        self.task_tree.heading("Category", text="Category")

        # Column Widths and Alignment
        self.task_tree.column("Status", width=50, anchor="center")
        self.task_tree.column("Title", width=200)
        self.task_tree.column("Priority", width=80, anchor="center")
        self.task_tree.column("Due Date", width=100, anchor="center")
        self.task_tree.column("Category", width=120)

        # Scrollbar for Task Treeview
        self.tree_scrollbar = ttk.Scrollbar(self.left_frame, orient=VERTICAL, command=self.task_tree.yview)
        self.tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.task_tree.configure(yscrollcommand=self.tree_scrollbar.set)

        self.main_paned_window.add(self.left_frame, weight=1)

        # --- Right Panel: Task Details ---
        self.right_frame = ttk.Frame(self.main_paned_window)

        # --- Form Layout with Collapsible Sections ---
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Basic Info Section
        self.basic_info_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.basic_info_frame, text="Basic Info")

        ttk.Label(self.basic_info_frame, text="Title:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.title_entry = ttk.Entry(self.basic_info_frame, width=40, foreground='gray')
        self.title_entry.insert(0, "Enter task title here")
        self.title_entry.bind("<FocusIn>", lambda event: self.clear_placeholder(self.title_entry, "Enter task title here"))
        self.title_entry.bind("<FocusOut>", lambda event: self.restore_placeholder(self.title_entry, "Enter task title here"))
        self.title_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)

        ttk.Label(self.basic_info_frame, text="Description:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.NW, padx=5, pady=2)
        self.desc_text = scrolledtext.ScrolledText(self.basic_info_frame, width=35, height=5, wrap=tk.WORD, foreground='gray')
        self.desc_text.insert("1.0", "Enter task description here")
        self.desc_text.bind("<FocusIn>", lambda event: self.clear_placeholder(self.desc_text, "Enter task description here"))
        self.desc_text.bind("<FocusOut>", lambda event: self.restore_placeholder(self.desc_text, "Enter task description here"))
        self.desc_text.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)

        ttk.Label(self.basic_info_frame, text="Priority:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.priority_combo = ttk.Combobox(self.basic_info_frame, values=["High", "Medium", "Low"], state="readonly")
        self.priority_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(self.basic_info_frame, text="Due Date:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.due_date = DateEntry(self.basic_info_frame, width=20, date_pattern='yyyy-mm-dd')
        self.due_date.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        # Advanced Options Section
        self.advanced_options_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.advanced_options_frame, text="Advanced Options")

        ttk.Label(self.advanced_options_frame, text="Category:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.category_entry = ttk.Entry(self.advanced_options_frame, width=40)
        self.category_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)

        self.completed_var = tk.BooleanVar()
        self.completed_check = ttk.Checkbutton(self.advanced_options_frame, text="Completed", variable=self.completed_var)
        self.completed_check.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(self.advanced_options_frame, text="Notes:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.NW, padx=5, pady=2)
        self.notes_text = scrolledtext.ScrolledText(self.advanced_options_frame, width=35, height=5, wrap=tk.WORD)
        self.notes_text.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)

        # Buttons Frame
        self.button_frame = ttk.Frame(self.right_frame)
        self.button_frame.pack(side=tk.TOP, fill=tk.X, pady=10)

        button_params = {'side': tk.LEFT, 'padx': 5}
        if self.icons["add"]:
            self.add_button = ttk.Button(self.button_frame, image=self.icons["add"], command=self.add_task, width=2)
        else:
            self.add_button = ttk.Button(self.button_frame, text="Add Task", command=self.add_task)
        self.add_button.pack(**button_params)

        if self.icons["edit"]:
            self.edit_button = ttk.Button(self.button_frame, image=self.icons["edit"], command=self.edit_task, width=2)
        else:
            self.edit_button = ttk.Button(self.button_frame, text="Edit Task", command=self.edit_task)
        self.edit_button.pack(**button_params)

        if self.icons["delete"]:
            self.delete_button = ttk.Button(self.button_frame, image=self.icons["delete"], command=self.delete_task, width=2)
        else:
            self.delete_button = ttk.Button(self.button_frame, text="Delete Task", command=self.delete_task)
        self.delete_button.pack(**button_params)

        if self.icons["reminder"]:
            self.reminder_button = ttk.Button(self.button_frame, image=self.icons["reminder"], command=self.add_reminder, width=2)
        else:
            self.reminder_button = ttk.Button(self.button_frame, text="Add Reminder", command=self.add_reminder)
        self.reminder_button.pack(**button_params)

        if self.icons["clear"]:
            self.clear_button = ttk.Button(self.button_frame, image=self.icons["clear"], command=self.clear_completed_tasks, width=2)
        else:
            self.clear_button = ttk.Button(self.button_frame, text="Clear Completed", command=self.clear_completed_tasks)
        self.clear_button.pack(**button_params)

        if self.icons["save"]:
            self.save_button = ttk.Button(self.button_frame, image=self.icons["save"], command=self.save_tasks, width=2)
        else:
            self.save_button = ttk.Button(self.button_frame, text="Save", command=self.save_tasks)
        self.save_button.pack(**button_params)

        self.main_paned_window.add(self.right_frame, weight=1)

        # --- Menu Bar ---
        self.menu_bar = tk.Menu(self.root)

        # File Menu
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_menu.add_command(label="Import Tasks", command=self.import_tasks, accelerator="Ctrl+I")
        self.file_menu.add_command(label="Export Tasks", command=self.export_tasks, accelerator="Ctrl+E")
        self.file_menu.add_separator()
        if self.icons["fileopen"]:
            self.file_menu.add_command(label="Open Task File", command=self.open_task_file, image=self.icons["fileopen"], compound=tk.LEFT)
        else:
            self.file_menu.add_command(label="Open Task File", command=self.open_task_file)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.on_close, accelerator="Ctrl+Q")
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)

        # Edit Menu
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        if self.icons["undo"]:
            self.edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z", image=self.icons["undo"], compound=tk.LEFT)
        else:
            self.edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        if self.icons["redo"]:
            self.edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y", image=self.icons["redo"], compound=tk.LEFT)
        else:
            self.edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        self.edit_menu.add_separator()
        if self.icons["duplicate"]:
            self.edit_menu.add_command(label="Duplicate Task", command=self.duplicate_task, image=self.icons["duplicate"], compound=tk.LEFT)
        else:
            self.edit_menu.add_command(label="Duplicate Task", command=self.duplicate_task)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Select All", command=self.select_all_tasks, accelerator="Ctrl+A")
        self.menu_bar.add_cascade(label="Edit", menu=self.edit_menu)

        # View Menu
        self.view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.view_menu.add_command(label="Show Filters", command=self.show_filter_panel)
        self.menu_bar.add_cascade(label="View", menu=self.view_menu)

        # Theme Menu
        self.theme_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.theme_menu.add_command(label="Default", command=lambda: self.set_theme("plastik"))  # Add Default option
        self.theme_menu.add_command(label="Dark", command=lambda: self.set_theme("darkly"))
        self.theme_menu.add_command(label="Light", command=lambda: self.set_theme("clam"))
        self.menu_bar.add_cascade(label="Theme", menu=self.theme_menu)

        # Help Menu
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        if self.icons["userguide"]:
            self.help_menu.add_command(label="User Guide", command=self.show_user_guide, image=self.icons["userguide"], compound=tk.LEFT)
        else:
            self.help_menu.add_command(label="User Guide", command=self.show_user_guide)
        if self.icons["feedback"]:
            self.help_menu.add_command(label="Feedback", command=self.show_feedback_form, image=self.icons["feedback"], compound=tk.LEFT)
        else:
            self.help_menu.add_command(label="Feedback", command=self.show_feedback_form)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="About", command=self.show_about)
        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)

        self.root.config(menu=self.menu_bar)

        # --- Filters Section (Floating Panel) ---
        self.filter_panel = tk.Toplevel(self.root)
        self.filter_panel.title("Filters")
        self.filter_panel.geometry("300x200")
        self.filter_panel.protocol("WM_DELETE_WINDOW", self.hide_filter_panel)
        self.filter_panel.withdraw()  # Hide initially

        filter_frame = ttk.Frame(self.filter_panel)
        filter_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Label(filter_frame, text="Priority:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.filter_priority = ttk.Combobox(filter_frame, values=["All", "High", "Medium", "Low"], state="readonly")
        self.filter_priority.set("All")
        self.filter_priority.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)

        ttk.Label(filter_frame, text="Status:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.filter_completed_var = tk.StringVar(value="All")
        ttk.Radiobutton(filter_frame, text="All", variable=self.filter_completed_var,
                       value="All", command=self.filter_tasks).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Radiobutton(filter_frame, text="Completed", variable=self.filter_completed_var,
                       value="Completed", command=self.filter_tasks).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Radiobutton(filter_frame, text="Not Completed", variable=self.filter_completed_var,
                       value="Not Completed", command=self.filter_tasks).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(filter_frame, text="Category:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.filter_category = ttk.Entry(filter_frame, width=20)
        self.filter_category.grid(row=4, column=1, sticky=tk.EW, padx=5, pady=2)
        self.filter_category.bind("<KeyRelease>", self.filter_tasks)

        if self.icons["reset"]:
            self.reset_filter_button = ttk.Button(filter_frame, image=self.icons["reset"], command=self.reset_filters, width=2)
        else:
            self.reset_filter_button = ttk.Button(filter_frame, text="Reset Filters", command=self.reset_filters)
        self.reset_filter_button.grid(row=5, column=1, sticky=tk.E, padx=5, pady=5)

        # Bind Ctrl+I, Ctrl+E, Ctrl+Q
        self.root.bind("<Control-i>", self.import_tasks)
        self.root.bind("<Control-e>", self.export_tasks)
        self.root.bind("<Control-q>", self.on_close)

        # Bind Ctrl+Z, Ctrl+Y
        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)

        # Bind Ctrl+A
        self.root.bind("<Control-a>", self.select_all_tasks)

        # --- Initial Focus ---
        self.title_entry.focus_set()

    def setup_bindings(self):
        self.task_tree.bind('<<TreeviewSelect>>', self.on_select_task)
        self.filter_priority.bind("<<ComboboxSelected>>", self.filter_tasks)

    def add_task(self):
        try:
            title = self.title_entry.get().strip()
            if not title or title == "Enter task title here":
                messagebox.showerror("Error", "Title is required!")
                return

            description = self.desc_text.get("1.0", tk.END).strip()
            if description == "Enter task description here":
                description = ""

            priority = self.priority_combo.get()
            due_date = self.due_date.get_date().strftime("%Y-%m-%d")
            completed = self.completed_var.get()
            category = self.category_entry.get().strip()
            notes = self.notes_text.get("1.0", tk.END).strip()

            task = Task(title, description, priority, due_date, completed, category, notes=notes)
            self.tasks.append(task)

            # Record Action for Undo/Redo
            action = Action("add", len(self.tasks) - 1, None, copy.deepcopy(task.to_dict()))
            self.record_action(action)

            self.save_tasks()
            self.update_task_list()
            self.clear_fields()
            logging.info(f"Task added: {title}")
            self.update_status_bar("Task added successfully.", "green")

        except Exception as e:
            logging.error(f"Error adding task: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"An error occurred while adding the task: {e}")
            self.update_status_bar(f"Error adding task: {e}", "red")

    def edit_task(self):
        try:
            selected_items = self.task_tree.selection()
            if not selected_items:
                messagebox.showwarning("Warning", "Please select a task to edit!")
                return

            if len(selected_items) > 1:
                messagebox.showwarning("Warning", "Please select only one task to edit!")
                return

            selected_item = selected_items[0]
            index = int(self.task_tree.item(selected_item, 'text')) - 1

            title = self.title_entry.get().strip()
            if not title or title == "Enter task title here":
                messagebox.showerror("Error", "Title is required!")
                return

            description = self.desc_text.get("1.0", tk.END).strip()
            if description == "Enter task description here":
                description = ""

            priority = self.priority_combo.get()
            due_date = self.due_date.get_date().strftime("%Y-%m-%d")
            completed = self.completed_var.get()
            category = self.category_entry.get().strip()
            notes = self.notes_text.get("1.0", tk.END).strip()

            # Record Action for Undo/Redo
            old_state = copy.deepcopy(self.tasks[index].to_dict())

            self.tasks[index] = Task(title, description, priority, due_date, completed, category, self.tasks[index].reminders, notes)  # Keep existing reminders
            new_state = copy.deepcopy(self.tasks[index].to_dict())

            action = Action("edit", index, old_state, new_state)
            self.record_action(action)

            self.save_tasks()
            self.update_task_list()
            self.clear_fields()
            logging.info(f"Task edited: {title}")
            self.update_status_bar("Task edited successfully.", "green")

        except Exception as e:
            logging.error(f"Error editing task: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"An error occurred while editing the task: {e}")
            self.update_status_bar(f"Error editing task: {e}", "red")

    def delete_task(self):
        try:
            selected_items = self.task_tree.selection()
            if not selected_items:
                messagebox.showwarning("Warning", "Please select a task to delete!")
                return

            if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete the selected task(s)?"):
                # Sort selected items in reverse order to delete from the end
                selected_indices = sorted([int(self.task_tree.item(item, 'text')) - 1 for item in selected_items], reverse=True)

                for index in selected_indices:
                    # Record Action for Undo/Redo
                    deleted_task = self.tasks[index]
                    action = Action("delete", index, copy.deepcopy(deleted_task.to_dict()), None)
                    self.record_action(action)

                    deleted_task_title = self.tasks[index].title
                    del self.tasks[index]
                    logging.info(f"Task deleted: {deleted_task_title}")

                self.save_tasks()
                self.update_task_list()
                self.clear_fields()
                self.update_status_bar("Tasks deleted successfully.", "green")

        except Exception as e:
            logging.error(f"Error deleting task: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"An error occurred while deleting the task: {e}")
            self.update_status_bar(f"Error deleting task: {e}", "red")

    def on_select_task(self, event):
        try:
            selected_items = self.task_tree.selection()
            if not selected_items:
                return

            selected_item = selected_items[0]
            index = int(self.task_tree.item(selected_item, 'text')) - 1
            task = self.tasks[index]

            self.clear_fields()
            self.title_entry.insert(0, task.title)
            self.desc_text.insert("1.0", task.description)
            self.priority_combo.set(task.priority)
            self.due_date.set_date(datetime.strptime(task.due_date, "%Y-%m-%d"))
            self.completed_var.set(task.completed)
            self.category_entry.insert(0, task.category)
            self.notes_text.insert("1.0", task.notes)
            self.update_status_bar("Task selected.", "blue")

        except Exception as e:
            logging.error(f"Error selecting task: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"An error occurred while selecting the task: {e}")
            self.update_status_bar(f"Error selecting task: {e}", "red")

    def filter_tasks(self, event=None):
        self.update_task_list()

    def update_task_list(self):
        try:
            # Clear the treeview
            for item in self.task_tree.get_children():
                self.task_tree.delete(item)

            priority_filter = self.filter_priority.get()
            completed_filter = self.filter_completed_var.get()
            category_filter = self.filter_category.get().strip().lower()
            search_term = self.search_var.get().strip().lower()

            for i, task in enumerate(self.tasks, start=1):
                if priority_filter != "All" and task.priority != priority_filter:
                    continue

                if completed_filter == "Completed" and not task.completed:
                    continue
                elif completed_filter == "Not Completed" and task.completed:
                    continue

                if category_filter and category_filter not in task.category.lower():
                    continue

                if search_term and search_term not in task.title.lower() and search_term not in task.category.lower() and search_term not in task.description.lower() and search_term not in task.notes.lower():
                    continue

                status_icon = self.icons["completed"] if task.completed else self.icons["pending"]
                status = "✓" if task.completed else " "
                self.task_tree.insert("", tk.END, text=str(i), values=(status, task.title, task.priority, task.due_date, task.category), image=status_icon)

            self.update_status_bar("Task list updated.", "blue")

        except Exception as e:
            logging.error(f"Error updating task list: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"An error occurred while updating the task list: {e}")
            self.update_status_bar(f"Error updating task list: {e}", "red")

    def clear_fields(self):
        self.title_entry.delete(0, tk.END)
        self.desc_text.delete("1.0", tk.END)
        self.priority_combo.set("")
        self.due_date.set_date(datetime.now())
        self.completed_var.set(False)
        self.category_entry.delete(0, tk.END)
        self.notes_text.delete("1.0", tk.END)

        # Restore placeholders
        self.restore_placeholder(self.desc_text, "Enter task description here")

        self.update_status_bar("Fields cleared.", "blue")

    def clear_placeholder(self, widget, placeholder):
        if isinstance(widget, ttk.Entry):
            if widget.get() == placeholder:
                widget.delete(0, tk.END)
                widget.config(foreground='black')
        elif isinstance(widget, scrolledtext.ScrolledText):
            if widget.get("1.0", tk.END).strip() == placeholder:
                widget.delete("1.0", tk.END)
                widget.config(foreground='black')

    def restore_placeholder(self, widget, placeholder):
        if isinstance(widget, ttk.Entry):
            if not widget.get():
                widget.insert(0, placeholder)
                widget.config(foreground='gray')
        elif isinstance(widget, scrolledtext.ScrolledText):
            if not widget.get("1.0", tk.END).strip():
                widget.insert("1.0", placeholder)
                widget.config(foreground='gray')

    def save_tasks(self):
        try:
            with open(self.task_file, "w") as f:
                json.dump([task.to_dict() for task in self.tasks], f, indent=4) # Added indent for readability
            logging.info("Tasks saved successfully.")
            self.update_status_bar("Tasks saved.", "green")
        except Exception as e:
            logging.error(f"Error saving tasks: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"An error occurred while saving tasks: {e}")
            self.update_status_bar(f"Error saving tasks: {e}", "red")

    def load_tasks(self):
        try:
            if os.path.exists(self.task_file):
                with open(self.task_file, "r") as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(task_data) for task_data in data]
                logging.info("Tasks loaded successfully.")
                self.update_status_bar("Tasks loaded.", "blue")
        except FileNotFoundError:
            self.tasks = []
            logging.info("No task file found. Starting with an empty task list.")
            self.update_status_bar("No task file found. Starting with an empty task list.", "blue")
        except json.JSONDecodeError:
            self.tasks = []
            logging.warning("Task file is corrupt. Starting with an empty task list.")
            messagebox.showerror("Error", "The task file is corrupt. Starting with an empty task list.")
            self.update_status_bar("Task file is corrupt. Starting with an empty task list.", "red")
        except Exception as e:
            logging.error(f"Error loading tasks: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"An error occurred while loading tasks: {e}")
            self.update_status_bar(f"Error loading tasks: {e}", "red")

    def import_tasks(self, event=None):
        try:
            filename = filedialog.askopenfilename(defaultextension=".json",
                                                filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
            if filename:
                with open(filename, "r") as f:
                    data = json.load(f)
                    imported_tasks = [Task.from_dict(task_data) for task_data in data]
                    self.tasks.extend(imported_tasks)
                    self.save_tasks()
                    self.update_task_list()
                logging.info(f"Tasks imported from {filename}")
                self.update_status_bar(f"Tasks imported from {filename}", "green")
        except Exception as e:
            logging.error(f"Error importing tasks: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"An error occurred while importing tasks: {e}")
            self.update_status_bar(f"Error importing tasks: {e}", "red")

    def export_tasks(self, event=None):
        try:
            filename = filedialog.asksaveasfilename(defaultextension=".json",
                                                 filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
            if filename:
                with open(filename, "w") as f:
                    json.dump([task.to_dict() for task in self.tasks], f, indent=4) # Added indent for readability
                logging.info(f"Tasks exported to {filename}")
                self.update_status_bar(f"Tasks exported to {filename}", "green")
        except Exception as e:
            logging.error(f"Error exporting tasks: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"An error occurred while exporting tasks: {e}")
            self.update_status_bar(f"Error exporting tasks: {e}", "red")

    def show_about(self):
        messagebox.showinfo("About Daily Task Manager",
                            "Daily Task Manager\nVersion 1.2\nCreated by dominus1122\n\n"
                            "This application helps you manage your daily tasks effectively.\n"
                            "It allows you to add, edit, delete, and filter tasks.\n"
                            "You can also set reminders for your tasks.")
        self.update_status_bar("About dialog shown.", "blue")

    def show_user_guide(self):
        # Placeholder for user guide functionality
        messagebox.showinfo("User Guide", "User guide content will be available soon.")
        self.update_status_bar("User guide shown.", "blue")

    def show_feedback_form(self):
        # Placeholder for feedback form functionality
        messagebox.showinfo("Feedback", "Feedback form will be available soon.")
        self.update_status_bar("Feedback form shown.", "blue")

    def on_close(self, event=None):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            # Save current window size before closing
            window_size = self.root.geometry().split("+")[0]  # Get size without position
            self.config_manager.set_setting("last_window_size", window_size)
            self.root.destroy()
            logging.info("Application closed.")

    def add_reminder(self):
        selection = self.task_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a task to add a reminder!")
            return

        selected_item = selection[0]
        index = int(self.task_tree.item(selected_item, 'text')) - 1
        task = self.tasks[index]

        def set_reminder():
            reminder_time_str = simpledialog.askstring("Add Reminder", "Enter reminder time (YYYY-MM-DD HH:MM):")
            if reminder_time_str:
                try:
                    reminder_time = datetime.strptime(reminder_time_str, "%Y-%m-%d %H:%M")
                    if reminder_time <= datetime.now():
                         messagebox.showerror("Error", "Reminder time must be in the future.")
                         return
                    task.reminders.append(reminder_time)
                    self.save_tasks()
                    messagebox.showinfo("Reminder Added", f"Reminder set for {reminder_time_str}")
                    logging.info(f"Reminder added for task '{task.title}' at {reminder_time_str}")
                    self.update_status_bar(f"Reminder added for task '{task.title}' at {reminder_time_str}", "green")
                except ValueError:
                    messagebox.showerror("Error", "Invalid date/time format. Please use YYYY-MM-DD HH:MM.")
                    logging.warning("Invalid date/time format entered for reminder.")
                    self.update_status_bar("Invalid date/time format entered for reminder.", "red")
                except Exception as e:
                     logging.error(f"Error adding reminder: {e}\n{traceback.format_exc()}")
                     messagebox.showerror("Error", f"An error occurred while adding reminder: {e}")
                     self.update_status_bar(f"Error adding reminder: {e}", "red")

        threading.Thread(target=set_reminder, daemon=True).start()

    def check_reminders(self):
        while True:
            now = datetime.now()
            for task in self.tasks:
                for reminder in task.reminders[:]:  # Iterate over a copy to allow removal
                    if reminder <= now:
                        self.show_reminder_notification(task)
                        task.reminders.remove(reminder)  # Remove the reminder
                        self.save_tasks()  # Save the updated task list
            time.sleep(60)  # Check every minute

    def show_reminder_notification(self, task):
        def display_notification():
            messagebox.showinfo("Reminder", f"Reminder: {task.title}\n{task.description}")
            try:
                notification.notify(
                    title="Task Reminder",
                    message=f"{task.title}\n{task.description}",
                    app_name="Daily Task Manager",
                    timeout=10
                )
            except NameError:
                messagebox.showinfo("Reminder", f"Reminder: {task.title}\n{task.description}")

        self.root.after(0, display_notification)

    def clear_completed_tasks(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all completed tasks?"):
            # Record Action for Undo/Redo
            old_tasks = copy.deepcopy(self.tasks)
            action = Action("clear_completed", None, old_tasks, None)
            self.record_action(action)

            self.tasks = [task for task in self.tasks if not task.completed]
            self.save_tasks()
            self.update_task_list()
            self.update_status_bar("Completed tasks cleared.", "green")

    def select_all_tasks(self, event=None):
        for item in self.task_tree.get_children():
            self.task_tree.selection_add(item)
        self.update_status_bar("All tasks selected.", "blue")

    def record_action(self, action):
        self.undo_stack.append(action)
        self.redo_stack = []  # Clear redo stack after a new action
        logging.info(f"Action recorded: {action.action_type}")

    def undo(self, event=None):
        if self.undo_stack:
            action = self.undo_stack.pop()
            logging.info(f"Undoing action: {action.action_type}")
            self.redo_stack.append(action)  # Move to redo stack

            if action.action_type == "add":
                del self.tasks[action.task_index]
            elif action.action_type == "edit":
                self.tasks[action.task_index] = Task.from_dict(action.old_state)
            elif action.action_type == "delete":
                # Restore task at its original index
                self.tasks.insert(action.task_index, Task.from_dict(action.old_state))
            elif action.action_type == "clear_completed":
                self.tasks = action.old_state  # Restore the old task list

            self.save_tasks()
            self.update_task_list()
            self.update_status_bar("Undo action.", "blue")
        else:
            messagebox.showinfo("Undo", "Nothing to undo.")
            self.update_status_bar("Nothing to undo.", "blue")

    def redo(self, event=None):
        if self.redo_stack:
            action = self.redo_stack.pop()
            logging.info(f"Redoing action: {action.action_type}")
            self.undo_stack.append(action)  # Move back to undo stack

            if action.action_type == "add":
                self.tasks.append(Task.from_dict(action.new_state))
            elif action.action_type == "edit":
                self.tasks[action.task_index] = Task.from_dict(action.new_state)
            elif action.action_type == "delete":
                del self.tasks[action.task_index]
            elif action.action_type == "clear_completed":
                self.tasks = [task for task in self.tasks if not task.completed]  # Clear completed again

            self.save_tasks()
            self.update_task_list()
            self.update_status_bar("Redo action.", "blue")
        else:
            messagebox.showinfo("Redo", "Nothing to redo.")
            self.update_status_bar("Nothing to redo.", "blue")

    def duplicate_task(self):
        selection = self.task_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a task to duplicate!")
            return

        selected_item = selection[0]
        index = int(self.task_tree.item(selected_item, 'text')) - 1
        task = self.tasks[index]

        # Create a new task with the same attributes
        new_task = Task(
            title=f"{task.title} (copy)",
            description=task.description,
            priority=task.priority,
            due_date=task.due_date,
            completed=task.completed,
            category=task.category,
            reminders=task.reminders[:],  # Copy the reminders list
            notes=task.notes
        )

        self.tasks.append(new_task)

        # Record Action for Undo/Redo
        action = Action("add", len(self.tasks) - 1, None, copy.deepcopy(new_task.to_dict()))
        self.record_action(action)

        self.save_tasks()
        self.update_task_list()
        self.update_status_bar("Task duplicated successfully.", "green")

    def reset_filters(self):
        self.filter_priority.set("All")
        self.filter_completed_var.set("All")
        self.filter_category.delete(0, tk.END)
        self.search_var.set("")
        self.filter_tasks()
        self.update_status_bar("Filters reset.", "blue")

    def hide_filter_panel(self):
        self.filter_panel.withdraw()

    def show_filter_panel(self):
        self.filter_panel.deiconify()

    def update_status_bar(self, message, color="black"):
        if hasattr(self, 'status_bar'):
            self.status_bar.config(text=message, foreground=color)
        else:
            logging.warning(f"Status bar not initialized. Message: {message}")

    def open_task_file(self):
        try:
            if platform.system() == 'Darwin':  # macOS
                subprocess.call(('open', self.task_file))
            elif platform.system() == 'Windows':  # Windows
                os.startfile(self.task_file)
            else:  # linux variants
                subprocess.call(('xdg-open', self.task_file))
        except:
            messagebox.showerror("Error", "Could not open task file. Please check your OS configuration.")

    def set_theme(self, theme):
        try:
            available_themes = THEMES
            
            # Store all widgets that need style update
            widgets_to_update = [
                self.task_tree,
                self.title_entry,
                self.desc_text,
                self.priority_combo,
                self.due_date,
                self.category_entry,
                self.notes_text,
                self.search_entry,
                self.filter_category,
                self.status_bar
            ]
            
            # Apply theme
            if theme == "plastik":  # Handle default theme
                self.root.set_theme("plastik")
                theme = "plastik"
            elif theme == "darkly":  # Handle the darkly theme request
                if "equilux" in available_themes:
                    self.root.set_theme("equilux")
                    theme = "equilux"
                elif "black" in available_themes:
                    self.root.set_theme("black")
                    theme = "black"
                else:
                    raise ValueError("No suitable dark theme available")
            else:
                self.root.set_theme(theme)

            # Update style configuration
            style = ttk.Style()

            # Apply new styles and maintain layout
            self.update_widget_styles()
            self.maintain_widget_layout()

            # Force complete redraw
            self.root.update_idletasks()

            # Configure Treeview colors based on theme
            if theme in ["equilux", "black"]:  # Dark themes
                style.configure("Treeview", 
                    background="#2d2d2d",
                    fieldbackground="#2d2d2d",
                    foreground="white")
                style.configure("Treeview.Heading",
                    background="#3d3d3d",
                    foreground="white")
                
                # Configure Text widgets for dark theme
                text_bg = "#2d2d2d"
                text_fg = "white"
            else:  # Light themes
                style.configure("Treeview",
                    background="white",
                    fieldbackground="white",
                    foreground="black")
                style.configure("Treeview.Heading",
                    background="#f0f0f0",
                    foreground="black")
                
                # Configure Text widgets for light theme
                text_bg = "white"
                text_fg = "black"

            # Update Text widget colors
            for widget in [self.desc_text, self.notes_text]:
                widget.configure(
                    background=text_bg,
                    foreground=text_fg,
                    insertbackground=text_fg  # Cursor color
                )

            # Force redraw of all widgets
            for widget in widgets_to_update:
                widget.update()

            # Update DateEntry widget if theme changed
            if hasattr(self, 'due_date'):
                if theme in ["equilux", "black"]:
                    self.due_date.configure(
                        background="#2d2d2d",
                        foreground="white",
                        selectbackground="#404040"
                    )
                else:
                    self.due_date.configure(
                        background="white",
                        foreground="black",
                        selectbackground="#0078d7"
                    )

            self.current_theme = theme
            self.config_manager.set_setting("theme", theme)
            
            # Force a complete redraw of the main window
            self.root.update_idletasks()
            
            if theme == "plastik":
                messagebox.showinfo("Theme Changed", "Theme has been reset to default (plastik)")
                
        except Exception as e:
            logging.error(f"Error setting theme: {e}")
            messagebox.showerror("Error", f"Could not set theme: {e}")

class Action:
    def __init__(self, action_type, task_index, old_state, new_state):
        self.action_type = action_type
        self.task_index = task_index
        self.old_state = old_state
        self.new_state = new_state

def main():
    root = ThemedTk(theme="plastik")  # Initialize with a safe default theme
    available_themes = THEMES
    print("Available themes:", list(available_themes))
    
    # Create config manager to load saved settings
    config_manager = ConfigManager()
    saved_theme = config_manager.get_setting("theme")
    
    # Try to set the saved theme
    try:
        if saved_theme == "plastik":  # Handle default theme
            root.set_theme("plastik")
        elif saved_theme in available_themes:
            root.set_theme(saved_theme)
        elif saved_theme == "darkly":  # Handle dark theme specifically
            if "equilux" in available_themes:
                root.set_theme("equilux")
            elif "black" in available_themes:
                root.set_theme("black")
            else:
                root.set_theme("plastik")  # Fallback to default
        else:
            root.set_theme("plastik")  # Fallback to default
    except Exception as e:
        print(f"Error setting saved theme '{saved_theme}', falling back to 'plastik': {e}")
        root.set_theme("plastik")

    app = DailyTaskManager(root)
    root.mainloop()

if __name__ == "__main__":
    # Create icons directory if it doesn't exist
    if not os.path.exists("icons"):
        os.makedirs("icons")
    main()