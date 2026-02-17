"""
FinSight AI Classifier - PRODUCTION VERSION
CFO-level categorization with research flagging and transfer detection.
"""
import os
import re
import json
from backend.config import CATEGORIES, ANTHROPIC_MODEL
from backend.logger import setup_logger, log_exception
from backend.validators import validate_transaction, sanitize_description

logger = setup_logger(__name__)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.warning("Anthropic library not installed. AI classification unavailable.")


# ============================================================================
# CFO-LEVEL CATEGORIZATION
# ============================================================================

def apply_cfo_categorization(description: str, amount: float, ai_category: str) -> tuple:
    """
    Apply CFO-level judgment to categorization.
    Returns: (final_category, needs_research, confidence)
    """
    desc_lower = description.lower()
    abs_amount = abs(amount)
    
    # High-value always needs review
    if abs_amount >= 1000:
        return f"{ai_category} - Research (High Value)", True, 0.0
    
    # MEALS (Dining Out)
    meal_keywords = [
        'restaurant', 'cafe', 'bistro', 'grill', 'kitchen', 'bar', 'diner',
        'pizza', 'sushi', 'taco', 'burger', 'starbucks', 'dunkin',
        'mcdonalds', 'wendys', 'chipotle', 'panera', 'subway',
        'uber eats', 'doordash', 'grubhub', 'delivery'
    ]
    if any(kw in desc_lower for kw in meal_keywords):
        return 'Meals', False, 0.98
    
    # GROCERIES
    grocery_keywords = [
        'walmart', 'costco', 'sams club', "sam's", 'kroger', 'safeway',
        'whole foods', 'trader joe', 'aldi', 'publix', 'target',
        'commissary', 'econo', 'pueblo', 'selectos', 'supermercado',
        'supermarket', 'grocery', 'market'
    ]
    if any(kw in desc_lower for kw in grocery_keywords):
        if any(store in desc_lower for store in ['walmart', 'target']) and abs_amount < 50:
            return 'Groceries', True, 0.75
        return 'Groceries', False, 0.95
    
    # ENTERTAINMENT
    entertainment_keywords = [
        'netflix', 'hulu', 'disney', 'spotify', 'youtube premium', 'apple music',
        'theater', 'theatre', 'cinema', 'movie', 'amc', 'regal',
        'ticketmaster', 'stubhub', 'ticketera', 'concert', 'event'
    ]
    if any(kw in desc_lower for kw in entertainment_keywords):
        return 'Entertainment', False, 0.95
    
    # SHOPPING
    shopping_keywords = [
        'amazon', 'ebay', 'best buy', 'apple store', 'macys', 'nordstrom',
        'kohls', 'nike', 'home depot', 'lowes', "lowe's"
    ]
    if any(kw in desc_lower for kw in shopping_keywords):
        return 'Shopping', False, 0.95
    
    # HEALTHCARE
    healthcare_keywords = [
        'pharmacy', 'cvs', 'walgreens', 'hospital', 'doctor', 'dr ',
        'dental', 'medical', 'clinic', 'depto cobro'
    ]
    if any(kw in desc_lower for kw in healthcare_keywords):
        return 'Healthcare', False, 0.95
    
    # UTILITIES
    utility_keywords = [
        'electric', 'aee', 'prepa', 'water', 'internet', 'cable',
        'phone', 'verizon', 'att', 'tmobile', 'liberty'
    ]
    if any(kw in desc_lower for kw in utility_keywords):
        return 'Utilities', False, 0.98
    
    # CHILDCARE
    if any(kw in desc_lower for kw in ['daycare', 'child dev', 'preschool']):
        return 'Childcare', False, 0.98
    
    # TRANSPORTATION
    if any(kw in desc_lower for kw in ['shell', 'exxon', 'chevron', 'total', 'gas', 'uber', 'lyft']):
        return 'Transportation', False, 0.95
    
    # FLAG SUSPICIOUS
    suspicious = ['atm', 'cash', 'withdrawal', 'venmo', 'zelle', 'paypal', 'cashapp']
    for kw in suspicious:
        if kw in desc_lower:
            return f"Other", True, 0.0
    
    # TRANSFER DETECTION
    transfer_keywords = ['payment thank you', 'mobile payment', 'autopay', 'bill payment']
    if any(kw in desc_lower for kw in transfer_keywords):
        return 'Transfer', False, 0.99
    
    # Use AI category if available
    if ai_category and ai_category != "Other":
        return ai_category, False, 0.85
    
    # Unknown
    if amount > 0:
        return "Other", True, 0.0
    else:
        return "Other", True, 0.0


def classify_with_ai(statement_text: str, bank: str, account_type: str, api_key: str = None) -> list:
    """Use Claude to extract and classify transactions."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        logger.info("AI unavailable, using rule-based")
        return classify_with_rules(statement_text, bank, account_type)

    logger.info(f"AI classifying {bank} {account_type}")
    client = anthropic.Anthropic(api_key=api_key)

    category_list = json.dumps({k: v for k, v in CATEGORIES.items()}, indent=2)

    # Credit card sign reversal
    if account_type == "Credit":
        amount_instruction = """amount (REVERSE ALL SIGNS):
- PDF shows amount → MULTIPLY BY -1
- Example: PDF -$500 → Output +$500
- Example: PDF $50 → Output -$50
Why: Cardholder perspective (payments reduce debt, purchases increase debt)"""
    else:
        amount_instruction = "amount (exact sign from PDF)"

    prompt = f"""Extract ALL transactions. For each provide:
- date (YYYY-MM-DD)
- description (original text)
- {amount_instruction}
- type (Credit or Debit)
- category (from: {', '.join(CATEGORIES.keys())})
- classification (subcategory)

Bank: {bank}
Account: {account_type}

Extract ALL: purchases, payments, credits, refunds, transfers.

Statement:
{statement_text[:50000]}

JSON array only:"""

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()
        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

        transactions = json.loads(response_text)
        
        validated_transactions = []
        for tx in transactions:
            if "description" in tx:
                tx["description"] = sanitize_description(tx["description"])
            
            # Apply CFO categorization
            ai_category = tx.get("category", "Other")
            final_category, needs_research, confidence = apply_cfo_categorization(
                tx.get("description", ""),
                tx.get("amount", 0),
                ai_category
            )
            
            tx["category"] = final_category
            tx["needs_research"] = needs_research
            tx["confidence"] = confidence
            
            if validate_transaction(tx):
                validated_transactions.append(tx)
            else:
                logger.warning(f"Invalid transaction: {tx}")
        
        logger.info(f"AI extracted {len(validated_transactions)} transactions")
        return validated_transactions

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed: {e}")
        log_exception(e, {"response": response_text[:500]})
        return classify_with_rules(statement_text, bank, account_type)
    except Exception as e:
        logger.error(f"AI error: {e}")
        log_exception(e)
        return classify_with_rules(statement_text, bank, account_type)


def classify_with_rules(statement_text: str, bank: str, account_type: str) -> list:
    """Rule-based fallback."""
    logger.info(f"Rule-based classification for {bank} {account_type}")
    
    transactions = []
    lines = statement_text.split('\n')
    
    date_pattern = r'\d{1,2}/\d{1,2}/\d{2,4}'
    amount_pattern = r'[\$\-]?[\d,]+\.\d{2}'
    
    for line in lines:
        date_match = re.search(date_pattern, line)
        amount_match = re.search(amount_pattern, line)
        
        if date_match and amount_match:
            try:
                date_str = date_match.group()
                amount_str = amount_match.group().replace('$', '').replace(',', '')
                amount = float(amount_str)
                
                if account_type == "Credit":
                    amount = -amount
                
                description = line[:100].strip()
                
                category, needs_research, confidence = apply_cfo_categorization(
                    description, amount, "Other"
                )
                
                tx = {
                    "date": date_str,
                    "description": sanitize_description(description),
                    "amount": amount,
                    "type": "Credit" if amount > 0 else "Debit",
                    "category": category,
                    "classification": category,
                    "needs_research": needs_research,
                    "confidence": confidence
                }
                
                if validate_transaction(tx):
                    transactions.append(tx)
                    
            except (ValueError, AttributeError):
                continue
    
    logger.info(f"Rule-based extracted {len(transactions)} transactions")
    return transactions


def process_statement_transactions(statement_text: str, bank: str, account_type: str, api_key: str = None) -> list:
    """Main entry point."""
    return classify_with_ai(statement_text, bank, account_type, api_key)
