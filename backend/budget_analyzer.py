"""
FinSight Budget Analyzer - FINAL FIXED VERSION
Handles multiple date formats correctly
"""
from collections import defaultdict
from datetime import datetime


def analyze_budget(transactions: list) -> dict:
    """Analyze transactions with proper date handling."""
    
    if not transactions:
        return {
            'avg_monthly_income': 0,
            'avg_monthly_expenses': 0,
            'avg_monthly_savings': 0,
            'savings_rate': 0,
            'num_months': 0,
            'category_spending': {},
            'recommendations': [],
        }
    
    # Calculate totals
    total_income = sum(tx.get('amount', 0) for tx in transactions if tx.get('amount', 0) > 0)
    total_expenses = sum(abs(tx.get('amount', 0)) for tx in transactions if tx.get('amount', 0) < 0)
    
    # FIXED: Parse dates correctly regardless of format
    unique_months = set()
    for tx in transactions:
        date_str = tx.get('date', '')
        if not date_str:
            continue
        
        # Try multiple date formats
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%Y/%m/%d']:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                unique_months.add(dt.strftime('%Y-%m'))  # Always convert to YYYY-MM
                break
            except:
                continue
    
    num_months = max(len(unique_months), 1)
    
    print(f"\n🔍 BUDGET DEBUG:")
    print(f"  Total income: ${total_income:,.2f}")
    print(f"  Total expenses: ${total_expenses:,.2f}")
    print(f"  Unique months detected: {num_months}")
    print(f"  Months: {sorted(unique_months)}")
    
    avg_monthly_income = total_income / num_months
    avg_monthly_expenses = total_expenses / num_months
    avg_monthly_savings = avg_monthly_income - avg_monthly_expenses
    savings_rate = avg_monthly_savings / avg_monthly_income if avg_monthly_income > 0 else 0
    
    # Category breakdown
    category_spending = defaultdict(float)
    for tx in transactions:
        if tx.get('amount', 0) < 0:
            category_spending[tx.get('category', 'Other')] += abs(tx['amount'])
    
    for cat in category_spending:
        category_spending[cat] /= num_months
    
    return {
        'avg_monthly_income': avg_monthly_income,
        'avg_monthly_expenses': avg_monthly_expenses,
        'avg_monthly_savings': avg_monthly_savings,
        'savings_rate': savings_rate,
        'num_months': num_months,
        'category_spending': dict(category_spending),
        'recommendations': [],
    }
