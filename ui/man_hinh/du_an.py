# ui/man_hinh/du_an.py
import os
import re
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from data import csdl, import_excel
from data.du_lieu import TRANG_THAI_DU_AN

# Tắt cảnh báo SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KHONG_XAC_DINH = "Không xác định"
TIMEOUT = (5, 10)  # (connect, read)

# Một session dùng chung: tự giải nén gzip/deflate, tự theo redirect.
# verify=False để vẫn đọc được site dùng chứng chỉ tự ký / hết hạn / lệch hostname.
SESSION = requests.Session()
SESSION.verify = False
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
})

# ======================================================================
# PHẦN 1: LOGIC CHECK PHIÊN BẢN WORDPRESS
# ======================================================================
def _is_valid_link(s):
    """Chỉ chấp nhận hostname / IP / URL hợp lệ. Loại '1.0', '7.1.4'..."""
    if not s:
        return False
    s = s.strip()
    if not s:
        return False
    # Có scheme http(s) và có host
    if re.match(r"^https?://[^\s/]+", s, re.IGNORECASE):
        return True
    # IPv4
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", s):
        return True
    # Domain có TLD >= 2 ký tự (loại '1.0' vì TLD '0' chỉ 1 ký tự)
    if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z0-9\-]+)*\.[a-zA-Z]{2,}$", s):
        return True
    return False

def _chuan_hoa_base(link):
    """Chuẩn hóa link về dạng https://domain (bỏ '/' cuối, bỏ đuôi '/feed')."""
    base = link.strip().rstrip("/")
    if not re.match(r"^https?://", base, re.IGNORECASE):
        base = "https://" + base
    return re.sub(r"/feed/?$", "", base, flags=re.IGNORECASE)


def _fetch(url):
    """Tải URL, trả về text (requests tự giải nén gzip/deflate) hoặc None."""
    try:
        resp = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code == 200 and resp.text:
            return resp.text
    except requests.RequestException as e:
        print(f"[_fetch] {url} -> {type(e).__name__}: {e}")
    return None


def _extract_generator_from_feed(text):
    if not text:
        return None
    # Regex linh hoạt: cho phép attribute, khoảng trắng, http/https
    m = re.search(
        r"<generator[^>]*>\s*https?://wordpress\.org/\?v=([0-9][0-9A-Za-z\.\-]*)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    # Fallback: đôi khi generator chỉ là "WordPress 7.1.4"
    m = re.search(
        r"<generator[^>]*>\s*WordPress\s+([0-9][0-9A-Za-z\.\-]*)",
        text,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _extract_generator_from_html(text):
    """Fallback: đọc <meta name="generator" content="WordPress x.y.z">."""
    if not text:
        return None
    m = re.search(
        r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']WordPress\s+([0-9][0-9A-Za-z\.\-]*)',
        text,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def check_wp_version_remote(target_link):
    """
    Kiểm tra phiên bản WordPress từ xa.
    - Ưu tiên /feed lấy thẻ <generator>
    - Fallback meta generator trong HTML trang chủ
    """
    if not _is_valid_link(target_link):
        print(f"[check] link không hợp lệ: {target_link!r}")
        return KHONG_XAC_DINH

    base = _chuan_hoa_base(target_link)
    return (
        _extract_generator_from_feed(_fetch(base + "/feed"))
        or _extract_generator_from_html(_fetch(base + "/"))
        or KHONG_XAC_DINH
    )


def _lay_cac_link_kiem_tra(host, url):
    """Danh sách link có thể check: host trước, url sau (bỏ trùng).

    Dùng chung cho cả check-chọn và check-all để 2 nút luôn ra cùng kết quả.
    Trước đây check-all ưu tiên url nên các dòng có url rác ('1.0') ra
    'Không xác định', còn check-chọn ưu tiên host nên vẫn ra phiên bản.
    """
    ds = []
    for gia_tri in (host, url):
        gia_tri = (gia_tri or "").strip()
        if _is_valid_link(gia_tri) and gia_tri not in ds:
            ds.append(gia_tri)
    return ds


# ======================================================================
# PHẦN 2: HÀM CẬP NHẬT PHIÊN BẢN WP
# ======================================================================

def _doc_link_du_an(id_du_an):
    with csdl.ket_noi() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT host, url FROM `{csdl.TABLE_DU_AN}` WHERE id = %s",
            (id_du_an,),
        )
        return cursor.fetchone()


def _luu_wp_version(id_du_an, version):
    try:
        with csdl.ket_noi() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE `{csdl.TABLE_DU_AN}` SET wp_version = %s WHERE id = %s",
                (version, id_du_an),
            )
            conn.commit()
    except Exception as e:
        print(f"[DB write] Lỗi cập nhật dự án id={id_du_an}: {e}")


def _kiem_tra_va_luu(id_du_an):
    """Đọc host/url từ DB, check phiên bản rồi ghi lại. Trả về version."""
    try:
        record = _doc_link_du_an(id_du_an)
    except Exception as e:
        print(f"[DB read] Lỗi đọc dự án id={id_du_an}: {e}")
        return KHONG_XAC_DINH

    version = KHONG_XAC_DINH
    for link in _lay_cac_link_kiem_tra(record.get("host"), record.get("url")) if record else []:
        try:
            version = check_wp_version_remote(link)
        except Exception as e:
            print(f"[Check] Lỗi check {link}: {e}")
            continue
        if version != KHONG_XAC_DINH:
            break

    _luu_wp_version(id_du_an, version)
    return version


def _cap_nhat_dong(ung_dung, item, version):
    """Cập nhật 1 dòng của bảng + cache, giữ nguyên bộ lọc đang dùng."""
    tree = ung_dung.tree_du_an
    values = list(tree.item(item, "values"))
    if len(values) < 10:
        return
    values[8] = version
    tree.item(item, values=values)
    id_du_an = str(values[9])
    for da in ung_dung.danh_sach_du_an:
        if str(da["id"]) == id_du_an:
            da["wp_version"] = version
            break


def update_wp_version(ung_dung):
    """Check phiên bản WP cho dòng đang chọn (chạy nền, không treo UI)."""
    dong_chon = ung_dung.tree_du_an.selection()
    if not dong_chon:
        messagebox.showwarning("Cảnh báo", "Vui lòng chọn dự án cần kiểm tra!", parent=ung_dung.root)
        return

    item = dong_chon[0]
    gia_tri = ung_dung.tree_du_an.item(item, "values")
    id_du_an = gia_tri[9]
    ten_du_an = gia_tri[2] if len(gia_tri) > 2 else str(id_du_an)

    ung_dung.root.config(cursor="watch")
    ung_dung.root.update_idletasks()

    def _chay():
        version = _kiem_tra_va_luu(id_du_an)

        def _xong():
            ung_dung.root.config(cursor="")
            try:
                _cap_nhat_dong(ung_dung, item, version)
            except tk.TclError:
                pass  # màn hình đã bị đổi trong lúc chờ
            messagebox.showinfo("Kết quả", f"{ten_du_an}: {version}", parent=ung_dung.root)

        ung_dung.root.after(0, _xong)

    threading.Thread(target=_chay, daemon=True).start()

def update_all_wp_version(ung_dung, max_workers: int = 10):
    """Check phiên bản WP cho TẤT CẢ dự án đang hiển thị (chạy đa luồng)."""
    items = ung_dung.tree_du_an.get_children()
    if not items:
        messagebox.showwarning(
            "Cảnh báo", "Không có dự án nào đang hiển thị!", parent=ung_dung.root
        )
        return

    if not messagebox.askyesno(
        "Xác nhận",
        f"Check phiên bản WP cho {len(items)} dự án?\n"
        f"(Chạy song song {max_workers} luồng để tối ưu tốc độ)",
        parent=ung_dung.root,
    ):
        return

    # Đọc Treeview trên main thread — Tkinter không thread-safe
    du_lieu = []
    for item in items:
        gia_tri = ung_dung.tree_du_an.item(item, "values")
        ten = gia_tri[2] if len(gia_tri) > 2 else str(gia_tri[9])
        du_lieu.append((item, gia_tri[9], ten))

    tong = len(du_lieu)
    ten_theo_item = {item: ten for item, _, ten in du_lieu}

    # ----- Cửa sổ tiến trình -----
    cua_so = tk.Toplevel(ung_dung.root)
    cua_so.title("Đang kiểm tra...")
    cua_so.geometry("480x160")
    cua_so.transient(ung_dung.root)
    cua_so.grab_set()
    cua_so.resizable(False, False)

    lbl_trang_thai = tk.Label(
        cua_so, text="Đang chuẩn bị...", font=("Arial", 10), anchor="w", justify="left"
    )
    lbl_trang_thai.pack(pady=(10, 4), padx=10, fill="x")

    progress = ttk.Progressbar(cua_so, length=440, mode="determinate", maximum=tong)
    progress.pack(pady=6, padx=10, fill="x")

    lbl_dem = tk.Label(cua_so, text=f"0 / {tong}", font=("Arial", 9))
    lbl_dem.pack()

    stop_event = threading.Event()

    def _huy():
        stop_event.set()
        lbl_trang_thai.config(text="Đang dừng... vui lòng chờ hoàn tất các luồng hiện tại")

    tk.Button(cua_so, text="Hủy", command=_huy).pack(pady=6)

    # ----- Cập nhật UI (luôn chạy trên main thread qua root.after) -----
    def _cap_nhat_giao_dien(item, version, da_xong):
        if version is not None:
            _cap_nhat_dong(ung_dung, item, version)
            lbl_trang_thai.config(text=f"Vừa check: {ten_theo_item[item]} → {version}")
        progress.configure(value=da_xong)
        lbl_dem.config(text=f"{da_xong} / {tong}")

    # ----- Worker chính -----
    def _worker():
        so_da_kiem_tra = 0

        def _task(id_du_an):
            if stop_event.is_set():
                return None  # dự án chưa kịp chạy thì bỏ qua
            return _kiem_tra_va_luu(id_du_an)

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(_task, id_du_an): item
                    for item, id_du_an, _ in du_lieu
                }
                for da_xong, future in enumerate(as_completed(futures), start=1):
                    item = futures[future]
                    try:
                        version = future.result()
                    except Exception as e:
                        print(f"[Worker] Lỗi future: {e}")
                        version = KHONG_XAC_DINH
                    if version is not None:
                        so_da_kiem_tra += 1
                    ung_dung.root.after(
                        0,
                        lambda it=item, v=version, n=da_xong: _cap_nhat_giao_dien(it, v, n),
                    )
        except Exception as e:
            print(f"[Worker] Lỗi tổng: {e}")

        def _hoan_thanh():
            try:
                cua_so.destroy()
            except Exception:
                pass
            if stop_event.is_set():
                messagebox.showinfo(
                    "Đã dừng",
                    f"Đã dừng. Đã kiểm tra {so_da_kiem_tra}/{tong} dự án.",
                    parent=ung_dung.root,
                )
            else:
                messagebox.showinfo(
                    "Thành công",
                    f"Đã kiểm tra và cập nhật xong {so_da_kiem_tra} dự án!",
                    parent=ung_dung.root,
                )

        ung_dung.root.after(0, _hoan_thanh)

    threading.Thread(target=_worker, daemon=True).start()


def _gan_sap_xep_cot(tree, cot_so=(), cot_phien_ban=()):
    """Click tiêu đề cột để sắp xếp bảng; trả về hàm áp dụng lại thứ tự hiện tại."""
    tieu_de_goc = {c: tree.heading(c, "text") for c in tree["columns"]}
    trang_thai = {"cot": None, "giam": False}

    def _khoa(item):
        cot = trang_thai["cot"]
        gia_tri = tree.set(item, cot).strip()
        if cot in cot_so:
            try:
                return float(gia_tri.replace("%", ""))
            except ValueError:
                return float("-inf")
        if cot in cot_phien_ban:
            # So sánh tự nhiên: 7.1.4 < 7.1.13
            return tuple(
                (0, int(phan), "") if phan.isdigit() else (1, 0, phan.lower())
                for phan in re.split(r"(\d+)", gia_tri) if phan
            )
        return gia_tri.lower()

    def sap_xep_lai():
        if not trang_thai["cot"]:
            return
        for index, item in enumerate(
            sorted(tree.get_children(), key=_khoa, reverse=trang_thai["giam"])
        ):
            tree.move(item, "", index)

    def _khi_click(cot):
        if trang_thai["cot"] == cot:
            trang_thai["giam"] = not trang_thai["giam"]
        else:
            trang_thai["cot"] = cot
            trang_thai["giam"] = False
        sap_xep_lai()
        for c in tree["columns"]:
            nhan = tieu_de_goc[c]
            if c == cot:
                nhan += " ▼" if trang_thai["giam"] else " ▲"
            tree.heading(c, text=nhan)

    for cot in tree["columns"]:
        tree.heading(cot, command=lambda c=cot: _khi_click(c))

    return sap_xep_lai


def thong_ke_wp_version(ung_dung):
    """Vẽ màn hình thống kê số dự án theo từng phiên bản WP."""
    try:
        du_lieu = csdl.nhom_du_an_theo_wp_version()
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thống kê được:\n{e}", parent=ung_dung.root)
        return

    nhom = dict(du_lieu)
    tong = sum(len(ds) for ds in nhom.values())

    khung = tk.Frame(ung_dung.vung_noi_dung, bg="#f0f0f0")
    khung.pack(fill="both", expand=True)

    tk.Label(
        khung,
        text=f"📊 THỐNG KÊ PHIÊN BẢN WP — {tong} dự án",
        font=("Arial", 12, "bold"),
        bg="#f0f0f0",
    ).pack(pady=10)

    # ----- Bảng thống kê -----
    frame_tk = tk.Frame(khung, bg="#f0f0f0")
    frame_tk.pack(fill="x", padx=10, pady=(0, 8))

    tree_tk = ttk.Treeview(
        frame_tk, columns=("wp_version", "so_luong", "ty_le"), show="headings", height=8
    )
    tree_tk.heading("wp_version", text="Phiên bản WP")
    tree_tk.heading("so_luong", text="Số dự án")
    tree_tk.heading("ty_le", text="Tỷ lệ")
    tree_tk.column("wp_version", width=260)
    tree_tk.column("so_luong", width=110, anchor="center")
    tree_tk.column("ty_le", width=110, anchor="center")

    for version, ds in du_lieu:
        ty_le = f"{len(ds) / tong * 100:.1f}%" if tong else "0%"
        tree_tk.insert("", "end", values=(version, len(ds), ty_le))

    scroll_tk = ttk.Scrollbar(frame_tk, orient="vertical", command=tree_tk.yview)
    tree_tk.configure(yscrollcommand=scroll_tk.set)
    tree_tk.pack(side="left", fill="both", expand=True)
    scroll_tk.pack(side="right", fill="y")
    tree_tk.focus_set()
    _gan_sap_xep_cot(tree_tk, cot_so=("so_luong", "ty_le"), cot_phien_ban=("wp_version",))

    # ----- Bảng chi tiết -----
    lbl_chi_tiet = tk.Label(
        khung,
        text="Chọn một phiên bản để xem danh sách dự án",
        font=("Arial", 10, "bold"),
        anchor="w",
        bg="#f0f0f0",
    )
    lbl_chi_tiet.pack(fill="x", padx=10, pady=(4, 4))

    frame_ct = tk.Frame(khung, bg="#f0f0f0")
    frame_ct.pack(fill="both", expand=True, padx=10, pady=(0, 8))

    tree_ct = ttk.Treeview(
        frame_ct,
        columns=("id", "name", "host", "dev", "status"),
        show="headings",
        height=8,
    )
    tree_ct.heading("id", text="Mã DA")
    tree_ct.heading("name", text="Tên dự án")
    tree_ct.heading("host", text="Host")
    tree_ct.heading("dev", text="Dev")
    tree_ct.heading("status", text="Trạng thái")
    tree_ct.column("id", width=60)
    tree_ct.column("name", width=220)
    tree_ct.column("host", width=260)
    tree_ct.column("dev", width=90)
    tree_ct.column("status", width=140)

    scroll_ct = ttk.Scrollbar(frame_ct, orient="vertical", command=tree_ct.yview)
    tree_ct.configure(yscrollcommand=scroll_ct.set)
    tree_ct.pack(side="left", fill="both", expand=True)
    scroll_ct.pack(side="right", fill="y")
    sap_xep_chi_tiet = _gan_sap_xep_cot(tree_ct, cot_so=("id",))

    def _hien_danh_sach(event=None):
        chon = tree_tk.selection()
        for item in tree_ct.get_children():
            tree_ct.delete(item)
        if not chon:
            lbl_chi_tiet.config(text="Chọn một phiên bản để xem danh sách dự án")
            return

        version = tree_tk.item(chon[0], "values")[0]
        ds = nhom.get(version, [])
        lbl_chi_tiet.config(text=f"Dự án dùng WP {version} ({len(ds)})")
        for da in ds:
            tree_ct.insert(
                "",
                "end",
                values=(
                    da["id"],
                    da["name"] or "",
                    da["host"] or "",
                    da["dev"] or "",
                    da["status"] or "",
                ),
            )
        sap_xep_chi_tiet()

    tree_tk.bind("<<TreeviewSelect>>", _hien_danh_sach)
    tree_tk.bind("<Return>", _hien_danh_sach)

    tk.Button(
        khung,
        text="← Về danh sách dự án",
        command=lambda: ung_dung.hien_thi_noi_dung("du_an"),
    ).pack(pady=(0, 10))


# ======================================================================
# PHẦN 3: MÀN HÌNH DANH SÁCH
# ======================================================================
def tao_danh_sach(ung_dung):
    """Vẽ trang danh sách dự án + thanh công cụ."""
    # 1. Kiểm tra kết nối DB
    ok, loi = csdl.kiem_tra_ket_noi()
    if not ok:
        messagebox.showerror("Chưa kết nối Database", f"Không thể kết nối MySQL:\n\n{loi}", parent=ung_dung.root)
        ung_dung.hien_thi_noi_dung("dang_nhap")
        return

    try:
        ung_dung.danh_sach_du_an = csdl.lay_tat_ca_du_an()
    except Exception as e:
        messagebox.showerror("Lỗi tải dữ liệu", f"Không thể tải danh sách dự án:\n\n{e}", parent=ung_dung.root)
        ung_dung.hien_thi_noi_dung("dang_nhap")
        return
        
    # 2. Thanh công cụ
    thanh_cong_cu = tk.Frame(ung_dung.vung_noi_dung, bg="#f0f0f0")
    thanh_cong_cu.pack(fill="x", padx=20, pady=10)

    tk.Label(thanh_cong_cu, text="📁 QUẢN LÝ DỰ ÁN", font=("Arial", 18, "bold"), bg="#f0f0f0").pack(side="left")

    tk.Button(thanh_cong_cu, text="🗑 Xóa dự án", font=("Arial", 10, "bold"), fg="red", command=lambda: xoa(ung_dung)).pack(side="right", padx=5)

    tk.Button(thanh_cong_cu, text="✏️ Sửa dự án", font=("Arial", 10, "bold"), command=lambda: mo_form_sua(ung_dung)).pack(side="right", padx=5)

    tk.Button(thanh_cong_cu, text="➕ Thêm dự án", font=("Arial", 10, "bold"), command=lambda: ung_dung.hien_thi_noi_dung("them_du_an")).pack(side="right", padx=5)

    tk.Button(thanh_cong_cu, text="Check WP chọn", font=("Arial", 10, "bold"), bg="#FF9800", fg="white", command=lambda: update_wp_version(ung_dung)).pack(side="right", padx=5)

    tk.Button(thanh_cong_cu, text="Check WP all", font=("Arial", 10, "bold"), bg="#FF9800", fg="white", command=lambda: update_all_wp_version(ung_dung)).pack(side="right", padx=5)

    # tk.Button(thanh_cong_cu, text="Mở công cụ WP", font=("Arial", 10, "bold"), bg="#FF9800", fg="white", command=lambda: update_wp_version(ung_dung)).pack(side="right", padx=5)

    # 3. Bộ lọc
    filter_row = tk.Frame(ung_dung.vung_noi_dung, bg="#f0f0f0")
    filter_row.pack(fill="x", padx=20, pady=(0, 10)) 

    tk.Label(filter_row, text="Tìm mã/tên:", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(side=tk.LEFT, padx=(0, 2))
    ung_dung.entry_search_name = tk.Entry(filter_row, font=("Arial", 10), width=14)
    ung_dung.entry_search_name.pack(side=tk.LEFT, padx=5)
    ung_dung.entry_search_name.bind("<KeyRelease>", lambda event: ung_dung.load_data())

    tk.Label(filter_row, text="Dev:", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(side=tk.LEFT, padx=(0, 2))
    ung_dung.combo_dev_filter = ttk.Combobox(filter_row, values=["Tất cả", "ZN", "NQ", "PNS", "AKX"], state="readonly", width=10, font=("Arial", 9))
    ung_dung.combo_dev_filter.current(0)
    ung_dung.combo_dev_filter.pack(side=tk.LEFT, padx=(0, 15))
    ung_dung.combo_dev_filter.bind("<<ComboboxSelected>>", lambda e: ung_dung.load_data())

    ung_dung.var_chi_co_host = tk.BooleanVar(value=False)
    tk.Checkbutton(filter_row, text="Chỉ có host", variable=ung_dung.var_chi_co_host, font=("Arial", 9), bg="#f0f0f0", command=ung_dung.load_data).pack(side=tk.LEFT, padx=(15, 2))

    ung_dung.var_dang_lam = tk.BooleanVar(value=False)
    tk.Checkbutton(filter_row, text="Đang làm", variable=ung_dung.var_dang_lam, font=("Arial", 9), bg="#f0f0f0", command=ung_dung.load_data).pack(side=tk.LEFT, padx=(10, 2))

    tk.Button(filter_row, text="✖ Xóa lọc", font=("Arial", 9), bg="#f0f0f0", command=lambda: ung_dung.xoa_bo_loc()).pack(side=tk.LEFT, padx=(15, 0))

    # 4. Khởi tạo Bảng và Thanh cuộn
    frame_bang = tk.Frame(ung_dung.vung_noi_dung)
    frame_bang.pack(fill="both", expand=True, padx=20, pady=10)

    cot = ("stt", "mada", "name", "url", "host", "dev", "status", "deadline", "wp_version", "id")
    tree = ttk.Treeview(
        frame_bang,
        columns=cot,
        show="headings",
        height=15,
        displaycolumns=("stt", "mada", "name", "url", "host", "dev",
                        "status", "deadline", "wp_version"),
    )
    
    tree.heading("stt", text="STT")
    tree.heading("mada", text="Mã DA")
    tree.heading("name", text="Tên dự án")
    tree.heading("url", text="URL")
    tree.heading("host", text="Host")
    tree.heading("dev", text="Dev")
    tree.heading("status", text="Trạng thái")
    tree.heading("deadline", text="Hạn chót")
    tree.heading("wp_version", text="Phiên bản WP")

    tree.column("stt", width=50, anchor="center")
    tree.column("mada", width=90)
    tree.column("name", width=220)
    tree.column("url", width=200)
    tree.column("host", width=200)
    tree.column("dev", width=200)
    tree.column("status", width=150)
    tree.column("deadline", width=150)
    tree.column("wp_version", width=150)
    tree.column("id", width=0, stretch=False)

    scroll_doc = ttk.Scrollbar(frame_bang, orient="vertical", command=tree.yview)
    scroll_ngang = ttk.Scrollbar(frame_bang, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=scroll_doc.set, xscrollcommand=scroll_ngang.set)

    tree.grid(row=0, column=0, sticky="nsew")
    scroll_doc.grid(row=0, column=1, sticky="ns")
    scroll_ngang.grid(row=1, column=0, sticky="ew")

    frame_bang.grid_rowconfigure(0, weight=1)
    frame_bang.grid_columnconfigure(0, weight=1)

    tree.focus_set()
    ung_dung.tree_du_an = tree

    tree.bind("<Double-1>", lambda e: mo_form_sua(ung_dung))
    tree.bind("<Delete>", lambda e: xoa(ung_dung))

    nap_danh_sach(ung_dung)


def nap_danh_sach(ung_dung):
    """Đổ dữ liệu từ list vào Treeview."""
    tree = ung_dung.tree_du_an
    for item in tree.get_children():
        tree.delete(item)
    for stt, da in enumerate(ung_dung.danh_sach_du_an, 1):
        tree.insert("", "end", values=(
            stt,
            da.get("mada") or da["id"],
            da["name"],
            da["url"],
            da["host"],
            da["dev"],
            da["status"],
            da["deadline"],
            da["wp_version"],
            da["id"],
        ))


# ======================================================================
# PHẦN 4: FORM THÊM / SỬA / XÓA
# ======================================================================
def tao_form(ung_dung, che_do="them", du_lieu=None):
    dang_sua = (che_do == "sua" and du_lieu is not None)

    tk.Button(ung_dung.vung_noi_dung, text="← Quay lại danh sách", command=lambda: ung_dung.hien_thi_noi_dung("du_an")).pack(anchor="w", padx=20, pady=10)

    tieu_de = "✏️ SỬA DỰ ÁN" if dang_sua else "➕ THÊM DỰ ÁN MỚI"
    tk.Label(ung_dung.vung_noi_dung, text=tieu_de, font=("Arial", 18, "bold"), bg="#f0f0f0").pack(pady=10)

    frame_form = tk.Frame(ung_dung.vung_noi_dung, bg="#f0f0f0")
    frame_form.pack(pady=10)

    tk.Label(frame_form, text="Mã dự án (VD: GKV_001):", bg="#f0f0f0").grid(row=0, column=0, sticky="e", padx=10, pady=8)
    entry_ma = tk.Entry(frame_form, width=40)
    entry_ma.grid(row=0, column=1, padx=10, pady=8)

    tk.Label(frame_form, text="Tên dự án 1:", bg="#f0f0f0").grid(row=1, column=0, sticky="e", padx=10, pady=8)
    entry_ten = tk.Entry(frame_form, width=40)
    entry_ten.grid(row=1, column=1, padx=10, pady=8)

    tk.Label(frame_form, text="Url:", bg="#f0f0f0").grid(row=2, column=0, sticky="e", padx=10, pady=8)
    entry_url = tk.Entry(frame_form, width=40)
    entry_url.grid(row=2, column=1, padx=10, pady=8)

    tk.Label(frame_form, text="Host:", bg="#f0f0f0").grid(row=3, column=0, sticky="e", padx=10, pady=8)
    entry_host = tk.Entry(frame_form, width=40)
    entry_host.grid(row=3, column=1, padx=10, pady=8)

    tk.Label(frame_form, text="Dev:", bg="#f0f0f0").grid(row=4, column=0, sticky="ne", padx=10, pady=8)
    dev_frame = tk.Frame(frame_form, bg="#f0f0f0")
    dev_frame.grid(row=4, column=1, sticky="w", padx=10, pady=8)
    dev_vars = {}
    dev_list = ["ZN", "NQ", "PNS", "AKX"]

    dev_da_chon = set()
    if dang_sua:
        dev_da_chon = {d.strip() for d in (du_lieu.get("dev") or "").split(",") if d.strip()}

    for i, dev_name in enumerate(dev_list):
        var = tk.BooleanVar(value=(dev_name in dev_da_chon))
        dev_vars[dev_name] = var
        cb = tk.Checkbutton(dev_frame, text=dev_name, variable=var, font=("Arial", 9), bg="#f0f0f0")
        cb.grid(row=i // 2, column=i % 2, sticky="w", padx=10, pady=2)

    tk.Label(frame_form, text="Trạng thái:", bg="#f0f0f0").grid(row=5, column=0, sticky="e", padx=10, pady=8)
    combo = ttk.Combobox(frame_form, width=37, values=TRANG_THAI_DU_AN)
    combo.grid(row=5, column=1, padx=10, pady=8)

    tk.Label(frame_form, text="Hạn giao (YYYY-mm-dd):", bg="#f0f0f0").grid(row=6, column=0, sticky="e", padx=10, pady=8)
    entry_deadline = tk.Entry(frame_form, width=40)
    entry_deadline.grid(row=6, column=1, padx=10, pady=8)

    if dang_sua:
        entry_ma.insert(0, du_lieu.get("mada") or "")
        entry_ten.insert(0, du_lieu.get("name") or "")
        entry_url.insert(0, du_lieu.get("url") or "")
        entry_host.insert(0, du_lieu.get("host") or "")
        
        status_hien_tai = du_lieu.get("status")
        if status_hien_tai:
            combo.set(status_hien_tai)
        else:
            combo.current(0)
            
        entry_deadline.insert(0, du_lieu.get("deadline") or "")
    else:
        combo.current(0)

    entry_ten.focus_set()

    def luu():
        ma = entry_ma.get().strip()
        ten = entry_ten.get().strip()
        url = entry_url.get().strip()
        host = entry_host.get().strip()
        trang_thai = combo.get().strip()
        deadline = entry_deadline.get().strip()
        dev = ",".join(ten_dev for ten_dev, var in dev_vars.items() if var.get())

        if not ma or not ten:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập Mã và Tên dự án!")
            return

        if dang_sua:
            ok, loi = csdl.cap_nhat_du_an(du_lieu["id"], ma, ten, url, host, dev, trang_thai, deadline)
        else:
            ok, loi = csdl.them_du_an(ma, ten, url, host, dev, trang_thai, deadline)

        if not ok:
            messagebox.showerror("Lỗi CSDL", loi)
            return

        ung_dung.du_an_dang_sua = None
        ung_dung.hien_thi_noi_dung("du_an")

    frame_nut = tk.Frame(ung_dung.vung_noi_dung, bg="#f0f0f0")
    frame_nut.pack(pady=20)
    tk.Button(frame_nut, text="💾 Lưu", width=12, command=luu).pack(side="left", padx=5)
    tk.Button(frame_nut, text="❌ Hủy", width=12, command=lambda: ung_dung.hien_thi_noi_dung("du_an")).pack(side="left", padx=5)


def mo_form_sua(ung_dung):
    dong_chon = ung_dung.tree_du_an.selection()
    if not dong_chon:
        messagebox.showinfo("Chưa chọn", "Vui lòng chọn một dự án để sửa!")
        return

    gia_tri = ung_dung.tree_du_an.item(dong_chon[0], "values")
    id_da = gia_tri[9]

    for da in ung_dung.danh_sach_du_an:
        if str(da["id"]) == str(id_da):
            ung_dung.du_an_dang_sua = da.copy() 
            break
    else:
        messagebox.showerror("Lỗi", f"Không tìm thấy dự án ID {id_da}")
        return

    ung_dung.hien_thi_noi_dung("sua_du_an")


def xoa(ung_dung):
    dong_chon = ung_dung.tree_du_an.selection()
    if not dong_chon:
        messagebox.showinfo("Chưa chọn", "Vui lòng chọn một dự án để xóa!")
        return

    gia_tri = ung_dung.tree_du_an.item(dong_chon[0], "values")
    ma_da, ten_da = gia_tri[1], gia_tri[2]

    tra_loi = messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa dự án:\n\n  Mã: {ma_da}\n  Tên: {ten_da}\n\nHành động này không thể hoàn tác!")
    if not tra_loi: return

    ok, loi = csdl.xoa_du_an(gia_tri[9])
    if not ok:
        messagebox.showerror("Lỗi CSDL", loi)
        return

    ung_dung.hien_thi_noi_dung("du_an")
    messagebox.showinfo("Đã xóa", f"Đã xóa dự án '{ten_da}'.")


def reset_du_lieu_du_an(ung_dung):
    """Xóa toàn bộ dự án trong CSDL sau 2 lần xác nhận."""
    so_du_an = len(ung_dung.danh_sach_du_an)

    if not messagebox.askyesno(
        "Reset dữ liệu dự án",
        f"Xóa TOÀN BỘ {so_du_an} dự án trong CSDL?\n\n"
        "Dữ liệu sẽ mất hết và không thể hoàn tác.\n"
        "Nên dùng 'Dữ liệu → Xuất Excel' để sao lưu trước khi reset.",
        icon="warning",
        parent=ung_dung.root,
    ):
        return

    if not messagebox.askyesno(
        "Xác nhận lần 2",
        f"Bạn chắc chắn muốn XÓA VĨNH VIỄN {so_du_an} dự án?\n\n"
        "Mã dự án mới sẽ bắt đầu lại từ 1.",
        icon="warning",
        parent=ung_dung.root,
    ):
        return

    ok, loi = csdl.xoa_tat_ca_du_an()
    if not ok:
        messagebox.showerror("Lỗi reset dữ liệu", loi, parent=ung_dung.root)
        return

    ung_dung.hien_thi_noi_dung("du_an")
    messagebox.showinfo(
        "Đã reset",
        f"Đã xóa toàn bộ {so_du_an} dự án. Bảng dự án hiện đang trống.",
        parent=ung_dung.root,
    )


# ======================================================================
# PHẦN 5: EXCEL (IMPORT / EXPORT)
# ======================================================================
def mo_import_excel(ung_dung):
    duong_dan = filedialog.askopenfilename(title="Chọn file Excel để import", filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")])
    if not duong_dan: return

    try:
        df = import_excel.doc_file_excel(duong_dan)
    except ValueError as e:
        messagebox.showerror("Lỗi đọc file", str(e), parent=ung_dung.root)
        return

    du_lieu_hop_le, loi = import_excel.kiem_tra_du_lieu(df)

    if not du_lieu_hop_le:
        messagebox.showerror("Không có dữ liệu hợp lệ", f"File Excel không có dòng nào hợp lệ.\n\nSố lỗi: {len(loi)}", parent=ung_dung.root)
        return

    _hien_thi_xem_truoc(ung_dung, duong_dan, df, du_lieu_hop_le, loi)


def _hien_thi_xem_truoc(ung_dung, duong_dan, df, du_lieu_hop_le, loi):
    cua_so = tk.Toplevel(ung_dung.root)
    cua_so.title("Xem trước Import Excel")
    cua_so.geometry("1000x600")
    cua_so.transient(ung_dung.root)
    cua_so.grab_set()

    info_frame = tk.Frame(cua_so, bg="#f0f0f0")
    info_frame.pack(fill="x", padx=10, pady=10)

    tk.Label(info_frame, text=f"📄 File: {os.path.basename(duong_dan)}", font=("Arial", 10, "bold"), bg="#f0f0f0", anchor="w").pack(fill="x")

    tong_dong = len(df)
    tk.Label(info_frame, text=f"Tổng số dòng: {tong_dong}  |  ✅ Hợp lệ: {len(du_lieu_hop_le)}  |  ❌ Lỗi: {len(loi)}", font=("Arial", 10), bg="#f0f0f0", anchor="w").pack(fill="x", pady=(5, 0))

    frame_bang = tk.Frame(cua_so)
    frame_bang.pack(fill="both", expand=True, padx=10, pady=5)

    cot = ("dong", "mada", "name", "url", "host", "dev", "status", "deadline", "wp_version", "trang_thai")
    tree = ttk.Treeview(frame_bang, columns=cot, show="headings", height=15)
    
    tree.heading("dong", text="Dòng")
    tree.heading("mada", text="Mã DA")
    tree.heading("name", text="Name")
    tree.heading("url", text="URL")
    tree.heading("host", text="Host")
    tree.heading("dev", text="Dev")
    tree.heading("status", text="Status")
    tree.heading("deadline", text="Deadline")
    tree.heading("wp_version", text="WP ver")
    tree.heading("trang_thai", text="Kết quả")

    tree.column("dong", width=50, anchor="center")
    tree.column("mada", width=90)
    tree.column("name", width=200)
    tree.column("url", width=150)
    tree.column("host", width=120)
    tree.column("dev", width=80)
    tree.column("status", width=100)
    tree.column("deadline", width=100)
    tree.column("wp_version", width=80)
    tree.column("trang_thai", width=120)

    tree.tag_configure("loi", background="#ffebee", foreground="#c62828")
    tree.tag_configure("ok", background="#e8f5e9")

    scroll = ttk.Scrollbar(frame_bang, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    for i, du_lieu in enumerate(du_lieu_hop_le):
        tree.insert("", "end", values=(i + 2, du_lieu["mada"] or "", du_lieu["name"] or "", du_lieu["url"] or "", du_lieu["host"] or "", du_lieu["dev"] or "", du_lieu["status"] or "", du_lieu["deadline"] or "", du_lieu["wp_version"] or "", "✅ Hợp lệ"), tags=("ok",))

    for loi_item in loi:
        tree.insert("", "end", values=(loi_item["dong"], "—", "—", "—", "—", "—", "—", "—", "—", f"❌ {loi_item['noi_dung']}"), tags=("loi",))

    frame_che_do = tk.Frame(cua_so, bg="#f0f0f0")
    frame_che_do.pack(fill="x", padx=10, pady=5)

    tk.Label(frame_che_do, text="Chế độ:", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(side="left", padx=(0, 10))
    bien_che_do = tk.StringVar(value="bo_qua")
    tk.Radiobutton(frame_che_do, text="Bỏ qua nếu trùng mã hoặc tên", variable=bien_che_do, value="bo_qua", bg="#f0f0f0", font=("Arial", 10)).pack(side="left", padx=5)
    tk.Radiobutton(frame_che_do, text="Ghi đè nếu trùng mã hoặc tên", variable=bien_che_do, value="ghi_de", bg="#f0f0f0", font=("Arial", 10)).pack(side="left", padx=5)

    frame_nut = tk.Frame(cua_so, bg="#f0f0f0")
    frame_nut.pack(pady=10)

    def _bat_dau_import():
        che_do = bien_che_do.get()
        tra_loi = messagebox.askyesno("Xác nhận", f"Sẽ import {len(du_lieu_hop_le)} dự án?\nChế độ: {'Bỏ qua' if che_do == 'bo_qua' else 'Ghi đè'}\n\nTiếp tục?", parent=cua_so)
        if not tra_loi: return

        cua_so.destroy()
        ket_qua = import_excel.import_vao_mysql(du_lieu_hop_le, che_do)

        thong_bao = f"✅ Thành công: {ket_qua['thanh_cong']}\n⏭️ Bỏ qua: {ket_qua['bo_qua']}\n❌ Thất bại: {ket_qua['that_bai']}"
        if ket_qua["loi"]:
            thong_bao += "\n\nChi tiết lỗi:\n" + "\n".join(ket_qua["loi"][:5])
            if len(ket_qua["loi"]) > 5: thong_bao += f"\n... và {len(ket_qua['loi']) - 5} lỗi khác"

        messagebox.showinfo("Kết quả Import", thong_bao, parent=ung_dung.root)
        ung_dung.hien_thi_noi_dung("du_an")

    tk.Button(frame_nut, text="📥 Bắt đầu Import", width=18, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), command=_bat_dau_import).pack(side="left", padx=5)
    tk.Button(frame_nut, text="❌ Hủy", width=12, font=("Arial", 10), command=cua_so.destroy).pack(side="left", padx=5)


def xuat_excel(ung_dung):
    dong_chon = ung_dung.tree_du_an.selection()
    if dong_chon:
        tra_loi = messagebox.askyesnocancel("Xuất Excel", f"Bạn đang chọn {len(dong_chon)} dòng.\n\nYES: Xuất dòng chọn\nNO: Xuất tất cả", parent=ung_dung.root)
        if tra_loi is None: return
        if tra_loi:              
            ds_xuat = []
            for item_id in dong_chon:
                gia_tri = ung_dung.tree_du_an.item(item_id, "values")
                id_da = gia_tri[9]
                for da in ung_dung.danh_sach_du_an:
                    if str(da["id"]) == str(id_da):
                        ds_xuat.append(da)
                        break
        else:                    
            ds_xuat = ung_dung.danh_sach_du_an
    else:
        ds_xuat = ung_dung.danh_sach_du_an

    if not ds_xuat:
        messagebox.showinfo("Không có dữ liệu", "Không có dự án nào để xuất!", parent=ung_dung.root)
        return

    tu_ngay = datetime.now().strftime("%Y%m%d_%H%M")
    duong_dan = filedialog.asksaveasfilename(title="Lưu file Excel", defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")], initialfile=f"danh_sach_du_an_{tu_ngay}.xlsx", parent=ung_dung.root)
    if not duong_dan: return

    try:
        import_excel.xuat_ra_excel(ds_xuat, duong_dan)
    except Exception as e:
        messagebox.showerror("Lỗi xuất file", str(e), parent=ung_dung.root)
        return

    tra_loi = messagebox.askyesno("Thành công", f"Đã xuất {len(ds_xuat)} dòng ra file:\n\n{duong_dan}\n\nMở thư mục chứa file?", parent=ung_dung.root)
    if tra_loi:
        try:
            if os.name == "nt":
                os.startfile(os.path.dirname(duong_dan))
            else:
                import subprocess
                subprocess.Popen(["xdg-open", os.path.dirname(duong_dan)])
        except Exception:
            pass

def _tai_file_mau(ung_dung):
    duong_dan = filedialog.asksaveasfilename(title="Lưu file Excel mẫu", defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")], initialfile="mau_du_an.xlsx", parent=ung_dung.root)
    if not duong_dan: return
    try:
        import_excel.tao_file_mau(duong_dan)
        messagebox.showinfo("Thành công", f"Đã tạo file mẫu tại:\n{duong_dan}", parent=ung_dung.root)
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thể tạo file mẫu:\n{e}", parent=ung_dung.root)