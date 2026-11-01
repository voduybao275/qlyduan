# ui/man_hinh/resize_hinh.py
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageOps
except ImportError:  # chưa cài Pillow thì vẫn mở được app
    Image = None
    ImageOps = None

SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")
INVALID_NAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def tao(ung_dung):
    """Vẽ màn hình Resize hình vào vùng nội dung dùng chung."""
    if Image is None:
        tk.Label(ung_dung.vung_noi_dung, text="📷 RESIZE HÌNH ẢNH",
                 font=("Arial", 18, "bold"), bg="#f0f0f0").pack(pady=30)
        tk.Label(
            ung_dung.vung_noi_dung,
            text="Chưa cài thư viện Pillow.\n\n"
                 "Mở Command Prompt và chạy:\n"
                 "py -3 -m pip install pillow\n\n"
                 "Sau đó khởi động lại ứng dụng.",
            bg="#f0f0f0", justify="center", font=("Arial", 12)
        ).pack()
        return None

    return ManHinhResizeHinh(ung_dung)


class ManHinhResizeHinh:
    def __init__(self, ung_dung):
        self.ung_dung = ung_dung
        self.root = ung_dung.root
        self.files = []

        self.width_var = tk.StringVar(value="900")
        self.height_var = tk.StringVar(value="600")
        self.keep_ratio_var = tk.BooleanVar(value=True)
        self.no_enlarge_var = tk.BooleanVar(value=False)
        self.to_webp_var = tk.BooleanVar(value=False)
        self.output_var = tk.StringVar()
        self.rename_var = tk.BooleanVar(value=True)
        self.prefix_var = tk.StringVar(value="img")
        self.start_var = tk.StringVar(value="1")
        self.max_workers = min(1, max(1, (os.cpu_count() or 2)))

        self._funcid_return = None

        self.create_ui()

    def create_ui(self):
        self.khung_ngoai = tk.Frame(self.ung_dung.vung_noi_dung, bg="#f0f0f0")
        self.khung_ngoai.pack(fill="both", expand=True)

        main = ttk.Frame(self.khung_ngoai, padding=20)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="RESIZE HÌNH ẢNH",
            font=("Arial", 20, "bold")
        ).pack(pady=(0, 20))

        # Chọn hình ảnh
        file_frame = ttk.LabelFrame(main, text="Hình ảnh", padding=10)
        file_frame.pack(fill="x", pady=5)

        ttk.Button(
            file_frame,
            text="Chọn hình ảnh...",
            command=self.select_files
        ).grid(row=0, column=0, padx=5, pady=5)

        ttk.Button(
            file_frame,
            text="Chọn thư mục...",
            command=self.select_folder
        ).grid(row=0, column=1, padx=5, pady=5)

        self.file_label = ttk.Label(
            file_frame,
            text="Chưa chọn hình ảnh"
        )
        self.file_label.grid(row=0, column=2, padx=10, sticky="w")

        # Kích thước
        size_frame = ttk.LabelFrame(main, text="Kích thước", padding=10)
        size_frame.pack(fill="x", pady=10)

        ttk.Label(size_frame, text="Rộng:").grid(
            row=0, column=0, padx=5, pady=5
        )

        self.width_entry = ttk.Entry(
            size_frame,
            textvariable=self.width_var,
            width=10
        )
        self.width_entry.grid(row=0, column=1, padx=5)

        ttk.Label(size_frame, text="px").grid(
            row=0, column=2, padx=(0, 15)
        )

        ttk.Label(size_frame, text="Cao:").grid(
            row=0, column=3, padx=5
        )

        self.height_entry = ttk.Entry(
            size_frame,
            textvariable=self.height_var,
            width=10
        )
        self.height_entry.grid(row=0, column=4, padx=5)

        ttk.Label(size_frame, text="px").grid(
            row=0, column=5, padx=5
        )

        # Tùy chọn
        option_frame = ttk.LabelFrame(main, text="Tùy chọn", padding=10)
        option_frame.pack(fill="x", pady=5)

        ttk.Checkbutton(
            option_frame,
            text="Giữ tỷ lệ khung hình",
            variable=self.keep_ratio_var
        ).pack(anchor="w", pady=3)

        ttk.Checkbutton(
            option_frame,
            text="Không phóng to ảnh nhỏ hơn kích thước yêu cầu",
            variable=self.no_enlarge_var
        ).pack(anchor="w", pady=3)

        ttk.Checkbutton(
            option_frame,
            text="Đổi đuôi sang WEBP (mọi định dạng)",
            variable=self.to_webp_var
        ).pack(anchor="w", pady=3)

        # Đổi tên file
        rename_frame = ttk.LabelFrame(main, text="Đổi tên file", padding=10)
        rename_frame.pack(fill="x", pady=5)

        ttk.Checkbutton(
            rename_frame,
            text="Đổi tên hàng loạt",
            variable=self.rename_var,
            command=self.toggle_rename
        ).grid(row=0, column=0, padx=5, pady=5, sticky="w")

        ttk.Label(rename_frame, text="Tên:").grid(
            row=0, column=1, padx=(15, 5)
        )

        self.prefix_entry = ttk.Entry(
            rename_frame,
            textvariable=self.prefix_var,
            width=14
        )
        self.prefix_entry.grid(row=0, column=2, padx=5)

        ttk.Label(rename_frame, text="Bắt đầu từ:").grid(
            row=0, column=3, padx=(15, 5)
        )

        self.start_entry = ttk.Entry(
            rename_frame,
            textvariable=self.start_var,
            width=6
        )
        self.start_entry.grid(row=0, column=4, padx=5)

        self.rename_preview = ttk.Label(rename_frame, text="")
        self.rename_preview.grid(
            row=1, column=0, columnspan=5, padx=5, sticky="w"
        )

        self.prefix_var.trace_add("write", lambda *a: self.update_rename_preview())
        self.start_var.trace_add("write", lambda *a: self.update_rename_preview())

        # Thư mục lưu
        output_frame = ttk.LabelFrame(main, text="Thư mục lưu", padding=10)
        output_frame.pack(fill="x", pady=10)

        ttk.Entry(
            output_frame,
            textvariable=self.output_var
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ttk.Button(
            output_frame,
            text="Chọn...",
            command=self.select_output
        ).pack(side="right")

        # Tiến trình
        self.progress = ttk.Progressbar(
            main,
            orient="horizontal",
            mode="determinate"
        )
        self.progress.pack(fill="x", pady=(15, 5))

        self.status_label = ttk.Label(
            main,
            text="Sẵn sàng"
        )
        self.status_label.pack()

        button_frame = ttk.Frame(main)
        button_frame.pack(fill="x", pady=(18, 8))

        self.resize_button = tk.Button(
            button_frame,
            text="▶  BẮT ĐẦU RESIZE",
            command=self.resize_images,
            font=("Arial", 13, "bold"),
            padx=30,
            pady=10,
            cursor="hand2"
        )
        self.resize_button.pack()

        self.update_rename_preview()

        # Phím Enter chỉ có tác dụng khi màn hình này còn hiển thị.
        self._funcid_return = self.root.bind(
            "<Return>", self._on_return, add="+"
        )
        self.khung_ngoai.bind("<Destroy>", self._khi_huy_man_hinh)

    def _on_return(self, event=None):
        self.resize_images()

    def _khi_huy_man_hinh(self, event):
        if event.widget is not self.khung_ngoai:
            return
        if self._funcid_return:
            try:
                self.root.unbind("<Return>", self._funcid_return)
            except tk.TclError:
                pass
            self._funcid_return = None

    def _con_hien_thi(self):
        try:
            return bool(self.khung_ngoai.winfo_exists())
        except tk.TclError:
            return False

    def toggle_rename(self):
        state = "normal" if self.rename_var.get() else "disabled"
        self.prefix_entry.config(state=state)
        self.start_entry.config(state=state)
        self.update_rename_preview()

    def update_rename_preview(self):
        if not self.rename_var.get():
            self.rename_preview.config(text="")
            return

        prefix = self.prefix_var.get().strip()
        try:
            start = int(self.start_var.get())
        except ValueError:
            start = 1

        self.rename_preview.config(
            text=f"Ví dụ: {prefix}{start}, {prefix}{start + 1}, {prefix}{start + 2}..."
        )

    def select_files(self):
        files = filedialog.askopenfilenames(
            parent=self.root,
            title="Chọn hình ảnh",
            filetypes=[
                (
                    "Hình ảnh",
                    "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"
                ),
                ("Tất cả", "*.*")
            ]
        )

        if files:
            self.files = list(files)
            self.file_label.config(
                text=f"Đã chọn {len(self.files)} hình ảnh"
            )

            if not self.output_var.get():
                first_folder = os.path.dirname(self.files[0])
                self.output_var.set(
                    os.path.join(first_folder, "resized")
                )

    def select_folder(self):
        folder = filedialog.askdirectory(
            parent=self.root,
            title="Chọn thư mục chứa hình ảnh"
        )

        if not folder:
            return

        self.files = []

        for root, dirs, filenames in os.walk(folder):
            dirs.sort()
            for filename in sorted(filenames):
                if filename.lower().endswith(SUPPORTED_EXTENSIONS):
                    self.files.append(
                        os.path.join(root, filename)
                    )

        self.file_label.config(
            text=f"Đã tìm thấy {len(self.files)} hình ảnh"
        )

        self.output_var.set(
            os.path.join(folder, "resized")
        )

    def select_output(self):
        folder = filedialog.askdirectory(
            parent=self.root,
            title="Chọn thư mục lưu ảnh"
        )

        if folder:
            self.output_var.set(folder)

    def get_size(self):
        try:
            width = int(self.width_var.get())
            height = int(self.height_var.get())

            if width <= 0 or height <= 0:
                raise ValueError

            return width, height

        except ValueError:
            messagebox.showerror(
                "Lỗi",
                "Chiều rộng và chiều cao phải là số nguyên lớn hơn 0.",
                parent=self.root
            )
            return None

    def get_rename_options(self):
        """Trả về (prefix, start) nếu bật đổi tên, (None, None) nếu tắt,
        hoặc False nếu dữ liệu không hợp lệ."""
        if not self.rename_var.get():
            return None, None

        prefix = self.prefix_var.get().strip()

        if not prefix:
            messagebox.showwarning(
                "Thiếu tên",
                "Vui lòng nhập tên gốc để đổi tên (ví dụ: img).",
                parent=self.root
            )
            return False

        if INVALID_NAME_CHARS.search(prefix):
            messagebox.showerror(
                "Tên không hợp lệ",
                'Tên không được chứa các ký tự: \\ / : * ? " < > |',
                parent=self.root
            )
            return False

        try:
            start = int(self.start_var.get())
            if start < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Lỗi",
                "Số bắt đầu phải là số nguyên không âm.",
                parent=self.root
            )
            return False

        return prefix, start

    def resize_images(self):
        if not self.files:
            messagebox.showwarning(
                "Chưa chọn hình",
                "Vui lòng chọn hình ảnh hoặc thư mục hình ảnh.",
                parent=self.root
            )
            return

        size = self.get_size()
        if size is None:
            return

        rename = self.get_rename_options()
        if rename is False:
            return
        rename_prefix, rename_start = rename

        output_folder = self.output_var.get().strip()
        if not output_folder:
            messagebox.showwarning(
                "Chưa chọn thư mục",
                "Vui lòng chọn thư mục lưu ảnh.",
                parent=self.root
            )
            return

        os.makedirs(output_folder, exist_ok=True)

        # Khóa nút để tránh chạy nhiều lần cùng lúc.
        self.resize_button.config(state="disabled")
        self.progress["maximum"] = len(self.files)
        self.progress["value"] = 0
        self.status_label.config(text=f"Đang chuẩn bị: 0/{len(self.files)}")

        target_width, target_height = size
        keep_ratio = self.keep_ratio_var.get()
        no_enlarge = self.no_enlarge_var.get()
        to_webp = self.to_webp_var.get()

        # Chạy xử lý ảnh ở thread nền để Tkinter không bị treo.
        thread = threading.Thread(
            target=self._resize_worker,
            args=(
                list(self.files),
                output_folder,
                target_width,
                target_height,
                keep_ratio,
                no_enlarge,
                rename_prefix,
                rename_start,
                to_webp,
            ),
            daemon=True
        )
        thread.start()

    def _resize_worker(
        self,
        files,
        output_folder,
        target_width,
        target_height,
        keep_ratio,
        no_enlarge,
        rename_prefix,
        rename_start,
        to_webp
    ):
        success = 0
        failed = []

        # Dùng một số worker vừa phải để tránh ngốn RAM khi ảnh lớn.
        workers = min(self.max_workers, len(files))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}

            for index, file_path in enumerate(files):
                # Tên mới: prefix + số thứ tự (img1, img2, ...).
                new_name = (
                    f"{rename_prefix}{rename_start + index}"
                    if rename_prefix is not None
                    else None
                )

                future = executor.submit(
                    self.process_image,
                    file_path,
                    output_folder,
                    target_width,
                    target_height,
                    keep_ratio,
                    no_enlarge,
                    new_name,
                    to_webp
                )
                futures[future] = file_path

            completed = 0

            for future in as_completed(futures):
                file_path = futures[future]
                completed += 1

                try:
                    future.result()
                    success += 1
                except Exception as error:
                    failed.append(
                        f"{os.path.basename(file_path)}: {error}"
                    )

                self._gui_ve_ui(
                    self._update_progress,
                    completed,
                    len(files)
                )

        self._gui_ve_ui(
            self._resize_finished,
            success,
            failed,
            len(files),
            output_folder
        )

    def _gui_ve_ui(self, ham, *args):
        """Chuyển callback từ thread worker về main thread an toàn."""
        try:
            self.root.after(0, ham, *args)
        except (tk.TclError, RuntimeError):
            pass

    def _update_progress(self, completed, total):
        if not self._con_hien_thi():
            return
        self.progress["value"] = completed
        percent = int((completed / total) * 100) if total else 0
        self.status_label.config(
            text=f"Đang xử lý: {completed}/{total} ({percent}%)"
        )

    def _resize_finished(self, success, failed, total, output_folder):
        if not self._con_hien_thi():
            return

        self.resize_button.config(state="normal")
        self.progress["value"] = total

        if failed:
            self.status_label.config(
                text=f"Hoàn thành: {success}/{total} ({int(success / total * 100)}%)"
            )
            messagebox.showwarning(
                "Hoàn thành nhưng có lỗi",
                f"Đã xử lý thành công {success}/{total} ảnh.\n\n"
                f"Có {len(failed)} ảnh không xử lý được.\n\n"
                + "\n".join(failed[:10])
                + (f"\n... và {len(failed) - 10} lỗi khác." if len(failed) > 10 else ""),
                parent=self.root
            )
        else:
            self.status_label.config(
                text=f"Hoàn thành: {success}/{total} (100%)"
            )
            messagebox.showinfo(
                "Hoàn thành",
                f"Đã resize thành công {success} hình ảnh.\n\n"
                f"Lưu tại:\n{output_folder}",
                parent=self.root
            )

    def process_image(
        self,
        file_path,
        output_folder,
        target_width,
        target_height,
        keep_ratio,
        no_enlarge,
        new_name=None,
        to_webp=False
    ):
        with Image.open(file_path) as image:
            # Correct orientation based on EXIF.
            image = ImageOps.exif_transpose(image)

            if not keep_ratio:
                new_width, new_height = target_width, target_height
            else:
                original_width, original_height = image.size
                ratio = min(
                    target_width / original_width,
                    target_height / original_height
                )

                if no_enlarge:
                    ratio = min(ratio, 1)

                new_width = max(1, round(original_width * ratio))
                new_height = max(1, round(original_height * ratio))

            resized = image.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )

            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)

            # Dùng tên mới nếu bật đổi tên.
            if new_name:
                name = new_name

            ext_lower = ext.lower()

            if to_webp:
                output_path = os.path.join(
                    output_folder,
                    name + ".webp"
                )

                if resized.mode not in ("RGB", "RGBA"):
                    co_alpha = (
                        "A" in resized.mode
                        or resized.mode == "P"
                        and "transparency" in resized.info
                    )
                    resized = resized.convert("RGBA" if co_alpha else "RGB")

                resized.save(
                    output_path,
                    "WEBP",
                    quality=90,
                    method=4
                )

            elif ext_lower in (".jpg", ".jpeg"):
                output_path = os.path.join(
                    output_folder,
                    name + ".jpg"
                )

                if resized.mode not in ("RGB", "L"):
                    resized = resized.convert("RGB")

                resized.save(
                    output_path,
                    "JPEG",
                    quality=90,
                    optimize=False
                )

            elif ext_lower == ".png":
                output_path = os.path.join(
                    output_folder,
                    name + ".png"
                )
                resized.save(
                    output_path,
                    "PNG",
                    optimize=False
                )

            elif ext_lower == ".webp":
                output_path = os.path.join(
                    output_folder,
                    name + ".webp"
                )
                resized.save(
                    output_path,
                    "WEBP",
                    quality=90,
                    method=4
                )

            else:
                # Convert uncommon formats to PNG.
                output_path = os.path.join(
                    output_folder,
                    name + ".png"
                )

                if resized.mode not in ("RGB", "RGBA", "L"):
                    resized = resized.convert("RGBA")

                resized.save(
                    output_path,
                    "PNG",
                    optimize=False
                )
