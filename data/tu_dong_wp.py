# data/tu_dong_wp.py
"""Điều khiển Chrome thật (Playwright) cho công cụ WordPress Auto Manager."""
import atexit
import os
import queue
import re
import threading

from data.cau_hinh import lay_duong_dan_db

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

    class PlaywrightTimeout(Exception):
        pass

# Profile riêng để giữ cookie/phiên đăng nhập giữa các lần mở app
PROFILE_DIR = os.path.join(os.path.dirname(lay_duong_dan_db()), "chrome_profile")

O_CAPTCHA = (
    'input[name*="captcha" i]',
    'input[id*="captcha" i]',
    'input[placeholder*="captcha" i]',
)


class LoiTrinhDuyet(Exception):
    pass


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

    def mo(self, url, vao_dang_nhap=False):
        """Mở Chrome tới trang web (hoặc trang đăng nhập WP)."""
        def _lam():
            page = self._dam_bao_chrome()
            dich = self._url_trang_web(url)
            if vao_dang_nhap:
                dich += "/wp-login.php"
            page.goto(dich, wait_until="domcontentloaded", timeout=45000)
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

    def dang_nhap(self, url, username, password, captcha="", cho_captcha=None):
        """Đăng nhập wp-login.php; nếu có CAPTCHA thì chờ mã do người dùng nhập."""
        def _lam():
            page = self._dam_bao_chrome()
            page.goto(
                self._url_trang_web(url) + "/wp-login.php",
                wait_until="domcontentloaded",
                timeout=45000,
            )
            self.ghi_log(f"Mở trang đăng nhập: {page.url}")

            if self._da_dang_nhap(page):
                self.ghi_log("Chrome đang có phiên đăng nhập sẵn.")
                return True

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
