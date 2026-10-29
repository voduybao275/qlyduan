# data/cau_hinh.py
"""
Lưu thông tin cấu hình kết nối MySQL vào database.db (SQLite).

Cấu trúc bảng:
    cau_hinh(key TEXT PRIMARY KEY, value TEXT)

Các key:
    db_host, db_port, db_user, db_password, db_name
"""

import os
import sys
import sqlite3

def lay_duong_dan_db():
    # Nếu đang chạy từ file .exe (PyInstaller)
    if getattr(sys, 'frozen', False):
        # Lấy thư mục chứa file .exe thực tế
        thu_muc_goc = os.path.dirname(sys.executable)
    else:
        # Đang chạy từ source (python main.py)
        thu_muc_goc = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return os.path.join(thu_muc_goc, "database.db")

DUONG_DAN_CAU_HINH = lay_duong_dan_db()
# DUONG_DAN_CAU_HINH = os.path.join(
#     os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
#     "database.db",
# )

MAC_DINH = {
    "db_host": "127.0.0.1",
    "db_port": "3306",
    "db_user": "root",
    "db_password": "",
    "db_name": "quan_ly_du_an",
}


def _ket_noi_sqlite():
    """Kết nối SQLite tới database.db, tạo bảng nếu chưa có."""
    conn = sqlite3.connect(DUONG_DAN_CAU_HINH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cau_hinh (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    return conn


def doc_cau_hinh():
    """Đọc toàn bộ cấu hình. Trả về dict (có default nếu thiếu key)."""
    ket_qua = dict(MAC_DINH)   # khởi tạo với giá trị mặc định

    if not os.path.exists(DUONG_DAN_CAU_HINH):
        return ket_qua

    try:
        conn = _ket_noi_sqlite()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM cau_hinh")
        for key, value in cursor.fetchall():
            ket_qua[key] = value
        conn.close()
    except sqlite3.Error as e:
        print(f"[cau_hinh] Lỗi đọc: {e}")

    return ket_qua


def ghi_cau_hinh(du_lieu: dict):
    """
    Ghi đè cấu hình.
    du_lieu: dict với các key db_host, db_port, db_user, db_password, db_name
    """
    try:
        conn = _ket_noi_sqlite()
        cursor = conn.cursor()
        for key, value in du_lieu.items():
            cursor.execute("""
                INSERT INTO cau_hinh (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, str(value)))
        conn.commit()
        conn.close()
        return True, None
    except sqlite3.Error as e:
        return False, f"Lỗi ghi cấu hình: {e}"