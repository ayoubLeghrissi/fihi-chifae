"""Sales analytics and Excel reporting."""

import io
import time

from . import db as database


def sales_summary():
    with database.db() as conn:
        totals = dict(
            conn.execute(
                "SELECT COUNT(DISTINCT order_id) orders, COALESCE(SUM(qty),0) units,"
                " COALESCE(SUM(price*qty),0) revenue FROM order_items"
            ).fetchone()
        )
        m = time.strftime("%Y-%m")
        month = dict(
            conn.execute(
                "SELECT COUNT(DISTINCT order_id) orders, COALESCE(SUM(qty),0) units,"
                " COALESCE(SUM(price*qty),0) revenue FROM order_items"
                " WHERE strftime('%Y-%m',created)=?",
                (m,),
            ).fetchone()
        )
        by_month = [
            dict(r)
            for r in conn.execute(
                "SELECT strftime('%Y-%m',created) ym, COUNT(DISTINCT order_id) orders,"
                " COALESCE(SUM(qty),0) units, COALESCE(SUM(price*qty),0) revenue"
                " FROM order_items GROUP BY ym ORDER BY ym DESC LIMIT 6"
            ).fetchall()
        ]
        top = [
            dict(r)
            for r in conn.execute(
                "SELECT product_name name, COALESCE(SUM(qty),0) units,"
                " COALESCE(SUM(price*qty),0) revenue FROM order_items"
                " GROUP BY product_name ORDER BY revenue DESC LIMIT 6"
            ).fetchall()
        ]
        by_cat = [
            dict(r)
            for r in conn.execute(
                "SELECT cat label, COALESCE(SUM(qty),0) units,"
                " COALESCE(SUM(price*qty),0) revenue FROM order_items"
                " GROUP BY cat ORDER BY revenue DESC"
            ).fetchall()
        ]
        latest = [
            dict(r)
            for r in conn.execute(
                "SELECT oi.order_id, oi.product_name, oi.price, oi.qty, oi.cat, oi.size, "
                "o.buyer, o.phone, o.created"
                " FROM order_items oi JOIN orders o ON o.id = oi.order_id"
                " ORDER BY oi.id DESC LIMIT 120"
            ).fetchall()
        ]
    by_month.reverse()
    return {
        "totals": totals,
        "month": dict(month, label=m),
        "revenueByMonth": by_month,
        "topSellers": top,
        "byCategory": by_cat,
        "latest": latest,
    }


def export_month(ym):
    with database.db() as conn:
        if ym:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT oi.product_name, oi.size, oi.price, oi.qty,"
                    " o.buyer, o.phone, o.created"
                    " FROM order_items oi JOIN orders o ON o.id = oi.order_id"
                    " WHERE strftime('%Y-%m', oi.created)=? ORDER BY oi.created",
                    (ym,),
                )
            ]
        else:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT oi.product_name, oi.size, oi.price, oi.qty,"
                    " o.buyer, o.phone, o.created"
                    " FROM order_items oi JOIN orders o ON o.id = oi.order_id"
                    " ORDER BY oi.created"
                )
            ]
    return _build_excel(rows, ym)


def _build_excel(rows, ym):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Ventes"
    title = f"Ventes du mois {ym}" if ym else "Ventes - tous les mois"
    ws.cell(1, 1, title).font = Font(bold=True, size=13, color="FFFFFF")
    ws.cell(1, 1).fill = PatternFill("solid", fgColor="12843D")

    headers = [
        "Date",
        "Produit",
        "Format",
        "Prix unitaire (MAD)",
        "Quantité",
        "Total (MAD)",
        "Acheteur",
        "Téléphone",
    ]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(2, col, h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="16A34A")
        c.alignment = Alignment(horizontal="center")

    r = 3
    grand_total = 0
    for row in rows:
        total = (row["price"] or 0) * (row["qty"] or 0)
        grand_total += total
        ws.cell(r, 1, (row["created"] or "")[:10])
        ws.cell(r, 2, row["product_name"])
        ws.cell(r, 3, row["size"] or "")
        ws.cell(r, 4, round(row["price"] or 0, 2))
        ws.cell(r, 5, row["qty"])
        ws.cell(r, 6, round(total, 2))
        ws.cell(r, 7, row["buyer"] or "")
        ws.cell(r, 8, row["phone"] or "")
        r += 1

    ws.cell(r, 5, "TOTAL").font = Font(bold=True)
    ws.cell(r, 6, round(grand_total, 2)).font = Font(bold=True)

    widths = [12, 34, 12, 16, 10, 14, 26, 16]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf, (f"ventes_{ym}.xlsx") if ym else "ventes_tous_mois.xlsx"
