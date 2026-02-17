"""
FinSight AI Classifier - AMEX FIXED VERSION
Works specifically with Amex statement format.
"""
import os
import re
import json
from backend.config import CATEGORIES, ANTHROPIC_MODEL
from backend.logger import setup_logger

logger = setup_logger(__name__)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.warning("Anthropic not installed")


def apply_cfo_categorization(description: str, amount: float, ai_category: str) -> tuple:
    """CFO-level categorization."""
    desc_lower = description.lower()
    abs_amount = abs(amount)
    
    if abs_amount >= 1000:
        return f"{ai_category}", True, 0.0
    
    # MEALS
    if any(kw in desc_lower for kw in ['restaurant', 'cafe', 'starbucks', 'uber eats', 'el cam']):
        return 'Meals', False, 0.98
    
    # GROCERIES
    if any(kw in desc_lower for kw in ['commissary', 'samsclub', 'grocery', 'walmart', 'costco']):
        return 'Groceries', False, 0.95
    
    # ENTERTAINMENT
    if any(kw in desc_lower for kw in ['disney', 'netflix', 'youtube', 'spotify', 'ticketera', 'apple.com/bill']):
        return 'Entertainment', False, 0.95
    
    # SHOPPING
    if any(kw in desc_lower for kw in ['amazon', 'ebay', 'home depot', 'dyson', 'ocean lab', 'denko']):
        return 'Shopping', False, 0.95
    
    # HEALTHCARE
    if any(kw in desc_lower for kw in ['dr ', 'doctor', 'hospital', 'depto cobro']):
        return 'Healthcare', False, 0.95
    
    # UTILITIES
    if any(kw in desc_lower for kw in ['aee', 'prepa', 'liberty communication']):
        return 'Utilities', False, 0.98
    
    # CHILDCARE
    if 'child dev' in desc_lower or 'buchanan child' in desc_lower:
        return 'Childcare', False, 0.98
    
    # TRANSPORTATION
    if any(kw in desc_lower for kw in ['total levittown', 'gas', 'uber']):
        return 'Transportation', False, 0.95
    
    # TRANSFER
    if 'payment - thank you' in desc_lower or 'mobile payment' in desc_lower:
        return 'Transfer', False, 0.99
    
    # P2P / Research
    if any(kw in desc_lower for kw in ['paypal', 'furiusmotor', 'veterans affrs', 'incfile', 'helium10', 'us patriot']):
        return "Other", True, 0.0
    
    if ai_category and ai_category != "Other":
        return ai_category, False, 0.85
    
    return "Other", True, 0.0


def parse_amex_transactions(text: str, account_type: str) -> list:
    """Parse Amex-specific format from statement text."""
    transactions = []
    
    # Look for transaction sections
    lines = text.split('\n')
    
    # Amex format: MM/DD/YY DESCRIPTION AMOUNT ⧫
    # Example: 10/07/25 PAYPAL *EBAY 800-456-3229 4029357733 CA $64.11 ⧫
    
    for i, line in enumerate(lines):
        # Match Amex date format: MM/DD/YY
        date_match = re.search(r'(\d{2}/\d{2}/\d{2})\s+(.+?)(\$[\d,]+\.\d{2})\s*[⧫♦◆]', line)
        
        if date_match:
            date_str = date_match.group(1)
            desc = date_match.group(2).strip()
            amount_str = date_match.group(3).replace('$', '').replace(',', '')
            
            try:
                amount = float(amount_str)
                
                # For CREDIT CARDS: Purchases are POSITIVE in PDF, but should be NEGATIVE
                # Payments/Credits are shown as negative in PDF (or in "Credits" section)
                if 'payment' in desc.lower() or 'credit' in desc.lower():
                    # This is a payment/credit - keep it positive
                    amount = abs(amount)
                else:
                    # This is a purchase - make it negative
                    amount = -abs(amount)
                
                # Convert date to YYYY-MM-DD
                parts = date_str.split('/')
                if len(parts) == 3:
                    month, day, year = parts
                    year = '20' + year if len(year) == 2 else year
                    date_formatted = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                else:
                    date_formatted = date_str
                
                cat, needs_research, confidence = apply_cfo_categorization(desc, amount, "Other")
                
                transactions.append({
                    'date': date_formatted,
                    'description': desc[:200],
                    'amount': amount,
                    'type': 'Credit' if amount > 0 else 'Debit',
                    'category': cat,
                    'classification': cat,
                    'needs_research': needs_research,
                    'confidence': confidence,
                })
            except ValueError:
                continue
    
    return transactions


def classify_with_ai(statement_text: str, bank: str, account_type: str, api_key: str = None) -> list:
    """Use Claude AI."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        logger.info("AI unavailable, using Amex parser")
        return parse_amex_transactions(statement_text, account_type)

    logger.info(f"AI classifying {bank} {account_type}")
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = f"""Extract ALL transactions from this Amex statement as JSON array.

For each transaction provide:
- date: "YYYY-MM-DD"
- description: merchant name
- amount: number (NEGATIVE for purchases, POSITIVE for payments/credits)
- type: "Credit" or "Debit"
- category: best category
- classification: subcategory

IMPORTANT SIGN RULES:
- Purchases (like "DISNEY PLUS $33.44") → amount: -33.44
- Payments/Credits (like "MOBILE PAYMENT") → amount: 3500.00

Statement text:
{statement_text[:40000]}

Return ONLY JSON array:"""

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()
        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)
        
        try:
            transactions = json.loads(response_text)
        except json.JSONDecodeError:
            logger.error("JSON parse failed, using Amex parser")
            return parse_amex_transactions(statement_text, account_type)
        
        validated = []
        for tx in transactions:
            if not isinstance(tx, dict) or 'description' not in tx or 'amount' not in tx:
                continue
            
            desc = str(tx.get('description', ''))[:200]
            ai_cat = tx.get('category', 'Other')
            final_cat, needs_research, confidence = apply_cfo_categorization(desc, tx.get('amount', 0), ai_cat)
            
            validated.append({
                'date': tx.get('date', ''),
                'description': desc,
                'amount': float(tx.get('amount', 0)),
                'type': tx.get('type', 'Debit'),
                'category': final_cat,
                'classification': tx.get('classification', final_cat),
                'needs_research': needs_research,
                'confidence': confidence,
            })
        
        if len(validated) > 0:
            logger.info(f"AI extracted {len(validated)} transactions")
            return validated
        else:
            logger.info("AI returned empty, using Amex parser")
            return parse_amex_transactions(statement_text, account_type)
        
    except Exception as e:
        logger.error(f"AI error: {type(e).__name__}: {str(e)}")
        return parse_amex_transactions(statement_text, account_type)


def process_statement_transactions(processed_file: dict, api_key: str = None) -> list:
    """Main entry point."""
    statement_text = processed_file.get('statement_text', '')
    bank = processed_file.get('bank', 'Unknown')
    account_type = processed_file.get('account_type', 'Checking')
    period_label = processed_file.get('period_label', '')
    account_number = processed_file.get('account_number', 'Unknown')
    
    transactions = classify_with_ai(statement_text, bank, account_type, api_key)
    
    for tx in transactions:
        tx['bank'] = bank
        tx['account_type'] = account_type
        tx['period_label'] = period_label
        tx['account_number'] = account_number
        tx['account_name'] = f"{bank} {account_type} ...{str(account_number)[-4:]}"
    
    logger.info(f"Returning {len(transactions)} transactions for {bank}")
    return transactions
