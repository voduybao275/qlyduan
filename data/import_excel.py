# data/import_excel.py
"""
Đọc file Excel và import vào bảng du_an (MySQL).

Cột Excel mong đợi (theo tên header, không phân biệt hoa/thường):
    mada, name, url, host, dev, status, deadline, wp_version

Cột "name" phải có trong file nhưng giá trị được phép trống — dòng thiếu tên
vẫn được import và lưu với tên rỗng. "mada" (mã dự án, ví dụ GKV_001) dùng để
nhận diện dòng khi import; nếu trống thì nhận diện theo "name".
"""

import os
from datetime import datetime, date

try:
    import pandas as pd
except ImportError:
    pd = None

from data import csdl


# Thứ tự cột mong đợi
COT_BAT_BUOC = ["name"]
COT_TUY_CHON = ["mada", "url", "host", "dev", "status", "deadline", "wp_version"]
COT_HOP_LE = COT_BAT_BUOC + COT_TUY_CHON

TRANG_THAI_HOP_LE = ["Chưa bắt đầu", "Đang làm", "Hoàn thành"]


def doc_file_excel(duong_dan):
    """
    Đọc file Excel, trả về DataFrame đã chuẩn hóa.

    Raise ValueError nếu:
        - Không cài pandas
        - File không tồn tại
        - Thiếu cột 'name'
    """
    if pd is None:
        raise ValueError(
            "Chưa cài pandas. Chạy: pip install pandas openpyxl"
        )

    if not os.path.exists(duong_dan):
        raise ValueError(f"File không tồn tại: {duong_dan}")

    try:
        df = pd.read_excel(duong_dan, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"Không đọc được file Excel: {e}")

    # Chuẩn hóa tên cột: strip, lower
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Kiểm tra cột bắt buộc
    if "name" not in df.columns:
        raise ValueError(
            f"File Excel thiếu cột bắt buộc 'name'.\n"
            f"Các cột hiện có: {list(df.columns)}"
        )

    # Bổ sung cột thiếu (nếu có)
    for cot in COT_HOP_LE:
        if cot not in df.columns:
            df[cot] = None

    # Chỉ giữ các cột hợp lệ
    df = df[COT_HOP_LE]

    return df


def chuan_hoa_dong(row):
    """
    Chuẩn hóa 1 dòng dữ liệu từ DataFrame thành dict.
    Cột name có thể trống — dòng vẫn được import với tên để trống.
    Trả về (dict, danh_sach_loi).
    """
    loi = []

    def _lay(cot):
        val = row.get(cot)
        if pd is not None and pd.isna(val):
            return None
        if isinstance(val, str):
            return val.strip() or None
        return val

    name = _lay("name")
    mada = _lay("mada")
    url = _lay("url")
    host = _lay("host")
    dev = _lay("dev")
    wp_version = _lay("wp_version")

    # Trạng thái
    status = _lay("status")
    if status and status not in TRANG_THAI_HOP_LE:
        loi.append(f"Status '{status}' không hợp lệ")
        status = "Chưa bắt đầu"
    elif not status:
        status = "Chưa bắt đầu"

    # Deadline
    deadline = _lay("deadline")
    if deadline is not None:
        # Xử lý nhiều định dạng ngày
        if isinstance(deadline, (datetime, date)):
            deadline = deadline.strftime("%Y-%m-%d")
        else:
            deadline_str = str(deadline).strip()
            # Thử parse các dạng phổ biến
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
                try:
                    dt = datetime.strptime(deadline_str, fmt)
                    deadline = dt.strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue
            else:
                loi.append(f"Deadline '{deadline}' sai định dạng")
                deadline = None

    du_lieu = {
        "mada": mada,
        "name": name,
        "url": url,
        "host": host,
        "dev": dev,
        "status": status,
        "deadline": deadline,
        "wp_version": wp_version,
    }
    return du_lieu, loi


def kiem_tra_du_lieu(df):
    """
    Kiểm tra toàn bộ DataFrame.
    Trả về (danh_sach_dict, danh_sach_loi).

    Mỗi lỗi: {"dong": <số dòng Excel>, "noi_dung": <mô tả>}
    """
    du_lieu_hop_le = []
    loi = []

    for idx, row in df.iterrows():
        so_dong = idx + 2   # +2: header là dòng 1, dòng dữ liệu bắt đầu từ 2
        du_lieu, ds_loi_dong = chuan_hoa_dong(row)

        if ds_loi_dong:
            for msg in ds_loi_dong:
                loi.append({"dong": so_dong, "noi_dung": msg})
        else:
            du_lieu_hop_le.append(du_lieu)

    return du_lieu_hop_le, loi


def import_vao_mysql(danh_sach_dict, che_do="bo_qua"):
    """
    Import dữ liệu vào MySQL.

    che_do:
        "bo_qua"  — nếu trùng mã (hoặc trùng tên khi không có mã) thì bỏ qua
        "ghi_de"  — nếu trùng thì UPDATE
    """
    thanh_cong = 0
    bo_qua = 0
    that_bai = 0
    ds_loi = []

    for du_lieu in danh_sach_dict:
        ten = du_lieu["name"] or ""
        try:
            with csdl.ket_noi() as cnx:
                cursor = cnx.cursor()
                # Ưu tiên nhận diện theo mã dự án, sau đó mới theo tên
                existed = None
                if du_lieu["mada"]:
                    cursor.execute(
                        f"SELECT id FROM `{csdl.TABLE_DU_AN}` WHERE mada = %s",
                        (du_lieu["mada"],),
                    )
                    existed = cursor.fetchone()
                if existed is None and ten:
                    cursor.execute(
                        f"SELECT id FROM `{csdl.TABLE_DU_AN}` WHERE name = %s",
                        (ten,),
                    )
                    existed = cursor.fetchone()

                if existed:
                    if che_do == "bo_qua":
                        bo_qua += 1
                        cursor.close()
                        continue
                    # ghi_de: cập nhật toàn bộ thông tin theo dòng Excel
                    cursor.execute(
                        f"UPDATE `{csdl.TABLE_DU_AN}` SET "
                        f"mada=%s, name=%s, url=%s, host=%s, dev=%s, status=%s, "
                        f"deadline=%s, wp_version=%s "
                        f"WHERE id=%s",
                        (
                            du_lieu["mada"], ten, du_lieu["url"],
                            du_lieu["host"], du_lieu["dev"], du_lieu["status"],
                            du_lieu["deadline"], du_lieu["wp_version"],
                            existed[0],
                        ),
                    )
                    cnx.commit()
                    thanh_cong += 1
                    cursor.close()
                    continue

                # Chưa tồn tại → INSERT
                cursor.execute(
                    f"INSERT INTO `{csdl.TABLE_DU_AN}` "
                    f"(mada, name, url, host, dev, status, deadline, wp_version) "
                    f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        du_lieu["mada"], ten, du_lieu["url"],
                        du_lieu["host"], du_lieu["dev"],
                        du_lieu["status"], du_lieu["deadline"],
                        du_lieu["wp_version"],
                    ),
                )
                cnx.commit()
                cursor.close()
            thanh_cong += 1

        except Exception as e:
            that_bai += 1
            ds_loi.append(f"Dòng '{ten}': {e}")

    return {
        "thanh_cong": thanh_cong,
        "bo_qua": bo_qua,
        "that_bai": that_bai,
        "loi": ds_loi,
    }


def tao_file_mau(duong_dan):
    """Tạo file Excel mẫu để user biết định dạng."""
    if pd is None:
        raise ValueError("Chưa cài pandas")

    mau = pd.DataFrame([
        {
            "mada": "GKV_001",
            "name": "Website ABC",
            "url": "https://abc.vn",
            "host": "https://abc.vn",
            "dev": "ZN,NQ",
            "status": "Đang làm",
            "deadline": "2025-12-31",
            "wp_version": "6.4.3",
        },
        {
            "mada": "GKV_002",
            "name": "Blog XYZ",
            "url": "",
            "host": "https://blog.xyz",
            "dev": "PNS",
            "status": "Hoàn thành",
            "deadline": "2025-06-15",
            "wp_version": "6.3.2",
        },
    ])
    mau.to_excel(duong_dan, index=False)

def xuat_ra_excel(danh_sach_du_an, duong_dan):
    """
    Xuất list[dict] ra file Excel (.xlsx).
    Header giống file import: mada, name, url, host, dev, status, deadline, wp_version.
    """
    if pd is None:
        raise ValueError(
            "Chưa cài pandas. Chạy: pip install pandas openpyxl"
        )

    if not danh_sach_du_an:
        raise ValueError("Không có dữ liệu để xuất!")

    # Chuyển đổi sang DataFrame
    df = pd.DataFrame(danh_sach_du_an)

    # Đảm bảo đủ cột, theo thứ tự mong muốn
    cot_xuat = ["mada", "name", "url", "host", "dev",
                "status", "deadline", "wp_version"]
    for cot in cot_xuat:
        if cot not in df.columns:
            df[cot] = ""
    df = df[cot_xuat]

    # Ghi ra Excel
    try:
        df.to_excel(duong_dan, index=False, engine="openpyxl")
    except PermissionError:
        raise ValueError(
            f"Không ghi được file. Có thể file đang mở trong Excel:\n{duong_dan}"
        )
    except Exception as e:
        raise ValueError(f"Lỗi ghi file Excel: {e}")

    return True