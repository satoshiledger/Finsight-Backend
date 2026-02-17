"""
FinSight AI Classifier - ROBUST VERSION
Handles all error cases gracefully.
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
    """CFO-level categorization. Returns: (category, needs_research, confidence)"""
    desc_lower = description.lower()
    abs_amount = abs(amount)
    
    if abs_amount >= 1000:
        return f"{ai_category} - Research (High Value)", True, 0.0
    
    # MEALS
    if any(kw in desc_lower for kw in ['restaurant', 'cafe', 'starbucks', 'dunkin', 'uber eats', 'doordash']):
        return 'Meals', False, 0.98
    
    # GROCERIES
    if any(kw in desc_lower for kw in ['walmart', 'costco', 'commissary', 'grocery', 'market', 'pueblo', 'econo']):
        return 'Groceries', False, 0.95
    
    # ENTERTAINMENT
    if any(kw in desc_lower for kw in ['netflix', 'hulu', 'disney', 'spotify', 'ticketmaster', 'theater', 'movie']):
        return 'Entertainment', False, 0.95
    
    # SHOPPING
    if any(kw in desc_lower for kw in ['amazon', 'ebay', 'best buy', 'home depot', 'macys']):
        return 'Shopping', False, 0.95
    
    # HEALTHCARE
    if any(kw in desc_lower for kw in ['pharmacy', 'cvs', 'hospital', 'doctor', 'dr ', 'medical']):
        return 'Healthcare', False, 0.95
    
    # UTILITIES
    if any(kw in desc_lower for kw in ['electric', 'aee', 'water', 'internet', 'cable', 'liberty']):
        return 'Utilities', False, 0.98
    
    # CHILDCARE
    if any(kw in desc_lower for kw in ['daycare', 'child dev']):
        return 'Childcare', False, 0.98
    
    # TRANSPORTATION
    if any(kw in desc_lower for kw in ['shell', 'exxon', 'gas', 'uber', 'lyft']):
        return 'Transportation', False, 0.95
    
    # TRANSFER
    if any(kw in desc_lower for kw in ['payment thank you', 'mobile payment', 'autopay']):
        return 'Transfer', False, 0.99
    
    # FLAG SUSPICIOUS
    if any(kw in desc_lower for kw in ['atm', 'cash', 'venmo', 'zelle']):
        return "Other", True, 0.0
    
    # Use AI category
    if ai_category and ai_category != "Other":
        return ai_category, False, 0.85
    
    return "Other", True, 0.0


def classify_with_ai(statement_text: str, bank: str, account_type: str, api_key: str = None) -> list:
    """Use Claude AI to classify."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        logger.info("AI unavailable, using rules")
        return classify_with_rules(statement_text, bank, account_type)

    logger.info(f"AI classifying {bank} {account_type}")
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        # Sign reversal for credit cards
        if account_type == "Credit":
            amount_instruction = "REVERSE signs: PDF -$500 → Output +$500, PDF $50 → Output -$50"
        else:
            amount_instruction = "Use exact sign from PDF"

        prompt = f"""Extract ALL transactions as JSON array.
Each transaction: {{"date": "YYYY-MM-DD", "description": "text", "amount": number, "type": "Credit or Debit", "category": "Shopping", "classification": "subcategory"}}

{amount_instruction}

Bank: {bank}, Account: {account_type}

Statement:
{statement_text[:40000]}

Return ONLY JSON array, no markdown:"""

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()
        
        # Clean markdown
        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)
        response_text = response_text.strip()
        
        # Parse JSON
        try:
            transactions = json.loads(response_text)
        except json.JSONDecodeError as je:
            logger.error(f"JSON parse failed: {str(je)}")
            logger.error(f"Response was: {response_text[:500]}")
            return classify_with_rules(statement_text, bank, account_type)
        
        # Validate and categorize
        validated = []
        for tx in transactions:
            if not isinstance(tx, dict):
                continue
            
            # Required fields
            if not all(k in tx for k in ['description', 'amount']):
                continue
            
            # Clean description
            desc = str(tx.get('description', ''))[:200]
            
            # Apply CFO categorization
            ai_cat = tx.get('category', 'Other')
            final_cat, needs_research, confidence = apply_cfo_categorization(
                desc, tx.get('amount', 0), ai_cat
            )
            
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
        
        logger.info(f"AI extracted {len(validated)} transactions")
        return validated
        
    except Exception as e:
        logger.error(f"AI error: {type(e).__name__}: {str(e)}")
        return classify_with_rules(statement_text, bank, account_type)


def classify_with_rules(statement_text: str, bank: str, account_type: str) -> list:
    """Rule-based fallback."""
    logger.info(f"Rule-based for {bank} {account_type}")
    
    transactions = []
    lines = statement_text.split('\n')
    
    for line in lines:
        date_match = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', line)
        amount_match = re.search(r'[\$\-]?[\d,]+\.\d{2}', line)
        
        if date_match and amount_match:
            try:
                date_str = date_match.group()
                amount = float(amount_match.group().replace('$', '').replace(',', ''))
                
                if account_type == "Credit":
                    amount = -amount
                
                desc = line[:100].strip()
                cat, needs_research, confidence = apply_cfo_categorization(desc, amount, "Other")
                
                transactions.append({
                    'date': date_str,
                    'description': desc,
                    'amount': amount,
                    'type': 'Credit' if amount > 0 else 'Debit',
                    'category': cat,
                    'classification': cat,
                    'needs_research': needs_research,
                    'confidence': confidence,
                })
            except:
                continue
    
    logger.info(f"Rule-based extracted {len(transactions)}")
    return transactions


def process_statement_transactions(processed_file: dict, api_key: str = None) -> list:
    """
    Main entry point - compatible with pipeline.
    
    Args:
        processed_file: Dict with statement_text, bank, account_type, etc.
        api_key: Anthropic API key
    
    Returns:
        List of transaction dicts
    """
    statement_text = processed_file.get('statement_text', '')
    bank = processed_file.get('bank', 'Unknown')
    account_type = processed_file.get('account_type', 'Checking')
    period_label = processed_file.get('period_label', '')
    account_number = processed_file.get('account_number', 'Unknown')
    
    # Extract transactions
    transactions = classify_with_ai(statement_text, bank, account_type, api_key)
    
    # Add metadata
    for tx in transactions:
        tx['bank'] = bank
        tx['account_type'] = account_type
        tx['period_label'] = period_label
        tx['account_number'] = account_number
        tx['account_name'] = f"{bank} {account_type} ...{str(account_number)[-4:]}"
    
    return transactions
