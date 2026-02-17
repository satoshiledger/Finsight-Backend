"""
FinSight PDF Processor - COMPLETE FINAL VERSION
Extracts text, identifies bank/account, and extracts balances (including Amex)
"""
import os
import re
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
    """Identify which bank issued this statement."""
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
    """Identify account type."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["credit card", "card member", "cardmember", "rewards", "platinum card", "gold card"]):
        return "Credit"
    elif any(kw in text_lower for kw in ["savings account", "savings statement", "money market"]):
        return "Savings"
    elif any(kw in text_lower for kw in ["checking", "dda", "demand deposit"]):
        return "Checking"
    elif any(kw in text_lower for kw in ["investment", "brokerage", "portfolio"]):
        return "Investment"
    return "Unknown"


def identify_period(text: str) -> dict:
    """Identify the statement period."""
    period_patterns = [
        r"statement\s*period[:\s]*(\w+\s+\d{1,2},?\s*\d{4})\s*(?:to|through|-|–)\s*(\w+\s+\d{1,2},?\s*\d{4})",
        r"(\d{1,2}/\d{1,2}/\d{2,4})\s*(?:to|through|-|–)\s*(\d{1,2}/\d{1,2}/\d{2,4})",
        r"closing\s*date[:\s]*(\w+\s+\d{1,2},?\s*\d{4})",
    ]

    for pattern in period_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                return {"start": groups[0].strip(), "end": groups[1].strip()}
            else:
                return {"date": groups[0].strip()}
    
    return {}


def extract_statement_balances(text: str, bank: str, account_type: str) -> dict:
    """
    Extract beginning and ending balances from statement.
    ENHANCED for American Express credit cards.
    """
    balances = {}
    
    # American Express Credit Cards - ENHANCED PATTERNS
    if bank == "American Express" and account_type == "Credit":
        print(f"  🔍 Extracting Amex credit card balances...")
        
        # Previous balance patterns (more comprehensive)
        prev_patterns = [
            r'Previous\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Previous\s+New\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Balance\s+from\s+Last\s+Statement[\s:$]*\$?([\d,]+\.\d{2})',
            r'Opening\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Starting\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Previous\s+Statement\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
        ]
        
        for pattern in prev_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                balances['previous_balance'] = float(match.group(1).replace(',', ''))
                print(f"  ✅ Previous Balance: ${balances['previous_balance']:,.2f}")
                break
        
        # New balance patterns
        new_patterns = [
            r'New\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Current\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Balance\s+Due[\s:$]*\$?([\d,]+\.\d{2})',
            r'Total\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Closing\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Statement\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
        ]
        
        for pattern in new_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                balances['new_balance'] = float(match.group(1).replace(',', ''))
                print(f"  ✅ New Balance: ${balances['new_balance']:,.2f}")
                break
        
        # Payments & Credits
        payment_patterns = [
            r'Payments?\s+(?:and\s+)?Credits?[\s:$]*\$?([\d,]+\.\d{2})',
            r'Total\s+Payments?[\s:$]*\$?([\d,]+\.\d{2})',
        ]
        
        for pattern in payment_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                balances['total_payments_credits'] = float(match.group(1).replace(',', ''))
                break
        
        # Charges
        charge_patterns = [
            r'New\s+Charges?[\s:$]*\$?([\d,]+\.\d{2})',
            r'Total\s+Charges?[\s:$]*\$?([\d,]+\.\d{2})',
            r'Purchases?[\s:$]*\$?([\d,]+\.\d{2})',
        ]
        
        for pattern in charge_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                balances['total_charges'] = float(match.group(1).replace(',', ''))
                break
    
    # Checking/Savings accounts
    elif account_type in ["Checking", "Savings"]:
        prev_patterns = [
            r'Beginning\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Previous\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Opening\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
        ]
        
        for pattern in prev_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                balances['previous_balance'] = float(match.group(1).replace(',', ''))
                break
        
        new_patterns = [
            r'Ending\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'New\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
            r'Current\s+Balance[\s:$]*\$?([\d,]+\.\d{2})',
        ]
        
        for pattern in new_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                balances['new_balance'] = float(match.group(1).replace(',', ''))
                break
    
    return balances


def identify_account_number(text: str) -> str:
    """Extract last 4 digits of account number."""
    patterns = [
        r"account\s*(?:number|#|no\.?)[:\s]*\*+(\d{4})",
        r"account\s*(?:number|#|no\.?)[:\s]*x+(\d{4})",
        r"account\s*(?:ending\s*in)[:\s]*(\d{4})",
        r"\*+(\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"****{match.group(1)}"
    return "****0000"


def get_period_label(period_info: dict) -> str:
    """Generate label like 'Nov_2025' from period info."""
    if "end" in period_info:
        try:
            for fmt in ["%B %d, %Y", "%m/%d/%Y", "%m/%d/%y"]:
                try:
                    dt = datetime.strptime(period_info["end"].strip().rstrip(","), fmt)
                    return dt.strftime("%b_%Y")
                except:
                    continue
        except:
            pass
    if "date" in period_info:
        try:
            for fmt in ["%B %d, %Y", "%m/%d/%Y", "%m/%d/%y"]:
                try:
                    dt = datetime.strptime(period_info["date"].strip().rstrip(","), fmt)
                    return dt.strftime("%b_%Y")
                except:
                    continue
        except:
            pass
    return "Unknown_Period"


def process_single_pdf(pdf_path: str) -> dict:
    """Process a single PDF and return all metadata."""
    text = extract_text_from_pdf(pdf_path)
    tables = extract_tables_from_pdf(pdf_path)

    bank = identify_bank(text)
    account_type = identify_account_type(text)
    period_info = identify_period(text)
    account_number = identify_account_number(text)
    period_label = get_period_label(period_info)
    balances = extract_statement_balances(text, bank, account_type)

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
        "text": text,  # IMPORTANT: stored as 'text' not 'statement_text'
        "tables": tables,
        "new_filename": f"{bank.replace(' ', '_')}_{account_type}_{account_number}_{period_label}.pdf",
        "previous_balance": balances.get('previous_balance', 0),
        "new_balance": balances.get('new_balance', 0),
        "total_payments_credits": balances.get('total_payments_credits'),
        "total_charges": balances.get('total_charges'),
    }


def rename_and_organize(processed_files: list, output_base: str) -> list:
    """Rename and organize PDFs into folder structure."""
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
