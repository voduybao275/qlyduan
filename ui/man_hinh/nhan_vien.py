# ui/man_hinh/nhan_vien.py
import tkinter as tk


def tao(ung_dung):
    tk.Label(ung_dung.vung_noi_dung, text="👥 QUẢN LÝ NHÂN VIÊN",
             font=("Arial", 18, "bold"), bg="#f0f0f0").pack(pady=30)
    tk.Label(ung_dung.vung_noi_dung,
             text="(Danh sách nhân viên sẽ ở đây)",
             bg="#f0f0f0").pack()