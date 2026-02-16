"""
FinSight Validation Utilities
Provides data validation and sanitization functions.
"""
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_transaction(tx: dict) -> Tuple[bool, List[str]]:
    """
    Validate a transaction dictionary.
    
    Args:
        tx: Transaction dictionary
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Required fields
    required_fields = ["date", "description", "amount", "type", "category"]
    for field in required_fields:
        if field not in tx or tx[field] is None:
            errors.append(f"Missing required field: {field}")
    
    # Validate date format
    if "date" in tx:
        try:
            datetime.strptime(tx["date"], "%Y-%m-%d")
        except (ValueError, TypeError):
            errors.append(f"Invalid date format: {tx.get('date')}. Expected YYYY-MM-DD")
    
    # Validate amount
    if "amount" in tx:
        try:
            float(tx["amount"])
        except (ValueError, TypeError):
            errors.append(f"Invalid amount: {tx.get('amount')}")
    
    # Validate type
    if "type" in tx:
        valid_types = ["Credit", "Debit", "Transfer"]
        if tx["type"] not in valid_types:
            errors.append(f"Invalid type: {tx.get('type')}. Must be one of {valid_types}")
    
    # Validate description length
    if "description" in tx:
        if not tx["description"] or len(tx["description"].strip()) == 0:
            errors.append("Description cannot be empty")
        elif len(tx["description"]) > 500:
            errors.append("Description too long (max 500 characters)")
    
    return (len(errors) == 0, errors)


def detect_duplicates(transactions: List[dict], threshold: float = 0.1) -> List[Tuple[int, int]]:
    """
    Detect potential duplicate transactions.
    
    Args:
        transactions: List of transaction dicts
        threshold: Maximum time difference in days to consider duplicates
        
    Returns:
        List of tuples (index1, index2) of potential duplicates
    """
    duplicates = []
    
    for i in range(len(transactions)):
        for j in range(i + 1, len(transactions)):
            tx1 = transactions[i]
            tx2 = transactions[j]
            
            # Check if amounts match
            if tx1.get("amount") != tx2.get("amount"):
                continue
            
            # Check if descriptions are similar
            desc1 = tx1.get("description", "").lower().strip()
            desc2 = tx2.get("description", "").lower().strip()
            
            if desc1 != desc2:
                continue
            
            # Check if dates are close
            try:
                date1 = datetime.strptime(tx1["date"], "%Y-%m-%d")
                date2 = datetime.strptime(tx2["date"], "%Y-%m-%d")
                diff_days = abs((date1 - date2).days)
                
                if diff_days <= threshold:
                    duplicates.append((i, j))
            except (ValueError, KeyError):
                continue
    
    return duplicates


def sanitize_description(description: str) -> str:
    """
    Clean and standardize transaction descriptions.
    
    Args:
        description: Raw transaction description
        
    Returns:
        Cleaned description
    """
    if not description:
        return "Unknown Transaction"
    
    # Remove excessive whitespace
    cleaned = " ".join(description.split())
    
    # Remove common noise patterns
    noise_patterns = [
        r"#\d+",  # Transaction IDs
        r"CARD\s*\d{4}",  # Card numbers
        r"AUTH\s*\d+",  # Authorization codes
        r"POS\s*\d+",  # POS transaction codes
    ]
    
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    
    # Capitalize properly
    cleaned = cleaned.strip()
    if cleaned:
        # Don't capitalize if it's all caps (likely a business name)
        if not cleaned.isupper():
            cleaned = cleaned.title()
    
    return cleaned or "Unknown Transaction"


def validate_pdf_file(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that a file is a readable PDF.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    import os
    
    if not os.path.exists(file_path):
        return False, "File does not exist"
    
    if not file_path.lower().endswith(".pdf"):
        return False, "File is not a PDF"
    
    file_size = os.path.getsize(file_path)
    
    # Check minimum size (PDF header is at least 5 bytes)
    if file_size < 5:
        return False, "File is too small to be a valid PDF"
    
    # Check maximum size (100 MB)
    max_size = 100 * 1024 * 1024
    if file_size > max_size:
        return False, f"File is too large (max {max_size / 1024 / 1024:.0f} MB)"
    
    # Check PDF signature
    try:
        with open(file_path, "rb") as f:
            header = f.read(5)
            if not header.startswith(b"%PDF-"):
                return False, "File does not have a valid PDF header"
    except Exception as e:
        return False, f"Error reading file: {str(e)}"
    
    return True, None


def validate_api_key(api_key: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Anthropic API key format.
    
    Args:
        api_key: API key string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key:
        return False, "API key is empty"
    
    if not api_key.startswith("sk-ant-"):
        return False, "API key must start with 'sk-ant-'"
    
    if len(api_key) < 20:
        return False, "API key is too short"
    
    return True, None


def standardize_bank_name(bank: str) -> str:
    """
    Standardize bank names for consistency.
    
    Args:
        bank: Raw bank name
        
    Returns:
        Standardized bank name
    """
    bank_mappings = {
        "jpmorgan chase": "Chase",
        "chase bank": "Chase",
        "bofa": "Bank of America",
        "bankofamerica": "Bank of America",
        "bank of america": "Bank of America",
        "wells": "Wells Fargo",
        "wellsfargo": "Wells Fargo",
        "citi": "Citibank",
        "amex": "American Express",
        "capitalone": "Capital One",
    }
    
    bank_lower = bank.lower().strip()
    for key, value in bank_mappings.items():
        if key in bank_lower:
            return value
    
    # If no mapping found, use title case
    return bank.strip().title()
