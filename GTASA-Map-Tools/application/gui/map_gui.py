import os
import tkinter as tk
from tkinter import Canvas, Label, Entry, Checkbutton, BooleanVar, OptionMenu, StringVar
from PIL import Image, ImageTk, ImageDraw
import math
import pyperclip
import random

RESOURCES_DIR = "resources"
SA_PATHS_DATA_EXTENDER_DIR = os.path.join(RESOURCES_DIR, "SAPathsDataExtender")
SA_PATHS_DATA_EXTENDER_NAME = "sa-pathsdata-extender.exe"
SA_PATHS_DATA_EXTENDER_PATH = os.path.join(SA_PATHS_DATA_EXTENDER_DIR, SA_PATHS_DATA_EXTENDER_NAME)
SA_PATH_UTILITY_DIR = os.path.join(RESOURCES_DIR, "SAPathUtility")
SA_PATH_UTILITY_NAME = "SAPathUtility.exe"
SA_PATH_UTILITY_PATH = os.path.join(SA_PATHS_DATA_EXTENDER_DIR, SA_PATHS_DATA_EXTENDER_NAME)

class MapGui:
    def __init__(self, root, get_coordinates_func, installed_coordinates, map_size=6000, args=None):
        self.root = root
        self.root.bind_all('<F2>', self.copy_coordinates_to_clipboard)
        
        self.start_x = 0
        self.start_y = 0
        self.offset_x = 0
        self.offset_y = 0
        self.rotation_angle = 0  # Initialize rotation angle
        
        self.get_coordinates_func = get_coordinates_func
        self.installed_coordinates = installed_coordinates

        # Initialize the map size variable
        self.map_size_var = StringVar(value=str(map_size))
        self.map_size_options = {"6000": "resources/map_6000.png",
                                 "12000": "resources/map_12000.png",
                                 "24000": "resources/map_24000.png",
                                 "48000": "resources/map_48000.png"}
        
        # Update map_size based on dropdown selection
        self.map_size = int(self.map_size_var.get())
        self.canvas_size = 600  # Canvas size in pixels
        self.scale = self.canvas_size / self.map_size

        self.canvas = Canvas(root, width=self.canvas_size, height=self.canvas_size, bg='white')
        self.canvas.pack()

        # Add the dropdown menu for map size
        self.map_size_dropdown = OptionMenu(root, self.map_size_var, *self.map_size_options.keys(), command=self.update_map)
        self.map_size_dropdown.pack()

        self.load_background_image()
        self.create_points_image()

        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        self.canvas.bind("<MouseWheel>", self.adjust_rotation)  # Bind mouse wheel event

        # Bind mouse motion event to update coordinates display
        self.canvas.bind("<Motion>", self.update_mouse_coordinates)

        self.create_coordinate_labels()

        # Label to display the current mouse coordinates
        self.mouse_coordinates_label = Label(root, text="X: 0.00 Y: 0.00")
        self.mouse_coordinates_label.pack()
        
        self.save_button = tk.Button(root, text="Save", command=self.save_data)
        self.save_button.pack()
        
        self.map_coordinates = None
        self.rotation_values = None
        self.fix_command = True
        self.id_command = True
        self.path_sapu_command = False
        self.path_sapde_command = False
        
        # Initialize BooleanVars for checkboxes
        self.fix_invalid_var = BooleanVar(value=True)
        self.replace_ids_var = BooleanVar(value=True)
        self.move_paths_sapu_var = BooleanVar(value=False)
        self.move_paths_sapde_var = BooleanVar(value=False)

        # Create checkboxes
        self.checkbox_fix_invalid = Checkbutton(root, text="Fix invalid objects", variable=self.fix_invalid_var)
        self.checkbox_fix_invalid.pack()

        self.checkbox_replace_ids = Checkbutton(root, text="Replace objects IDs", variable=self.replace_ids_var)
        self.checkbox_replace_ids.pack()
        
        self.checkbox_move_paths_sapu = Checkbutton(root, text="Move paths (SA Path Utility)", variable=self.move_paths_sapu_var, command=self.adapt_gui_to_move_paths)
        self.checkbox_move_paths_sapu.pack()
        self.checkbox_move_paths_sapde = Checkbutton(root, text="Move paths (SA Paths Data Extender)", variable=self.move_paths_sapde_var, command=self.adapt_gui_to_move_paths)
        self.checkbox_move_paths_sapde.pack()
        self.update_move_paths_checkboxes()
        self.adapt_gui_to_move_paths()
        
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

    def update_move_paths_checkboxes(self):
        if os.path.isfile(SA_PATHS_DATA_EXTENDER_PATH) and self.map_size == 24000:
            self.checkbox_move_paths_sapde.config(state=tk.NORMAL)
        else:
            self.checkbox_move_paths_sapde.config(state=tk.DISABLED) 
            self.move_paths_sapde_var.set(False)
            
        if os.path.isfile(SA_PATH_UTILITY_PATH):
            self.checkbox_move_paths_sapu.config(state=tk.NORMAL)
        else:
            self.checkbox_move_paths_sapu.config(state=tk.DISABLED) 
            self.move_paths_sapu_var.set(False)
            
    def adapt_gui_to_move_paths(self):
        if self.move_paths_sapu_var.get():
            self.path_sapu_command = True
            self.checkbox_move_paths_sapde.config(state=tk.DISABLED)
        else:
            self.path_sapu_command = False
            if self.map_size == 24000:
                self.checkbox_move_paths_sapde.config(state=tk.NORMAL)
            
        if self.move_paths_sapde_var.get():
            self.path_sapde_command = True
            self.checkbox_move_paths_sapu.config(state=tk.DISABLED)
        else:
            self.path_sapde_command = False
            self.checkbox_move_paths_sapu.config(state=tk.NORMAL)
        
        if self.move_paths_sapu_var.get() or self.move_paths_sapde_var.get():
            self.update_offsets_for_paths()
            self.update_coordinate_labels()
            self.entry_angle.config(state=tk.DISABLED)
            self.entry_qx.config(state=tk.DISABLED)
            self.entry_qy.config(state=tk.DISABLED)
            self.entry_qz.config(state=tk.DISABLED)
            self.entry_qw.config(state=tk.DISABLED)
        else:
            self.entry_angle.config(state=tk.NORMAL)
            self.entry_qx.config(state=tk.NORMAL)
            self.entry_qy.config(state=tk.NORMAL)
            self.entry_qz.config(state=tk.NORMAL)
            self.entry_qw.config(state=tk.NORMAL)

    def update_mouse_coordinates(self, event):
        # Get cursor coordinates on screen
        canvas_x, canvas_y = event.x, event.y
        
        # Get respective coordinates on the game map
        map_x = (canvas_x / self.scale) - (self.map_size / 2)
        map_y = (self.canvas_size - canvas_y) / self.scale - (self.map_size / 2)
        
        self.current_mouse_x = map_x
        self.current_mouse_y = map_y
        
        # Show current coordinates
        self.mouse_coordinates_label.config(text=f"X: {map_x:.2f} Y: {map_y:.2f}")
        
    def copy_coordinates_to_clipboard(self, event):
        # Copy "X Y 0" coordinates in focus to clipboard
        coordinates_text = f"{self.current_mouse_x:.2f} {self.current_mouse_y:.2f} 0"
        pyperclip.copy(coordinates_text)

    def load_background_image(self):
        try:
            # Get the correct image path based on map size
            image_path = self.map_size_options[self.map_size_var.get()]
            self.bg_image = Image.open(image_path)
        except FileNotFoundError:
            self.bg_image = None

        if self.bg_image:
            self.bg_image = self.bg_image.resize((self.canvas_size, self.canvas_size))
            self.tk_bg_image = ImageTk.PhotoImage(self.bg_image)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_bg_image)
            
    def update_map(self, *args):
        # Update map size and reload the background image
        self.map_size = int(self.map_size_var.get())
        self.scale = self.canvas_size / self.map_size
        self.load_background_image()
        self.create_points_image()
        self.update_move_paths_checkboxes()
        self.adapt_gui_to_move_paths()

    def create_points_image(self):
        self.points_image = Image.new('RGBA', (self.canvas_size, self.canvas_size), (0, 0, 0, 0))
        
        # Draw object points, convert them to PhotoImage to improve performance and add to canvas
        self.draw_points()
        self.tk_points_image = ImageTk.PhotoImage(self.points_image)
        self.render_points()

    def generate_random_color(self):
        return f'#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}'

    def draw_points(self):
        draw = ImageDraw.Draw(self.points_image)

        # Draw current mod's object points
        for x, y in self.get_coordinates_func:
            x, y = self.rotate_point(x, y)
            adj_x = (x + self.map_size / 2) * self.scale
            adj_y = self.canvas_size - ((y + self.map_size / 2) * self.scale)
            draw.rectangle([adj_x-2, adj_y-2, adj_x+2, adj_y+2], fill='purple', outline='black')

        # Draw already installed mods' object points in a different layer
        self.installed_coords_image = Image.new('RGBA', (self.canvas_size, self.canvas_size), (0, 0, 0, 0))
        draw_installed_coords = ImageDraw.Draw(self.installed_coords_image)

        for mod, coords in self.installed_coordinates.items():
            mod_color = self.generate_random_color()

            for x, y in coords:
                adj_x = (x + self.map_size / 2) * self.scale
                adj_y = self.canvas_size - ((y + self.map_size / 2) * self.scale)
                draw_installed_coords.rectangle([adj_x-2, adj_y-2, adj_x+2, adj_y+2], fill=mod_color, outline='black')

        self.tk_installed_coords_image = ImageTk.PhotoImage(self.installed_coords_image)


    def create_coordinate_labels(self):
        self.label_x = Label(self.root, text="X:")
        self.label_x.pack()

        self.entry_x = Entry(self.root)
        self.entry_x.pack()
        self.entry_x.bind("<Return>", self.update_coordinates_from_entry)

        self.label_y = Label(self.root, text="Y:")
        self.label_y.pack()

        self.entry_y = Entry(self.root)
        self.entry_y.pack()
        self.entry_y.bind("<Return>", self.update_coordinates_from_entry)

        self.label_z = Label(self.root, text="Z:")
        self.label_z.pack()

        self.entry_z = Entry(self.root)
        self.entry_z.pack()
        self.entry_z.bind("<Return>", self.update_coordinates_from_entry)

        self.label_angle = Label(self.root, text="Angle (degrees):")
        self.label_angle.pack()

        self.entry_angle = Entry(self.root)
        self.entry_angle.pack()
        self.entry_angle.bind("<Return>", self.update_rotation_from_entry)

        # Quaternion fields
        self.label_qx = Label(self.root, text="Quaternion X:")
        self.label_qx.pack()
        self.entry_qx = Entry(self.root)
        self.entry_qx.pack()

        self.label_qy = Label(self.root, text="Quaternion Y:")
        self.label_qy.pack()
        self.entry_qy = Entry(self.root)
        self.entry_qy.pack()

        self.label_qz = Label(self.root, text="Quaternion Z:")
        self.label_qz.pack()
        self.entry_qz = Entry(self.root)
        self.entry_qz.pack()

        self.label_qw = Label(self.root, text="Quaternion W:")
        self.label_qw.pack()
        self.entry_qw = Entry(self.root)
        self.entry_qw.pack()

        self.update_coordinate_labels()

    def render_points(self):
        self.canvas.delete("all")
        if self.bg_image:
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_bg_image)
        if self.tk_installed_coords_image:
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_installed_coords_image)
        if self.tk_points_image:
            self.canvas.create_image(self.offset_x * self.scale, -self.offset_y * self.scale, anchor=tk.NW, image=self.tk_points_image)

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
            self.create_points_image()  # Recreate points image with the new rotation
            self.render_points()
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

    def update_rotation_from_entry(self, event):
        try:
            self.rotation_angle = float(self.entry_angle.get())
            self.rotation_angle %= 360  # Keep angle within 0-360 degrees
            self.create_points_image()  # Recreate points image with the new rotation
            self.render_points()
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