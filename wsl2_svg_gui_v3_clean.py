#!/usr/bin/env python3
"""
Complete Potrace GUI with WSL2 SVG Preview Integration - VERSION 3
Hybrid approach: Windows GUI + controls, WSL2 for visual SVG preview
Solves Cairo dependency issues by using Linux SVG tools

VERSION 3 FIXES (Live Preview Enhancement):
- Fixed original image display to match mkbitmap panel sizing for easy comparison
- Fixed SVG aspect ratio distortion in WSL2 conversion (was squashing images)
- Fixed Stage 2 parameter live updates (turdsize, alphamax, opttolerance now trigger reprocessing)
- Added auto-population of Final Icon panel (Panel 4) - no more manual button clicking needed
- Implemented true 4-panel live preview pipeline
- Enhanced parameter change detection for all controls
- Improved image scaling consistency across all panels

VERSION 2 FIXES (Previous):
- Fixed WSL2 path conversion for temp files
- Improved original image display (centered and properly scaled)  
- Better temp file handling for WSL2 accessibility
- Enhanced error handling for SVG conversion
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk
import subprocess
import tempfile
import os
import shutil
from pathlib import Path
import threading
import xml.etree.ElementTree as ET
import re
import json
import datetime

class WSL2MkbitmapPotraceGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("WWII Silhouette Icon Generator - WSL2 Enhanced v3")
        self.root.geometry("1800x1000")
        
        # Project paths
        self.project_root = Path("G:\\Claude Wargame Icon Generator\\WWII Silhouette Icon System")
        self.blueprints_dir = self.project_root / "wwii_icons" / "blueprints"
        self.output_dir = self.project_root / "wwii_icons" / "silhouettes"
        
        # Processing variables
        self.current_image = None
        self.original_image = None
        self.mkbitmap_result = None
        self.potrace_svg_path = None
        self.potrace_svg_content = None
        self.svg_preview_image = None
        self.live_preview = tk.BooleanVar(value=True)
        self.processing = False
        
        # V3: Add final icon preview storage
        self.final_icon_preview = None
        
        # WSL2 integration
        self.wsl_available = self.check_wsl2_availability()
        
        # Default values for reset functionality
        self.default_values = {
            'blur': 1.0, 'threshold': 0.45, 'scale': 2, 'filter': 2,
            'turnpolicy': 'minority', 'turdsize': 2, 'alphamax': 1.0, 'opttolerance': 0.2
        }
        
        self.setup_gui()
        self.auto_load_test_image()
        self.verify_tools()
    
    def check_wsl2_availability(self):
        """Check if WSL2 is available and has required tools"""
        try:
            # Check if WSL is available
            result = subprocess.run(['wsl', '--list'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False
                
            # Check for rsvg-convert (librsvg) in WSL
            result = subprocess.run(['wsl', 'which', 'rsvg-convert'], capture_output=True, timeout=10)
            if result.returncode == 0:
                return True
            
            # If not found, try to install it
            print("Installing librsvg-tools in WSL...")
            install_result = subprocess.run([
                'wsl', 'sudo', 'apt', 'update', '&&', 
                'sudo', 'apt', 'install', '-y', 'librsvg2-bin'
            ], capture_output=True, timeout=60)
            
            if install_result.returncode == 0:
                return True
                
        except Exception as e:
            print(f"WSL2 check failed: {e}")
            
        return False
    
    def setup_gui(self):
        """Create main GUI with enhanced WSL2 preview"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Top controls
        self.setup_top_controls(main_frame)
        
        # Main content
        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        self.setup_controls_panel(content_frame)
        self.setup_preview_panel(content_frame)
        
        # Status bar with WSL2 info
        wsl_status = "✅ WSL2 SVG Preview" if self.wsl_available else "⚠️ WSL2 Not Available"
        self.status_var = tk.StringVar(value=f"Ready - {wsl_status}")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def setup_top_controls(self, parent):
        """Create top controls with WSL2 options"""
        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # File controls
        file_frame = ttk.LabelFrame(controls_frame, text="Load Blueprint", padding="5")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(file_frame, text="Browse File", command=self.load_file).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(file_frame, text="Load Test Image", command=self.load_test_image).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(file_frame, text="Batch Process", command=self.batch_process).grid(row=0, column=2)
        
        # Processing controls - V3: Updated description to reflect true live preview
        process_frame = ttk.LabelFrame(controls_frame, text="Live Preview Controls", padding="5")
        process_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        
        ttk.Checkbutton(process_frame, text="Live Preview (All 4 Panels)", variable=self.live_preview, 
                       command=self.toggle_live_preview).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(process_frame, text="Process Now", command=self.manual_process).grid(row=0, column=1, padx=(0, 10))
        ttk.Button(process_frame, text="Reset All", command=self.reset_parameters).grid(row=0, column=2, padx=(0, 10))
        
        # Save/export controls  
        save_frame = ttk.LabelFrame(controls_frame, text="Export & Save", padding="5")
        save_frame.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=(5, 0))
        
        ttk.Button(save_frame, text="Save SVG", command=self.save_result).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(save_frame, text="Copy SVG Code", command=self.copy_svg_code).grid(row=0, column=1, padx=(0, 5))
        # V3: Updated button text to reflect it's now for export only
        ttk.Button(save_frame, text="Export Final Icon", command=self.export_final_icon).grid(row=0, column=2)
    
    def setup_controls_panel(self, parent):
        """Create enhanced controls panel with presets"""
        controls_panel = ttk.Frame(parent, width=400)
        controls_panel.grid(row=0, column=0, sticky=(tk.W, tk.N, tk.S), padx=(0, 10))
        controls_panel.grid_propagate(False)
        
        # Preset controls at top
        preset_frame = ttk.LabelFrame(controls_panel, text="Quick Presets", padding="10")
        preset_frame.pack(fill=tk.X, pady=(0, 10))
        
        preset_buttons = [
            ("Technical Drawing", "technical", "Sharp edges, clean lines"),
            ("Smooth Silhouette", "smooth", "Rounded curves, simplified"),
            ("High Detail", "detail", "Maximum detail retention")
        ]
        
        for i, (name, preset, desc) in enumerate(preset_buttons):
            btn_frame = ttk.Frame(preset_frame)
            btn_frame.grid(row=i//2, column=i%2, sticky=(tk.W, tk.E), padx=5, pady=2)
            ttk.Button(btn_frame, text=name, command=lambda p=preset: self.load_preset(p)).pack(side=tk.LEFT)
            ttk.Label(btn_frame, text=f"- {desc}", font=('Arial', 8)).pack(side=tk.LEFT, padx=(5, 0))
        
        preset_frame.columnconfigure((0, 1), weight=1)
        
        # Mkbitmap Controls with enhanced descriptions
        mkbitmap_frame = ttk.LabelFrame(controls_panel, text="Stage 1: Image Preprocessing (Mkbitmap)", padding="10")
        mkbitmap_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Blur radius with real-time feedback
        self.create_parameter_control(mkbitmap_frame, 0, "Blur Radius:", "blur", 0.1, 3.0, 
                                     "Smooths image details - higher = smoother silhouette")
        self.create_parameter_control(mkbitmap_frame, 1, "Threshold:", "threshold", 0.1, 0.9,
                                     "Black/white cutoff - lower = more black areas")
        self.create_parameter_control(mkbitmap_frame, 2, "Scale Factor:", "scale", 1, 4,
                                     "Enlargement - higher = more detail retention", is_int=True)
        self.create_parameter_control(mkbitmap_frame, 3, "Filter Passes:", "filter", 0, 8,
                                     "Noise reduction - higher = cleaner result", is_int=True)
        
        mkbitmap_frame.columnconfigure(1, weight=1)
        
        # Potrace Controls with enhanced descriptions
        potrace_frame = ttk.LabelFrame(controls_panel, text="Stage 2: Vector Tracing (Potrace)", padding="10")
        potrace_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Turn policy with description
        ttk.Label(potrace_frame, text="Turn Policy:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Label(potrace_frame, text="How to resolve ambiguities", font=('Arial', 8), foreground='gray').grid(row=0, column=2, sticky=tk.W, padx=(5, 0))
        self.turnpolicy_var = tk.StringVar(value=self.default_values['turnpolicy'])
        turnpolicy_combo = ttk.Combobox(potrace_frame, textvariable=self.turnpolicy_var,
                                       values=["black", "white", "majority", "minority", "right", "left"],
                                       state="readonly", width=15)
        turnpolicy_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 5), pady=2)
        # V3: Enhanced parameter change binding for immediate live updates
        turnpolicy_combo.bind('<<ComboboxSelected>>', self.on_parameter_change)
        
        self.create_parameter_control(potrace_frame, 1, "Noise Removal:", "turdsize", 0, 10,
                                     "Removes small speckles - higher = cleaner", is_int=True)
        self.create_parameter_control(potrace_frame, 2, "Curve Smoothing:", "alphamax", 0.0, 1.34,
                                     "Corner sharpness - lower = sharper corners")
        self.create_parameter_control(potrace_frame, 3, "Optimization:", "opttolerance", 0.0, 1.0,
                                     "Path simplification - higher = simpler paths")
        
        potrace_frame.columnconfigure(1, weight=1)
        
        # Processing pipeline info
        pipeline_frame = ttk.LabelFrame(controls_panel, text="Pipeline Status", padding="10")
        pipeline_frame.pack(fill=tk.X)
        
        self.pipeline_status = tk.Text(pipeline_frame, height=6, font=('Consolas', 9), wrap=tk.WORD)
        self.pipeline_status.pack(fill=tk.BOTH, expand=True)
        self.update_pipeline_status("Ready to process blueprint images - V3 Full Live Preview")
    
    def create_parameter_control(self, parent, row, label, var_name, min_val, max_val, description, is_int=False):
        """Create a parameter control with description - V3: Enhanced change detection"""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        
        if is_int:
            var = tk.IntVar(value=int(self.default_values[var_name]))
        else:
            var = tk.DoubleVar(value=self.default_values[var_name])
        setattr(self, f"{var_name}_var", var)
        
        scale = ttk.Scale(parent, from_=min_val, to=max_val, variable=var,
                         orient=tk.HORIZONTAL, command=self.on_parameter_change)
        scale.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(10, 5), pady=2)
        
        # V3: Add variable tracing for immediate parameter change detection
        var.trace_add('write', self.on_parameter_change)
        
        if is_int:
            label_text = str(int(self.default_values[var_name]))
        else:
            label_text = f"{self.default_values[var_name]:.2f}"
        value_label = ttk.Label(parent, text=label_text, width=6)
        value_label.grid(row=row, column=2, padx=(0, 5), pady=2)
        setattr(self, f"{var_name}_label", value_label)
        
        # Description label
        desc_label = ttk.Label(parent, text=description, font=('Arial', 8), foreground='gray')
        desc_label.grid(row=row, column=3, sticky=tk.W, padx=(5, 0), pady=2)
    
    def setup_preview_panel(self, parent):
        """Create enhanced preview panel with WSL2 SVG preview"""
        preview_frame = ttk.Frame(parent)
        preview_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        
        self.preview_notebook = ttk.Notebook(preview_frame)
        self.preview_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Enhanced Pipeline tab with 4 stages - V3: Updated descriptions
        pipeline_frame = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(pipeline_frame, text="🔧 Live Preview Pipeline")
        
        stages_frame = ttk.Frame(pipeline_frame)
        stages_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Four processing stages - V3: Updated final stage description
        stage_configs = [
            ("1. Original Blueprint", "original_canvas", "📋"),
            ("2. Mkbitmap Result", "mkbitmap_canvas", "🔄"),
            ("3. SVG Vector", "svg_preview_canvas", "🎯"),
            ("4. Final Icon Preview", "final_icon_canvas", "✅")
        ]
        
        for i, (title, canvas_attr, icon) in enumerate(stage_configs):
            stage_frame = ttk.LabelFrame(stages_frame, text=f"{icon} {title}")
            stage_frame.grid(row=i//2, column=i%2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
            
            canvas = tk.Canvas(stage_frame, width=400, height=300, bg='white')
            canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            setattr(self, canvas_attr, canvas)
        
        stages_frame.columnconfigure((0, 1), weight=1)
        stages_frame.rowconfigure((0, 1), weight=1)
        
        # SVG Info tab
        svg_info_frame = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(svg_info_frame, text="📊 SVG Analysis")
        
        info_text_frame = ttk.Frame(svg_info_frame)
        info_text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.svg_info_text = scrolledtext.ScrolledText(info_text_frame, font=('Consolas', 10), wrap=tk.WORD)
        self.svg_info_text.pack(fill=tk.BOTH, expand=True)
        
        # SVG Code tab with enhanced syntax highlighting
        svg_code_frame = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(svg_code_frame, text="📝 SVG Source Code")
        
        code_controls = ttk.Frame(svg_code_frame)
        code_controls.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        ttk.Button(code_controls, text="Copy All", command=self.copy_svg_code).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(code_controls, text="Save SVG", command=self.save_svg_only).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(code_controls, text="Validate SVG", command=self.validate_svg).pack(side=tk.LEFT)
        
        self.svg_code_text = scrolledtext.ScrolledText(svg_code_frame, font=('Consolas', 10), wrap=tk.NONE)
        self.svg_code_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
    
    def update_pipeline_status(self, message):
        """Update pipeline status display"""
        self.pipeline_status.delete(1.0, tk.END)
        timestamp = tk.StringVar()
        import datetime
        timestamp.set(datetime.datetime.now().strftime("%H:%M:%S"))
        self.pipeline_status.insert(1.0, f"[{timestamp.get()}] {message}")
    
    def convert_svg_to_png_wsl2(self, svg_path, output_path, target_canvas_size=(400, 300)):
        """Convert SVG to PNG using WSL2 rsvg-convert - V3 FIXED: Preserve aspect ratio"""
        try:
            # First, get SVG dimensions to calculate proper aspect ratio
            try:
                with open(svg_path, 'r', encoding='utf-8') as f:
                    svg_content = f.read()
                root = ET.fromstring(svg_content)
                
                # Extract dimensions
                width_str = root.get('width', '100')
                height_str = root.get('height', '100')
                
                # Handle different unit formats
                import re
                width_match = re.search(r'[\d.]+', width_str)
                height_match = re.search(r'[\d.]+', height_str)
                
                if width_match and height_match:
                    svg_width = float(width_match.group())
                    svg_height = float(height_match.group())
                else:
                    # Fallback to viewBox if width/height not available
                    viewbox = root.get('viewBox', '0 0 100 100')
                    viewbox_parts = viewbox.split()
                    if len(viewbox_parts) >= 4:
                        svg_width = float(viewbox_parts[2])
                        svg_height = float(viewbox_parts[3])
                    else:
                        svg_width, svg_height = 100, 100
                        
            except Exception as e:
                print(f"Could not parse SVG dimensions: {e}, using defaults")
                svg_width, svg_height = 100, 100
            
            # V3 FIX: Calculate size preserving aspect ratio
            canvas_width, canvas_height = target_canvas_size
            
            # Calculate scale factor to fit canvas while preserving aspect ratio
            scale_x = canvas_width / svg_width
            scale_y = canvas_height / svg_height
            scale_factor = min(scale_x, scale_y)  # Use smaller scale to fit entirely
            
            # Calculate final dimensions
            final_width = int(svg_width * scale_factor)
            final_height = int(svg_height * scale_factor)
            
            # V3 FIX: Handle temp files by copying to WSL2-accessible location
            if 'Temp' in svg_path or 'temp' in svg_path or 'tmp' in svg_path:
                # Create temp directory in project folder (WSL2 accessible)
                wsl_temp_dir = self.project_root / "temp"
                wsl_temp_dir.mkdir(exist_ok=True)
                
                temp_svg_name = f"temp_{os.path.basename(svg_path)}"
                wsl_accessible_svg = wsl_temp_dir / temp_svg_name
                
                # Copy temp file to WSL2-accessible location
                shutil.copy2(svg_path, str(wsl_accessible_svg))
                wsl_svg_path = str(wsl_accessible_svg).replace('\\', '/').replace('G:', '/mnt/g')
                
            else:
                # Convert regular Windows paths to WSL2 paths
                wsl_svg_path = svg_path.replace('\\', '/').replace('C:', '/mnt/c').replace('G:', '/mnt/g')
            
            # Handle output path
            if 'Temp' in output_path or 'temp' in output_path or 'tmp' in output_path:
                # For temp output, use project temp dir too
                wsl_temp_dir = self.project_root / "temp"
                wsl_temp_dir.mkdir(exist_ok=True)
                
                temp_png_name = f"temp_{os.path.basename(output_path)}"
                wsl_accessible_png = wsl_temp_dir / temp_png_name
                wsl_output_path = str(wsl_accessible_png).replace('\\', '/').replace('G:', '/mnt/g')
                final_output_path = str(wsl_accessible_png)
            else:
                wsl_output_path = output_path.replace('\\', '/').replace('C:', '/mnt/c').replace('G:', '/mnt/g')
                final_output_path = output_path
            
            # V3 FIX: Use calculated dimensions instead of fixed size
            cmd = f'wsl rsvg-convert "{wsl_svg_path}" -w {final_width} -h {final_height} -o "{wsl_output_path}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"rsvg-convert failed: {result.stderr}")
            
            # Check if output file exists
            if os.path.exists(final_output_path):
                return final_output_path
            else:
                raise Exception("Output file was not created")
                
        except Exception as e:
            print(f"WSL2 SVG conversion failed: {e}")
            return None
    
    def display_original_image(self, image_path):
        """Display the original blueprint image in panel 1 - V3 FIXED: Consistent sizing with mkbitmap panel"""
        try:
            # Load image
            pil_image = Image.open(image_path)
            
            # V3 FIX: Use same display logic as other panels for consistency
            self.display_image_consistent(pil_image, self.original_canvas, "Original Blueprint")
            
        except Exception as e:
            print(f"Error displaying original image: {e}")
            # Show error message on canvas
            self.original_canvas.delete("all")
            self.original_canvas.create_text(200, 150, text=f"Error loading image:\n{e}", 
                                           fill="red", font=('Arial', 10), justify=tk.CENTER)
    
    def display_image_consistent(self, image, canvas, label="Image"):
        """V3: New consistent image display method used across all panels"""
        if not image:
            return
        
        try:
            canvas.update_idletasks()
            canvas_width = max(canvas.winfo_width(), 390)
            canvas_height = max(canvas.winfo_height(), 290)
            
            # Calculate size to fit canvas while maintaining aspect ratio
            padding = 10
            available_width = canvas_width - (2 * padding)
            available_height = canvas_height - (2 * padding)
            
            width_ratio = available_width / image.width
            height_ratio = available_height / image.height
            scale_factor = min(width_ratio, height_ratio, 1.0)  # Don't upscale
            
            new_width = int(image.width * scale_factor)
            new_height = int(image.height * scale_factor)
            
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(resized_image)
            
            # Clear canvas and center image
            canvas.delete("all")
            x = (canvas_width - new_width) // 2
            y = (canvas_height - new_height) // 2
            canvas.create_image(x, y, anchor=tk.NW, image=photo)
            
            # Keep reference to prevent garbage collection
            canvas.image = photo
            canvas.photo_image = resized_image  # Keep PIL image reference too
            
        except Exception as e:
            print(f"Error in display_image_consistent for {label}: {e}")
            canvas.delete("all")
            canvas.create_text(200, 150, text=f"Display error:\n{e}", 
                             fill="red", font=('Arial', 9), justify=tk.CENTER)
    
    def display_svg_preview(self, svg_content):
        """Display SVG using WSL2 conversion - V3 ENHANCED: Fixed aspect ratio"""
        if not svg_content or not self.wsl_available:
            # Fallback to text info
            self.display_svg_info(svg_content)
            self.svg_preview_canvas.delete("all")
            self.svg_preview_canvas.create_text(200, 150, text="WSL2 not available\nShowing SVG info instead", 
                                              fill="gray", font=('Arial', 10), justify=tk.CENTER)
            return
        
        try:
            # Save SVG to temporary file
            temp_svg = tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False, encoding='utf-8')
            temp_svg.write(svg_content)
            temp_svg.close()
            
            # Create temp PNG path
            temp_png = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_png.close()
            
            # V3 FIX: Convert to PNG using improved WSL2 method with proper aspect ratio
            png_path = self.convert_svg_to_png_wsl2(temp_svg.name, temp_png.name, (400, 300))
            
            if png_path and os.path.exists(png_path):
                # Load and display PNG using consistent method
                preview_img = Image.open(png_path)
                self.display_image_consistent(preview_img, self.svg_preview_canvas, "SVG Preview")
                
                # V3: Store for final icon panel
                self.final_icon_preview = preview_img.copy()
                
                self.update_pipeline_status("✅ SVG preview rendered via WSL2 (aspect ratio preserved)")
            else:
                # Fallback display
                self.display_svg_info(svg_content)
                self.svg_preview_canvas.delete("all")
                self.svg_preview_canvas.create_text(200, 150, text="SVG conversion failed\nShowing analysis instead", 
                                                  fill="orange", font=('Arial', 10), justify=tk.CENTER)
            
            # Clean up temp files
            try:
                if os.path.exists(temp_svg.name):
                    os.unlink(temp_svg.name)
                if png_path and os.path.exists(png_path) and png_path != temp_png.name:
                    os.unlink(png_path)
                if os.path.exists(temp_png.name):
                    os.unlink(temp_png.name)
            except Exception as cleanup_error:
                print(f"Temp file cleanup warning: {cleanup_error}")
                
        except Exception as e:
            print(f"SVG preview error: {e}")
            self.display_svg_info(svg_content)
            self.svg_preview_canvas.delete("all")
            self.svg_preview_canvas.create_text(200, 150, text=f"SVG preview error:\n{e}", 
                                              fill="red", font=('Arial', 9), justify=tk.CENTER)
    
    def display_final_icon_preview(self):
        """V3: NEW - Auto-populate final icon panel (Panel 4) for live preview"""
        if self.final_icon_preview:
            try:
                # Display the final icon preview using consistent method
                self.display_image_consistent(self.final_icon_preview, self.final_icon_canvas, "Final Icon")
                
                # Add "ready" indicator
                self.final_icon_canvas.update_idletasks()
                canvas_width = max(self.final_icon_canvas.winfo_width(), 390)
                
                # Add ready indicator text at bottom
                self.final_icon_canvas.create_text(canvas_width//2, 280, 
                                                 text="✅ Ready for Export", 
                                                 fill="green", font=('Arial', 10, 'bold'))
                
                self.update_pipeline_status("✅ Final icon preview ready - all 4 panels populated!")
                
            except Exception as e:
                print(f"Error displaying final icon preview: {e}")
                self.final_icon_canvas.delete("all")
                self.final_icon_canvas.create_text(200, 150, text="Final icon preview error", 
                                                 fill="red", font=('Arial', 10))
        else:
            # Clear panel if no preview available
            self.final_icon_canvas.delete("all")
            self.final_icon_canvas.create_text(200, 150, text="Processing...", 
                                             fill="gray", font=('Arial', 10))
    
    def export_final_icon(self):
        """V3: RENAMED from create_final_icon - Now just exports, no dialog needed"""
        if not self.potrace_svg_content:
            messagebox.showwarning("No SVG", "Process an image first to export final icon")
            return
            
        # Direct export dialog
        filename = filedialog.asksaveasfilename(
            title="Export Final Icon",
            initialdir=str(self.output_dir),
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg"), ("PNG files", "*.png"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                file_ext = Path(filename).suffix.lower()
                
                if file_ext == '.svg':
                    # Export SVG
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(self.potrace_svg_content)
                    self.status_var.set(f"✅ SVG exported: {Path(filename).name}")
                    
                elif file_ext == '.png' and self.final_icon_preview:
                    # Export PNG
                    # Create high-quality version for export
                    if self.wsl_available and self.potrace_svg_path:
                        # Use WSL2 to create high-res PNG
                        temp_png = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                        temp_png.close()
                        
                        # Export at higher resolution
                        high_res_path = self.convert_svg_to_png_wsl2(self.potrace_svg_path, 
                                                                   temp_png.name, (512, 512))
                        if high_res_path and os.path.exists(high_res_path):
                            high_res_img = Image.open(high_res_path)
                            high_res_img.save(filename, 'PNG')
                            os.unlink(high_res_path)
                        else:
                            # Fallback to preview version
                            self.final_icon_preview.save(filename, 'PNG')
                    else:
                        self.final_icon_preview.save(filename, 'PNG')
                        
                    self.status_var.set(f"✅ PNG exported: {Path(filename).name}")
                    
                else:
                    messagebox.showerror("Export Error", "Unsupported file format or no preview available")
                    return
                
                messagebox.showinfo("Export Complete", f"Final icon exported successfully!\n{Path(filename).name}")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not export final icon: {e}")
    
    def batch_process(self):
        """Batch process multiple blueprint files"""
        folder = filedialog.askdirectory(
            title="Select Folder with Blueprint Images",
            initialdir=str(self.blueprints_dir)
        )
        
        if not folder:
            return
            
        # Find image files
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
        image_files = []
        
        for file_path in Path(folder).iterdir():
            if file_path.suffix.lower() in image_extensions:
                image_files.append(file_path)
        
        if not image_files:
            messagebox.showwarning("No Images", "No supported image files found in selected folder")
            return
        
        # Batch processing dialog
        batch_dialog = tk.Toplevel(self.root)
        batch_dialog.title(f"Batch Process {len(image_files)} Images")
        batch_dialog.geometry("600x500")
        batch_dialog.transient(self.root)
        batch_dialog.grab_set()
        
        # Progress display
        progress_frame = ttk.Frame(batch_dialog, padding="10")
        progress_frame.pack(fill=tk.X)
        
        ttk.Label(progress_frame, text=f"Processing {len(image_files)} blueprint images...").pack()
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=len(image_files))
        progress_bar.pack(fill=tk.X, pady=(5, 0))
        
        # Results display
        results_frame = ttk.LabelFrame(batch_dialog, text="Processing Results", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))
        
        results_text = scrolledtext.ScrolledText(results_frame, font=('Consolas', 9))
        results_text.pack(fill=tk.BOTH, expand=True)
        
        # Control buttons
        button_frame = ttk.Frame(batch_dialog, padding="10")
        button_frame.pack(fill=tk.X)
        
        start_btn = ttk.Button(button_frame, text="Start Batch Processing")
        start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(button_frame, text="Close", command=batch_dialog.destroy).pack(side=tk.RIGHT)
        
        def run_batch_processing():
            """Execute batch processing"""
            start_btn.config(state='disabled')
            successful = 0
            failed = 0
            
            for i, image_file in enumerate(image_files):
                try:
                    # Update progress
                    progress_var.set(i + 1)
                    batch_dialog.update()
                    
                    results_text.insert(tk.END, f"Processing: {image_file.name}...\n")
                    results_text.see(tk.END)
                    batch_dialog.update()
                    
                    # Load image
                    self.load_image(str(image_file))
                    
                    # Wait for processing to complete
                    while self.processing:
                        batch_dialog.update()
                        self.root.after(100)
                    
                    # Save result
                    if self.potrace_svg_content:
                        output_name = image_file.stem + "_silhouette"
                        output_path = self.output_dir / f"{output_name}.svg"
                        
                        with open(str(output_path), 'w', encoding='utf-8') as f:
                            f.write(self.potrace_svg_content)
                        
                        results_text.insert(tk.END, f"✅ Saved: {output_path.name}\n")
                        successful += 1
                    else:
                        results_text.insert(tk.END, f"❌ Failed to process {image_file.name}\n")
                        failed += 1
                        
                except Exception as e:
                    results_text.insert(tk.END, f"❌ Error processing {image_file.name}: {e}\n")
                    failed += 1
                
                results_text.see(tk.END)
                batch_dialog.update()
            
            # Final summary
            results_text.insert(tk.END, f"\n🎯 BATCH PROCESSING COMPLETE\n")
            results_text.insert(tk.END, f"✅ Successful: {successful}\n")
            results_text.insert(tk.END, f"❌ Failed: {failed}\n")
            results_text.insert(tk.END, f"📁 Output folder: {self.output_dir}\n")
            
            start_btn.config(state='normal')
            progress_var.set(len(image_files))
        
        start_btn.config(command=run_batch_processing)
    
    def validate_svg(self):
        """Validate SVG content"""
        if not self.potrace_svg_content:
            messagebox.showwarning("No SVG", "No SVG content to validate")
            return
        
        try:
            # Parse SVG
            root = ET.fromstring(self.potrace_svg_content)
            
            # Basic validation checks
            issues = []
            
            # Check for required attributes
            if not root.get('width') or not root.get('height'):
                issues.append("Missing width/height attributes")
            
            # Check for paths
            paths = root.findall('.//{http://www.w3.org/2000/svg}path')
            if not paths:
                issues.append("No path elements found")
            
            # Check path data
            empty_paths = 0
            for path in paths:
                if not path.get('d') or len(path.get('d', '').strip()) == 0:
                    empty_paths += 1
            
            if empty_paths > 0:
                issues.append(f"{empty_paths} empty path elements")
            
            # Size analysis
            try:
                width = float(root.get('width', 0))
                height = float(root.get('height', 0))
                if width > 1000 or height > 1000:
                    issues.append("Very large dimensions - may need optimization")
            except:
                issues.append("Invalid dimension values")
            
            # File size check
            file_size = len(self.potrace_svg_content.encode('utf-8'))
            if file_size > 100000:  # 100KB
                issues.append(f"Large file size: {file_size:,} bytes")
            
            # Report results
            if not issues:
                messagebox.showinfo("SVG Validation", "✅ SVG is valid!\n\n" +
                                  f"• {len(paths)} path elements\n" +
                                  f"• {width}×{height} dimensions\n" +
                                  f"• {file_size:,} bytes")
            else:
                messagebox.showwarning("SVG Issues", "⚠️ Issues found:\n\n" + 
                                     "\n".join(f"• {issue}" for issue in issues))
        
        except Exception as e:
            messagebox.showerror("Validation Error", f"Could not validate SVG: {e}")
    
    def save_svg_only(self):
        """Save just the SVG file"""
        if not self.potrace_svg_content:
            messagebox.showwarning("No SVG", "No SVG content to save")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Save SVG File",
            initialdir=str(self.output_dir),
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.potrace_svg_content)
                self.status_var.set(f"✅ SVG saved: {Path(filename).name}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Could not save SVG: {e}")
    
    def copy_svg_code(self):
        """Copy SVG to clipboard"""
        if self.potrace_svg_content:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.potrace_svg_content)
            self.status_var.set("✅ SVG code copied to clipboard!")
        else:
            messagebox.showwarning("No SVG", "No SVG content to copy. Process an image first.")
    
    def verify_tools(self):
        """Check if tools are installed"""
        tools_status = []
        
        # Check Windows tools
        for tool in ['mkbitmap', 'potrace']:
            try:
                subprocess.run([tool, '--version'], capture_output=True, timeout=5)
                tools_status.append(f"✅ {tool}")
            except:
                tools_status.append(f"❌ {tool}")
        
        # Check WSL2 status
        if self.wsl_available:
            tools_status.append("✅ WSL2 SVG")
        else:
            tools_status.append("⚠️ WSL2 not available")
        
        self.status_var.set(" | ".join(tools_status))
        
        if "❌" in " ".join(tools_status):
            messagebox.showwarning("Tools Missing", 
                                 "Missing tools detected!\n\n" +
                                 "Install potrace from: http://potrace.sourceforge.net/\n" +
                                 "Enable WSL2 for enhanced SVG preview")
    
    def auto_load_test_image(self):
        """Load test image if available"""
        test_files = [
            self.blueprints_dir / "German_Tank_PzKpfw_IV_F1_side.png",
            self.blueprints_dir / "German_Tank_PzKpfw_IV_F1.png",
            self.blueprints_dir / "test_tank.png"
        ]
        for test_file in test_files:
            if test_file.exists():
                self.load_image(str(test_file))
                break
    
    def load_file(self):
        """Open file dialog"""
        filename = filedialog.askopenfilename(
            title="Load Blueprint Image",
            initialdir=str(self.blueprints_dir),
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff"), ("All files", "*.*")]
        )
        if filename:
            self.load_image(filename)
    
    def load_test_image(self):
        self.auto_load_test_image()
    
    def reset_parameters(self):
        """Reset all parameters"""
        for param, value in self.default_values.items():
            getattr(self, f"{param}_var").set(value)
        
        # Update labels
        self.on_parameter_change()
        self.status_var.set("Parameters reset to defaults")
        
        if self.live_preview.get() and self.current_image:
            self.start_processing()
    
    def load_image(self, filepath):
        """Load image and start processing"""
        try:
            self.current_image = Image.open(filepath)
            self.original_image = self.current_image.copy()
            self.current_image_path = filepath  # Store path for saving
            
            # V3 FIX: Use the improved consistent display method
            self.display_original_image(filepath)
            
            self.update_pipeline_status(f"Loaded: {Path(filepath).name}")
            self.status_var.set(f"Loaded: {Path(filepath).name}")
            
            if self.live_preview.get():
                self.start_processing()
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image: {e}")
            self.update_pipeline_status(f"❌ Failed to load: {e}")
    
    def display_image(self, image, canvas, align="center"):
        """Display image on canvas with proper scaling - V3: DEPRECATED, use display_image_consistent instead"""
        # This method kept for backward compatibility but should use display_image_consistent
        self.display_image_consistent(image, canvas, "Legacy Display")
    
    def on_parameter_change(self, *args):
        """Handle parameter changes with live updates - V3 ENHANCED: Better change detection"""
        # Update parameter labels
        for param in ['blur', 'threshold', 'alphamax', 'opttolerance']:
            if hasattr(self, f"{param}_var"):
                try:
                    value = getattr(self, f"{param}_var").get()
                    getattr(self, f"{param}_label").config(text=f"{value:.2f}")
                except:
                    pass
        
        for param in ['scale', 'filter', 'turdsize']:
            if hasattr(self, f"{param}_var"):
                try:
                    value = getattr(self, f"{param}_var").get()
                    getattr(self, f"{param}_label").config(text=str(int(value)))
                except:
                    pass
        
        # V3 FIX: Trigger processing if live preview is on (with debouncing to prevent too frequent calls)
        if self.live_preview.get() and self.current_image and not self.processing:
            # Cancel any existing delayed call
            if hasattr(self, '_parameter_change_job'):
                self.root.after_cancel(self._parameter_change_job)
            
            # Schedule processing with small delay to avoid too frequent updates
            self._parameter_change_job = self.root.after(300, self.start_processing)
    
    def toggle_live_preview(self):
        """Toggle live preview mode"""
        if self.live_preview.get() and self.current_image:
            self.start_processing()
        else:
            # Clear panels 2-4 when live preview is disabled
            for canvas in [self.mkbitmap_canvas, self.svg_preview_canvas, self.final_icon_canvas]:
                canvas.delete("all")
                canvas.create_text(200, 150, text="Live Preview Disabled", 
                                 fill="gray", font=('Arial', 10))
    
    def manual_process(self):
        """Manual processing trigger"""
        if self.current_image:
            self.start_processing()
        else:
            messagebox.showwarning("No Image", "Load a blueprint image first")
    
    def start_processing(self):
        """Start processing pipeline in background thread"""
        if self.processing:
            return
        
        self.processing = True
        self.update_pipeline_status("🔄 Starting V3 live preview pipeline (all 4 panels)...")
        
        thread = threading.Thread(target=self.process_pipeline, daemon=True)
        thread.start()
    
    def process_pipeline(self):
        """Run complete processing pipeline - V3 ENHANCED: Auto-populate all 4 panels"""
        try:
            # Stage 1: Mkbitmap preprocessing
            self.root.after(0, lambda: self.update_pipeline_status("🔄 Stage 1: Running mkbitmap preprocessing..."))
            mkbitmap_result = self.run_mkbitmap()
            
            if mkbitmap_result:
                self.mkbitmap_result = mkbitmap_result  # Store for later use
                # V3: Use consistent display method
                self.root.after(0, lambda: self.display_image_consistent(mkbitmap_result, self.mkbitmap_canvas, "Mkbitmap Result"))
                self.root.after(0, lambda: self.update_pipeline_status("✅ Stage 1: Mkbitmap preprocessing complete"))
                
                # Stage 2: Potrace vector tracing
                self.root.after(0, lambda: self.update_pipeline_status("🔄 Stage 2: Running potrace vector tracing..."))
                svg_path, svg_content = self.run_potrace(mkbitmap_result)
                
                if svg_path and svg_content:
                    self.potrace_svg_path = svg_path
                    self.potrace_svg_content = svg_content
                    
                    # Stage 3: SVG preview generation
                    self.root.after(0, lambda: self.update_pipeline_status("🔄 Stage 3: Generating SVG preview..."))
                    self.root.after(0, lambda: self.display_svg_results(svg_content))
                    
                    # V3: Stage 4: Auto-populate final icon panel
                    self.root.after(0, lambda: self.update_pipeline_status("🔄 Stage 4: Auto-populating final icon preview..."))
                    self.root.after(0, self.display_final_icon_preview)
                    
                    self.root.after(0, lambda: self.update_pipeline_status("✅ V3 Full pipeline complete! All 4 panels populated automatically."))
                    self.root.after(0, lambda: self.status_var.set("✅ All Stages Complete! Live preview active across all 4 panels"))
                else:
                    self.root.after(0, lambda: self.update_pipeline_status("❌ Stage 2: Potrace tracing failed"))
                    self.root.after(0, lambda: self.status_var.set("❌ Potrace failed"))
            else:
                self.root.after(0, lambda: self.update_pipeline_status("❌ Stage 1: Mkbitmap preprocessing failed"))
                self.root.after(0, lambda: self.status_var.set("❌ Mkbitmap failed"))
                
        except Exception as e:
            self.root.after(0, lambda: self.update_pipeline_status(f"❌ Pipeline error: {e}"))
            self.root.after(0, lambda: self.status_var.set(f"❌ Error: {e}"))
        finally:
            self.processing = False
    
    def run_mkbitmap(self):
        """Run mkbitmap preprocessing"""
        if not self.current_image:
            return None
        
        try:
            # Convert to grayscale
            img = self.current_image.convert('L')
            
            # Create temporary files
            input_fd, input_path = tempfile.mkstemp(suffix='.bmp')
            output_fd, output_path = tempfile.mkstemp(suffix='.pbm')
            
            try:
                os.close(input_fd)
                os.close(output_fd)
                
                # Save input image
                img.save(input_path, 'BMP')
                
                # Build mkbitmap command
                cmd = [
                    'mkbitmap',
                    '-s', str(int(self.scale_var.get())),
                    '-b', str(self.blur_var.get()),
                    '-t', str(self.threshold_var.get()),
                    '-f', str(int(self.filter_var.get())),
                    '-o', output_path,
                    input_path
                ]
                
                # Run mkbitmap
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    processed_img = Image.open(output_path).convert('L')
                    return processed_img
                else:
                    print(f"Mkbitmap error: {result.stderr}")
                    return None
                    
            finally:
                # Cleanup temporary files
                for path in [input_path, output_path]:
                    try:
                        if os.path.exists(path):
                            os.unlink(path)
                    except:
                        pass
                        
        except Exception as e:
            print(f"Mkbitmap exception: {e}")
            return None
    
    def run_potrace(self, input_image):
        """Run potrace vector tracing"""
        if not input_image:
            return None, None
        
        try:
            # Create temporary files
            input_fd, input_path = tempfile.mkstemp(suffix='.pbm')
            output_fd, output_path = tempfile.mkstemp(suffix='.svg')
            
            try:
                os.close(input_fd)
                os.close(output_fd)
                
                # Save bitmap image
                if input_image.mode != '1':
                    input_image = input_image.convert('1')
                input_image.save(input_path, 'PPM')
                
                # Build potrace command
                cmd = [
                    'potrace', '--svg',
                    '--turnpolicy', self.turnpolicy_var.get(),
                    '--turdsize', str(int(self.turdsize_var.get())),
                    '--alphamax', str(self.alphamax_var.get()),
                    '--opttolerance', str(self.opttolerance_var.get()),
                    '--output', output_path,
                    input_path
                ]
                
                # Run potrace
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    # Read SVG content
                    with open(output_path, 'r', encoding='utf-8') as f:
                        svg_content = f.read()
                    
                    # Create permanent copy
                    temp_svg = tempfile.NamedTemporaryFile(suffix='.svg', delete=False)
                    temp_svg.write(svg_content.encode('utf-8'))
                    temp_svg.close()
                    
                    return temp_svg.name, svg_content
                else:
                    print(f"Potrace error: {result.stderr}")
                    return None, None
                    
            finally:
                # Cleanup temporary files
                for path in [input_path, output_path]:
                    try:
                        if os.path.exists(path):
                            os.unlink(path)
                    except:
                        pass
                        
        except Exception as e:
            print(f"Potrace exception: {e}")
            return None, None
    
    def display_svg_results(self, svg_content):
        """Display SVG results in all relevant places - V3: Enhanced with final icon auto-population"""
        # Display SVG preview (using WSL2 if available)
        self.display_svg_preview(svg_content)
        
        # Display SVG info
        self.display_svg_info(svg_content)
        
        # Display SVG code
        self.display_svg_code(svg_content)
    
    def display_svg_info(self, svg_content):
        """Display SVG analysis information"""
        if not svg_content:
            info_text = "No SVG content available"
        else:
            try:
                root = ET.fromstring(svg_content)
                width = root.get('width', 'Unknown')
                height = root.get('height', 'Unknown')
                viewbox = root.get('viewBox', 'None')
                
                paths = root.findall('.//{http://www.w3.org/2000/svg}path')
                path_count = len(paths)
                total_path_data = sum(len(path.get('d', '')) for path in paths)
                file_size = len(svg_content.encode('utf-8'))
                
                # Calculate complexity score
                complexity = "Low"
                if path_count > 10 or total_path_data > 1000:
                    complexity = "Medium"
                if path_count > 50 or total_path_data > 5000:
                    complexity = "High"
                
                info_text = f"""✅ SVG VECTOR ANALYSIS - V3

📐 DIMENSIONS
• Width: {width}
• Height: {height}  
• ViewBox: {viewbox}

🎯 VECTOR DATA
• Path Elements: {path_count}
• Path Complexity: {total_path_data:,} characters
• Complexity Level: {complexity}
• File Size: {file_size:,} bytes

🔧 PROCESSING SETTINGS
• Blur Radius: {self.blur_var.get():.1f}
• Threshold: {self.threshold_var.get():.2f}
• Scale Factor: {self.scale_var.get()}x
• Filter Passes: {self.filter_var.get()}
• Turn Policy: {self.turnpolicy_var.get()}
• Noise Removal: {self.turdsize_var.get()}
• Curve Smoothing: {self.alphamax_var.get():.2f}
• Optimization: {self.opttolerance_var.get():.2f}

💡 OPTIMIZATION TIPS
• For simpler paths: Increase optimization tolerance
• For sharper edges: Decrease curve smoothing  
• For cleaner result: Increase noise removal
• For smaller files: Increase optimization

🎮 V3 LIVE PREVIEW ACTIVE!
All 4 panels auto-update with parameter changes.
Final icon preview ready for export!"""
                
            except Exception as e:
                info_text = f"⚠️ SVG parsing error: {e}\n\nRaw file size: {len(svg_content):,} bytes"
        
        self.svg_info_text.delete(1.0, tk.END)
        self.svg_info_text.insert(1.0, info_text)
    
    def display_svg_code(self, svg_content):
        """Display SVG source code with syntax highlighting"""
        self.svg_code_text.delete(1.0, tk.END)
        if svg_content:
            self.svg_code_text.insert(1.0, svg_content)
            self.highlight_svg_syntax()
    
    def highlight_svg_syntax(self):
        """Apply syntax highlighting to SVG code"""
        # Configure tags
        self.svg_code_text.tag_configure("element", foreground="#0066CC")
        self.svg_code_text.tag_configure("attribute", foreground="#CC0000")
        self.svg_code_text.tag_configure("string", foreground="#006600")
        self.svg_code_text.tag_configure("comment", foreground="#666666", font=('Consolas', 10, 'italic'))
        
        content = self.svg_code_text.get(1.0, tk.END)
        
        # Highlight XML elements
        for match in re.finditer(r'<(/?)(\w+)', content):
            start = f"1.0+{match.start(2)}c"
            end = f"1.0+{match.end(2)}c"
            self.svg_code_text.tag_add("element", start, end)
        
        # Highlight attributes
        for match in re.finditer(r'(\w+)=', content):
            start = f"1.0+{match.start(1)}c"
            end = f"1.0+{match.end(1)}c"
            self.svg_code_text.tag_add("attribute", start, end)
        
        # Highlight strings
        for match in re.finditer(r'"[^"]*"', content):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.svg_code_text.tag_add("string", start, end)
        
        # Highlight comments
        for match in re.finditer(r'<!--.*?-->', content, re.DOTALL):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.svg_code_text.tag_add("comment", start, end)
    
    def load_preset(self, preset_name):
        """Load parameter presets optimized for different use cases"""
        presets = {
            "technical": {
                "name": "Technical Drawing",
                "description": "Sharp edges, precise lines, minimal smoothing",
                "blur": 1.0, "threshold": 0.45, "scale": 2, "filter": 2,
                "turnpolicy": "minority", "turdsize": 2, "alphamax": 1.0, "opttolerance": 0.2
            },
            "smooth": {
                "name": "Smooth Silhouette", 
                "description": "Rounded curves, simplified shapes",
                "blur": 2.0, "threshold": 0.4, "scale": 3, "filter": 4,
                "turnpolicy": "minority", "turdsize": 5, "alphamax": 0.8, "opttolerance": 0.5
            },
            "detail": {
                "name": "High Detail",
                "description": "Maximum detail retention, complex paths",
                "blur": 0.5, "threshold": 0.5, "scale": 2, "filter": 1,
                "turnpolicy": "black", "turdsize": 1, "alphamax": 1.2, "opttolerance": 0.1
            }
        }
        
        if preset_name in presets:
            preset = presets[preset_name]
            
            # Apply preset values
            for param in ['blur', 'threshold', 'scale', 'filter', 'turnpolicy', 'turdsize', 'alphamax', 'opttolerance']:
                if param in preset:
                    getattr(self, f"{param}_var").set(preset[param])
            
            # Update parameter labels
            self.on_parameter_change()
            
            self.update_pipeline_status(f"📋 Applied preset: {preset['name']} - {preset['description']}")
            self.status_var.set(f"Loaded {preset['name']} preset")
            
            # Auto-process if live preview is on
            if self.live_preview.get() and self.current_image:
                self.start_processing()
    
    def save_result(self):
        """Save complete processing results"""
        if not self.potrace_svg_content:
            messagebox.showwarning("No Result", "No SVG content to save. Process an image first.")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Save Silhouette Icon Files",
            initialdir=str(self.output_dir),
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                base_path = Path(filename).with_suffix('')
                
                # Save main SVG file
                svg_path = base_path.with_suffix('.svg')
                with open(str(svg_path), 'w', encoding='utf-8') as f:
                    f.write(self.potrace_svg_content)
                
                # Save processing parameters
                params_file = base_path.with_suffix('.json')
                params = {
                    "processing_timestamp": str(datetime.datetime.now()),
                    "version": "v3",
                    "source_image": getattr(self, 'current_image_path', 'unknown'),
                    "mkbitmap_parameters": {
                        "blur_radius": self.blur_var.get(),
                        "threshold": self.threshold_var.get(),
                        "scale_factor": self.scale_var.get(),
                        "filter_passes": self.filter_var.get()
                    },
                    "potrace_parameters": {
                        "turn_policy": self.turnpolicy_var.get(),
                        "noise_removal": self.turdsize_var.get(),
                        "curve_smoothing": self.alphamax_var.get(),
                        "optimization": self.opttolerance_var.get()
                    },
                    "svg_analysis": {
                        "file_size_bytes": len(self.potrace_svg_content.encode('utf-8')),
                        "paths_count": len(ET.fromstring(self.potrace_svg_content).findall('.//{http://www.w3.org/2000/svg}path')) if self.potrace_svg_content else 0
                    }
                }
                
                with open(str(params_file), 'w') as f:
                    json.dump(params, f, indent=2)
                
                # Save preview PNG if mkbitmap result exists
                if hasattr(self, 'mkbitmap_result') and self.mkbitmap_result:
                    png_path = base_path.with_suffix('.png')
                    self.mkbitmap_result.save(str(png_path), 'PNG')
                    saved_files = f"• {svg_path.name} (main SVG)\n• {png_path.name} (preview)\n• {params_file.name} (parameters)"
                else:
                    saved_files = f"• {svg_path.name} (main SVG)\n• {params_file.name} (parameters)"
                
                self.status_var.set(f"✅ Saved: {svg_path.name}")
                self.update_pipeline_status(f"✅ Files saved to: {svg_path.parent}")
                
                messagebox.showinfo("Files Saved", 
                                  f"Silhouette icon saved successfully!\n\n{saved_files}")
                                  
            except Exception as e:
                messagebox.showerror("Save Error", f"Could not save files: {e}")


def main():
    """Main function to run the enhanced WWII Silhouette Icon Generator"""
    root = tk.Tk()
    
    # Set application icon if available
    try:
        # You could add an icon file here
        # root.iconbitmap("icon.ico")
        pass
    except:
        pass
    
    # Initialize the application
    app = WSL2MkbitmapPotraceGUI(root)
    
    # Run the GUI
    root.mainloop()


if __name__ == "__main__":
    main()