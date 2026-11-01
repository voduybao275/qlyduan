# ui/man_hinh/cong_cu_wp.py
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from data import cau_hinh
from data.tu_dong_wp import LoiTrinhDuyet, lay_trinh_duyet
from ui.man_hinh.du_an import _is_valid_link, _lay_cac_link_kiem_tra

BG = "#f2f2f2"


def _du_an_dang_chon(ung_dung):
    tree = getattr(ung_dung, "tree_du_an", None)
    if tree is None or not tree.winfo_exists():
        return None

    dong_chon = tree.selection()
    if not dong_chon:
        return None

    id_da = tree.item(dong_chon[0], "values")[9]
    for da in ung_dung.danh_sach_du_an:
        if str(da["id"]) == str(id_da):
            return da
    return None


def _du_an_co_host(du_an):
    return bool(du_an) and bool(_is_valid_link((du_an.get("host") or "").strip()))


def mo_cong_cu_wp(ung_dung):
    """Chuyển sang màn hình WordPress Auto Manager (dùng chung vùng nội dung)."""
    # Lấy dự án đang chọn trước khi danh sách dự án bị thay bằng màn hình mới.
    ung_dung.du_an_cho_cong_cu = _du_an_dang_chon(ung_dung)
    ung_dung.hien_thi_noi_dung("cong_cu_wp")


def tao(ung_dung):
    """Vẽ màn hình WordPress Auto Manager vào vùng nội dung dùng chung."""
    du_an_chon = getattr(ung_dung, "du_an_cho_cong_cu", None)
    ung_dung.du_an_cho_cong_cu = None

    khung_ngoai = tk.Frame(ung_dung.vung_noi_dung, bg=BG)
    khung_ngoai.pack(fill="both", expand=True)

    khung = tk.Frame(khung_ngoai, bg=BG)
    khung.pack(fill="both", expand=True, padx=12, pady=10)

    tk.Label(
        khung,
        text="WORDPRESS AUTO MANAGER",
        font=("Arial", 20, "bold"),
        bg=BG,
    ).pack(pady=(4, 14))

    # Trạng thái dùng chung giữa UI và thread automation
    trang_thai = {"ma_captcha": "", "dang_chay": False}
    hang_log = queue.Queue()

    def _ghi_log(noi_dung):
        """Chỉ đẩy vào hàng đợi — thread không gọi Tk trực tiếp."""
        hang_log.put(noi_dung)

    # ----- Cấu hình trang web -----
    khung_web = tk.LabelFrame(
        khung, text=" Cấu hình Trang Web ", font=("Arial", 10), bg=BG, fg="#333333"
    )
    khung_web.pack(fill="x", pady=(0, 10))

    hang_url = tk.Frame(khung_web, bg=BG)
    hang_url.pack(fill="x", padx=12, pady=(8, 4))

    tk.Label(hang_url, text="URL Domain:", font=("Arial", 10, "bold"), bg=BG).pack(
        anchor="w"
    )
    hang_nhap_url = tk.Frame(hang_url, bg=BG)
    hang_nhap_url.pack(fill="x", pady=(4, 0))

    entry_url = tk.Entry(hang_nhap_url, font=("Arial", 10))
    entry_url.pack(side="left", fill="x", expand=True)

    # Điền sẵn host/url của dự án đang chọn lúc mở công cụ
    if du_an_chon:
        cac_link = _lay_cac_link_kiem_tra(
            du_an_chon.get("host"), du_an_chon.get("url")
        )
        if cac_link:
            entry_url.insert(0, cac_link[0])

    # Dự án có host thì mặc định bật "Đăng nhập CMS"; chỉ có url thì không
    bien_dang_nhap_cms = tk.BooleanVar(value=_du_an_co_host(du_an_chon))

    tk.Checkbutton(
        hang_nhap_url,
        text="Đăng nhập CMS",
        variable=bien_dang_nhap_cms,
        font=("Arial", 10),
        bg=BG,
        activebackground=BG,
    ).pack(side="left", padx=(12, 0))

    # ----- Tài khoản & CAPTCHA -----
    khung_tai_khoan = tk.LabelFrame(
        khung, text=" Thông tin Tài khoản & CAPTCHA ", font=("Arial", 10), bg=BG, fg="#333333"
    )
    khung_tai_khoan.pack(fill="x", pady=(0, 10))

    luoi_tk = tk.Frame(khung_tai_khoan, bg=BG)
    luoi_tk.pack(fill="x", padx=12, pady=(8, 10))
    luoi_tk.grid_columnconfigure(0, weight=1, uniform="cot")
    luoi_tk.grid_columnconfigure(1, weight=1, uniform="cot")

    tk.Label(luoi_tk, text="Username / Email:", font=("Arial", 10, "bold"), bg=BG).grid(
        row=0, column=0, sticky="w"
    )
    tk.Label(luoi_tk, text="Mật khẩu:", font=("Arial", 10, "bold"), bg=BG).grid(
        row=0, column=1, sticky="w", padx=(10, 0)
    )

    entry_username = tk.Entry(luoi_tk, font=("Arial", 10))
    entry_username.grid(row=1, column=0, sticky="ew", pady=(4, 8))

    entry_mat_khau = tk.Entry(luoi_tk, font=("Arial", 10), show="•")
    entry_mat_khau.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(4, 8))

    # Nạp lại tài khoản đã lưu lần trước
    cau_hinh_da_luu = cau_hinh.doc_cau_hinh()
    entry_username.insert(0, cau_hinh_da_luu.get("wp_username") or "admin")
    entry_mat_khau.insert(0, cau_hinh_da_luu.get("wp_password") or "")

    tk.Label(
        luoi_tk,
        text="Mã CAPTCHA (Nhấn trên màn hình Chrome để nhập):",
        font=("Arial", 10, "bold"),
        fg="#1A237E",
        bg=BG,
    ).grid(row=2, column=0, columnspan=2, sticky="w")

    entry_captcha = tk.Entry(luoi_tk, font=("Arial", 10))
    entry_captcha.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    def _cap_nhat_captcha(event=None):
        trang_thai["ma_captcha"] = entry_captcha.get().strip()

    entry_captcha.bind("<KeyRelease>", _cap_nhat_captcha)

    # ----- Tùy chọn tác vụ -----
    khung_tuy_chon = tk.LabelFrame(
        khung, text=" Tùy chọn tác vụ thực thi ", font=("Arial", 10), bg=BG, fg="#333333"
    )
    khung_tuy_chon.pack(fill="x", pady=(0, 10))

    luoi_tc = tk.Frame(khung_tuy_chon, bg=BG)
    luoi_tc.pack(fill="x", padx=12, pady=(8, 10))
    luoi_tc.grid_columnconfigure(0, weight=1, uniform="cot")
    luoi_tc.grid_columnconfigure(1, weight=1, uniform="cot")

    bien_tu_dong_dang_nhap = tk.BooleanVar(value=True)
    bien_backup = tk.BooleanVar(value=True)
    bien_cap_nhat_core = tk.BooleanVar(value=True)
    bien_cap_nhat_plugin = tk.BooleanVar(value=True)

    cac_tuy_chon = (
        ("Tự động đăng nhập", bien_tu_dong_dang_nhap, 0, 0),
        ("Backup (All-in-One WP Migration)", bien_backup, 0, 1),
        ("Cập nhật WordPress Core", bien_cap_nhat_core, 1, 0),
        ("Cập nhật tất cả Plugins", bien_cap_nhat_plugin, 1, 1),
    )
    for nhan, bien, dong, cot in cac_tuy_chon:
        tk.Checkbutton(
            luoi_tc,
            text=nhan,
            variable=bien,
            font=("Arial", 10),
            bg=BG,
            activebackground=BG,
        ).grid(row=dong, column=cot, sticky="w", pady=3, padx=(0 if cot == 0 else 10, 0))

    # ----- Tiến trình thực thi -----
    khung_tien_trinh = tk.LabelFrame(
        khung, text=" Tiến trình thực thi ", font=("Arial", 10), bg=BG, fg="#333333"
    )
    khung_tien_trinh.pack(fill="both", expand=True, pady=(0, 10))

    log = tk.Text(
        khung_tien_trinh,
        height=12,
        bg="#1e1e1e",
        fg="#d4d4d4",
        insertbackground="#d4d4d4",
        font=("Consolas", 9),
        bd=0,
        padx=8,
        pady=6,
        state="disabled",
    )
    log.pack(fill="both", expand=True, padx=12, pady=(8, 12))

    # ----- Chạy 1 tác vụ trên thread nền -----
    def _chay_nen(ham):
        if trang_thai["dang_chay"]:
            _ghi_log("Đang có tác vụ chạy, vui lòng chờ hoàn tất.")
            return

        trang_thai["dang_chay"] = True

        def _worker():
            try:
                trinh_duyet = lay_trinh_duyet()
                trinh_duyet.ghi_log = _ghi_log
                ham(trinh_duyet)
            except LoiTrinhDuyet as e:
                _ghi_log(f"Lỗi: {e}")
            except Exception as e:
                _ghi_log(f"Lỗi không mong đợi: {type(e).__name__}: {e}")
            finally:
                trang_thai["dang_chay"] = False

        threading.Thread(target=_worker, daemon=True).start()

    # ----- Bắt Chrome -----
    def _bat_chrome(trinh_duyet, url, vao_dang_nhap):
        trinh_duyet.mo(url, vao_dang_nhap=vao_dang_nhap)

    def _khi_bat_chrome():
        url = entry_url.get().strip()
        if not url:
            messagebox.showwarning(
                "Thiếu thông tin", "Vui lòng nhập URL Domain!", parent=ung_dung.root
            )
            return
        vao_dang_nhap = bien_dang_nhap_cms.get()
        _chay_nen(lambda trinh_duyet: _bat_chrome(trinh_duyet, url, vao_dang_nhap))

    nut_chrome = tk.Button(
        khung_web,
        text="🌐 BẮT CHROME",
        font=("Arial", 11, "bold"),
        bg="#0097A7",
        fg="white",
        activebackground="#00838F",
        activeforeground="white",
        bd=0,
        pady=6,
        command=_khi_bat_chrome,
    )
    nut_chrome.pack(fill="x", padx=12, pady=(4, 12))

    # ----- Bắt đầu thực thi -----
    def _quy_trinh(trinh_duyet, url, username, password, captcha, tu_dong, tac_vu):
        _ghi_log(f"Bắt đầu thực thi: {url} (tài khoản: {username})")
        if tu_dong:
            ok = trinh_duyet.dang_nhap(
                url,
                username,
                password,
                captcha=captcha,
                cho_captcha=lambda: trang_thai["ma_captcha"],
            )
            if not ok:
                _ghi_log("Dừng quy trình vì đăng nhập chưa thành công.")
                return
        else:
            trinh_duyet.mo(url)
            _ghi_log("Đã mở trang web (không đăng nhập theo tùy chọn).")

        for ten in tac_vu:
            if ten == "Tự động đăng nhập":
                continue
            if ten == "Backup (All-in-One WP Migration)":
                _ghi_log("→ Backup (All-in-One WP Migration)...")
                try:
                    duong_dan = trinh_duyet.backup_ai1wm(url)
                except LoiTrinhDuyet as e:
                    _ghi_log(f"Backup thất bại: {e}")
                    _ghi_log("Dừng quy trình vì chưa có bản backup an toàn.")
                    return
                _ghi_log(f"Backup hoàn tất: {duong_dan}")
                continue
            if ten == "Cập nhật WordPress Core":
                _ghi_log("→ Cập nhật WordPress Core...")
                try:
                    phien_ban = trinh_duyet.cap_nhat_core(url)
                except LoiTrinhDuyet as e:
                    _ghi_log(f"Cập nhật WordPress thất bại: {e}")
                    _ghi_log("Dừng quy trình vì WordPress Core chưa cập nhật được.")
                    return
                if phien_ban:
                    _ghi_log(f"WordPress hiện tại: {phien_ban}")
                continue
            if ten == "Cập nhật tất cả Plugins":
                _ghi_log("→ Cập nhật tất cả Plugins...")
                try:
                    danh_sach = trinh_duyet.cap_nhat_plugin(url)
                except LoiTrinhDuyet as e:
                    _ghi_log(f"Cập nhật plugin thất bại: {e}")
                    return
                _ghi_log(f"Hoàn tất cập nhật {len(danh_sach)} plugin.")
                continue
            _ghi_log(f"→ {ten}: chưa hỗ trợ, sẽ bổ sung ở bước sau.")

    def _khi_bat_dau():
        url = entry_url.get().strip()
        if not url:
            messagebox.showwarning(
                "Thiếu thông tin", "Vui lòng nhập URL Domain!", parent=ung_dung.root
            )
            return

        username = entry_username.get().strip()
        if not username:
            messagebox.showwarning(
                "Thiếu thông tin", "Vui lòng nhập Username / Email!", parent=ung_dung.root
            )
            return

        password = entry_mat_khau.get()
        if not password:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập Mật khẩu!", parent=ung_dung.root)
            return

        captcha = entry_captcha.get().strip()
        trang_thai["ma_captcha"] = captcha

        tac_vu = []
        if bien_tu_dong_dang_nhap.get():
            tac_vu.append("Tự động đăng nhập")
        if bien_backup.get():
            tac_vu.append("Backup (All-in-One WP Migration)")
        if bien_cap_nhat_core.get():
            tac_vu.append("Cập nhật WordPress Core")
        if bien_cap_nhat_plugin.get():
            tac_vu.append("Cập nhật tất cả Plugins")
        if not tac_vu:
            messagebox.showwarning(
                "Chưa chọn tác vụ", "Vui lòng chọn ít nhất một tùy chọn tác vụ!", parent=ung_dung.root
            )
            return

        tu_dong = bien_tu_dong_dang_nhap.get()

        ok, loi = cau_hinh.ghi_cau_hinh(
            {"wp_username": username, "wp_password": password}
        )
        if ok:
            _ghi_log("Đã lưu tài khoản vào database.db.")
        else:
            _ghi_log(f"Không lưu được tài khoản: {loi}")

        _chay_nen(
            lambda trinh_duyet: _quy_trinh(
                trinh_duyet, url, username, password, captcha, tu_dong, tac_vu
            )
        )

    nut_chay = tk.Button(
        khung,
        text="▶ BẮT ĐẦU THỰC THI",
        font=("Arial", 14, "bold"),
        bg="#34A853",
        fg="white",
        activebackground="#2D8F47",
        activeforeground="white",
        bd=0,
        pady=10,
        command=_khi_bat_dau,
    )
    nut_chay.pack(fill="x", pady=(2, 4))

    # ----- Đọc log + bật/tắt nút trên main thread -----
    after_log = {"id": None}

    def _hut_log():
        if not khung_ngoai.winfo_exists():
            return

        while True:
            try:
                noi_dung = hang_log.get_nowait()
            except queue.Empty:
                break
            log.config(state="normal")
            log.insert("end", f"[{datetime.now():%H:%M:%S}] {noi_dung}\n")
            log.see("end")
            log.config(state="disabled")

        trang_thai_nut = "disabled" if trang_thai["dang_chay"] else "normal"
        nut_chrome.config(state=trang_thai_nut)
        nut_chay.config(state=trang_thai_nut)
        after_log["id"] = khung_ngoai.after(150, _hut_log)

    def _huy_hen_gio(event):
        if event.widget is not khung_ngoai:
            return
        if after_log["id"] is not None:
            try:
                khung_ngoai.after_cancel(after_log["id"])
            except tk.TclError:
                pass
            after_log["id"] = None

    khung_ngoai.bind("<Destroy>", _huy_hen_gio)
    after_log["id"] = khung_ngoai.after(150, _hut_log)

    entry_url.focus_set()
    _ghi_log("Sẵn sàng. Nhập URL Domain và bấm BẮT CHROME để bắt đầu.")
