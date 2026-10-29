# ui/man_hinh/khach_hang.py
import tkinter as tk


def tao(ung_dung):
    tk.Label(ung_dung.vung_noi_dung, text="🤝 QUẢN LÝ KHÁCH HÀNG",
             font=("Arial", 18, "bold"), bg="#f0f0f0").pack(pady=30)
    tk.Label(ung_dung.vung_noi_dung,
             text="(Danh sách khách hàng sẽ ở đây)",
             bg="#f0f0f0").pack()