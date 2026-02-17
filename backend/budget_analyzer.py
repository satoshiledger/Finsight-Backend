"""
FinSight Budget Analyzer - DEBUG VERSION
"""
from collections import defaultdict


def analyze_budget(transactions: list) -> dict:
    """Analyze with detailed debugging."""
    
    print(f"\n{'='*60}")
    print(f"🔍 BUDGET ANALYZER DEBUG")
    print(f"{'='*60}")
    print(f"Total transactions received: {len(transactions)}")
    
    if not transactions:
        print("⚠️ No transactions to analyze!")
        return {
            'avg_monthly_income': 0,
            'avg_monthly_expenses': 0,
            'avg_monthly_savings': 0,
            'savings_rate': 0,
            'num_months': 0,
            'category_spending': {},
            'recommendations': [],
        }
    
    # Debug: Show first 5 transactions
    print(f"\n📋 First 5 transactions:")
    for i, tx in enumerate(transactions[:5]):
        print(f"  {i+1}. Amount: ${tx.get('amount', 'MISSING')}, Desc: {tx.get('description', 'N/A')[:40]}")
    
    # Calculate totals
    positive_txs = [tx for tx in transactions if tx.get('amount', 0) > 0]
    negative_txs = [tx for tx in transactions if tx.get('amount', 0) < 0]
    
    total_income = sum(tx['amount'] for tx in positive_txs)
    total_expenses = sum(abs(tx['amount']) for tx in negative_txs)
    
    print(f"\n💰 CALCULATIONS:")
    print(f"  Positive transactions: {len(positive_txs)}")
    print(f"  Negative transactions: {len(negative_txs)}")
    print(f"  Total income (sum of positive): ${total_income:,.2f}")
    print(f"  Total expenses (sum of negative): ${total_expenses:,.2f}")
    
    # Count unique months
    dates = [tx.get('date', '') for tx in transactions if tx.get('date')]
    unique_months = len(set(d[:7] for d in dates if len(d) >= 7))
    num_months = max(unique_months, 1)
    
    print(f"\n📅 DATE ANALYSIS:")
    print(f"  Transactions with dates: {len(dates)}")
    print(f"  Unique months: {unique_months}")
    print(f"  Dividing by: {num_months} months")
    
    avg_monthly_income = total_income / num_months
    avg_monthly_expenses = total_expenses / num_months
    avg_monthly_savings = avg_monthly_income - avg_monthly_expenses
    savings_rate = avg_monthly_savings / avg_monthly_income if avg_monthly_income > 0 else 0
    
    print(f"\n📊 FINAL RESULTS:")
    print(f"  Avg Monthly Income: ${avg_monthly_income:,.2f}")
    print(f"  Avg Monthly Expenses: ${avg_monthly_expenses:,.2f}")
    print(f"  Avg Monthly Savings: ${avg_monthly_savings:,.2f}")
    print(f"  Savings Rate: {savings_rate*100:.1f}%")
    print(f"{'='*60}\n")
    
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
