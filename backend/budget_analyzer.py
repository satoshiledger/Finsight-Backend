"""
FinSight Budget Analyzer - FIXED VERSION
Income = ALL inflows (including payments/transfers)
Expenses = ALL outflows (spending only)
"""
from collections import defaultdict


def analyze_budget(transactions: list) -> dict:
    """
    Analyze transactions and generate budget recommendations.
    FIXED: Income includes all inflows, Expenses includes all outflows.
    """
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
    total_income = sum(tx['amount'] for tx in transactions if tx['amount'] > 0)  # ALL positive
    total_expenses = sum(abs(tx['amount']) for tx in transactions if tx['amount'] < 0)  # ALL negative
    
    # Count unique months
    dates = [tx.get('date', '') for tx in transactions if tx.get('date')]
    unique_months = len(set(d[:7] for d in dates if len(d) >= 7))  # YYYY-MM
    num_months = max(unique_months, 1)
    
    avg_monthly_income = total_income / num_months
    avg_monthly_expenses = total_expenses / num_months
    avg_monthly_savings = avg_monthly_income - avg_monthly_expenses
    savings_rate = avg_monthly_savings / avg_monthly_income if avg_monthly_income > 0 else 0
    
    # Category breakdown
    category_spending = defaultdict(float)
    for tx in transactions:
        if tx['amount'] < 0:  # Only expenses
            category_spending[tx.get('category', 'Other')] += abs(tx['amount'])
    
    # Convert to monthly averages
    for cat in category_spending:
        category_spending[cat] /= num_months
    
    # Recommendations
    recommendations = []
    
    return {
        'avg_monthly_income': avg_monthly_income,
        'avg_monthly_expenses': avg_monthly_expenses,
        'avg_monthly_savings': avg_monthly_savings,
        'savings_rate': savings_rate,
        'num_months': num_months,
        'category_spending': dict(category_spending),
        'recommendations': recommendations,
    }
