"""
FinSight PDF Processor
Reads bank statement PDFs, identifies institution/period, extracts transactions.
"""
import os
import re
import json
import shutil
import pdfplumber
from datetime import datetime


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
    return text


def extract_tables_from_pdf(pdf_path: str) -> list:
    """Extract all tables from a PDF file."""
    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                if table and len(table) > 1:
                    all_tables.append({"page": i + 1, "data": table})
    return all_tables


def identify_bank(text: str) -> str:
    """Identify which bank issued this statement from the text content."""
    text_lower = text.lower()

    bank_patterns = {
        "Chase": [r"jpmorgan\s*chase", r"chase\s*bank", r"chase\.com"],
        "Bank of America": [r"bank\s*of\s*america", r"bofa", r"bankofamerica\.com"],
        "Wells Fargo": [r"wells\s*fargo", r"wellsfargo\.com"],
        "Citibank": [r"citibank", r"citi\.com"],
        "Capital One": [r"capital\s*one", r"capitalone\.com"],
        "American Express": [r"american\s*express", r"amex", r"americanexpress\.com"],
        "US Bank": [r"u\.?s\.?\s*bank", r"usbank\.com"],
        "PNC": [r"pnc\s*bank", r"pnc\.com"],
        "TD Bank": [r"td\s*bank", r"tdbank\.com"],
        "Ally Bank": [r"ally\s*bank", r"ally\.com"],
        "Discover": [r"discover\s*(bank|card|financial)", r"discover\.com"],
        "HSBC": [r"hsbc"],
        "Charles Schwab": [r"charles\s*schwab", r"schwab\.com"],
        "Fidelity": [r"fidelity\s*investments", r"fidelity\.com"],
    }

    for bank, patterns in bank_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return bank

    return "Unknown Bank"


def identify_account_type(text: str) -> str:
    """Identify account type (Checking, Savings, Credit, etc.)."""
    text_lower = text.lower()
    # Check for credit cards FIRST (before savings) - more specific
    if any(kw in text_lower for kw in ["credit card", "card member", "cardmember", "rewards", "platinum card", "gold card", "charge card"]):
        return "Credit"
    elif any(kw in text_lower for kw in ["savings account", "savings statement", "money market", "mma"]):
        return "Savings"
    elif any(kw in text_lower for kw in ["checking", "dda", "demand deposit"]):
        return "Checking"
    elif any(kw in text_lower for kw in ["investment", "brokerage", "portfolio"]):
        return "Investment"
    elif any(kw in text_lower for kw in ["loan", "mortgage"]):
        return "Loan"
    return "Unknown"


def identify_period(text: str) -> dict:
    """Identify the statement period (start date, end date, month/year)."""
    # Common patterns for statement periods
    period_patterns = [
        r"statement\s*period[:\s]*(\w+\s+\d{1,2},?\s*\d{4})\s*(?:to|through|-|–)\s*(\w+\s+\d{1,2},?\s*\d{4})",
        r"(\d{1,2}/\d{1,2}/\d{2,4})\s*(?:to|through|-|–)\s*(\d{1,2}/\d{1,2}/\d{2,4})",
        r"for\s*(?:the\s*)?period\s*(?:of\s*)?(\w+\s+\d{1,2},?\s*\d{4})\s*(?:to|through|-|–)\s*(\w+\s+\d{1,2},?\s*\d{4})",
        r"closing\s*date[:\s]*(\w+\s+\d{1,2},?\s*\d{4})",
        r"statement\s*date[:\s]*(\w+\s+\d{1,2},?\s*\d{4})",
    ]

    for pattern in period_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            try:
                if len(groups) >= 2:
                    return {"start": groups[0].strip(), "end": groups[1].strip(), "raw": match.group(0)}
                else:
                    return {"date": groups[0].strip(), "raw": match.group(0)}
            except Exception:
                continue

    # Fallback: look for month/year mentions
    month_year = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if month_year:
        return {"month": month_year.group(1), "year": month_year.group(2), "raw": month_year.group(0)}

    return {"raw": "Unknown Period"}


def identify_account_number(text: str) -> str:
    """Extract last 4 digits of account number."""
    patterns = [
        r"account\s*(?:number|#|no\.?)[:\s]*\*{2,}(\d{4})",
        r"account\s*(?:number|#|no\.?)[:\s]*x{2,}(\d{4})",
        r"account\s*(?:number|#|no\.?)[:\s]*\.{2,}(\d{4})",
        r"account\s*(?:ending\s*in|last\s*4)[:\s]*(\d{4})",
        r"\*{2,}(\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"****{match.group(1)}"
    return "****0000"


def get_period_label(period_info: dict) -> str:
    """Generate a clean label like 'Jan_2026' from period info."""
    if "month" in period_info and "year" in period_info:
        return f"{period_info['month'][:3]}_{period_info['year']}"
    if "end" in period_info:
        try:
            for fmt in ["%B %d, %Y", "%B %d %Y", "%m/%d/%Y", "%m/%d/%y"]:
                try:
                    dt = datetime.strptime(period_info["end"].strip().rstrip(","), fmt)
                    return dt.strftime("%b_%Y")
                except ValueError:
                    continue
        except Exception:
            pass
    if "date" in period_info:
        try:
            for fmt in ["%B %d, %Y", "%B %d %Y", "%m/%d/%Y", "%m/%d/%y"]:
                try:
                    dt = datetime.strptime(period_info["date"].strip().rstrip(","), fmt)
                    return dt.strftime("%b_%Y")
                except ValueError:
                    continue
        except Exception:
            pass
    return "Unknown_Period"


def process_single_pdf(pdf_path: str) -> dict:
    """Process a single PDF and return all extracted metadata."""
    text = extract_text_from_pdf(pdf_path)
    tables = extract_tables_from_pdf(pdf_path)

    bank = identify_bank(text)
    account_type = identify_account_type(text)
    period_info = identify_period(text)
    account_number = identify_account_number(text)
    period_label = get_period_label(period_info)

    page_count = 0
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

    return {
        "original_filename": os.path.basename(pdf_path),
        "original_path": pdf_path,
        "bank": bank,
        "account_type": account_type,
        "account_number": account_number,
        "period": period_info,
        "period_label": period_label,
        "page_count": page_count,
        "text": text,
        "tables": tables,
        "new_filename": f"{bank.replace(' ', '_')}_{account_type}_{account_number}_{period_label}.pdf",
    }


def rename_and_organize(processed_files: list, output_base: str) -> list:
    """Rename and organize processed PDFs into folder structure."""
    organized = []

    for pf in processed_files:
        bank_folder = os.path.join(output_base, pf["bank"].replace(" ", "_"))
        period_folder = os.path.join(bank_folder, pf["period_label"])
        os.makedirs(period_folder, exist_ok=True)

        new_path = os.path.join(period_folder, pf["new_filename"])
        shutil.copy2(pf["original_path"], new_path)

        pf["organized_path"] = new_path
        pf["folder_structure"] = f"{pf['bank'].replace(' ', '_')}/{pf['period_label']}/"
        organized.append(pf)

    return organized


def process_all_pdfs(upload_dir: str, output_dir: str) -> list:
    """Process all PDFs in the upload directory."""
    results = []
    organized_dir = os.path.join(output_dir, "organized_statements")
    os.makedirs(organized_dir, exist_ok=True)

    for filename in sorted(os.listdir(upload_dir)):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(upload_dir, filename)
            try:
                result = process_single_pdf(pdf_path)
                results.append(result)
                print(f"  ✓ {filename} → {result['bank']} | {result['account_type']} | {result['period_label']}")
            except Exception as e:
                print(f"  ✗ {filename} → Error: {e}")
                results.append({
                    "original_filename": filename,
                    "original_path": pdf_path,
                    "error": str(e),
                })

    organized = rename_and_organize(
        [r for r in results if "error" not in r],
        organized_dir
    )

    return organized
