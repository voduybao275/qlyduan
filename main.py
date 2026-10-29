# main.py
import tkinter as tk
from tkinter import messagebox

# from data.csdl import khoi_tao_csdl, kiem_tra_ket_noi
# from ui.ung_dung import UngDungQuanLy

from data.cau_hinh import doc_cau_hinh, ghi_cau_hinh, MAC_DINH
from data.csdl import kiem_tra_ket_noi, khoi_tao_csdl
from ui.ung_dung import UngDungQuanLy


if __name__ == "__main__":
    # Đọc config hiện tại
    cfg = doc_cau_hinh()

    if not cfg.get("db_host"):
        ghi_cau_hinh(MAC_DINH)
        cfg = doc_cau_hinh()

    # Kiểm tra kết nối với config hiện tại
    ok, loi = kiem_tra_ket_noi()
    if not ok:
        root = tk.Tk()
        root.withdraw()
        tra_loi = messagebox.askyesno(
            "Không kết nối được MySQL",
            f"Không kết nối được MySQL:\n{loi}\n\n"
            f"Mở app và vào 'Hệ thống → Cấu hình Database' để sửa?"
        )
        root.destroy()
        if not tra_loi:
            raise SystemExit(1)

    # Tạo DB + bảng nếu chưa có
    ok_db, loi_db = khoi_tao_csdl()
    if not ok_db:
        print(f"[Cảnh báo] Không thể khởi tạo DB: {loi_db}")

    root = tk.Tk()
    app = UngDungQuanLy(root)
    root.mainloop()

    # Khởi tạo database + bảng (chạy 1 lần)
    # if not khoi_tao_csdl():
    #     root = tk.Tk()
    #     root.withdraw()  # ẩn cửa sổ chính
    #     messagebox.showerror(
    #         "Lỗi kết nối CSDL",
    #         "Không thể kết nối MySQL!\n\n"
    #         "Vui lòng kiểm tra:\n"
    #         "- MySQL service đã chạy chưa\n"
    #         "- Thông tin DB_HOST/DB_USER/DB_PASSWORD trong data/csdl.py"
    #     )
    #     root.destroy()
    #     raise SystemExit(1)

    # if not kiem_tra_ket_noi():
    #     print("[Cảnh báo] Kết nối MySQL không ổn định.")

    # root = tk.Tk()
    # app = UngDungQuanLy(root)
    # root.mainloop()