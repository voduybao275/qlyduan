# ui/man_hinh/tai_khoan.py
import tkinter as tk
from tkinter import messagebox

from data import cau_hinh, csdl


def tao_dang_nhap(ung_dung):
    """Form cập nhật thông tin kết nối MySQL, lưu vào database.db (SQLite)."""

    frame = tk.Frame(ung_dung.vung_noi_dung, bg="#f0f0f0")
    frame.pack(expand=True, pady=30)

    tk.Label(frame, text="⚙️ CẤU HÌNH KẾT NỐI MYSQL",
             font=("Arial", 18, "bold"), bg="#f0f0f0"
             ).grid(row=0, column=0, columnspan=3, pady=(0, 20))

    # Đọc config hiện tại
    cfg = cau_hinh.doc_cau_hinh()

    # ----- Hàm tạo dòng -----
    def _dong(row, nhan, gia_tri, show=None, width=35):
        tk.Label(frame, text=nhan, bg="#f0f0f0",
                 font=("Arial", 10)).grid(
            row=row, column=0, sticky="e", padx=5, pady=5)
        e = tk.Entry(frame, width=width, font=("Arial", 10), show=show)
        e.grid(row=row, column=1, padx=5, pady=5, columnspan=2, sticky="w")
        e.insert(0, gia_tri)
        return e

    entry_host = _dong(1, "Host:",     cfg.get("db_host", ""))
    entry_port = _dong(2, "Port:",     cfg.get("db_port", "3306"))
    entry_user = _dong(3, "User:",     cfg.get("db_user", "root"))
    entry_pass = _dong(4, "Password:", cfg.get("db_password", ""), show="*")
    entry_name = _dong(5, "Database:", cfg.get("db_name", ""))

    # Hiện/ẩn mật khẩu
    def _toggle_pass():
        entry_pass.config(show="" if entry_pass.cget("show") == "*" else "*")

    tk.Checkbutton(frame, text="Hiện mật khẩu", bg="#f0f0f0",
                   command=_toggle_pass
                   ).grid(row=4, column=2, padx=5, sticky="w")

    # Đường dẫn file SQLite
    tk.Label(frame, text="File cấu hình:", bg="#f0f0f0",
             font=("Arial", 9, "italic")).grid(
        row=6, column=0, sticky="e", padx=5, pady=(15, 5))
    tk.Label(frame, text=cau_hinh.DUONG_DAN_CAU_HINH,
             bg="#f0f0f0", fg="gray", font=("Arial", 9)).grid(
        row=6, column=1, columnspan=2, sticky="w", padx=5, pady=(15, 5))

    # ----- Hàm lấy dữ liệu form -----
    def _lay_du_lieu():
        return {
            "db_host":     entry_host.get().strip(),
            "db_port":     entry_port.get().strip(),
            "db_user":     entry_user.get().strip(),
            "db_password": entry_pass.get(),
            "db_name":     entry_name.get().strip(),
        }

    def _validate(du_lieu):
        if not du_lieu["db_host"]:
            return False, "Vui lòng nhập Host!"
        if not du_lieu["db_user"]:
            return False, "Vui lòng nhập User!"
        if not du_lieu["db_name"]:
            return False, "Vui lòng nhập tên Database!"
        try:
            int(du_lieu["db_port"] or "3306")
        except ValueError:
            return False, "Port phải là số nguyên!"
        return True, None

    # ----- Nút kiểm tra -----
    def _kiem_tra():
        du_lieu = _lay_du_lieu()
        ok, loi = _validate(du_lieu)
        if not ok:
            messagebox.showwarning("Thiếu thông tin", loi)
            return

        ok, loi = csdl.kiem_tra_ket_noi(
            host=du_lieu["db_host"],
            port=du_lieu["db_port"],
            user=du_lieu["db_user"],
            password=du_lieu["db_password"],
            database=du_lieu["db_name"],
        )
        if ok:
            messagebox.showinfo(
                "Thành công",
                "Kết nối MySQL thành công!\n"
                "(Chưa lưu — bấm Lưu để áp dụng)"
            )
        else:
            messagebox.showerror("Lỗi kết nối", loi)

    # ----- Nút lưu -----
    def _luu():
        du_lieu = _lay_du_lieu()
        ok, loi = _validate(du_lieu)
        if not ok:
            messagebox.showwarning("Thiếu thông tin", loi)
            return

        # Kiểm tra kết nối trước khi lưu
        ok, loi = csdl.kiem_tra_ket_noi(
            host=du_lieu["db_host"],
            port=du_lieu["db_port"],
            user=du_lieu["db_user"],
            password=du_lieu["db_password"],
            database=du_lieu["db_name"],
        )
        if not ok:
            tra_loi = messagebox.askyesno(
                "Không kết nối được",
                f"Không kết nối được MySQL:\n{loi}\n\n"
                f"Vẫn lưu cấu hình?"
            )
            if not tra_loi:
                return

        # Ghi vào SQLite
        ok, loi = cau_hinh.ghi_cau_hinh(du_lieu)
        if not ok:
            messagebox.showerror("Lỗi ghi cấu hình", loi)
            return

        # Tạo DB + bảng nếu kết nối được
        if ok_kn:
            ok_db, loi_db = csdl.khoi_tao_csdl()
            if ok_db:
                messagebox.showinfo(
                    "Thành công",
                    "Đã lưu cấu hình vào database.db và kết nối MySQL thành công!"
                )
            else:
                messagebox.showwarning(
                    "Đã lưu",
                    f"Đã lưu cấu hình nhưng lỗi tạo DB: {loi_db}"
                )
        else:
            messagebox.showwarning(
                "Đã lưu",
                "Đã lưu cấu hình nhưng chưa kết nối được MySQL."
            )

    # Gắn biến để hàm _luu dùng lại
    ok_kn = False

    def _luu_v2():
        nonlocal ok_kn
        du_lieu = _lay_du_lieu()
        ok, loi = _validate(du_lieu)
        if not ok:
            messagebox.showwarning("Thiếu thông tin", loi)
            return

        ok_kn, loi_kn = csdl.kiem_tra_ket_noi(
            host=du_lieu["db_host"],
            port=du_lieu["db_port"],
            user=du_lieu["db_user"],
            password=du_lieu["db_password"],
            database=du_lieu["db_name"],
        )
        if not ok_kn:
            tra_loi = messagebox.askyesno(
                "Không kết nối được",
                f"Không kết nối được MySQL:\n{loi_kn}\n\n"
                f"Vẫn lưu cấu hình?"
            )
            if not tra_loi:
                return

        ok, loi = cau_hinh.ghi_cau_hinh(du_lieu)
        if not ok:
            messagebox.showerror("Lỗi ghi cấu hình", loi)
            return

        if ok_kn:
            ok_db, loi_db = csdl.khoi_tao_csdl()
            if ok_db:
                messagebox.showinfo(
                    "Thành công",
                    "Đã lưu cấu hình và kết nối MySQL thành công!"
                )
            else:
                messagebox.showwarning(
                    "Đã lưu",
                    f"Đã lưu cấu hình nhưng lỗi tạo DB: {loi_db}"
                )
        else:
            messagebox.showwarning(
                "Đã lưu",
                "Đã lưu cấu hình nhưng chưa kết nối được MySQL."
            )

    # ----- Các nút -----
    frame_nut = tk.Frame(frame, bg="#f0f0f0")
    frame_nut.grid(row=7, column=0, columnspan=3, pady=20)

    tk.Button(frame_nut, text="🔍 Kiểm tra kết nối", width=18,
              bg="#2196F3", fg="white", font=("Arial", 10, "bold"),
              command=_kiem_tra).pack(side="left", padx=5)

    tk.Button(frame_nut, text="💾 Lưu", width=14,
              bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
              command=_luu_v2).pack(side="left", padx=5)

    tk.Button(frame_nut, text="❌ Hủy", width=14,
              font=("Arial", 10),
              command=lambda: ung_dung.hien_thi_noi_dung("trang_chu")
              ).pack(side="left", padx=5)