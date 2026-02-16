"""
FinSight Configuration
Central config for the entire application.
"""
import os

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Anthropic API (set via environment variable)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# Enhanced AI Features
USE_PROMPT_CACHING = True  # 90% cost reduction on cache hits
USE_BATCH_PROCESSING = False  # Enable for large batch jobs (50% cheaper, 24hr processing)
USE_VISION_API = True  # Enable for scanned/photographed statements
USE_EXTENDED_THINKING = True  # Enable for deep financial analysis
ENABLE_NL_QUERIES = True  # Natural language query interface

# Supported banks (extend as needed)
KNOWN_BANKS = [
    "Chase", "Bank of America", "Wells Fargo", "Citibank", "Capital One",
    "American Express", "US Bank", "PNC", "TD Bank", "Ally Bank",
    "Discover", "HSBC", "Goldman Sachs", "Charles Schwab", "Fidelity",
]

# Transaction categories for classification
CATEGORIES = {
    "Income": ["Salary", "Direct Deposit", "Interest", "Dividend", "Refund", "Reimbursement"],
    "Housing": ["Rent", "Mortgage", "HOA", "Property Tax", "Home Insurance", "Home Repair"],
    "Food & Dining": ["Groceries", "Restaurants", "Coffee & Drinks", "Food Delivery", "Fast Food"],
    "Transportation": ["Gas & Fuel", "Car Payment", "Car Insurance", "Parking", "Rideshare", "Public Transit", "Tolls"],
    "Utilities": ["Electric", "Gas", "Water", "Internet", "Phone", "Trash"],
    "Entertainment": ["Subscriptions", "Streaming", "Movies", "Events", "Games", "Hobbies"],
    "Shopping": ["Online Shopping", "Department Store", "Electronics", "Clothing", "Wholesale", "Home Goods"],
    "Health & Fitness": ["Gym Membership", "Medical", "Pharmacy", "Dental", "Vision", "Health Insurance"],
    "Insurance": ["Life Insurance", "Disability", "Umbrella"],
    "Debt": ["Credit Card Payment", "Student Loan", "Personal Loan"],
    "Transfer": ["Internal Transfer", "External Transfer", "Wire Transfer"],
    "Other": ["ATM Withdrawal", "Fee", "Miscellaneous"],
}

# Budget recommendation thresholds (% of income)
BUDGET_THRESHOLDS = {
    "Housing": {"ideal": 0.28, "max": 0.35},
    "Food & Dining": {"ideal": 0.10, "max": 0.15},
    "Transportation": {"ideal": 0.10, "max": 0.15},
    "Utilities": {"ideal": 0.05, "max": 0.10},
    "Entertainment": {"ideal": 0.05, "max": 0.10},
    "Shopping": {"ideal": 0.05, "max": 0.10},
    "Health & Fitness": {"ideal": 0.05, "max": 0.10},
    "Insurance": {"ideal": 0.10, "max": 0.15},
    "Debt": {"ideal": 0.05, "max": 0.15},
    "Savings & Investment": {"ideal": 0.20, "target": 0.30},
}
