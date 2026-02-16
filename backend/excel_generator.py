"""
FinSight Excel Generator
Creates a professional multi-tab Excel workbook:
  - One tab per bank statement (raw transactions)
  - Consolidated tab (all data merged with categories)
  - Summary tab (pivot-style analysis by category, bank, period)
  - Budget Analysis tab (spending vs. recommended budget)
"""
import os
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
from openpyxl.utils import get_column_letter


# Style constants
HEADER_FONT = Font(name="Arial", bold=True, size=11, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="1E40AF")
SUBHEADER_FILL = PatternFill("solid", fgColor="3B82F6")
TITLE_FONT = Font(name="Arial", bold=True, size=14, color="1E40AF")
SECTION_FONT = Font(name="Arial", bold=True, size=12, color="1E40AF")
MONEY_FORMAT = '$#,##0.00;[Red]($#,##0.00);"-"'
PCT_FORMAT = '0.0%'
BORDER = Border(
    left=Side(style="thin", color="D1D5DB"),
    right=Side(style="thin", color="D1D5DB"),
    top=Side(style="thin", color="D1D5DB"),
    bottom=Side(style="thin", color="D1D5DB"),
)
ALT_ROW_FILL = PatternFill("solid", fgColor="F8FAFC")
GREEN_FILL = PatternFill("solid", fgColor="DCFCE7")
RED_FILL = PatternFill("solid", fgColor="FEE2E2")
YELLOW_FILL = PatternFill("solid", fgColor="FEF9C3")


def style_header_row(ws, row, num_cols):
    """Apply header styling to a row."""
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER


def style_data_cell(ws, row, col, is_alt=False):
    """Apply data cell styling."""
    cell = ws.cell(row=row, column=col)
    cell.font = Font(name="Arial", size=10)
    cell.border = BORDER
    if is_alt:
        cell.fill = ALT_ROW_FILL
    return cell


def auto_width(ws, min_width=10, max_width=40):
    """Auto-adjust column widths."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max(max_len + 2, min_width), max_width)


def create_statement_tab(wb, statement_info, transactions):
    """Create a tab for a single bank statement."""
    tab_name = f"{statement_info['bank'][:8]}_{statement_info['period_label']}"
    # Ensure unique tab name (max 31 chars)
    tab_name = tab_name[:31]
    ws = wb.create_sheet(title=tab_name)

    # Title
    ws.merge_cells("A1:H1")
    ws["A1"] = f"{statement_info['bank']} — {statement_info['account_type']} {statement_info['account_number']} — {statement_info['period_label']}"
    ws["A1"].font = TITLE_FONT
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30

    # Headers
    headers = ["Date", "Description", "Amount", "Type", "Category", "Classification", "Bank", "Account"]
    for col, h in enumerate(headers, 1):
        ws.cell(row=3, column=col, value=h)
    style_header_row(ws, 3, len(headers))

    # Data
    for i, tx in enumerate(transactions):
        row = i + 4
        is_alt = i % 2 == 1
        values = [
            tx.get("date", ""),
            tx.get("description", ""),
            tx.get("amount", 0),
            tx.get("type", ""),
            tx.get("category", ""),
            tx.get("classification", ""),
            tx.get("bank", ""),
            tx.get("account_type", ""),
        ]
        for col, val in enumerate(values, 1):
            cell = style_data_cell(ws, row, col, is_alt)
            cell.value = val
            if col == 3:  # Amount column
                cell.number_format = MONEY_FORMAT
                cell.alignment = Alignment(horizontal="right")

    # Summary at bottom
    last_row = len(transactions) + 4
    ws.cell(row=last_row + 1, column=1, value="").border = BORDER
    ws.cell(row=last_row + 2, column=2, value="Total Credits:").font = Font(name="Arial", bold=True, size=10)
    ws.cell(row=last_row + 2, column=3, value=f"=SUMIF(D4:D{last_row},\"Credit\",C4:C{last_row})")
    ws.cell(row=last_row + 2, column=3).number_format = MONEY_FORMAT
    ws.cell(row=last_row + 2, column=3).font = Font(name="Arial", bold=True, size=10, color="10B981")

    ws.cell(row=last_row + 3, column=2, value="Total Debits:").font = Font(name="Arial", bold=True, size=10)
    ws.cell(row=last_row + 3, column=3, value=f"=SUMIF(D4:D{last_row},\"Debit\",C4:C{last_row})")
    ws.cell(row=last_row + 3, column=3).number_format = MONEY_FORMAT
    ws.cell(row=last_row + 3, column=3).font = Font(name="Arial", bold=True, size=10, color="EF4444")

    ws.cell(row=last_row + 4, column=2, value="Net:").font = Font(name="Arial", bold=True, size=10)
    ws.cell(row=last_row + 4, column=3, value=f"=SUM(C4:C{last_row})")
    ws.cell(row=last_row + 4, column=3).number_format = MONEY_FORMAT
    ws.cell(row=last_row + 4, column=3).font = Font(name="Arial", bold=True, size=10, color="1E40AF")

    auto_width(ws)
    return ws


def create_consolidated_tab(wb, all_transactions):
    """Create a consolidated tab with ALL transactions from all statements."""
    ws = wb.create_sheet(title="All Transactions")

    ws.merge_cells("A1:J1")
    ws["A1"] = "Consolidated Transaction Data — All Statements"
    ws["A1"].font = TITLE_FONT
    ws.row_dimensions[1].height = 30

    headers = ["Date", "Description", "Amount", "Type", "Category", "Classification",
               "Bank", "Account", "Period", "Source File"]
    for col, h in enumerate(headers, 1):
        ws.cell(row=3, column=col, value=h)
    style_header_row(ws, 3, len(headers))

    # Sort transactions by date
    sorted_txs = sorted(all_transactions, key=lambda x: x.get("date", ""))

    for i, tx in enumerate(sorted_txs):
        row = i + 4
        is_alt = i % 2 == 1
        values = [
            tx.get("date", ""),
            tx.get("description", ""),
            tx.get("amount", 0),
            tx.get("type", ""),
            tx.get("category", ""),
            tx.get("classification", ""),
            tx.get("bank", ""),
            tx.get("account_type", ""),
            tx.get("period_label", ""),
            tx.get("source_file", ""),
        ]
        for col, val in enumerate(values, 1):
            cell = style_data_cell(ws, row, col, is_alt)
            cell.value = val
            if col == 3:
                cell.number_format = MONEY_FORMAT
                cell.alignment = Alignment(horizontal="right")

    auto_width(ws)

    # Auto-filter
    ws.auto_filter.ref = f"A3:J{len(sorted_txs) + 3}"

    return ws


def create_summary_tab(wb, all_transactions):
    """Create a summary/pivot tab breaking down spending by category, bank, period."""
    ws = wb.create_sheet(title="Summary Analysis")

    ws.merge_cells("A1:F1")
    ws["A1"] = "Financial Summary Analysis"
    ws["A1"].font = TITLE_FONT
    ws.row_dimensions[1].height = 30

    # --- Section 1: By Category ---
    ws["A3"] = "Spending by Category"
    ws["A3"].font = SECTION_FONT

    cat_headers = ["Category", "Total Amount", "# Transactions", "Avg Transaction", "% of Total Spend"]
    for col, h in enumerate(cat_headers, 1):
        ws.cell(row=4, column=col, value=h)
    style_header_row(ws, 4, len(cat_headers))

    # Aggregate by category
    by_category = defaultdict(lambda: {"total": 0, "count": 0})
    total_expenses = 0
    for tx in all_transactions:
        cat = tx.get("category", "Other")
        amt = tx.get("amount", 0)
        by_category[cat]["total"] += amt
        by_category[cat]["count"] += 1
        if amt < 0:
            total_expenses += abs(amt)

    row = 5
    for cat, data in sorted(by_category.items(), key=lambda x: x[1]["total"]):
        is_alt = (row - 5) % 2 == 1
        style_data_cell(ws, row, 1, is_alt).value = cat
        style_data_cell(ws, row, 2, is_alt).value = data["total"]
        ws.cell(row=row, column=2).number_format = MONEY_FORMAT
        style_data_cell(ws, row, 3, is_alt).value = data["count"]
        avg = data["total"] / data["count"] if data["count"] > 0 else 0
        style_data_cell(ws, row, 4, is_alt).value = avg
        ws.cell(row=row, column=4).number_format = MONEY_FORMAT
        pct = abs(data["total"]) / total_expenses if total_expenses > 0 and data["total"] < 0 else 0
        style_data_cell(ws, row, 5, is_alt).value = pct
        ws.cell(row=row, column=5).number_format = PCT_FORMAT
        row += 1

    # --- Section 2: By Bank ---
    row += 2
    ws.cell(row=row, column=1, value="Spending by Bank").font = SECTION_FONT
    row += 1

    bank_headers = ["Bank", "Total Credits", "Total Debits", "Net", "# Transactions"]
    for col, h in enumerate(bank_headers, 1):
        ws.cell(row=row, column=col, value=h)
    style_header_row(ws, row, len(bank_headers))
    row += 1

    by_bank = defaultdict(lambda: {"credits": 0, "debits": 0, "count": 0})
    for tx in all_transactions:
        bank = tx.get("bank", "Unknown")
        amt = tx.get("amount", 0)
        by_bank[bank]["count"] += 1
        if amt > 0:
            by_bank[bank]["credits"] += amt
        else:
            by_bank[bank]["debits"] += amt

    for bank, data in sorted(by_bank.items()):
        is_alt = (row % 2) == 0
        style_data_cell(ws, row, 1, is_alt).value = bank
        style_data_cell(ws, row, 2, is_alt).value = data["credits"]
        ws.cell(row=row, column=2).number_format = MONEY_FORMAT
        style_data_cell(ws, row, 3, is_alt).value = data["debits"]
        ws.cell(row=row, column=3).number_format = MONEY_FORMAT
        style_data_cell(ws, row, 4, is_alt).value = data["credits"] + data["debits"]
        ws.cell(row=row, column=4).number_format = MONEY_FORMAT
        style_data_cell(ws, row, 5, is_alt).value = data["count"]
        row += 1

    # --- Section 3: By Period ---
    row += 2
    ws.cell(row=row, column=1, value="Spending by Period").font = SECTION_FONT
    row += 1

    period_headers = ["Period", "Total Income", "Total Expenses", "Net", "Savings Rate"]
    for col, h in enumerate(period_headers, 1):
        ws.cell(row=row, column=col, value=h)
    style_header_row(ws, row, len(period_headers))
    row += 1

    by_period = defaultdict(lambda: {"income": 0, "expenses": 0})
    for tx in all_transactions:
        period = tx.get("period_label", "Unknown")
        amt = tx.get("amount", 0)
        if amt > 0:
            by_period[period]["income"] += amt
        else:
            by_period[period]["expenses"] += abs(amt)

    for period, data in sorted(by_period.items()):
        is_alt = (row % 2) == 0
        net = data["income"] - data["expenses"]
        savings_rate = net / data["income"] if data["income"] > 0 else 0
        style_data_cell(ws, row, 1, is_alt).value = period
        style_data_cell(ws, row, 2, is_alt).value = data["income"]
        ws.cell(row=row, column=2).number_format = MONEY_FORMAT
        style_data_cell(ws, row, 3, is_alt).value = -data["expenses"]
        ws.cell(row=row, column=3).number_format = MONEY_FORMAT
        style_data_cell(ws, row, 4, is_alt).value = net
        ws.cell(row=row, column=4).number_format = MONEY_FORMAT
        ws.cell(row=row, column=4).font = Font(
            name="Arial", bold=True, size=10,
            color="10B981" if net >= 0 else "EF4444"
        )
        style_data_cell(ws, row, 5, is_alt).value = savings_rate
        ws.cell(row=row, column=5).number_format = PCT_FORMAT
        row += 1

    auto_width(ws)
    return ws


def create_budget_tab(wb, all_transactions, budget_analysis: dict):
    """Create a budget analysis tab with recommendations."""
    ws = wb.create_sheet(title="Budget Analysis")

    ws.merge_cells("A1:F1")
    ws["A1"] = "Budget Analysis & Recommendations"
    ws["A1"].font = TITLE_FONT
    ws.row_dimensions[1].height = 30

    ba = budget_analysis

    # Key metrics
    ws["A3"] = "Key Financial Metrics"
    ws["A3"].font = SECTION_FONT

    metrics = [
        ("Average Monthly Income", ba.get("avg_monthly_income", 0)),
        ("Average Monthly Expenses", ba.get("avg_monthly_expenses", 0)),
        ("Average Monthly Savings", ba.get("avg_monthly_savings", 0)),
        ("Current Savings Rate", ba.get("savings_rate", 0)),
    ]
    for i, (label, val) in enumerate(metrics):
        row = 5 + i
        ws.cell(row=row, column=1, value=label).font = Font(name="Arial", bold=True, size=10)
        cell = ws.cell(row=row, column=2, value=val)
        if isinstance(val, float) and val < 1:
            cell.number_format = PCT_FORMAT
        else:
            cell.number_format = MONEY_FORMAT

    # Category budget comparison
    row = 11
    ws.cell(row=row, column=1, value="Category Budget Comparison").font = SECTION_FONT
    row += 1

    budget_headers = ["Category", "Actual (Monthly Avg)", "Recommended Budget", "Difference", "Status"]
    for col, h in enumerate(budget_headers, 1):
        ws.cell(row=row, column=col, value=h)
    style_header_row(ws, row, len(budget_headers))
    row += 1

    for cat_data in ba.get("category_breakdown", []):
        is_alt = (row % 2) == 0
        style_data_cell(ws, row, 1, is_alt).value = cat_data["name"]
        style_data_cell(ws, row, 2, is_alt).value = cat_data["actual"]
        ws.cell(row=row, column=2).number_format = MONEY_FORMAT
        style_data_cell(ws, row, 3, is_alt).value = cat_data["budget"]
        ws.cell(row=row, column=3).number_format = MONEY_FORMAT
        diff = cat_data["budget"] - cat_data["actual"]
        style_data_cell(ws, row, 4, is_alt).value = diff
        ws.cell(row=row, column=4).number_format = MONEY_FORMAT
        ws.cell(row=row, column=4).font = Font(
            name="Arial", size=10,
            color="10B981" if diff >= 0 else "EF4444"
        )
        status = cat_data.get("status", "")
        status_cell = style_data_cell(ws, row, 5, is_alt)
        status_cell.value = status
        if status == "Over Budget":
            status_cell.fill = RED_FILL
        elif status == "Under Budget":
            status_cell.fill = GREEN_FILL
        else:
            status_cell.fill = YELLOW_FILL
        row += 1

    # Recommendations
    row += 2
    ws.cell(row=row, column=1, value="Savings Recommendations").font = SECTION_FONT
    row += 1

    rec_headers = ["Area", "Current Monthly", "Target Monthly", "Monthly Savings", "Priority", "Action"]
    for col, h in enumerate(rec_headers, 1):
        ws.cell(row=row, column=col, value=h)
    style_header_row(ws, row, len(rec_headers))
    row += 1

    for rec in ba.get("recommendations", []):
        is_alt = (row % 2) == 0
        style_data_cell(ws, row, 1, is_alt).value = rec["area"]
        style_data_cell(ws, row, 2, is_alt).value = rec["current"]
        ws.cell(row=row, column=2).number_format = MONEY_FORMAT
        style_data_cell(ws, row, 3, is_alt).value = rec["target"]
        ws.cell(row=row, column=3).number_format = MONEY_FORMAT
        style_data_cell(ws, row, 4, is_alt).value = rec["savings"]
        ws.cell(row=row, column=4).number_format = MONEY_FORMAT
        ws.cell(row=row, column=4).font = Font(name="Arial", bold=True, size=10, color="10B981")
        style_data_cell(ws, row, 5, is_alt).value = rec["priority"]
        style_data_cell(ws, row, 6, is_alt).value = rec["detail"]
        row += 1

    # Total potential savings
    row += 1
    ws.cell(row=row, column=3, value="Total Potential Monthly Savings:").font = Font(name="Arial", bold=True, size=11)
    total_savings = sum(r["savings"] for r in ba.get("recommendations", []))
    ws.cell(row=row, column=4, value=total_savings).number_format = MONEY_FORMAT
    ws.cell(row=row, column=4).font = Font(name="Arial", bold=True, size=12, color="10B981")

    auto_width(ws)
    return ws


def generate_workbook(processed_files: list, all_transactions: list, budget_analysis: dict, output_path: str) -> str:
    """Generate the full Excel workbook."""
    wb = Workbook()

    # Remove default sheet
    wb.remove(wb.active)

    # Group transactions by statement
    tx_by_statement = defaultdict(list)
    for tx in all_transactions:
        key = f"{tx.get('bank', '')}_{tx.get('period_label', '')}"
        tx_by_statement[key].append(tx)

    # Create per-statement tabs
    for pf in processed_files:
        key = f"{pf['bank']}_{pf['period_label']}"
        stmt_transactions = tx_by_statement.get(key, [])
        create_statement_tab(wb, pf, stmt_transactions)

    # Create consolidated tab
    create_consolidated_tab(wb, all_transactions)

    # Create summary tab
    create_summary_tab(wb, all_transactions)

    # Create budget analysis tab
    create_budget_tab(wb, all_transactions, budget_analysis)

    wb.save(output_path)
    return output_path
