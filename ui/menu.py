# ui/menu.py
import tkinter as tk
from ui.man_hinh.cong_cu_wp import mo_cong_cu_wp
from ui.man_hinh.du_an import (
    _tai_file_mau, mo_import_excel, thong_ke_wp_version, xuat_excel,
)

def tao_menu(root, ung_dung):
    """
    Tạo thanh menu và gắn vào root.

    Tham số:
        root: cửa sổ chính Tk.
        ung_dung: instance UngDungQuanLy (để gọi hien_thi_noi_dung).
    """
    menubar = tk.Menu(root)

    # Menu "Hệ thống"
    he_thong_menu = tk.Menu(menubar, tearoff=0)
    he_thong_menu.add_command(
        label="Đăng nhập (Ctrl+L)",
        command=lambda: ung_dung.hien_thi_noi_dung("dang_nhap"))
    he_thong_menu.add_command(
        label="Đổi mật khẩu",
        command=lambda: ung_dung.hien_thi_noi_dung("doi_mat_khau"))
    he_thong_menu.add_separator()
    he_thong_menu.add_command(label="Thoát (Ctr+E)", command=root.quit)
    menubar.add_cascade(label="Hệ thống", menu=he_thong_menu)

    root.bind("<Control-e>", lambda event: root.destroy())
    root.bind("<Control-d>", lambda event: ung_dung.hien_thi_noi_dung("du_an"))
    root.bind("<Control-l>", lambda event: ung_dung.hien_thi_noi_dung("dang_nhap"))

    # Menu "Quản lý"
    quan_ly_menu = tk.Menu(menubar, tearoff=0)
    quan_ly_menu.add_command(
        label="Dự án (Ctrl+D)",
        command=lambda: ung_dung.hien_thi_noi_dung("du_an"))
    quan_ly_menu.add_command(
        label="Nhân viên",
        command=lambda: ung_dung.hien_thi_noi_dung("nhan_vien"))
    quan_ly_menu.add_command(
        label="Khách hàng",
        command=lambda: ung_dung.hien_thi_noi_dung("khach_hang"))
    menubar.add_cascade(label="Quản lý", menu=quan_ly_menu)

    # Menu "Công cụ"
    cong_cu_menu = tk.Menu(menubar, tearoff=0)
    cong_cu_menu.add_command(
        label="Mở công cụ WP",
        command=lambda: mo_cong_cu_wp(ung_dung))
    menubar.add_cascade(label="Công cụ", menu=cong_cu_menu)

    # Menu "Dữ liệu" — import/export cần bảng dự án nên mở màn hình trước
    def _mo_man_hinh_du_an():
        tree = getattr(ung_dung, "tree_du_an", None)
        if tree is None or not tree.winfo_exists():
            ung_dung.hien_thi_noi_dung("du_an")

    def _chay_tren_man_hinh_du_an(ham):
        _mo_man_hinh_du_an()
        tree = getattr(ung_dung, "tree_du_an", None)
        if tree is not None and tree.winfo_exists():
            ham()

    dulieu_menu = tk.Menu(menubar, tearoff=0)
    dulieu_menu.add_command(
        label="Import Excel...",
        command=lambda: _chay_tren_man_hinh_du_an(lambda: mo_import_excel(ung_dung)))
    dulieu_menu.add_command(
        label="Xuất Excel...",
        command=lambda: _chay_tren_man_hinh_du_an(lambda: xuat_excel(ung_dung)))
    dulieu_menu.add_separator()
    dulieu_menu.add_command(
        label="Thống kê phiên bản WP",
        command=lambda: thong_ke_wp_version(ung_dung))
    dulieu_menu.add_command(
        label="Tải file Excel mẫu",
        command=lambda: _tai_file_mau(ung_dung))
    menubar.add_cascade(label="Dữ liệu", menu=dulieu_menu)

    # Menu "Trợ giúp"
    tro_giup_menu = tk.Menu(menubar, tearoff=0)
    tro_giup_menu.add_command(
        label="Hướng dẫn",
        command=lambda: ung_dung.hien_thi_noi_dung("huong_dan"))
    tro_giup_menu.add_command(
        label="Giới thiệu",
        command=lambda: ung_dung.hien_thi_noi_dung("gioi_thieu"))
    menubar.add_cascade(label="Trợ giúp", menu=tro_giup_menu)

    root.config(menu=menubar)
