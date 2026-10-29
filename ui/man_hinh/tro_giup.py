# ui/man_hinh/tro_giup.py
import tkinter as tk


def tao_huong_dan(ung_dung):
    tk.Label(ung_dung.vung_noi_dung, text="📖 HƯỚNG DẪN SỬ DỤNG",
             font=("Arial", 18, "bold"), bg="#f0f0f0").pack(pady=30)
    noi_dung = (
        "1. Chọn 'Quản lý → Dự án' để xem danh sách.\n"
        "2. Bấm '➕ Thêm dự án' để tạo dự án mới.\n"
        "3. Click đúp vào một dòng (hoặc bấm '✏️ Sửa') để chỉnh sửa.\n"
        "4. Chọn dòng rồi bấm '🗑 Xóa' (hoặc phím Delete) để xóa."
    )
    tk.Label(ung_dung.vung_noi_dung, text=noi_dung,
             bg="#f0f0f0", justify="left",
             font=("Arial", 11)).pack(padx=30, pady=10, anchor="w")


def tao_gioi_thieu(ung_dung):
    tk.Label(ung_dung.vung_noi_dung, text="ℹ️ GIỚI THIỆU",
             font=("Arial", 18, "bold"), bg="#f0f0f0").pack(pady=30)
    tk.Label(ung_dung.vung_noi_dung,
             text="Phần mềm Quản lý Dự án\nPhiên bản 1.0",
             bg="#f0f0f0", justify="center").pack()