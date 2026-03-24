from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from urllib import error, request


VIDEO_FILETYPES = [
    ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv"),
    ("All files", "*.*"),
]


class LocalApiTestApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("DriveGuard AI Local API Tester")
        self.root.geometry("980x760")

        self.base_url_var = tk.StringVar(value="http://127.0.0.1:8000")
        self.config_path_var = tk.StringVar(value="config.toml")
        self.mode_var = tk.StringVar(value="video")
        self.source_label_var = tk.StringVar(value="No video selected")
        self.status_var = tk.StringVar(value="Ready")

        self.selected_video: str | None = None
        self.selected_batch: list[str] = []
        self.worker_thread: threading.Thread | None = None

        self._build_layout()

    def run(self) -> None:
        self.root.mainloop()

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        connection_frame = ttk.LabelFrame(container, text="Connection", padding=12)
        connection_frame.pack(fill="x")

        ttk.Label(connection_frame, text="Base URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(connection_frame, textvariable=self.base_url_var, width=50).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        ttk.Label(connection_frame, text="Config Path").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(connection_frame, textvariable=self.config_path_var, width=50).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0)
        )
        connection_frame.columnconfigure(1, weight=1)

        source_frame = ttk.LabelFrame(container, text="Request", padding=12)
        source_frame.pack(fill="x", pady=(12, 0))

        mode_frame = ttk.Frame(source_frame)
        mode_frame.pack(fill="x")
        for value, label in [("video", "Single Video"), ("batch", "Batch Clips")]:
            ttk.Radiobutton(
                mode_frame,
                text=label,
                variable=self.mode_var,
                value=value,
                command=self._refresh_mode_ui,
            ).pack(side="left", padx=(0, 12))

        select_frame = ttk.Frame(source_frame)
        select_frame.pack(fill="x", pady=(10, 0))

        self.select_button = ttk.Button(select_frame, text="Choose Video", command=self._choose_source)
        self.select_button.pack(side="left")
        ttk.Label(select_frame, textvariable=self.source_label_var).pack(side="left", padx=12)

        action_frame = ttk.Frame(source_frame)
        action_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(action_frame, text="Health Check", command=self._health_check).pack(side="left")
        ttk.Button(action_frame, text="Analyze", command=self._analyze).pack(side="left", padx=(8, 0))

        response_frame = ttk.LabelFrame(container, text="Response", padding=12)
        response_frame.pack(fill="both", expand=True, pady=(12, 0))

        self.response_box = scrolledtext.ScrolledText(response_frame, wrap=tk.WORD, height=28)
        self.response_box.pack(fill="both", expand=True)

        footer = ttk.Frame(container)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(anchor="w")

        self._refresh_mode_ui()

    def _refresh_mode_ui(self) -> None:
        if self.mode_var.get() == "video":
            self.select_button.configure(text="Choose Video")
            self.source_label_var.set(Path(self.selected_video).name if self.selected_video else "No video selected")
        else:
            self.select_button.configure(text="Choose Clips")
            self.source_label_var.set(
                f"{len(self.selected_batch)} clip(s) selected" if self.selected_batch else "No batch selected"
            )

    def _choose_source(self) -> None:
        if self.mode_var.get() == "video":
            video_path = filedialog.askopenfilename(title="Choose a video", filetypes=VIDEO_FILETYPES)
            if video_path:
                self.selected_video = video_path
                self.selected_batch = []
        else:
            video_paths = filedialog.askopenfilenames(title="Choose video clips", filetypes=VIDEO_FILETYPES)
            if video_paths:
                self.selected_batch = list(video_paths)
                self.selected_video = None
        self._refresh_mode_ui()

    def _health_check(self) -> None:
        self._start_request_thread("GET", "/health", None)

    def _analyze(self) -> None:
        if self.mode_var.get() == "video":
            if not self.selected_video:
                messagebox.showwarning("Missing video", "Choose a video before calling the API.")
                return
            payload = {
                "video_path": self.selected_video,
                "config_path": self.config_path_var.get(),
            }
            self._start_request_thread("POST", "/analyze/video", payload)
            return

        if not self.selected_batch:
            messagebox.showwarning("Missing clips", "Choose one or more clips before calling the API.")
            return
        payload = {
            "video_paths": self.selected_batch,
            "config_path": self.config_path_var.get(),
        }
        self._start_request_thread("POST", "/analyze/batch", payload)

    def _start_request_thread(self, method: str, path: str, payload: dict | None) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Request running", "A request is already in progress.")
            return

        self.status_var.set(f"Calling {path} ...")
        self.worker_thread = threading.Thread(
            target=self._perform_request,
            args=(method, path, payload),
            daemon=True,
        )
        self.worker_thread.start()

    def _perform_request(self, method: str, path: str, payload: dict | None) -> None:
        url = f"{self.base_url_var.get().rstrip('/')}{path}"
        body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = request.Request(url=url, data=body, headers=headers, method=method)

        try:
            with request.urlopen(req, timeout=3600) as response:
                content = response.read().decode("utf-8")
                formatted = self._format_response(content)
                self.root.after(0, self._show_response, formatted, f"Success {response.status}")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            self.root.after(0, self._show_response, details, f"HTTP error {exc.code}")
        except Exception as exc:
            self.root.after(0, self._show_response, str(exc), "Request failed")

    def _show_response(self, content: str, status: str) -> None:
        self.response_box.delete("1.0", tk.END)
        self.response_box.insert(tk.END, content)
        self.status_var.set(status)

    @staticmethod
    def _format_response(content: str) -> str:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return content
        return json.dumps(parsed, indent=2)


def main() -> None:
    app = LocalApiTestApp()
    app.run()


if __name__ == "__main__":
    main()
