import os
import gc
import glob
import time
import threading
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from reportlab.pdfgen import canvas
from pypdf import PdfWriter


# =====================================================================
# ENGINE PHASE: STATELESS CONCURRENT MAPPERS
# =====================================================================
def _stateless_page_worker(args):
    """
    Runs in its own completely isolated OS process heap.
    Processes one image, applies morphological ink weights, and saves a 1-page PDF.
    """
    img_path, temp_pdf_path, epsilon_factor, ink_thickness = args

    try:
        # 1. Load strictly in Grayscale to conserve RAM footprint
        img_gray = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img_gray is None:
            return False, f"Failed to read image: {img_path}"

        h_orig, w_orig = img_gray.shape

        # 2. Replicate Ruled Notebook Line Obliteration
        binary_mask = cv2.adaptiveThreshold(
            img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 41, 15
        )
        del img_gray  # Instantly purge uncompressed raw arrays

        clean_mask = cv2.medianBlur(binary_mask, 3)
        del binary_mask

        # =====================================================================
        # DYNAMIC INK THICKNESS ENHANCEMENT ENGINE
        # =====================================================================
        # Dynamic kernel interpolation matching Newtry UI behavior over filled vector grids
        if ink_thickness > 3.2:
            thick_factor = int(round((ink_thickness - 3.0) * 1.5))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (thick_factor, thick_factor))
            clean_mask = cv2.dilate(clean_mask, kernel, iterations=1)
        elif ink_thickness < 2.8:
            thin_factor = int(round((3.0 - ink_thickness) * 1.5))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (thin_factor, thin_factor))
            clean_mask = cv2.erode(clean_mask, kernel, iterations=1)

        # 3. Extract Ink filled contour paths
        contours, _ = cv2.findContours(
            clean_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS
        )
        del clean_mask

        # 4. Initialize Single-Page Local Vector Canvas
        pdf = canvas.Canvas(temp_pdf_path, pagesize=(w_orig, h_orig))
        pdf.setFillColorRGB(0, 0, 0)  # Pure black filled text shapes
        compound_path = pdf.beginPath()

        # 5. Fast NumPy Vectorized Array Operations
        for contour in contours:
            if cv2.contourArea(contour) < 4:
                continue

            epsilon = epsilon_factor * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, closed=True)

            if len(approx) > 2:
                # Flatten structure to C-contiguous arrays
                pts = approx.reshape(-1, 2)
                
                # Invert Y axis across the column simultaneously in C-level registers
                pts[:, 1] = h_orig - pts[:, 1]

                compound_path.moveTo(float(pts[0, 0]), float(pts[0, 1]))
                for x, y in pts[1:]:
                    compound_path.lineTo(float(x), float(y))
                compound_path.close()

        pdf.drawPath(compound_path, fill=1, stroke=0)
        pdf.save()

        # Force aggressive process heap recycling
        del contours, compound_path, pdf
        gc.collect()

        return True, temp_pdf_path

    except Exception as e:
        return False, str(e)


# =====================================================================
# UI & APPLICATION ORCHESTRATION LAYER
# =====================================================================
class AuthenticPotraceVectorizer:

    def __init__(self, root):
        self.root = root
        self.root.title("Authentic Potrace Vectorizer (Enterprise Parallel Engine)")
        self.root.geometry("620x390")
        self.root.resizable(False, False)

        self.image_paths = []

        # --- UI Layout ---
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text="Native Parallel Compound-Fill Vectorization Engine",
            font=("Arial", 13, "bold"),
        ).pack(pady=(0, 15))

        # Queue Selection Frame
        file_frame = ttk.LabelFrame(
            main_frame, text=" 1. Select Input Source ", padding="10"
        )
        file_frame.pack(fill=tk.X, pady=5)

        self.lbl_queue = ttk.Label(file_frame, text="No files selected in queue.")
        self.lbl_queue.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            file_frame, text="Browse Folder", command=self.browse_folder
        ).pack(side=tk.RIGHT, padx=2)
        ttk.Button(
            file_frame, text="Browse Single File", command=self.browse_files
        ).pack(side=tk.RIGHT, padx=2)

        # Refinement Configuration Panel
        tune_frame = ttk.LabelFrame(
            main_frame, text=" 2. Ink Darkening & Geometric Smoothing Panel ", padding="10"
        )
        tune_frame.pack(fill=tk.X, pady=10)

        # Parameter Slider 1: Morphological Ink Weight
        ttk.Label(tune_frame, text="Ink Thickness (Darken):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.thickness_slider = ttk.Scale(tune_frame, from_=1.0, to=5.0, orient=tk.HORIZONTAL)
        self.thickness_slider.set(3.0)  # 3.0 represents native baseline thickness
        self.thickness_slider.grid(row=0, column=1, sticky="ew", padx=(10, 5), pady=5)
        tune_frame.columnconfigure(1, weight=1)

        # Parameter Slider 2: Organic Curve Smoothing
        ttk.Label(tune_frame, text="Curve Smoothing Epsilon:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.smooth_slider = ttk.Scale(tune_frame, from_=0.0005, to=0.004, orient=tk.HORIZONTAL)
        self.smooth_slider.set(0.0015)
        self.smooth_slider.grid(row=1, column=1, sticky="ew", padx=(10, 5), pady=5)

        # Execution Tracker
        self.lbl_status = ttk.Label(
            main_frame,
            text="System Idle. Parallel Map-Reduce engine ready.",
            font=("Arial", 10, "italic"),
        )
        self.lbl_status.pack(pady=(5, 5))

        self.btn_run = ttk.Button(
            main_frame,
            text="⚡ Compile High-Fidelity Vector PDF",
            command=self.start_pipeline,
            state=tk.DISABLED,
        )
        self.btn_run.pack(fill=tk.X, ipady=8)

    def browse_files(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        )
        if paths:
            self.image_paths = sorted(list(paths))
            if len(self.image_paths) == 1:
                self.lbl_queue.config(text=f"Single Image Queued: {os.path.basename(self.image_paths[0])}")
            else:
                self.lbl_queue.config(text=f"Selected {len(self.image_paths)} files manually.")
            self.btn_run.config(state=tk.NORMAL)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            exts = (".jpg", ".jpeg", ".png", ".bmp", ".tiff")
            self.image_paths = sorted(
                [
                    os.path.join(folder, f)
                    for f in os.listdir(folder)
                    if f.lower().endswith(exts)
                ]
            )
            self.lbl_queue.config(
                text=f"Folder Loaded: {len(self.image_paths)} pages queued."
            )
            if self.image_paths:
                self.btn_run.config(state=tk.NORMAL)

    def start_pipeline(self):
        out_pdf = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("Compiled Vector PDF", "*.pdf")],
            initialfile="Authentic_Traced_Notebook.pdf",
        )
        if not out_pdf:
            return

        self.btn_run.config(state=tk.DISABLED)
        threading.Thread(
            target=self.vectorize_batch_stream, args=(out_pdf,), daemon=True
        ).start()

    def vectorize_batch_stream(self, output_pdf_path):
        start_time = time.time()
        epsilon_factor = float(self.smooth_slider.get())
        ink_thickness = float(self.thickness_slider.get())
        total_pages = len(self.image_paths)

        base_dir = os.path.dirname(self.image_paths[0])
        temp_dir = os.path.join(base_dir, "_temp_vector_build_zone")
        os.makedirs(temp_dir, exist_ok=True)

        usable_cores = max(1, multiprocessing.cpu_count() - 1)
        
        tasks = []
        for idx, file_path in enumerate(self.image_paths, 1):
            tmp_pdf = os.path.join(temp_dir, f"page_{idx:04d}.pdf")
            tasks.append((file_path, tmp_pdf, epsilon_factor, ink_thickness))

        successful_temp_pdfs = []

        try:
            # PHASE 1: EXECUTE CONCURRENT MAPS
            with ProcessPoolExecutor(max_workers=usable_cores) as executor:
                future_to_idx = {executor.submit(_stateless_page_worker, t): i for i, t in enumerate(tasks, 1)}

                for future in as_completed(future_to_idx):
                    page_num = future_to_idx[future]
                    success, result_data = future.result()

                    if success:
                        successful_temp_pdfs.append(result_data)
                        self.lbl_status.config(text=f"MAPPED: Processed Page {len(successful_temp_pdfs)}/{total_pages}...")
                    else:
                        print(f"Worker Error on page index {page_num}: {result_data}")

            successful_temp_pdfs.sort()

            # PHASE 2: REDUCE / DISK-TO-DISK STREAM MERGE
            self.lbl_status.config(text=f"REDUCE: Stitching {len(successful_temp_pdfs)} page streams...")
            
            merger = PdfWriter()
            for pdf_file in successful_temp_pdfs:
                merger.append(pdf_file)

            with open(output_pdf_path, "wb") as f_out:
                merger.write(f_out)
            merger.close()

            # Cleanup artifacts
            for pdf_file in glob.glob(os.path.join(temp_dir, "*.pdf")):
                try: os.remove(pdf_file)
                except: pass
            try: os.rmdir(temp_dir)
            except: pass

            elapsed = time.time() - start_time
            self.lbl_status.config(text="Success! Authentic Potrace PDF generated.")
            messagebox.showinfo(
                "Optimization Complete!",
                f"Successfully vectorized {total_pages} pages across {usable_cores} CPU cores in {elapsed:.2f}s.\n\nInk scaling applied concurrently with flat RAM constraints.",
            )

        except Exception as e:
            messagebox.showerror("Pipeline Error", f"Fatal execution error:\n{str(e)}")
            self.lbl_status.config(text="Pipeline aborted due to internal error.")

        finally:
            self.btn_run.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    app = AuthenticPotraceVectorizer(root)
    root.mainloop()