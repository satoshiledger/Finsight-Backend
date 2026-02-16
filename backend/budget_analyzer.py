"""
FinSight Budget Analyzer
Computes budget analysis, spending patterns, savings recommendations,
and investment growth projections from transaction data.
"""
from collections import defaultdict
from backend.config import BUDGET_THRESHOLDS


def analyze_budget(all_transactions: list) -> dict:
    """
    Perform comprehensive budget analysis on all transactions.
    Returns a dict with income, expenses, category breakdowns,
    recommendations, and investment projections.
    """
    # Aggregate totals
    total_income = 0
    total_expenses = 0
    by_category = defaultdict(lambda: {"total": 0, "count": 0, "items": []})
    by_classification = defaultdict(lambda: {"total": 0, "count": 0})
    periods = set()

    for tx in all_transactions:
        amt = tx.get("amount", 0)
        cat = tx.get("category", "Other")
        clf = tx.get("classification", "Miscellaneous")
        period = tx.get("period_label", "Unknown")
        periods.add(period)

        if cat == "Transfer":
            continue  # Skip internal transfers for budget analysis

        if amt > 0:
            total_income += amt
        else:
            total_expenses += abs(amt)

        by_category[cat]["total"] += abs(amt) if amt < 0 else 0
        by_category[cat]["count"] += 1
        by_category[cat]["items"].append(tx)

        by_classification[clf]["total"] += abs(amt) if amt < 0 else 0
        by_classification[clf]["count"] += 1

    num_months = max(len(periods), 1)
    avg_monthly_income = total_income / num_months
    avg_monthly_expenses = total_expenses / num_months
    avg_monthly_savings = avg_monthly_income - avg_monthly_expenses
    savings_rate = avg_monthly_savings / avg_monthly_income if avg_monthly_income > 0 else 0

    # Category breakdown with budget recommendations
    category_breakdown = []
    for cat, data in sorted(by_category.items(), key=lambda x: -x[1]["total"]):
        if cat in ("Income", "Transfer"):
            continue
        monthly_avg = data["total"] / num_months
        thresholds = BUDGET_THRESHOLDS.get(cat, {"ideal": 0.05, "max": 0.10})
        recommended_budget = avg_monthly_income * thresholds["ideal"]

        if monthly_avg <= recommended_budget * 0.95:
            status = "Under Budget"
        elif monthly_avg <= recommended_budget * 1.05:
            status = "On Track"
        else:
            status = "Over Budget"

        category_breakdown.append({
            "name": cat,
            "actual": round(monthly_avg, 2),
            "budget": round(recommended_budget, 2),
            "difference": round(recommended_budget - monthly_avg, 2),
            "pct_of_income": round(monthly_avg / avg_monthly_income * 100, 1) if avg_monthly_income > 0 else 0,
            "status": status,
            "tx_count": data["count"],
        })

    # Generate specific recommendations
    recommendations = generate_recommendations(
        by_classification, avg_monthly_income, num_months
    )

    # Investment projections
    total_potential_savings = sum(r["savings"] for r in recommendations)
    new_monthly_investment = avg_monthly_savings + total_potential_savings
    investment_projection = project_investment_growth(new_monthly_investment)

    return {
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "net_savings": round(total_income - total_expenses, 2),
        "num_months": num_months,
        "num_periods": list(periods),
        "avg_monthly_income": round(avg_monthly_income, 2),
        "avg_monthly_expenses": round(avg_monthly_expenses, 2),
        "avg_monthly_savings": round(avg_monthly_savings, 2),
        "savings_rate": round(savings_rate, 4),
        "category_breakdown": category_breakdown,
        "recommendations": recommendations,
        "total_potential_monthly_savings": round(total_potential_savings, 2),
        "investment_projection": investment_projection,
    }


def generate_recommendations(by_classification: dict, avg_monthly_income: float, num_months: int) -> list:
    """Generate specific, actionable savings recommendations."""
    recommendations = []

    # Define recommendation rules: classification -> (target_pct_of_income, action)
    rules = {
        "Food Delivery": {
            "target_pct": 0.005,
            "detail": "Meal prepping 2-3 times per week can drastically reduce food delivery spending. "
                      "Try batch cooking on Sundays."
        },
        "Coffee & Drinks": {
            "target_pct": 0.003,
            "detail": "Brewing coffee at home saves significantly. Consider investing in a quality coffee maker "
                      "and buying beans in bulk."
        },
        "Online Shopping": {
            "target_pct": 0.03,
            "detail": "Implement a 48-hour rule before any non-essential purchase over $50. "
                      "Unsubscribe from promotional emails."
        },
        "Subscriptions": {
            "target_pct": 0.005,
            "detail": "Audit all subscriptions quarterly. Consider family plans or bundled services. "
                      "Cancel any service not used in the last 30 days."
        },
        "Groceries": {
            "target_pct": 0.06,
            "detail": "Switch to more cost-effective grocery stores, use a shopping list to avoid impulse buys, "
                      "and buy store-brand products."
        },
        "Restaurants": {
            "target_pct": 0.02,
            "detail": "Limit dining out to 2 times per week. Use happy hour specials and avoid appetizers/drinks "
                      "that inflate the bill."
        },
        "Rideshare": {
            "target_pct": 0.005,
            "detail": "Consider public transit for regular commutes. Use rideshare only for specific occasions. "
                      "Look into monthly transit passes."
        },
        "Department Store": {
            "target_pct": 0.02,
            "detail": "Create a needs vs. wants list before shopping. Wait for seasonal sales for non-urgent items."
        },
        "Electronics": {
            "target_pct": 0.01,
            "detail": "Research and plan electronics purchases in advance. Consider refurbished options "
                      "and look for deals during Black Friday or Prime Day."
        },
        "Wholesale": {
            "target_pct": 0.02,
            "detail": "Make a list before visiting wholesale stores and stick to it. "
                      "Buy in bulk only for items you regularly use."
        },
    }

    for clf, data in sorted(by_classification.items(), key=lambda x: -x[1]["total"]):
        if clf not in rules:
            continue

        monthly_avg = data["total"] / num_months
        if monthly_avg < 10:  # Skip trivial amounts
            continue

        rule = rules[clf]
        target = avg_monthly_income * rule["target_pct"]

        if monthly_avg > target * 1.2:  # Only recommend if significantly over target
            savings = monthly_avg - target
            priority = "High" if savings > 50 else "Medium" if savings > 20 else "Low"

            recommendations.append({
                "area": clf,
                "current": round(monthly_avg, 2),
                "target": round(target, 2),
                "savings": round(savings, 2),
                "priority": priority,
                "detail": rule["detail"],
            })

    # Sort by savings potential (highest first)
    recommendations.sort(key=lambda x: -x["savings"])
    return recommendations


def project_investment_growth(monthly_investment: float, annual_return: float = 0.07) -> dict:
    """
    Project investment growth over time assuming consistent monthly contributions.
    Uses compound interest formula with monthly compounding.
    """
    monthly_rate = annual_return / 12
    projections = {}

    for years in [1, 3, 5, 10, 15, 20, 25, 30]:
        months = years * 12
        # Future value of annuity formula
        if monthly_rate > 0:
            fv = monthly_investment * (((1 + monthly_rate) ** months - 1) / monthly_rate)
        else:
            fv = monthly_investment * months
        projections[f"{years}_year"] = round(fv, 2)

    projections["monthly_investment"] = round(monthly_investment, 2)
    projections["assumed_annual_return"] = annual_return

    return projections
