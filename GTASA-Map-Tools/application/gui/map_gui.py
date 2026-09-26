import os
import math
import random

import customtkinter as ctk
import tkinter as tk
import pyperclip
from PIL import Image, ImageTk, ImageDraw

RESOURCES_DIR = "resources"
SA_PATHS_DATA_EXTENDER_DIR = os.path.join(RESOURCES_DIR, "SAPathsDataExtender")
SA_PATHS_DATA_EXTENDER_NAME = "sa-pathsdata-extender.exe"
SA_PATHS_DATA_EXTENDER_PATH = os.path.join(SA_PATHS_DATA_EXTENDER_DIR, SA_PATHS_DATA_EXTENDER_NAME)
SA_PATH_UTILITY_DIR = os.path.join(RESOURCES_DIR, "SAPathUtility")
SA_PATH_UTILITY_NAME = "SAPathUtility.exe"
SA_PATH_UTILITY_PATH = os.path.join(SA_PATHS_DATA_EXTENDER_DIR, SA_PATHS_DATA_EXTENDER_NAME)

FONT_FAMILY = "Segoe UI"
SECTION_PADX = 10
SECTION_PADY = 10
SOURCE_RESOLUTION = 2048  # Resolution used to pre-render the point layers
RESIZE_DEBOUNCE_MS = 150  # Delay after the last resize event before re-rendering
RESIZE_THRESHOLD = 6      # Minimum pixel change that triggers a re-render


class MapGui:
    def __init__(self, root, get_coordinates_func, installed_coordinates, map_size=6000, args=None):
        self.root = root

        self.start_x = 0
        self.start_y = 0
        self.offset_x = 0
        self.offset_y = 0
        self.rotation_angle = 0  # Initialize rotation angle
        self._resize_job = None

        self.get_coordinates_func = get_coordinates_func
        self.installed_coordinates = installed_coordinates

        # Initialize the map size variable
        self.map_size_var = ctk.StringVar(value=str(map_size))
        self.map_size_options = {"6000": "resources/map_6000.png",
                                 "12000": "resources/map_12000.png",
                                 "24000": "resources/map_24000.png",
                                 "48000": "resources/map_48000.png"}

        # Update map_size based on dropdown selection
        self.map_size = int(self.map_size_var.get())
        self.canvas_width = 600
        self.canvas_height = 600
        self.render_size = 600  # Canvas size in pixels
        self.frame_x = 0
        self.frame_y = 0
        self.scale = self.render_size / self.map_size

        self._bg_source_cache = {}
        self._base_bg = None
        self._installed_colors = {}
        self._source_points_image = None
        self._source_installed_image = None

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self._build_layout()

        self.map_coordinates = None
        self.rotation_values = None
        self.fix_command = True
        self.id_command = True
        self.path_sapu_command = False
        self.path_sapde_command = False
        self.remove_grge_command = True
        self.clean_assets_command = True

        # Initialize BooleanVars for checkboxes
        self.fix_invalid_var = ctk.BooleanVar(value=True)
        self.replace_ids_var = ctk.BooleanVar(value=True)
        self.move_paths_sapu_var = ctk.BooleanVar(value=False)
        self.move_paths_sapde_var = ctk.BooleanVar(value=False)
        self.remove_grge_var = ctk.BooleanVar(value=True)
        self.clean_assets_var = ctk.BooleanVar(value=True)

        # Create checkboxes
        self.checkbox_fix_invalid = ctk.CTkCheckBox(self.options_section, text="Fix invalid objects",
                                                    variable=self.fix_invalid_var)
        self.checkbox_fix_invalid.pack(fill="x", pady=2)

        self.checkbox_replace_ids = ctk.CTkCheckBox(self.options_section, text="Replace objects IDs",
                                                    variable=self.replace_ids_var)
        self.checkbox_replace_ids.pack(fill="x", pady=2)

        self.checkbox_move_paths_sapu = ctk.CTkCheckBox(self.options_section, text="Move paths (SA Path Utility)",
                                                        variable=self.move_paths_sapu_var,
                                                        command=self.adapt_gui_to_move_paths)
        self.checkbox_move_paths_sapu.pack(fill="x", pady=2)

        self.checkbox_move_paths_sapde = ctk.CTkCheckBox(self.options_section,
                                                         text="Move paths (SA Paths Data Extender)",
                                                         variable=self.move_paths_sapde_var,
                                                         command=self.adapt_gui_to_move_paths)
        self.checkbox_move_paths_sapde.pack(fill="x", pady=2)

        self.checkbox_remove_grge = ctk.CTkCheckBox(self.options_section, text="Remove new garages",
                                                    variable=self.remove_grge_var)
        self.checkbox_remove_grge.pack(fill="x", pady=2)

        self.checkbox_clean_assets = ctk.CTkCheckBox(self.options_section, text="Clean assets",
                                                     variable=self.clean_assets_var)
        self.checkbox_clean_assets.pack(fill="x", pady=2)

        self.update_move_paths_checkboxes()
        self.adapt_gui_to_move_paths()

        self.create_coordinate_labels()

        self.root.bind_all('<F2>', self.copy_coordinates_to_clipboard)

        self._load_background_image_source()
        self._draw_point_sources()
        self._render_frame()

        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        self.canvas.bind("<MouseWheel>", self.adjust_rotation)  # Bind mouse wheel event

        # Bind mouse motion event to update coordinates display
        self.canvas.bind("<Motion>", self.update_mouse_coordinates)

        # Re-render the map whenever the canvas changes size
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # Initialize values from command line arguments
        if args:
            if args.map:
                self.entry_x.insert(0, f"{args.map[0]:.2f}")
                self.entry_y.insert(0, f"{args.map[1]:.2f}")
                self.entry_z.insert(0, f"{args.map[2]:.2f}")

            if args.rot:
                self.entry_qx.insert(0, f"{args.rot[0]:.2f}")
                self.entry_qy.insert(0, f"{args.rot[1]:.2f}")
                self.entry_qz.insert(0, f"{args.rot[2]:.2f}")
                self.entry_qw.insert(0, f"{args.rot[3]:.2f}")

        # Open maximized by default
        self.root.update_idletasks()
        self.root.after(10, self._maximize_window)
        self.root.bind("<Map>", self._on_window_map)

    def _maximize_window(self):
        try:
            self.root.state("zoomed")
        except tk.TclError:
            try:
                self.root.attributes("-zoomed", True)
            except tk.TclError:
                self.root.geometry("1280x840")

    def _on_window_map(self, event):
        if event.widget is self.root:
            self.root.after(10, self._maximize_window)
            self.root.unbind("<Map>")

    # Layout
    def _build_layout(self):
        self.root.title("GTA San Andreas Map Tools")

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)

        # Header
        self.header = ctk.CTkFrame(self.root, fg_color=("gray87", "gray17"), corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(self.header, text="GTA San Andreas Map Tools",
                             font=(FONT_FAMILY, 20, "bold"), anchor="w")
        title.grid(row=0, column=0, padx=(18, 10), pady=(13, 6))

        subtitle = ctk.CTkLabel(self.header, text="Position the map mod in your location of preference.",
                                text_color=("gray25", "gray65"))
        subtitle.grid(row=1, column=0, columnspan=2, sticky="w", padx=(18, 10), pady=(0, 12))

        # Main content
        self.content = ctk.CTkFrame(self.root, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=14, pady=(10, 14))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_columnconfigure(1, weight=0)
        self.content.grid_rowconfigure(0, weight=1)

        # Map card
        self.canvas_card = ctk.CTkFrame(self.content, corner_radius=14)
        self.canvas_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.canvas_card.grid_columnconfigure(0, weight=1)
        self.canvas_card.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.canvas_card, width=self.canvas_width, height=self.canvas_height,
                                bg="#141414", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 4))

        self.status_bar = ctk.CTkFrame(self.canvas_card, fg_color="transparent")
        self.status_bar.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        self.status_bar.grid_columnconfigure(1, weight=1)

        self.mouse_coordinates_label = ctk.CTkLabel(self.status_bar, text="X: 0.00  Y: 0.00",
                                                    anchor="w")
        self.mouse_coordinates_label.grid(row=0, column=0, sticky="w")

        self.hint_label = ctk.CTkLabel(self.status_bar,
                                       text="Drag to move  |  Scroll to rotate  |  F2: copy coords",
                                       text_color=("gray30", "gray60"))
        self.hint_label.grid(row=0, column=2, sticky="e")

        # Sidebar
        self.sidebar = ctk.CTkScrollableFrame(self.content, width=310, corner_radius=14)
        self.sidebar.grid(row=0, column=1, sticky="ns", padx=(12, 0))

        self._build_map_section()
        self._build_offset_section()
        self._build_rotation_section()
        self._build_options_section()
        self._build_actions_section()

    def _add_section(self, title_text):
        section = ctk.CTkFrame(self.sidebar, corner_radius=10, border_width=1,
                               border_color=("gray75", "gray25"))
        section.pack(fill="x", pady=(0, 10))

        heading = ctk.CTkLabel(section, text=title_text,
                               font=(FONT_FAMILY, 11, "bold"),
                               text_color=("gray25", "gray70"))
        heading.pack(anchor="w", padx=SECTION_PADX, pady=(8, 4))

        return section

    def _build_map_section(self):
        self.map_section = self._add_section("MAP")

        self.map_size_dropdown = ctk.CTkOptionMenu(self.map_section,
                                                   values=list(self.map_size_options.keys()),
                                                   variable=self.map_size_var,
                                                   command=self.update_map,
                                                   dynamic_resizing=False)
        self.map_size_dropdown.pack(fill="x", padx=SECTION_PADX, pady=(0, SECTION_PADY))

    def _add_entry_field(self, section, label_text):
        label = ctk.CTkLabel(section, text=label_text, text_color=("gray30", "gray60"))
        label.pack(anchor="w", padx=SECTION_PADX, pady=(2, 0))

        entry = ctk.CTkEntry(section)
        entry.pack(fill="x", padx=SECTION_PADX, pady=(0, 6))
        return entry

    def _build_offset_section(self):
        self.offset_section = self._add_section("OFFSET (X, Y, Z)")

        self.entry_x = self._add_entry_field(self.offset_section, "X:")
        self.entry_x.bind("<Return>", self.update_coordinates_from_entry)

        self.entry_y = self._add_entry_field(self.offset_section, "Y:")
        self.entry_y.bind("<Return>", self.update_coordinates_from_entry)

        self.entry_z = self._add_entry_field(self.offset_section, "Z:")
        self.entry_z.bind("<Return>", self.update_coordinates_from_entry)

    def _build_rotation_section(self):
        self.rotation_section = self._add_section("ROTATION")

        self.entry_angle = self._add_entry_field(self.rotation_section, "Angle (degrees):")
        self.entry_angle.bind("<Return>", self.update_rotation_from_entry)

        self.rotation_slider = ctk.CTkSlider(self.rotation_section, from_=0, to=360,
                                             number_of_steps=3600, command=self._on_rotation_slider)
        self.rotation_slider.pack(fill="x", padx=SECTION_PADX, pady=(0, 8))

        # Quaternion fields
        self.entry_qx = self._add_entry_field(self.rotation_section, "Quaternion X:")
        self.entry_qy = self._add_entry_field(self.rotation_section, "Quaternion Y:")
        self.entry_qz = self._add_entry_field(self.rotation_section, "Quaternion Z:")
        self.entry_qw = self._add_entry_field(self.rotation_section, "Quaternion W:")

    def _build_options_section(self):
        self.options_section = self._add_section("OPTIONS")

    def _build_actions_section(self):
        self.actions_section = ctk.CTkFrame(self.sidebar, corner_radius=10)
        self.actions_section.pack(fill="x", pady=(0, 6))

        self.save_button = ctk.CTkButton(self.actions_section, text="Save",
                                         command=self.save_data, height=40,
                                         font=(FONT_FAMILY, 13, "bold"),
                                         corner_radius=10)
        self.save_button.pack(fill="x", padx=12, pady=12)

    # Responsive canvas

    def _on_canvas_resize(self, event):
        if event.widget is not self.canvas:
            return
        if abs(event.width - self.canvas_width) < RESIZE_THRESHOLD and abs(event.height - self.canvas_height) < RESIZE_THRESHOLD:
            return
        if self._resize_job is not None:
            try:
                self.root.after_cancel(self._resize_job)
            except tk.TclError:
                pass
        self._resize_job = self.root.after(RESIZE_DEBOUNCE_MS,
                                           lambda: self._apply_canvas_size(event.width, event.height))

    def _apply_canvas_size(self, width, height):
        self._resize_job = None
        width = max(int(width), 200)
        height = max(int(height), 200)

        if width == self.canvas_width and height == self.canvas_height:
            return

        self.canvas_width = width
        self.canvas_height = height
        self.render_size = min(width, height)
        self.frame_x = max((width - self.render_size) // 2, 0)
        self.frame_y = max((height - self.render_size) // 2, 0)
        self.scale = self.render_size / self.map_size

        self.canvas.configure(width=self.canvas_width, height=self.canvas_height)
        self._render_frame()

    # Render sources

    def _load_background_image_source(self):
        image_path = self.map_size_options[self.map_size_var.get()]
        cached = self._bg_source_cache.get(image_path)
        if cached is None:
            try:
                cached = Image.open(image_path).convert("RGBA")
            except (FileNotFoundError, OSError):
                cached = None
            self._bg_source_cache[image_path] = cached
        self._base_bg = cached

    def _draw_point_sources(self):
        size = SOURCE_RESOLUTION
        scaling = size / self.map_size
        half = self.map_size / 2

        # Current mod's object points
        points = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(points)
        for x, y in self.get_coordinates_func:
            x, y = self.rotate_point(x, y)
            adj_x = (x + half) * scaling
            adj_y = size - ((y + half) * scaling)
            draw.rectangle([adj_x-2, adj_y-2, adj_x+2, adj_y+2], fill='purple', outline='black')
        self._source_points_image = points

        # Installed mods' object points
        installed = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw_installed = ImageDraw.Draw(installed)
        for mod, coords in self.installed_coordinates.items():
            mod_color = self._installed_colors.get(mod)
            if mod_color is None:
                mod_color = self.generate_random_color()
                self._installed_colors[mod] = mod_color
            for x, y in coords:
                adj_x = (x + half) * scaling
                adj_y = size - ((y + half) * scaling)
                draw_installed.rectangle([adj_x-2, adj_y-2, adj_x+2, adj_y+2], fill=mod_color, outline='black')
        self._source_installed_image = installed

    def _render_frame(self):
        size = self.render_size
        if self._base_bg is not None:
            self.tk_bg_image = ImageTk.PhotoImage(self._base_bg.resize((size, size), Image.BICUBIC))
        if self._source_points_image is not None:
            self.tk_points_image = ImageTk.PhotoImage(self._source_points_image.resize((size, size), Image.BILINEAR))
        if self._source_installed_image is not None:
            self.tk_installed_coords_image = ImageTk.PhotoImage(self._source_installed_image.resize((size, size), Image.BILINEAR))
        self.render_points()

    # Paths options

    def update_move_paths_checkboxes(self):
        if os.path.isfile(SA_PATHS_DATA_EXTENDER_PATH) and self.map_size == 24000:
            self.checkbox_move_paths_sapde.configure(state=tk.NORMAL)
        else:
            self.checkbox_move_paths_sapde.configure(state=tk.DISABLED)
            self.move_paths_sapde_var.set(False)

        if os.path.isfile(SA_PATH_UTILITY_PATH):
            self.checkbox_move_paths_sapu.configure(state=tk.NORMAL)
        else:
            self.checkbox_move_paths_sapu.configure(state=tk.DISABLED)
            self.move_paths_sapu_var.set(False)

    def adapt_gui_to_move_paths(self):
        if self.move_paths_sapu_var.get():
            self.path_sapu_command = True
            self.checkbox_move_paths_sapde.configure(state=tk.DISABLED)
        else:
            self.path_sapu_command = False
            if self.map_size == 24000:
                self.checkbox_move_paths_sapde.configure(state=tk.NORMAL)

        if self.move_paths_sapde_var.get():
            self.path_sapde_command = True
            self.checkbox_move_paths_sapu.configure(state=tk.DISABLED)
        else:
            self.path_sapde_command = False
            self.checkbox_move_paths_sapu.configure(state=tk.NORMAL)

        if self.move_paths_sapu_var.get() or self.move_paths_sapde_var.get():
            self.update_offsets_for_paths()
            self.update_coordinate_labels()
            self.entry_angle.configure(state=tk.DISABLED)
            self.entry_qx.configure(state=tk.DISABLED)
            self.entry_qy.configure(state=tk.DISABLED)
            self.entry_qz.configure(state=tk.DISABLED)
            self.entry_qw.configure(state=tk.DISABLED)
            self.rotation_slider.configure(state=tk.DISABLED)
        else:
            self.entry_angle.configure(state=tk.NORMAL)
            self.entry_qx.configure(state=tk.NORMAL)
            self.entry_qy.configure(state=tk.NORMAL)
            self.entry_qz.configure(state=tk.NORMAL)
            self.entry_qw.configure(state=tk.NORMAL)
            self.rotation_slider.configure(state=tk.NORMAL)

    # Map interaction

    def update_mouse_coordinates(self, event):
        # Get cursor coordinates on screen and translate them into frame coordinates
        canvas_x, canvas_y = event.x, event.y
        content_x = canvas_x - self.frame_x
        content_y = canvas_y - self.frame_y

        # Get respective coordinates on the game map
        map_x = (content_x / self.scale) - (self.map_size / 2)
        map_y = (self.render_size - content_y) / self.scale - (self.map_size / 2)

        self.current_mouse_x = map_x
        self.current_mouse_y = map_y

        # Show current coordinates
        self.mouse_coordinates_label.configure(text=f"X: {map_x:.2f}  Y: {map_y:.2f}")

    def copy_coordinates_to_clipboard(self, event):
        # Copy "X Y 0" coordinates in focus to clipboard
        coordinates_text = f"{self.current_mouse_x:.2f} {self.current_mouse_y:.2f} 0"
        pyperclip.copy(coordinates_text)

    def update_map(self, *args):
        # Update map size and reload the background image
        self.map_size = int(self.map_size_var.get())
        self.scale = self.render_size / self.map_size
        self._load_background_image_source()
        self._draw_point_sources()
        self._render_frame()
        self.update_move_paths_checkboxes()
        self.adapt_gui_to_move_paths()

    def generate_random_color(self):
        return f'#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}'

    def create_coordinate_labels(self):
        self.update_coordinate_labels()

    def render_points(self):
        self.canvas.delete("all")
        if self.tk_bg_image:
            self.canvas.create_image(self.frame_x, self.frame_y, anchor=tk.NW, image=self.tk_bg_image)
        if self.tk_installed_coords_image:
            self.canvas.create_image(self.frame_x, self.frame_y, anchor=tk.NW, image=self.tk_installed_coords_image)
        if self.tk_points_image:
            self.canvas.create_image(self.frame_x + self.offset_x * self.scale,
                                     self.frame_y - self.offset_y * self.scale,
                                     anchor=tk.NW, image=self.tk_points_image)

    def start_drag(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def drag(self, event):
        dx = (event.x - self.start_x) / self.scale
        dy = (event.y - self.start_y) / self.scale
        self.offset_x += dx
        self.offset_y -= dy  # Invert dy to match the coordinate system
        self.start_x = event.x
        self.start_y = event.y
        self.render_points()
        self.update_coordinate_labels()

    def stop_drag(self, event):
        # Adjust X and Y offsets in case paths moving is enabled
        if self.move_paths_sapu_var.get() or self.move_paths_sapde_var.get():
            self.update_offsets_for_paths()

        # Update rendered points
        self.render_points()
        self.update_coordinate_labels()

        # Reset drag start coordinates
        self.start_x = 0
        self.start_y = 0

    def adjust_rotation(self, event):
        if not self.move_paths_sapu_var.get() and not self.move_paths_sapde_var.get():
            # Scroll up: increase angle; Scroll down: decrease angle
            delta = -event.delta if event.delta else event.delta  # Handle delta sign (positive/negative) based on platform
            self.rotation_angle = (self.rotation_angle + delta / 120) % 360  # 120 is a common scroll delta step
            self._draw_point_sources()  # Rebuild the points layer with the new rotation
            self._render_frame()
            self.update_rotation_label()
            self.update_quaternion_labels()

    def rotate_point(self, x, y):
        radians = math.radians(self.rotation_angle)
        cos_a = math.cos(radians)
        sin_a = math.sin(radians)

        # Apply 2D rotation matrix
        new_x = x * cos_a - y * sin_a
        new_y = x * sin_a + y * cos_a
        return new_x, new_y

    def update_offsets_for_paths(self):
        self.offset_x = round(self.offset_x / 750) * 750
        self.offset_y = round(self.offset_y / 750) * 750

    def update_coordinate_labels(self):
        self.entry_x.delete(0, tk.END)
        self.entry_x.insert(0, f"{self.offset_x:.2f}")

        self.entry_y.delete(0, tk.END)
        self.entry_y.insert(0, f"{self.offset_y:.2f}")

    def update_coordinates_from_entry(self, event):
        try:
            self.offset_x = float(self.entry_x.get())
            self.offset_y = float(self.entry_y.get())

            if self.move_paths_sapu_var.get() or self.move_paths_sapde_var.get():
                self.update_offsets_for_paths()
                self.update_coordinate_labels()

            self.render_points()
        except ValueError:
            pass  # Ignore invalid entries

    def _on_rotation_slider(self, value):
        self.rotation_angle = float(value) % 360
        self._draw_point_sources()  # Rebuild the points layer with the new rotation
        self._render_frame()
        self.update_rotation_label()
        self.update_quaternion_labels()

    def update_rotation_from_entry(self, event):
        try:
            self.rotation_angle = float(self.entry_angle.get())
            self.rotation_angle %= 360  # Keep angle within 0-360 degrees
            self._draw_point_sources()  # Rebuild the points layer with the new rotation
            self._render_frame()
            self.update_quaternion_labels()
        except ValueError:
            pass  # Ignore invalid entries

    def update_rotation_label(self):
        self.entry_angle.delete(0, tk.END)
        self.entry_angle.insert(0, f"{self.rotation_angle:.2f}")

    def update_quaternion_labels(self):
        angle_rad = math.radians(self.rotation_angle)
        w = math.cos(angle_rad / 2)
        z = math.sin(angle_rad / 2)

        self.rotation_slider.set(self.rotation_angle)

        self.entry_qx.delete(0, tk.END)
        self.entry_qx.insert(0, f"{0:.2f}")

        self.entry_qy.delete(0, tk.END)
        self.entry_qy.insert(0, f"{0:.2f}")

        self.entry_qz.delete(0, tk.END)
        self.entry_qz.insert(0, f"{z:.2f}")

        self.entry_qw.delete(0, tk.END)
        self.entry_qw.insert(0, f"{w:.2f}")

    def save_data(self):
        # Save input data
        self.map_coordinates = self.get_map_coordinates()
        self.rotation_values = self.get_rotation_values()
        self.fix_command = self.fix_invalid_var.get()
        self.id_command = self.replace_ids_var.get()
        self.path_sapu_command = self.move_paths_sapu_var.get()
        self.path_sapde_command = self.move_paths_sapde_var.get()
        self.remove_grge_command = self.remove_grge_var.get()
        self.clean_assets_command = self.clean_assets_var.get()

        # Close GUI after saving data
        self.root.destroy()

    def get_map_coordinates(self):
        try:
            x = float(self.entry_x.get())
        except ValueError:
            x = 0.0

        try:
            y = float(self.entry_y.get())
        except ValueError:
            y = 0.0

        try:
            z = float(self.entry_z.get())
        except ValueError:
            z = 0.0

        return (x, y, z)

    def get_rotation_values(self):
        try:
            qx = float(self.entry_qx.get())
            qy = float(self.entry_qy.get())
            qz = float(self.entry_qz.get())
            qw = float(self.entry_qw.get())
            return (qx, qy, qz, qw)
        except ValueError:
            return (0.0, 0.0, 0.0, 0.0)