"""
FinSight PDF Processor - FINAL FIX
Extracts balances from "Account Total" section (works for all Amex statements)
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
        r"closing\s*date[:\s]*(\d{1,2}/\d{1,2}/\d{2,4})",
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
    FIXED: Uses "Account Total" section for Amex (not "Pay In Full" or "Pay Over Time")
    """
    balances = {}
    
    # American Express Credit Cards - ACCOUNT TOTAL SECTION
    if bank == "American Express" and account_type == "Credit":
        print(f"  🔍 Extracting Amex credit card balances from Account Total section...")
        
        # Find the "Account Total" section specifically
        account_total_section = ""
        
        # Extract everything after "Account Total" up to the next major section
        at_match = re.search(r'Account Total.*?(?=Pay Over Time Limit|p\.\s*\d+/\d+|$)', text, re.DOTALL | re.IGNORECASE)
        if at_match:
            account_total_section = at_match.group(0)
            print(f"  ✅ Found 'Account Total' section")
        else:
            # Fallback: use entire text
            account_total_section = text
            print(f"  ⚠️ No 'Account Total' section found, using entire text")
        
        # Extract Previous Balance from Account Total section
        # Pattern: "Previous Balance" followed by amount on next line or same line
        prev_patterns = [
            r'Previous\s+Balance[\s\r\n]*\$?([\d,]+\.\d{2})',
        ]
        
        for pattern in prev_patterns:
            match = re.search(pattern, account_total_section, re.IGNORECASE)
            if match:
                balances['previous_balance'] = float(match.group(1).replace(',', ''))
                print(f"  ✅ Previous Balance: ${balances['previous_balance']:,.2f}")
                break
        
        # Extract New Balance (last occurrence in Account Total section)
        new_patterns = [
            r'New\s+Balance[\s\r\n]*\$?([\d,]+\.\d{2})',
        ]
        
        # Find ALL matches and take the last one (in Account Total section)
        for pattern in new_patterns:
            matches = list(re.finditer(pattern, account_total_section, re.IGNORECASE))
            if matches:
                last_match = matches[-1]
                balances['new_balance'] = float(last_match.group(1).replace(',', ''))
                print(f"  ✅ New Balance: ${balances['new_balance']:,.2f}")
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
        r"account\s*(?:ending)[:\s]+(\d-\d{4,5})",  # For "Account Ending 1-82009"
        r"account\s*(?:number|#|no\.?|ending)[:\s]*.*?(\d{4})",
        r"\*+(\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            last_part = match.group(1)
            # Extract just the last 4 digits
            digits = re.findall(r'\d', last_part)
            if len(digits) >= 4:
                return ''.join(digits[-4:])
    return "0000"


def get_period_label(period_info: dict) -> str:
    """Generate label like 'Nov_2025' from period info."""
    if "date" in period_info:
        try:
            for fmt in ["%m/%d/%y", "%m/%d/%Y", "%B %d, %Y"]:
                try:
                    date_str = period_info["date"].strip().rstrip(",")
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%b_%Y")
                except:
                    continue
        except:
            pass
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
        "text": text,
        "tables": tables,
        "new_filename": f"{bank.replace(' ', '_')}_{account_type}_{account_number}_{period_label}.pdf",
        "previous_balance": balances.get('previous_balance', 0),
        "new_balance": balances.get('new_balance', 0),
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
