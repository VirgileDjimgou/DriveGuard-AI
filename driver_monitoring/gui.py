from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

import cv2
from PIL import Image, ImageTk

from driver_monitoring.pipeline import DriverMonitoringPipeline, FrameAnalysis, PipelineConfig
from driver_monitoring.reporting import BatchReport, SessionReport


VIDEO_FILETYPES = [
    ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv"),
    ("All files", "*.*"),
]


class DriverMonitoringApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Driver Monitoring Prototype")
        self.root.geometry("1280x860")
        self.root.configure(bg="#101820")

        self.mode_var = tk.StringVar(value="webcam")
        self.source_label_var = tk.StringVar(value="Webcam 0 selected")
        self.status_var = tk.StringVar(value="Ready")
        self.score_var = tk.StringVar(value="Driver score: -")
        self.events_var = tk.StringVar(value="Events: none")
        self.summary_var = tk.StringVar(value="Summary: none")

        self.selected_video: Optional[str] = None
        self.selected_batch: List[str] = []
        self.current_frame_image = None
        self.processing_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        self._build_layout()
        self._refresh_mode_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def run(self) -> None:
        self.root.mainloop()

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(container, text="Source Selection", padding=12)
        controls.pack(fill="x")

        modes = ttk.Frame(controls)
        modes.pack(fill="x", pady=(0, 10))
        for value, label in [("webcam", "Webcam"), ("video", "Single Video"), ("batch", "Batch Clips")]:
            ttk.Radiobutton(
                modes,
                text=label,
                variable=self.mode_var,
                value=value,
                command=self._refresh_mode_ui,
            ).pack(side="left", padx=(0, 12))

        source_actions = ttk.Frame(controls)
        source_actions.pack(fill="x")

        self.select_button = ttk.Button(source_actions, text="Choose Source", command=self._choose_source)
        self.select_button.pack(side="left")

        ttk.Label(source_actions, textvariable=self.source_label_var).pack(side="left", padx=12)

        run_actions = ttk.Frame(controls)
        run_actions.pack(fill="x", pady=(12, 0))

        self.start_button = ttk.Button(run_actions, text="Start Analysis", command=self._start_analysis)
        self.start_button.pack(side="left")

        self.stop_button = ttk.Button(run_actions, text="Stop", command=self._stop_analysis)
        self.stop_button.pack(side="left", padx=(8, 0))

        preview_frame = ttk.LabelFrame(container, text="Analysis Preview", padding=12)
        preview_frame.pack(fill="both", expand=True, pady=(12, 0))

        self.video_label = ttk.Label(preview_frame, anchor="center")
        self.video_label.pack(fill="both", expand=True)

        footer = ttk.Frame(container)
        footer.pack(fill="x", pady=(12, 0))

        ttk.Label(footer, textvariable=self.status_var).pack(anchor="w")
        ttk.Label(footer, textvariable=self.score_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(footer, textvariable=self.events_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(footer, textvariable=self.summary_var).pack(anchor="w", pady=(4, 0))

    def _refresh_mode_ui(self) -> None:
        mode = self.mode_var.get()
        if mode == "webcam":
            self.source_label_var.set("Webcam 0 selected")
            self.select_button.configure(text="Choose Webcam")
        elif mode == "video":
            label = Path(self.selected_video).name if self.selected_video else "No video selected"
            self.source_label_var.set(label)
            self.select_button.configure(text="Choose Video")
        else:
            count = len(self.selected_batch)
            label = f"{count} clip(s) selected" if count else "No batch selected"
            self.source_label_var.set(label)
            self.select_button.configure(text="Choose Clips")

    def _choose_source(self) -> None:
        mode = self.mode_var.get()
        if mode == "webcam":
            self.selected_video = None
            self.selected_batch = []
            self.source_label_var.set("Webcam 0 selected")
            return

        if mode == "video":
            video_path = filedialog.askopenfilename(title="Choose a video", filetypes=VIDEO_FILETYPES)
            if video_path:
                self.selected_video = video_path
                self.selected_batch = []
                self.source_label_var.set(Path(video_path).name)
            return

        video_paths = filedialog.askopenfilenames(title="Choose video clips", filetypes=VIDEO_FILETYPES)
        if video_paths:
            self.selected_batch = list(video_paths)
            self.selected_video = None
            self.source_label_var.set(f"{len(self.selected_batch)} clip(s) selected")

    def _start_analysis(self) -> None:
        if self.processing_thread and self.processing_thread.is_alive():
            messagebox.showinfo("Analysis running", "An analysis is already running.")
            return

        config = self._build_config()
        if config is None:
            return

        self.stop_event.clear()
        self.status_var.set("Starting analysis...")
        self.processing_thread = threading.Thread(
            target=self._run_analysis_loop,
            args=(config,),
            daemon=True,
        )
        self.processing_thread.start()

    def _build_config(self) -> Optional[PipelineConfig]:
        mode = self.mode_var.get()
        if mode == "webcam":
            return PipelineConfig(source_mode="webcam", source=0)
        if mode == "video":
            if not self.selected_video:
                messagebox.showwarning("Missing video", "Choose a video file before starting analysis.")
                return None
            return PipelineConfig(source_mode="video", source=self.selected_video)
        if not self.selected_batch:
            messagebox.showwarning("Missing clips", "Choose one or more clips before starting batch analysis.")
            return None
        return PipelineConfig(source_mode="batch", source=self.selected_batch)

    def _run_analysis_loop(self, config: PipelineConfig) -> None:
        pipeline = DriverMonitoringPipeline(config)
        source = pipeline.create_source()

        try:
            source.open()
            last_timestamp_seconds = 0.0
            while not self.stop_event.is_set():
                packet = source.read()
                if packet is None:
                    break

                last_timestamp_seconds = packet.timestamp_seconds
                analysis = pipeline.process_packet(packet)
                self.root.after(0, self._update_preview, analysis)
                completed_reports = pipeline.drain_completed_reports()
                for report in completed_reports:
                    self.root.after(0, self._handle_completed_session, report)
                time.sleep(0.01)

            batch_report = pipeline.finalize_run(last_timestamp_seconds)
            completed_reports = pipeline.drain_completed_reports()
            for report in completed_reports:
                self.root.after(0, self._handle_completed_session, report)
            self.root.after(0, self._handle_batch_completion, batch_report, self.stop_event.is_set())
            final_status = "Analysis stopped" if self.stop_event.is_set() else "Analysis complete"
            self.root.after(0, self.status_var.set, final_status)
        except Exception as exc:
            self.root.after(0, messagebox.showerror, "Analysis error", str(exc))
            self.root.after(0, self.status_var.set, "Analysis failed")
        finally:
            source.close()

    def _update_preview(self, analysis: FrameAnalysis) -> None:
        frame_bgr = analysis.annotated_frame
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        max_width = 1180
        max_height = 620
        height, width = frame_rgb.shape[:2]
        scale = min(max_width / width, max_height / height)
        resized = cv2.resize(frame_rgb, (int(width * scale), int(height * scale)))

        image = Image.fromarray(resized)
        photo = ImageTk.PhotoImage(image=image)
        self.current_frame_image = photo
        self.video_label.configure(image=photo)

        source_name = Path(analysis.packet.source_name).name if analysis.packet.source_name != "0" else "Webcam 0"
        self.status_var.set(f"Processing: {source_name} | Frame {analysis.packet.frame_index}")
        self.score_var.set(f"Driver score: {analysis.score_result.score}")

        if analysis.events:
            summary = " | ".join(event.event_type for event in analysis.events[:3])
            self.events_var.set(f"Events: {summary}")
        else:
            self.events_var.set("Events: none")
        self.summary_var.set(
            "Summary: "
            f"{analysis.session_state.closed_incident_count + analysis.session_state.active_incident_count} incident(s) | "
            f"{analysis.session_state.duration_seconds:.1f}s"
        )

    def _handle_completed_session(self, report: SessionReport) -> None:
        source_name = Path(report.source_name).name if report.source_name != "0" else "Webcam 0"
        self.summary_var.set(
            "Summary: "
            f"{source_name} finished | score {report.score_result.score} | "
            f"{len(report.incidents)} incident(s)"
        )

    def _handle_batch_completion(self, report: BatchReport, stopped: bool) -> None:
        self.summary_var.set(
            "Summary: "
            f"{report.total_sources} source(s) | {report.total_incidents} incident(s) | "
            f"avg score {report.average_score:.1f}"
        )
        title = "Analysis stopped" if stopped else "Analysis complete"
        messagebox.showinfo(
            title,
            (
                f"Sources processed: {report.total_sources}\n"
                f"Total incidents: {report.total_incidents}\n"
                f"Average score: {report.average_score:.1f}\n"
                f"Exports: {report.output_directory}"
            ),
        )

    def _stop_analysis(self) -> None:
        self.stop_event.set()
        self.status_var.set("Stopping analysis...")

    def _on_close(self) -> None:
        self.stop_event.set()
        self.root.destroy()
