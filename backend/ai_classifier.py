"""
FinSight AI Classifier
Uses the Anthropic API to intelligently extract and categorize transactions from statement text.
Falls back to rule-based classification when API is unavailable.
"""
import os
import re
import json
from backend.config import CATEGORIES, ANTHROPIC_MODEL
from backend.logger import setup_logger, log_exception
from backend.validators import validate_transaction, sanitize_description

# Set up logger
logger = setup_logger(__name__)

# Try to import anthropic, gracefully handle if not installed
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.warning("Anthropic library not installed. AI classification will be unavailable.")


def classify_with_ai(statement_text: str, bank: str, account_type: str, api_key: str = None) -> list:
    """
    Use Claude to extract and classify transactions from raw statement text.
    Returns a list of transaction dicts.
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        logger.info("AI classification unavailable, using rule-based fallback")
        return classify_with_rules(statement_text, bank, account_type)

    logger.info(f"Using AI classification for {bank} {account_type} statement")
    client = anthropic.Anthropic(api_key=api_key)

    category_list = json.dumps({k: v for k, v in CATEGORIES.items()}, indent=2)

    # For credit cards: REVERSE ALL SIGNS from what appears in the PDF
    # This is critical because credit card PDFs show amounts from the card issuer's perspective
    if account_type == "Credit":
        amount_instruction = """amount (CRITICAL - REVERSE ALL SIGNS):
- Read the amount from the PDF exactly as it appears (including the sign)
- Then MULTIPLY BY -1 to reverse the sign
- Example: PDF shows -$500.00 → You output +$500.00
- Example: PDF shows $50.00 → You output -$50.00
- Example: PDF shows -$9.40 → You output +$9.40

Why: Credit card PDFs show amounts from the issuer's perspective. We need the cardholder's perspective.
- Payments/credits in PDF (negative) become positive (debt reduction)
- Purchases in PDF (positive) become negative (debt increase)"""
    else:
        amount_instruction = "amount (use the sign exactly as shown in PDF: positive for deposits, negative for withdrawals)"

    prompt = f"""Analyze this bank statement text and extract ALL transactions. For each transaction, provide:
- date (YYYY-MM-DD format)
- description (original description from statement)
- {amount_instruction}
- type (Credit, Debit, or Transfer)
- category (one of the top-level categories below)
- classification (one of the sub-categories below)

Categories and sub-categories:
{category_list}

Bank: {bank}
Account Type: {account_type}

IMPORTANT: For credit card statements, make sure to extract:
1. All purchase transactions (charges from merchants)
2. All payment transactions (payments made TO the credit card - look for "PAYMENT", "AUTOPAY", "ONLINE PAYMENT", etc.)
3. All credits/refunds (returns, cashback, statement credits)

Statement text:
{statement_text[:8000]}

Respond ONLY with a JSON array of transaction objects. No other text."""

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()
        # Clean up potential markdown fences
        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

        transactions = json.loads(response_text)
        
        # Validate and clean transactions
        validated_transactions = []
        for tx in transactions:
            # Sanitize description
            if "description" in tx:
                tx["description"] = sanitize_description(tx["description"])
            
            is_valid, errors = validate_transaction(tx)
            if is_valid:
                validated_transactions.append(tx)
            else:
                logger.warning(f"Invalid transaction from AI: {errors}. Skipping: {tx.get('description', 'Unknown')}")
        
        logger.info(f"Successfully classified {len(validated_transactions)} transactions using AI")
        return validated_transactions

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        logger.debug(f"AI response was: {response_text[:500]}")
        return classify_with_rules(statement_text, bank, account_type)
    except Exception as e:
        log_exception(logger, e, "AI classification error, falling back to rules")
        return classify_with_rules(statement_text, bank, account_type)


def classify_with_rules(statement_text: str, bank: str, account_type: str) -> list:
    """
    Rule-based fallback for transaction extraction and classification.
    Attempts to parse common bank statement formats.
    """
    transactions = []
    lines = statement_text.split("\n")

    # Common transaction line patterns
    patterns = [
        # MM/DD or MM/DD/YYYY  Description  Amount
        r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(.+?)\s+(-?\$?[\d,]+\.\d{2})",
        # YYYY-MM-DD  Description  Amount
        r"(\d{4}-\d{2}-\d{2})\s+(.+?)\s+(-?\$?[\d,]+\.\d{2})",
        # Month DD  Description  Amount
        r"(\w{3}\s+\d{1,2})\s+(.+?)\s+(-?\$?[\d,]+\.\d{2})",
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                date_str, description, amount_str = match.groups()
                amount_str = amount_str.replace("$", "").replace(",", "")
                try:
                    amount = float(amount_str)
                except ValueError:
                    continue

                category, classification = categorize_description(description)
                tx_type = determine_type(amount, description, account_type)

                transactions.append({
                    "date": normalize_date(date_str),
                    "description": description.strip(),
                    "amount": amount,
                    "type": tx_type,
                    "category": category,
                    "classification": classification,
                })
                break

    return transactions


def categorize_description(description: str) -> tuple:
    """Categorize a transaction based on its description using keyword matching."""
    desc_lower = description.lower()

    keyword_map = {
        ("Income", "Salary"): ["payroll", "direct deposit", "salary", "wage", "employer"],
        ("Income", "Interest"): ["interest earned", "interest payment", "apy"],
        ("Income", "Refund"): ["refund", "reimbursement", "cashback", "cash back"],
        ("Housing", "Rent"): ["rent", "apartment", "lease"],
        ("Housing", "Mortgage"): ["mortgage", "home loan"],
        ("Food & Dining", "Groceries"): ["whole foods", "trader joe", "kroger", "safeway", "walmart", "costco", "target", "aldi", "publix", "heb"],
        ("Food & Dining", "Restaurants"): ["restaurant", "grubhub", "chipotle", "mcdonald", "subway", "chick-fil-a"],
        ("Food & Dining", "Coffee & Drinks"): ["starbucks", "dunkin", "coffee", "dutch bros"],
        ("Food & Dining", "Food Delivery"): ["doordash", "uber eats", "grubhub", "postmates", "instacart"],
        ("Transportation", "Gas & Fuel"): ["shell", "exxon", "chevron", "bp ", "gas station", "speedway", "circle k"],
        ("Transportation", "Rideshare"): ["uber", "lyft"],
        ("Transportation", "Car Payment"): ["car payment", "auto loan"],
        ("Utilities", "Electric"): ["electric", "power company", "energy"],
        ("Utilities", "Phone"): ["at&t", "verizon", "t-mobile", "sprint", "wireless"],
        ("Utilities", "Internet"): ["comcast", "xfinity", "spectrum", "cox", "att internet"],
        ("Entertainment", "Subscriptions"): ["netflix", "spotify", "hulu", "disney+", "hbo", "apple tv", "youtube premium", "amazon prime"],
        ("Shopping", "Online Shopping"): ["amazon", "ebay", "etsy"],
        ("Shopping", "Department Store"): ["target", "walmart", "best buy", "home depot", "lowes"],
        ("Shopping", "Electronics"): ["apple store", "best buy", "micro center"],
        ("Health & Fitness", "Gym Membership"): ["planet fitness", "equinox", "la fitness", "ymca", "gym"],
        ("Health & Fitness", "Medical"): ["doctor", "medical", "hospital", "urgent care", "clinic"],
        ("Health & Fitness", "Pharmacy"): ["cvs", "walgreens", "rite aid", "pharmacy"],
        ("Transfer", "Internal Transfer"): ["transfer", "xfer", "moving money"],
        ("Other", "ATM Withdrawal"): ["atm", "withdrawal", "cash"],
        ("Other", "Fee"): ["fee", "service charge", "overdraft", "maintenance"],
    }

    for (category, classification), keywords in keyword_map.items():
        for keyword in keywords:
            if keyword in desc_lower:
                return category, classification

    return "Other", "Miscellaneous"


def determine_type(amount: float, description: str, account_type: str) -> str:
    """Determine if a transaction is a Credit, Debit, or Transfer."""
    desc_lower = description.lower()

    if any(kw in desc_lower for kw in ["transfer", "xfer"]):
        return "Transfer"
    if amount > 0:
        return "Credit"
    return "Debit"


def normalize_date(date_str: str) -> str:
    """Attempt to normalize a date string to YYYY-MM-DD format."""
    from datetime import datetime

    formats = [
        "%m/%d/%Y", "%m/%d/%y", "%m/%d",
        "%Y-%m-%d",
        "%b %d", "%B %d", "%b %d, %Y", "%B %d, %Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.year < 2000:
                dt = dt.replace(year=2026)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str


def process_statement_transactions(processed_pdf: dict, api_key: str = None) -> list:
    """
    Extract and classify transactions from a processed PDF.
    Uses AI when available, falls back to rules.
    """
    transactions = classify_with_ai(
        processed_pdf["text"],
        processed_pdf["bank"],
        processed_pdf["account_type"],
        api_key
    )

    # Enrich each transaction with statement metadata
    for tx in transactions:
        tx["bank"] = processed_pdf["bank"]
        tx["account_type"] = processed_pdf["account_type"]
        tx["account_number"] = processed_pdf["account_number"]
        tx["period_label"] = processed_pdf["period_label"]
        tx["source_file"] = processed_pdf["original_filename"]

    return transactions
