"""
FinSight AI Classifier - FINAL FIXED VERSION
Fixed: Looks for 'text' field from pdf_processor (not 'statement_text')
"""
import os
import re
import json

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

print("🔧 AI Classifier loaded - HAS_ANTHROPIC:", HAS_ANTHROPIC)


def apply_cfo_categorization(description: str, amount: float, ai_category: str) -> tuple:
    """CFO-level categorization."""
    desc_lower = description.lower()
    abs_amount = abs(amount)
    
    if abs_amount >= 1000:
        return f"{ai_category}", True, 0.0
    
    # MEALS
    if any(kw in desc_lower for kw in ['restaurant', 'cafe', 'starbucks', 'uber eats', 'doordash', 'grubhub']):
        return 'Meals', False, 0.98
    
    # GROCERIES  
    if any(kw in desc_lower for kw in ['walmart', 'costco', 'commissary', 'grocery', 'buchanan', 'samsclub', 'sam club']):
        return 'Groceries', False, 0.95
    
    # ENTERTAINMENT
    if any(kw in desc_lower for kw in ['netflix', 'disney', 'spotify', 'ticketmaster', 'ticketera', 'youtube', 'apple.com/bill']):
        return 'Entertainment', False, 0.95
    
    # SHOPPING
    if any(kw in desc_lower for kw in ['amazon', 'ebay', 'best buy', 'home depot', 'dyson', 'paypal *ebay', 'ocean lab', 'national lumber']):
        return 'Shopping', False, 0.95
    
    # HEALTHCARE
    if any(kw in desc_lower for kw in ['pharmacy', 'cvs', 'hospital', 'doctor', 'dr ', 'medical', 'depto cobro', 'zaragoza']):
        return 'Healthcare', False, 0.95
    
    # UTILITIES
    if any(kw in desc_lower for kw in ['electric', 'aee', 'prepa', 'water', 'internet', 'liberty', 'cable']):
        return 'Utilities', False, 0.98
    
    # CHILDCARE
    if any(kw in desc_lower for kw in ['daycare', 'child dev', 'buchanan child']):
        return 'Childcare', False, 0.98
    
    # TRANSPORTATION
    if any(kw in desc_lower for kw in ['shell', 'exxon', 'total', 'gas', 'uber', 'lyft', 'levittown']):
        return 'Transportation', False, 0.95
    
    # TRANSFER
    if any(kw in desc_lower for kw in ['payment thank you', 'mobile payment', 'autopay']):
        return 'Transfer', False, 0.99
    
    # Use AI category
    if ai_category and ai_category != "Other":
        return ai_category, False, 0.85
    
    return "Other", True, 0.0


def classify_with_ai(statement_text: str, bank: str, account_type: str, api_key: str = None) -> list:
    """Use Claude AI."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    
    if not api_key:
        print("⚠️ No API key - using rule-based")
        return classify_with_rules(statement_text, bank, account_type)
    
    if not HAS_ANTHROPIC:
        print("⚠️ Anthropic not installed - using rule-based")
        return classify_with_rules(statement_text, bank, account_type)
    
    print(f"🤖 AI classifying {bank} {account_type}")
    print(f"📄 Statement text length: {len(statement_text)} chars")
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        # Sign handling
        if account_type == "Credit":
            sign_note = "IMPORTANT: Reverse ALL signs. Payment shown as -$500 should be +$500. Purchase shown as $50 should be -$50."
        else:
            sign_note = "Use exact signs from PDF."
        
        prompt = f"""Extract ALL transactions from this {bank} {account_type} statement.

{sign_note}

Return a JSON array. Each transaction must have:
- date: "YYYY-MM-DD" or "MM/DD/YYYY"
- description: merchant/description text
- amount: number (with proper sign)
- type: "Credit" or "Debit"
- category: best guess category

Statement text:
{statement_text[:45000]}

Return ONLY the JSON array, no explanation:"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text.strip()
        print(f"📥 AI response length: {len(response_text)} chars")
        
        # Clean markdown
        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)
        response_text = response_text.strip()
        
        # Try to parse
        try:
            transactions = json.loads(response_text)
            print(f"✅ Parsed {len(transactions)} transactions from AI")
        except json.JSONDecodeError as e:
            print(f"❌ JSON parse failed: {str(e)}")
            print(f"📄 First 500 chars of response: {response_text[:500]}")
            return classify_with_rules(statement_text, bank, account_type)
        
        # Validate
        validated = []
        for tx in transactions:
            if not isinstance(tx, dict):
                continue
            if 'description' not in tx or 'amount' not in tx:
                continue
            
            desc = str(tx.get('description', ''))[:200]
            amt = float(tx.get('amount', 0))
            
            cat, needs_research, conf = apply_cfo_categorization(desc, amt, tx.get('category', 'Other'))
            
            validated.append({
                'date': tx.get('date', ''),
                'description': desc,
                'amount': amt,
                'type': tx.get('type', 'Debit'),
                'category': cat,
                'classification': cat,
                'needs_research': needs_research,
                'confidence': conf,
            })
        
        print(f"✅ Validated {len(validated)} transactions")
        return validated
        
    except Exception as e:
        print(f"❌ AI error: {type(e).__name__}: {str(e)}")
        return classify_with_rules(statement_text, bank, account_type)


def classify_with_rules(statement_text: str, bank: str, account_type: str) -> list:
    """Rule-based extraction."""
    print(f"🔍 Rule-based extraction for {bank} {account_type}")
    print(f"📄 Text length: {len(statement_text)} chars")
    
    transactions = []
    lines = statement_text.split('\n')
    
    print(f"📝 Processing {len(lines)} lines")
    
    for line in lines:
        # Date patterns
        date_match = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', line)
        # Amount patterns
        amount_match = re.search(r'[\$\-]?[\d,]+\.\d{2}', line)
        
        if date_match and amount_match:
            try:
                date_str = date_match.group()
                amount_str = amount_match.group().replace('$', '').replace(',', '')
                amount = float(amount_str)
                
                # Credit card sign reversal
                if account_type == "Credit":
                    amount = -amount
                
                desc = line[:150].strip()
                cat, needs_research, conf = apply_cfo_categorization(desc, amount, "Other")
                
                transactions.append({
                    'date': date_str,
                    'description': desc,
                    'amount': amount,
                    'type': 'Credit' if amount > 0 else 'Debit',
                    'category': cat,
                    'classification': cat,
                    'needs_research': needs_research,
                    'confidence': conf,
                })
            except Exception as e:
                continue
    
    print(f"✅ Rule-based found {len(transactions)} transactions")
    return transactions


def process_statement_transactions(processed_file: dict, api_key: str = None) -> list:
    """Main entry point - FIXED to look for 'text' field."""
    print(f"\n{'='*60}")
    print(f"🔄 Processing statement")
    print(f"{'='*60}")
    
    # FIX: pdf_processor stores text in 'text' field, not 'statement_text'
    statement_text = processed_file.get('text', '')  # ← FIXED!
    
    bank = processed_file.get('bank', 'Unknown')
    account_type = processed_file.get('account_type', 'Checking')
    period_label = processed_file.get('period_label', '')
    account_number = processed_file.get('account_number', 'Unknown')
    
    # Also check for balances
    beginning_balance = processed_file.get('previous_balance', 0)
    ending_balance = processed_file.get('new_balance', 0)
    
    print(f"🏦 Bank: {bank}")
    print(f"📊 Account Type: {account_type}")
    print(f"📅 Period: {period_label}")
    print(f"🔢 Account: ...{str(account_number)[-4:]}")
    print(f"📄 Text length: {len(statement_text)} chars")
    print(f"💰 Beginning Balance: ${beginning_balance}")
    print(f"💰 Ending Balance: ${ending_balance}")
    
    # Extract
    transactions = classify_with_ai(statement_text, bank, account_type, api_key)
    
    # Add metadata
    for tx in transactions:
        tx['bank'] = bank
        tx['account_type'] = account_type
        tx['period_label'] = period_label
        tx['account_number'] = account_number
        tx['account_name'] = f"{bank} {account_type} ...{str(account_number)[-4:]}"
        tx['beginning_balance'] = beginning_balance
        tx['ending_balance'] = ending_balance
    
    print(f"✅ Returning {len(transactions)} transactions")
    print(f"{'='*60}\n")
    
    return transactions
