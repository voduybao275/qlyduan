# ui/ung_dung.py
import tkinter as tk

from data import csdl
from ui.menu import tao_menu
from ui.man_hinh import (
    trang_chu, tai_khoan, du_an,
    nhan_vien, khach_hang, tro_giup,
)


class UngDungQuanLy:
    def __init__(self, root):
        self.root = root
        self.root.title("Quản lý Dự án - đang kiểm tra kết nối CSDL")
        self.root.state('zoomed')

        self.du_an_dang_sua = None
        self.danh_sach_du_an = []   # sẽ load từ MySQL

        tao_menu(self.root, self)

        self.vung_noi_dung = tk.Frame(self.root, bg="#f0f0f0")
        self.vung_noi_dung.pack(fill="both", expand=True)

        self.hien_thi_noi_dung("trang_chu")

    def hien_thi_noi_dung(self, ten_man_hinh):
        for widget in self.vung_noi_dung.winfo_children():
            widget.destroy()

        danh_sach_man_hinh = {
            # "trang_chu":    lambda: trang_chu.tao(self),
            "trang_chu":    lambda: du_an.tao_danh_sach(self),
            # "trang_chu":    lambda: du_an.tao_form(self, "them"),
            # "trang_chu":    lambda: tai_khoan.tao_dang_nhap(self),
            "dang_nhap":    lambda: tai_khoan.tao_dang_nhap(self),
            "doi_mat_khau": lambda: tai_khoan.tao_doi_mat_khau(self),
            "du_an":        lambda: du_an.tao_danh_sach(self),
            "them_du_an":   lambda: du_an.tao_form(self, "them"),
            "sua_du_an":    lambda: du_an.tao_form(self, "sua", self.du_an_dang_sua),
            "nhan_vien":    lambda: nhan_vien.tao(self),
            "khach_hang":   lambda: khach_hang.tao(self),
            "huong_dan":    lambda: tro_giup.tao_huong_dan(self),
            "gioi_thieu":   lambda: tro_giup.tao_gioi_thieu(self),
        }

        ham_tao = danh_sach_man_hinh.get(ten_man_hinh)
        if ham_tao:
            ham_tao()
        else:
            tk.Label(self.vung_noi_dung,
                     text=f"Chưa có màn hình: {ten_man_hinh}",
                     font=("Arial", 14)).pack(pady=50)

    def load_data(self, event=None):
        """Lọc dữ liệu theo tên + dev + có host + đang làm, rồi vẽ lại Treeview."""
        if not hasattr(self, "entry_search_name") or not hasattr(self, "tree_du_an"):
            return

        # --- Lấy điều kiện ---
        tu_khoa = self.entry_search_name.get().strip().lower()

        dev_chon = self.combo_dev_filter.get() if hasattr(self, "combo_dev_filter") else "Tất cả"

        chi_co_host = self.var_chi_co_host.get()
        dang_lam = self.var_dang_lam.get()

        # --- Lọc ---
        du_lieu_loc = []
        for da in self.danh_sach_du_an:
            # 1. Tên chứa từ khóa?
            if tu_khoa and tu_khoa not in (da["name"] or "").lower():
                continue

            # 2. Dev có nằm trong nhóm được chọn?
            #    Cột "dev" lưu dạng "ZN,NQ" → tách thành set để so sánh
            if dev_chon != "Tất cả":
                cac_dev_cua_da = {
                    d.strip() for d in (da["dev"] or "").split(",") if d.strip()
                }
                if dev_chon not in cac_dev_cua_da:
                    continue

            # 3. Chỉ có host?
            if chi_co_host and not (da["host"] or "").strip():
                continue

            # 4. Đang làm?
            if dang_lam and (da["status"] or "").strip() != "Đang làm":
                continue

            du_lieu_loc.append(da)

        # --- Vẽ lại Treeview ---
        tree = self.tree_du_an
        for item in tree.get_children():
            tree.delete(item)
        for da in du_lieu_loc:
            tree.insert("", "end", values=(
                da["id"], da["name"], da["url"], da["host"],
                da["dev"], da["status"], da["deadline"], da["wp_version"],
            ))



    def xoa_bo_loc(self):
        if hasattr(self, "entry_search_name"):
            self.entry_search_name.delete(0, tk.END)
        if hasattr(self, "combo_dev_filter"):
            self.combo_dev_filter.current(0)     # về "Tất cả"
        if hasattr(self, "var_chi_co_host"):
            self.var_chi_co_host.set(False)
        if hasattr(self, "var_dang_lam"):
            self.var_dang_lam.set(False)
        self.load_data()