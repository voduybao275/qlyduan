# data/csdl.py
"""
Module kết nối MySQL và các thao tác CRUD cho bảng du_an.

Cài đặt thư viện:
    pip install mysql-connector-python

Cấu hình kết nối: sửa các hằng số DB_* bên dưới cho phù hợp.
"""
from mysql.connector.locales.eng import client_error

import mysql.connector
from mysql.connector import errorcode
from contextlib import contextmanager

from data.cau_hinh import doc_cau_hinh


# ======================================================================
# CẤU HÌNH KẾT NỐI — SỬA CHO ĐÚNG VỚI MYSQL CỦA BẠN
# ======================================================================
DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = ""          # <-- đổi mật khẩu MySQL của bạn
DB_NAME = "project_manager" # <-- tên database (sẽ tự tạo nếu chưa có)

# Bảng lưu dự án
TABLE_DU_AN = "projects"

def _lay_cau_hinh():
    """Đọc cấu hình MySQL hiện tại từ database.db."""
    cfg = doc_cau_hinh()
    return {
        "host": cfg.get("db_host", "127.0.0.1"),
        "port": int(cfg.get("db_port", "3306")),
        "user": cfg.get("db_user", "root"),
        "password": cfg.get("db_password", ""),
        "database": cfg.get("db_name", "quan_ly_du_an"),
    }


# ======================================================================
# KẾT NỐI
# ======================================================================
# def _ket_noi(kem_database=True):
#     """
#     Tạo kết nối MySQL.
#     Nếu kem_database=False: chỉ kết nối server (dùng để tạo DB).
#     """
#     config = {
#         "host": DB_HOST,
#         "port": DB_PORT,
#         "user": DB_USER,
#         "password": DB_PASSWORD,
#         "charset": "utf8mb4",
#         "use_unicode": True,
#     }
#     if kem_database:
#         config["database"] = DB_NAME
#     return mysql.connector.connect(**config)


# @contextmanager
def _ket_noi(kem_database=True):
    cfg = _lay_cau_hinh()
    config = {
        "host": cfg["host"],
        "port": cfg["port"],
        "user": cfg["user"],
        "password": cfg["password"],
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if kem_database:
        config["database"] = cfg["database"]
    return mysql.connector.connect(**config)


@contextmanager
# def ket_noi():
#     """
#     Context manager: tự động đóng kết nối sau khi dùng xong.

#     Cách dùng:
#         with ket_noi() as cnx:
#             cursor = cnx.cursor()
#             cursor.execute(...)
#     """
#     cnx = None
#     try:
#         cnx = _ket_noi()
#         yield cnx
#     finally:
#         if cnx and cnx.is_connected():
#             cnx.close()

def ket_noi():
    cnx = None
    try:
        cnx = _ket_noi()
        yield cnx
    finally:
        if cnx and cnx.is_connected():
            cnx.close()

def kiem_tra_ket_noi(host=None, port=None, user=None, password=None, database=None):
    try:
        if host is not None:
            cnx = mysql.connector.connect(
                host=host,
                port=int(port or 3306),
                user=user,
                password=password or "",
                database=database,
                connection_timeout=5,
            )
            cnx.close()
        else:
            with ket_noi() as cnx:
                if cnx.is_connected():
                    pass
        return True, None
    except mysql.connector.Error as err:
        return False, str(err)     # ← BẮT BUỘC có dòng này
# ======================================================================
# KHỞI TẠO DATABASE & BẢNG (chạy 1 lần khi app khởi động)
# ======================================================================
def khoi_tao_csdl():
    """Tạo database + bảng du_an nếu chưa có. Trả về (True, None) hoặc (False, lỗi)."""
    try:
        cfg = _lay_cau_hinh()

        # Bước 1: kết nối server (chưa database) để tạo DB
        cnx = _ket_noi(kem_database=False)
        cursor = cnx.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.close()
        cnx.close()

        # Bước 2: kết nối vào DB vừa tạo, tạo bảng
        with ket_noi() as cnx2:
            cursor2 = cnx2.cursor()
            cursor2.execute(f"""
                CREATE TABLE IF NOT EXISTS `{TABLE_DU_AN}` (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    mada       VARCHAR(50) NULL,
                    name       VARCHAR(255) NOT NULL,
                    url        VARCHAR(500),
                    host       VARCHAR(255),
                    dev        VARCHAR(255),
                    status     VARCHAR(50) DEFAULT 'Chưa bắt đầu',
                    deadline   DATE NULL,
                    wp_version VARCHAR(50),
                    UNIQUE KEY uq_mada (mada)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Bảng tạo từ phiên bản cũ chưa có cột mada → bổ sung
            cursor2.execute(f"SHOW COLUMNS FROM `{TABLE_DU_AN}` LIKE 'mada'")
            if cursor2.fetchone() is None:
                cursor2.execute(
                    f"ALTER TABLE `{TABLE_DU_AN}` "
                    f"ADD COLUMN `mada` VARCHAR(50) NULL AFTER `id`"
                )
            cursor2.execute(
                f"SHOW INDEX FROM `{TABLE_DU_AN}` WHERE Key_name = 'uq_mada'"
            )
            if cursor2.fetchone() is None:
                cursor2.execute(
                    f"ALTER TABLE `{TABLE_DU_AN}` ADD UNIQUE KEY `uq_mada` (`mada`)"
                )

            cnx2.commit()
            cursor2.close()
        return True, None
    except mysql.connector.Error as err:
        return False, str(err)


# ======================================================================
# CRUD DỰ ÁN
# ======================================================================
def lay_tat_ca_du_an():
    """
    Trả về list[dict] các dự án.
    Mỗi dict: {"id", "mada", "name", "url", "host", "dev", "status", "deadline", "wp_version"}.
    """
    with ket_noi() as cnx:
        cursor = cnx.cursor(dictionary=True)
        cursor.execute(
            f"SELECT id, mada, name, url, host, dev, status, deadline, wp_version "
            f"FROM `{TABLE_DU_AN}` "
            # Dự án có mã đứng trước, sắp theo mã; dự án chưa có mã xuống cuối.
            f"ORDER BY (mada IS NULL OR mada = ''), mada, id"
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows


def nhom_du_an_theo_wp_version():
    """
    Nhóm dự án theo phiên bản WP.
    Trả về list[tuple]: [(wp_version, [du_an, ...]), ...] giảm dần theo số lượng.
    """
    nhom = {}
    for da in lay_tat_ca_du_an():
        version = (da.get("wp_version") or "").strip() or "Chưa check"
        nhom.setdefault(version, []).append(da)
    return sorted(nhom.items(), key=lambda item: (-len(item[1]), item[0]))


def them_du_an(mada, ten, url, host, dev, trang_thai, deadline):
    """
    Thêm dự án mới.
    Trả về (True, None) nếu OK, hoặc (False, thong_bao_loi) nếu lỗi.
    """
    try:
        with ket_noi() as cnx:
            cursor = cnx.cursor()
            # Dùng parameterized query (%s) để chống SQL injection [citation:5][citation:13]
            cursor.execute(
                f"INSERT INTO `{TABLE_DU_AN}` (mada, name, url, host, dev, status, deadline) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (mada or None, ten, url, host, dev, trang_thai, deadline),
            )
            cnx.commit()  # Bắt buộc commit với InnoDB [citation:3]
            cursor.close()
        return True, None
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
            return False, f"Mã dự án '{mada}' đã tồn tại."
        return False, f"Lỗi thêm dự án: {err}"


def cap_nhat_du_an(id, mada, name, url, host, dev, status, deadline):
    """
    Cập nhật thông tin của dự án theo id.
    Trả về (True, None) hoặc (False, thong_bao_loi).
    """
    try:
        with ket_noi() as cnx:
            cursor = cnx.cursor()
            cursor.execute(
                f"UPDATE `{TABLE_DU_AN}` SET "
                f"mada=%s, name=%s, url=%s, host=%s, dev=%s, status=%s, deadline=%s "
                f"WHERE id=%s",
                (mada or None, name, url, host, dev, status, deadline, id),
            )
            cnx.commit()
            cursor.close()
        return True, None
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
            return False, f"Mã dự án '{mada}' đã tồn tại."
        return False, f"Lỗi cập nhật dự án: {err}"


def xoa_du_an(ma):
    """
    Xóa dự án theo mã.
    Trả về (True, None) hoặc (False, thong_bao_loi).
    """
    try:
        with ket_noi() as cnx:
            cursor = cnx.cursor()
            cursor.execute(
                f"DELETE FROM `{TABLE_DU_AN}` WHERE id = %s",
                (ma,),
            )
            cnx.commit()
            cursor.close()
        return True, None
    except mysql.connector.Error as err:
        return False, f"Lỗi xóa dự án: {err}"


def xoa_tat_ca_du_an():
    """
    Xóa toàn bộ dự án và đưa id tự tăng về 1.
    Trả về (True, None) hoặc (False, thong_bao_loi).
    """
    try:
        with ket_noi() as cnx:
            cursor = cnx.cursor()
            cursor.execute(f"DELETE FROM `{TABLE_DU_AN}`")
            cursor.execute(f"ALTER TABLE `{TABLE_DU_AN}` AUTO_INCREMENT = 1")
            cnx.commit()
            cursor.close()
        return True, None
    except mysql.connector.Error as err:
        return False, f"Lỗi reset dữ liệu dự án: {err}"


# def kiem_tra_ket_noi():
#     """Trả về True nếu kết nối MySQL thành công."""
#     try:
#         with ket_noi() as cnx:
#             return cnx.is_connected()
#     except mysql.connector.Error:
#         return False