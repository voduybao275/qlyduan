# ui/man_hinh/trang_chu.py
import tkinter as tk


def tao(ung_dung):
    """Màn hình trang chủ."""
    tk.Label(ung_dung.vung_noi_dung, text="🏠 TRANG CHỦ",
             font=("Arial", 24, "bold"), bg="#f0f0f0").pack(pady=50)
    tk.Label(ung_dung.vung_noi_dung,
             text="Chọn menu ở trên để bắt đầu",
             font=("Arial", 12), bg="#f0f0f0").pack()