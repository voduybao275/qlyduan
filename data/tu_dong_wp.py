# data/tu_dong_wp.py
"""Điều khiển Chrome thật (Playwright) cho công cụ WordPress Auto Manager."""
import atexit
import os
import queue
import re
import threading
from datetime import datetime
from urllib.parse import urlsplit

from data.cau_hinh import lay_duong_dan_db

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

    class PlaywrightTimeout(Exception):
        pass

    class PlaywrightError(Exception):
        pass

# Profile riêng để giữ cookie/phiên đăng nhập giữa các lần mở app
PROFILE_DIR = os.path.join(os.path.dirname(lay_duong_dan_db()), "chrome_profile")

# Trang đăng nhập CMS tùy biến (plugin đổi link login); không có thì dùng wp-login.php
DUONG_DAN_LOGIN_CMS = "/cms_login"

# Nơi lưu file backup .wpress
BACKUP_DIR = os.path.join(os.path.dirname(lay_duong_dan_db()), "backups")

O_CAPTCHA = (
    'input[name*="captcha" i]',
    'input[id*="captcha" i]',
    'input[placeholder*="captcha" i]',
)


class LoiTrinhDuyet(Exception):
    pass


def _gon_chu(text, gioi_han=300):
    text = " ".join((text or "").split())
    if len(text) <= gioi_han:
        return text
    return text[:gioi_han].rstrip() + "..."


def chuan_hoa_url(url):
    url = (url or "").strip()
    if not url:
        raise LoiTrinhDuyet("Chưa nhập URL Domain.")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    return url.rstrip("/")


class TrinhDuyetWP:
    """
    Playwright chỉ dùng được trong đúng thread đã khởi tạo nó, nên mọi thao tác
    được đẩy qua queue cho 1 thread riêng xử lý tuần tự.
    """

    def __init__(self):
        self.ghi_log = lambda noi_dung: None
        self._context = None
        self._page = None
        self._p = None
        self._loi_khoi_dong = None
        self._hang_doi = queue.Queue()
        self._san_sang = threading.Event()
        self._thread = threading.Thread(target=self._vong_lap, daemon=True)
        self._thread.start()
        self._san_sang.wait(30)

    # ----- Hạ tầng thread -----
    def _vong_lap(self):
        if sync_playwright is None:
            self._loi_khoi_dong = LoiTrinhDuyet(
                "Chưa cài Playwright. Chạy 'pip install playwright' rồi mở lại app."
            )
            self._san_sang.set()
            return

        try:
            with sync_playwright() as p:
                self._p = p
                self._san_sang.set()
                while True:
                    ham, xong, loi, ket_qua = self._hang_doi.get()
                    if ham is None:
                        break
                    try:
                        ket_qua.append(ham())
                    except Exception as e:
                        loi.append(e)
                    finally:
                        xong.set()
        except Exception as e:
            self.ghi_log(f"[Playwright] Không khởi động được: {e}")
        finally:
            self._san_sang.set()
            self._dong_chrome()

    def _chay(self, ham, thoi_gian_cho=300):
        if self._loi_khoi_dong is not None:
            raise self._loi_khoi_dong
        if not self._thread.is_alive():
            raise LoiTrinhDuyet("Tiến trình trình duyệt không chạy.")
        xong = threading.Event()
        loi, ket_qua = [], []
        self._hang_doi.put((ham, xong, loi, ket_qua))
        if not xong.wait(thoi_gian_cho):
            raise LoiTrinhDuyet("Chrome không phản hồi trong thời gian chờ.")
        if loi:
            raise loi[0]
        return ket_qua[0] if ket_qua else None

    # ----- Chrome -----
    def _dam_bao_chrome(self):
        if self._context is not None:
            try:
                if self._page is not None and not self._page.is_closed():
                    return self._page
            except Exception:
                pass
            self._dong_chrome()

        self.ghi_log("Đang khởi động Chrome...")
        os.makedirs(PROFILE_DIR, exist_ok=True)
        try:
            self._context = self._p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                channel="chrome",
                headless=False,
                no_viewport=True,
                ignore_https_errors=True,
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
            )
        except Exception as e:
            raise LoiTrinhDuyet(
                f"Không mở được Chrome: {e}\nNếu Chrome đang chạy với profile này, hãy đóng nó rồi thử lại."
            )

        self._page = (
            self._context.pages[0] if self._context.pages else self._context.new_page()
        )
        self.ghi_log("Chrome đã sẵn sàng.")
        return self._page

    def _dong_chrome(self):
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
        self._context = None
        self._page = None

    # ----- Điều hướng -----
    def _url_trang_web(self, url):
        base = chuan_hoa_url(url)
        return re.sub(r"/(wp-login\.php|wp-admin.*)$", "", base, flags=re.IGNORECASE)

    @staticmethod
    def _co_form_dang_nhap(page):
        try:
            return page.locator("#user_login").count() > 0
        except Exception:
            return False

    @staticmethod
    def _cung_domain(page, base):
        try:
            return urlsplit(page.url).netloc == urlsplit(base).netloc
        except Exception:
            return False

    def _di_chuyen(self, page, dich, mo_ta):
        try:
            return page.goto(dich, wait_until="domcontentloaded", timeout=45000)
        except PlaywrightTimeout:
            raise LoiTrinhDuyet(
                f"{mo_ta} quá thời gian chờ: {dich}\n"
                "Kiểm tra lại URL Domain hoặc kết nối mạng."
            )
        except PlaywrightError as e:
            raise LoiTrinhDuyet(f"{mo_ta} thất bại: {dich}\n{e}")

    def _di_toi_trang_dang_nhap(self, page, base):
        """Ưu tiên /cms_login, sau đó wp-login.php, cuối cùng để wp-admin tự chuyển hướng.

        Nhiều site đổi đường dẫn login (plugin bảo mật) nên wp-login.php trả 404;
        khi đó vào wp-admin, WordPress sẽ redirect về đúng trang đăng nhập.
        """
        for duong_dan, mo_ta in (
            (DUONG_DAN_LOGIN_CMS, "Mở trang đăng nhập CMS"),
            ("/wp-login.php", "Mở trang đăng nhập WordPress"),
        ):
            dich = base + duong_dan
            self.ghi_log(f"{mo_ta}: {dich}")
            resp = self._di_chuyen(page, dich, mo_ta)

            if self._co_form_dang_nhap(page):
                return True
            if "wp-admin" in page.url and "wp-login.php" not in page.url:
                self.ghi_log("Chrome đang có phiên đăng nhập sẵn.")
                return True

            ma_http = resp.status if resp is not None else 0
            if ma_http and ma_http < 400:
                return True
            self.ghi_log(f"{dich} không dùng được (HTTP {ma_http}).")

        self.ghi_log("Thử qua wp-admin để WordPress tự chuyển hướng...")
        self._di_chuyen(page, base + "/wp-admin/", "Mở wp-admin")

        if self._co_form_dang_nhap(page):
            self.ghi_log(f"Trang đăng nhập thật: {page.url}")
            return True
        if "wp-admin" in page.url:
            self.ghi_log("Chrome đang có phiên đăng nhập sẵn.")
            return True

        self.ghi_log(f"Không tìm thấy trang đăng nhập. URL hiện tại: {page.url}")
        return False

    def mo(self, url, vao_dang_nhap=False):
        """Mở Chrome tới wp-admin, hoặc trang đăng nhập nếu cần."""
        def _lam():
            page = self._dam_bao_chrome()
            base = self._url_trang_web(url)
            if vao_dang_nhap:
                self._di_toi_trang_dang_nhap(page, base)
            else:
                self.ghi_log("Mở trang quản trị (wp-admin)...")
                self._di_chuyen(page, base + "/wp-admin/", "Mở wp-admin")
                if "wp-login.php" in page.url:
                    self.ghi_log(
                        "Chưa có phiên đăng nhập — WordPress chuyển sang trang login."
                    )
            try:
                page.bring_to_front()
            except Exception:
                pass
            self.ghi_log(f"Đã mở: {page.url}")
            return page.url

        return self._chay(_lam)

    @staticmethod
    def _da_dang_nhap(page):
        try:
            if not page.url or "wp-login.php" in page.url:
                return False
            if "wp-admin" in page.url:
                return True
            return page.locator("#wpadminbar").count() > 0
        except Exception:
            return False

    @staticmethod
    def _tim_o_captcha(page):
        for selector in O_CAPTCHA:
            locator = page.locator(selector)
            if locator.count():
                return locator.first
        return None

    # ----- Backup (All-in-One WP Migration) -----
    @staticmethod
    def _bam_export_file(page):
        o_file = page.locator("#ai1wm-export-file")
        if not o_file.count():
            raise LoiTrinhDuyet(
                "Không tìm thấy nút File của All-in-One WP Migration.\n"
                "Kiểm tra plugin đã kích hoạt và tài khoản có quyền admin."
            )
        # Nút File nằm trong menu xổ xuống bị phần tử khác che; click chuột thật
        # bị Playwright chặn nên gọi thẳng sự kiện click của plugin.
        try:
            o_file.first.dispatch_event("click")
        except PlaywrightError as e:
            raise LoiTrinhDuyet(f"Không bấm được nút File để export: {e}")

    @staticmethod
    def _loi_export(page):
        for selector in (".ai1wm-modal-container .ai1wm-title-red", ".ai1wm-title-red"):
            o_loi = page.locator(selector)
            if o_loi.count():
                noi_dung = " ".join(o_loi.first.inner_text().split())
                if noi_dung:
                    return noi_dung
        return ""

    def _cho_export_xong(self, page, thoi_gian_toi_da=3600, thoi_gian_khoi_dong=20):
        """Poll modal trạng thái của AI1WM; trả về nút Download khi export xong.

        Báo lỗi sớm khi export không khởi động được (ví dụ bật mã hóa backup
        nhưng thiếu mật khẩu) thay vì chờ im lặng.
        """
        modal = page.locator(".ai1wm-modal-container")

        da_cho = 0
        while da_cho < thoi_gian_khoi_dong:
            loi = self._loi_export(page)
            if loi:
                raise LoiTrinhDuyet(f"Export thất bại: {loi}")
            o_ma_hoa = page.locator(".ai1wm-has-error")
            if o_ma_hoa.count() and o_ma_hoa.first.is_visible():
                raise LoiTrinhDuyet(
                    "Tùy chọn mã hóa backup đang bật nhưng thiếu/không khớp mật khẩu.\n"
                    "Tắt mã hóa trong All-in-One WP Migration rồi thử lại."
                )
            if modal.count() and modal.first.is_visible():
                break
            page.wait_for_timeout(1000)
            da_cho += 1
        else:
            raise LoiTrinhDuyet(
                "Đã bấm File nhưng tiến trình export không bắt đầu sau "
                f"{thoi_gian_khoi_dong}s.\n"
                "Mở Chrome kiểm tra trang Export, hoặc thử export thủ công một lần."
            )

        noi_dung_cu = ""
        moc_nhip = 0
        da_cho = 0
        while da_cho <= thoi_gian_toi_da:
            try:
                modal_hien = modal.count() and modal.first.is_visible()
            except PlaywrightError:
                modal_hien = False

            if modal_hien:
                try:
                    noi_dung = " ".join(modal.first.inner_text().split())
                except PlaywrightError:
                    noi_dung = ""

                if noi_dung and noi_dung != noi_dung_cu:
                    noi_dung_cu = noi_dung
                    self.ghi_log(f"  {noi_dung}")

                nut_tai = modal.locator(".ai1wm-button-download, .ai1wm-direct-download")
            else:
                nut_tai = page.locator(".ai1wm-button-download, .ai1wm-direct-download")

            if nut_tai.count():
                return nut_tai.first

            loi = self._loi_export(page)
            if loi:
                raise LoiTrinhDuyet(f"Export thất bại: {loi}")

            page.wait_for_timeout(2000)
            da_cho += 2
            moc_nhip += 2
            if moc_nhip >= 30:
                moc_nhip = 0
                self.ghi_log(f"  ... vẫn đang export ({da_cho}s)")

        raise LoiTrinhDuyet("Export quá thời gian chờ (1 giờ).")

    def backup_ai1wm(self, url, thu_muc_luu=None):
        """Xuất file backup .wpress bằng All-in-One WP Migration và lưu về máy."""
        def _lam():
            page = self._dam_bao_chrome()
            base = self._url_trang_web(url)

            if not self._da_dang_nhap(page):
                raise LoiTrinhDuyet(
                    "Chưa đăng nhập WordPress nên không backup được.\n"
                    "Bật 'Tự động đăng nhập' hoặc đăng nhập thủ công trên Chrome."
                )

            self.ghi_log("Mở trang Export của All-in-One WP Migration...")
            self._di_chuyen(
                page,
                base + "/wp-admin/admin.php?page=ai1wm_export",
                "Mở trang Export AI1WM",
            )

            if not page.locator("#ai1wm-export-form").count():
                raise LoiTrinhDuyet(
                    "Trang hiện tại không có form Export của All-in-One WP Migration.\n"
                    "Kiểm tra plugin đã cài/kích hoạt và tài khoản có quyền admin."
                )

            self.ghi_log("Bắt đầu export...")
            self._bam_export_file(page)
            nut_tai = self._cho_export_xong(page)
            self.ghi_log("Export xong, đang tải file backup...")

            try:
                with page.expect_download(timeout=120000) as thong_tin:
                    try:
                        nut_tai.click(force=True)
                    except PlaywrightTimeout:
                        # Modal còn hiệu ứng nên nút bị coi là "không ổn định";
                        # gọi thẳng sự kiện click để plugin xử lý tải xuống.
                        nut_tai.dispatch_event("click")
                tep = thong_tin.value
            except PlaywrightTimeout:
                raise LoiTrinhDuyet(
                    "Trình duyệt không tải được file backup (quá thời gian chờ)."
                )

            ten_file = os.path.basename(tep.suggested_filename or "backup.wpress")
            if not ten_file.lower().endswith(".wpress"):
                ten_file += ".wpress"

            thu_muc = thu_muc_luu or os.path.join(
                BACKUP_DIR, urlsplit(base).netloc.replace(":", "_")
            )
            os.makedirs(thu_muc, exist_ok=True)
            duong_dan = os.path.join(
                thu_muc, f"{datetime.now():%Y%m%d-%H%M%S}_{ten_file}"
            )
            tep.save_as(duong_dan)

            self.ghi_log(f"Đã lưu backup: {duong_dan}")
            return duong_dan

        return self._chay(_lam, thoi_gian_cho=3700)

    # ----- Cập nhật WordPress Core / Plugins -----
    def _mo_trang_cap_nhat(self, page, base):
        if not self._da_dang_nhap(page):
            raise LoiTrinhDuyet(
                "Chưa đăng nhập WordPress nên không cập nhật được.\n"
                "Bật 'Tự động đăng nhập' hoặc đăng nhập thủ công trên Chrome."
            )

        self.ghi_log("Mở trang Cập nhật WordPress...")
        self._di_chuyen(
            page, base + "/wp-admin/update-core.php", "Mở trang Cập nhật WordPress"
        )

        if "wp-login.php" in page.url:
            raise LoiTrinhDuyet(
                "Phiên đăng nhập WordPress đã hết hạn — hãy đăng nhập lại rồi thử tiếp."
            )

        o_loi = page.locator("#error-page")
        if o_loi.count():
            raise LoiTrinhDuyet(
                "Không truy cập được trang cập nhật: "
                + _gon_chu(o_loi.first.inner_text())
            )

        if not page.locator("h2.wp-current-version, #update-plugins-table").count():
            raise LoiTrinhDuyet(
                "Không mở được trang Cập nhật WordPress (URL hiện tại: "
                f"{page.url}).\n"
                "Kiểm tra tài khoản có quyền quản trị hoặc plugin bảo mật đang chặn."
            )

    @staticmethod
    def _phien_ban_core(page):
        o_phien_ban = page.locator("h2.wp-current-version")
        if o_phien_ban.count():
            m = re.search(r"\d+(?:\.\d+)+", o_phien_ban.first.inner_text())
            if m:
                return m.group(0)
        return ""

    @staticmethod
    def _thong_bao_loi_admin(page):
        for selector in ("#error-page", ".notice-error", "div.error"):
            o_loi = page.locator(selector)
            if o_loi.count():
                noi_dung = _gon_chu(o_loi.first.inner_text())
                if noi_dung:
                    return noi_dung
        return ""

    def cap_nhat_core(self, url, thoi_gian_toi_da=1800):
        """Cập nhật WordPress Core lên bản mới nhất nếu có."""
        def _lam():
            page = self._dam_bao_chrome()
            base = self._url_trang_web(url)
            self._mo_trang_cap_nhat(page, base)

            hien_tai = self._phien_ban_core(page)
            form = page.locator("form[name='upgrade']").first
            if not form.count():
                self.ghi_log(
                    "WordPress đã ở phiên bản mới nhất"
                    + (f" ({hien_tai})" if hien_tai else "")
                    + "."
                )
                return hien_tai

            # WordPress luôn có form re-install khi đã mới nhất; chỉ form
            # do-core-upgrade mới là bản cập nhật thật.
            hanh_dong = form.get_attribute("action") or ""
            if "do-core-upgrade" not in hanh_dong:
                self.ghi_log(
                    "WordPress đã ở phiên bản mới nhất"
                    + (f" ({hien_tai})" if hien_tai else "")
                    + " — không cần cập nhật."
                )
                return hien_tai

            nut = page.locator("#upgrade").first
            if not nut.count():
                ly_do = ""
                o_ly_do = page.locator(".core-updates li").first
                if o_ly_do.count():
                    ly_do = _gon_chu(o_ly_do.inner_text())
                raise LoiTrinhDuyet(
                    "WordPress có bản mới nhưng không cập nhật tự động được.\n"
                    + (
                        f"Lý do: {ly_do}"
                        if ly_do
                        else "Kiểm tra yêu cầu PHP/MySQL của bản cập nhật."
                    )
                )

            o_muc_tieu = form.locator("input[name='version']").first
            muc_tieu = o_muc_tieu.input_value() if o_muc_tieu.count() else ""
            self.ghi_log(
                "Có bản cập nhật WordPress"
                + (f" {muc_tieu}" if muc_tieu else "")
                + f" (hiện tại {hien_tai or 'không rõ'}) — đang cập nhật..."
            )

            try:
                with page.expect_navigation(timeout=thoi_gian_toi_da * 1000):
                    nut.click()
            except PlaywrightTimeout:
                raise LoiTrinhDuyet(
                    "Cập nhật WordPress quá thời gian chờ.\n"
                    "Mở Chrome kiểm tra tiến trình, hoặc chạy cập nhật thủ công."
                )
            except PlaywrightError:
                # POST xong chuyển ngay sang about.php có thể làm gián đoạn
                # việc chờ điều hướng — trạng thái trang bên dưới sẽ xác minh.
                pass

            # Thành công thì WordPress tự chuyển tới about.php?updated
            da_cho = 0
            while da_cho < 10:
                if "about.php?updated" in page.url:
                    break
                if page.locator("#error-page").count():
                    break
                if page.locator("#request-filesystem-credentials-form").count():
                    break
                if self._thong_bao_loi_admin(page):
                    break
                page.wait_for_timeout(1000)
                da_cho += 1

            if "about.php?updated" in page.url:
                if muc_tieu:
                    self.ghi_log(f"WordPress đã cập nhật lên {muc_tieu}.")
                else:
                    self.ghi_log("WordPress đã cập nhật xong.")
                return muc_tieu

            if page.locator("#request-filesystem-credentials-form").count():
                raise LoiTrinhDuyet(
                    "WordPress yêu cầu thông tin FTP/SSH để ghi file nên không tự cập nhật được.\n"
                    "Cấu hình quyền ghi file cho WordPress rồi thử lại."
                )

            loi = self._thong_bao_loi_admin(page)
            if loi:
                raise LoiTrinhDuyet(f"Cập nhật WordPress thất bại: {loi}")

            thong_diep = ""
            o_ket_qua = page.locator(".wrap").first
            if o_ket_qua.count():
                thong_diep = _gon_chu(o_ket_qua.inner_text(), 500)

            # Không thấy chuyển trang: mở lại trang cập nhật để xác minh
            self._di_chuyen(
                page,
                base + "/wp-admin/update-core.php",
                "Kiểm tra lại phiên bản WordPress",
            )
            if "wp-login.php" in page.url:
                raise LoiTrinhDuyet(
                    "Phiên đăng nhập WordPress đã hết hạn — hãy đăng nhập lại rồi thử tiếp."
                )
            sau = self._phien_ban_core(page)
            form_sau = page.locator("form[name='upgrade']").first
            con_cap_nhat = form_sau.count() and "do-core-upgrade" in (
                form_sau.get_attribute("action") or ""
            )
            if con_cap_nhat:
                raise LoiTrinhDuyet(
                    f"Cập nhật WordPress chưa thành công (vẫn ở phiên bản {sau or 'cũ'})."
                    + (f"\n{thong_diep}" if thong_diep else "")
                )

            self.ghi_log(f"WordPress đã cập nhật lên {sau or muc_tieu}.")
            return sau or muc_tieu

        return self._chay(_lam, thoi_gian_cho=thoi_gian_toi_da + 300)

    @staticmethod
    def _danh_sach_plugin_can_cap_nhat(page):
        return [
            ten
            for ten in (
                _gon_chu(chu, 120)
                for chu in page.locator(
                    "#update-plugins-table td.plugin-title strong"
                ).all_inner_texts()
            )
            if ten
        ]

    def _tim_frame_cap_nhat_plugin(self, page, thoi_gian_cho=60):
        da_cho = 0
        while da_cho < thoi_gian_cho:
            try:
                for khung in page.frames:
                    if "update.php" in khung.url and "update-selected" in khung.url:
                        return khung
            except PlaywrightError:
                pass
            page.wait_for_timeout(500)
            da_cho += 1
        return None

    def cap_nhat_plugin(self, url, thoi_gian_toi_da=1800):
        """Cập nhật tất cả plugin đang có bản mới."""
        def _lam():
            page = self._dam_bao_chrome()
            base = self._url_trang_web(url)
            self._mo_trang_cap_nhat(page, base)

            form = page.locator("form[name='upgrade-plugins']").first
            if not form.count():
                self.ghi_log("Tất cả plugin đã ở phiên bản mới nhất — không cần cập nhật.")
                return []

            ten_plugin = self._danh_sach_plugin_can_cap_nhat(page)
            self.ghi_log(
                f"Có {len(ten_plugin)} plugin cần cập nhật: {', '.join(ten_plugin)}"
            )

            cac_o = page.locator("#update-plugins-table input[name='checked[]']")
            for i in range(cac_o.count()):
                cac_o.nth(i).check()
            self.ghi_log("Đã chọn tất cả plugin — bắt đầu cập nhật...")

            try:
                with page.expect_navigation(timeout=120000):
                    page.locator("#upgrade-plugins").click()
            except PlaywrightTimeout:
                raise LoiTrinhDuyet(
                    "Không mở được tiến trình cập nhật plugin (quá thời gian chờ)."
                )

            if "wp-login.php" in page.url:
                raise LoiTrinhDuyet(
                    "Phiên đăng nhập WordPress đã hết hạn — hãy đăng nhập lại rồi thử tiếp."
                )

            khung = self._tim_frame_cap_nhat_plugin(page)
            if khung is None:
                raise LoiTrinhDuyet(
                    "Không thấy khung tiến trình cập nhật plugin.\n"
                    "Mở Chrome kiểm tra trang Cập nhật, hoặc thử cập nhật thủ công."
                )

            loi = []
            tieu_de_da_log = set()
            xong = False
            da_cho = 0
            while da_cho <= thoi_gian_toi_da:
                try:
                    for tieu_de in khung.locator("h2").all_inner_texts():
                        tieu_de = _gon_chu(tieu_de)
                        if tieu_de and tieu_de not in tieu_de_da_log:
                            tieu_de_da_log.add(tieu_de)
                            self.ghi_log(f"  {tieu_de}")

                    for chu in khung.locator(".notice-error, div.error").all_inner_texts():
                        chu = _gon_chu(chu)
                        if chu and chu not in loi:
                            loi.append(chu)
                            self.ghi_log(f"  Lỗi: {chu}")

                    if khung.locator('a[target="_parent"]').count():
                        xong = True
                        break
                except PlaywrightError:
                    pass

                if da_cho and da_cho % 30 == 0:
                    self.ghi_log(f"  ... vẫn đang cập nhật plugin ({da_cho}s)")

                page.wait_for_timeout(2000)
                da_cho += 2

            if not xong:
                raise LoiTrinhDuyet(
                    f"Cập nhật plugin quá thời gian chờ ({thoi_gian_toi_da // 60} phút)."
                )

            self._di_chuyen(
                page,
                base + "/wp-admin/update-core.php",
                "Kiểm tra lại danh sách plugin",
            )
            if "wp-login.php" in page.url:
                raise LoiTrinhDuyet(
                    "Phiên đăng nhập WordPress đã hết hạn — hãy đăng nhập lại rồi thử tiếp."
                )
            con_lai = self._danh_sach_plugin_can_cap_nhat(page)

            if loi:
                raise LoiTrinhDuyet(
                    "Một số plugin cập nhật lỗi:\n- " + "\n- ".join(loi)
                    + (
                        "\nCòn cần cập nhật: " + ", ".join(con_lai)
                        if con_lai
                        else ""
                    )
                )
            if con_lai:
                raise LoiTrinhDuyet(
                    "Còn plugin chưa cập nhật được: " + ", ".join(con_lai)
                )

            self.ghi_log(f"Đã cập nhật xong toàn bộ {len(ten_plugin)} plugin.")
            return ten_plugin

        return self._chay(_lam, thoi_gian_cho=thoi_gian_toi_da + 300)

    def dang_nhap(self, url, username, password, captcha="", cho_captcha=None):
        """Đăng nhập trang quản trị; nếu có CAPTCHA thì chờ mã do người dùng nhập."""
        def _lam():
            page = self._dam_bao_chrome()
            base = self._url_trang_web(url)

            if self._cung_domain(page, base) and self._co_form_dang_nhap(page):
                self.ghi_log(f"Điền vào trang đang mở (không tải lại): {page.url}")
            else:
                if self._da_dang_nhap(page) and not self._co_form_dang_nhap(page):
                    self.ghi_log("Chrome đang có phiên đăng nhập sẵn.")
                    return True

                if not self._di_toi_trang_dang_nhap(page, base):
                    raise LoiTrinhDuyet(
                        f"Không mở được trang đăng nhập của {base}.\n"
                        "Kiểm tra lại URL Domain hoặc đăng nhập thủ công trên Chrome."
                    )
                self.ghi_log(f"Mở trang đăng nhập: {page.url}")

                if self._da_dang_nhap(page):
                    self.ghi_log("Chrome đang có phiên đăng nhập sẵn.")
                    return True

                if not self._co_form_dang_nhap(page):
                    raise LoiTrinhDuyet(
                        f"Không thấy ô đăng nhập WordPress tại {page.url}.\n"
                        "Có thể site dùng trang đăng nhập tùy biến — hãy đăng nhập thủ công trên Chrome."
                    )

            page.fill("#user_login", username)
            page.fill("#user_pass", password)

            o_captcha = self._tim_o_captcha(page)
            ma_captcha = (captcha or "").strip()
            if o_captcha is not None:
                if not ma_captcha and cho_captcha is not None:
                    self.ghi_log(
                        "Phát hiện CAPTCHA — nhập mã vào ô 'Mã CAPTCHA' trong app "
                        "(chờ tối đa 3 phút)."
                    )
                    for _ in range(180):
                        ma_captcha = (cho_captcha() or "").strip()
                        if ma_captcha:
                            break
                        page.wait_for_timeout(1000)
                if ma_captcha:
                    o_captcha.fill(ma_captcha)
                    self.ghi_log("Đã điền mã CAPTCHA.")
                else:
                    self.ghi_log("Chưa có mã CAPTCHA, vẫn thử đăng nhập.")

            page.click("#wp-submit")
            try:
                page.wait_for_load_state("domcontentloaded", timeout=30000)
            except PlaywrightTimeout:
                pass

            if self._da_dang_nhap(page):
                self.ghi_log(f"Đăng nhập thành công: {page.url}")
                return True

            thong_bao_loi = ""
            o_loi = page.locator("#login_error")
            if o_loi.count():
                thong_bao_loi = o_loi.first.inner_text().strip()
            self.ghi_log(
                "Đăng nhập thất bại. "
                + (thong_bao_loi or "Kiểm tra tài khoản/mật khẩu hoặc CAPTCHA.")
            )
            return False

        return self._chay(_lam)

    def dong(self):
        self._hang_doi.put((None, None, None, None))
        self._thread.join(8)


_TRINH_DUYET = None


def lay_trinh_duyet():
    global _TRINH_DUYET
    if _TRINH_DUYET is None:
        _TRINH_DUYET = TrinhDuyetWP()
    return _TRINH_DUYET


@atexit.register
def _tat_trinh_duyet():
    if _TRINH_DUYET is not None:
        _TRINH_DUYET.dong()
