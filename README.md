# Authentic Potrace Vectorizer (Enterprise Parallel Engine)

A high-performance, memory-efficient Python application designed to convert scanned images, document pages, or handwritten notes into clean, high-fidelity vector PDFs. 

By leveraging native multiprocessing for parallel image transformation and vectorized NumPy contour plotting, this tool handles massive document queues concurrently under strict RAM constraints.

---

## 🚀 Features

*   **Multiprocessing Map-Reduce Architecture:** Isolates processing overhead into stateless OS process heaps, allowing multiple pages to compile simultaneously while squeezing max performance out of multi-core CPUs.
*   **Ruled Line & Noise Obliteration:** Built-in adaptive Gaussian thresholding and median blurring to automatically eliminate background lines and scanner noise.
*   **Dynamic Ink Thickness Adjustment:** Features an interactive slider mechanism that handles morphological dilation and erosion to smoothly darken or thin out stroke ink weights before processing.
*   **Organic Curve Smoothing:** Leverages the Douglas-Peucker algorithm ($\text{approxPolyDP}$) with customizable epsilon parameters to strike the perfect balance between accurate contour matching and geometric path optimization.
*   **Zero-Overhead Vector Generation:** Draws single-page local vector paths directly into individual PDF files using `ReportLab` streams before conducting a low-footprint sequential file merge with `pypdf`.

---



**Workflow**
[ Input Files Queue ]
             │
      (Parallel Map) ──> Spawns workers across (CPU Cores - 1) 
             │
             ├──> Worker 1: Grayscale -> Adaptive Threshold -> Morphological Edit -> Path Generation -> Temp PDF
             ├──> Worker 2: Grayscale -> Adaptive Threshold -> Morphological Edit -> Path Generation -> Temp PDF
             └──> Worker N: Grayscale -> Adaptive Threshold -> Morphological Edit -> Path Generation -> Temp PDF
             │
     (Parallel Reduce) ──> Aggregates sequential stream buffer
             │
   [ Final Traced PDF ] ──> Automated Temp Cache Evacuation & Memory Flush
