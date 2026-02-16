"""
Test Suite for FinSight Validators
Run with: python -m pytest backend/test_validators.py -v
Or: python backend/test_validators.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.validators import (
    validate_transaction,
    detect_duplicates,
    sanitize_description,
    validate_pdf_file,
    validate_api_key,
    standardize_bank_name,
)


def test_validate_transaction():
    """Test transaction validation."""
    print("Testing validate_transaction...")
    
    # Valid transaction
    valid_tx = {
        "date": "2026-01-15",
        "description": "Amazon.com Purchase",
        "amount": -45.99,
        "type": "Debit",
        "category": "Shopping",
        "classification": "Online Shopping"
    }
    is_valid, errors = validate_transaction(valid_tx)
    assert is_valid, f"Valid transaction marked as invalid: {errors}"
    print("  ✓ Valid transaction passes")
    
    # Missing required field
    invalid_tx = {
        "date": "2026-01-15",
        "amount": -45.99,
        # missing description, type, category
    }
    is_valid, errors = validate_transaction(invalid_tx)
    assert not is_valid, "Invalid transaction (missing fields) passed validation"
    assert len(errors) >= 3, f"Expected at least 3 errors, got {len(errors)}"
    print(f"  ✓ Missing fields detected: {len(errors)} errors")
    
    # Invalid date format
    invalid_date_tx = {
        "date": "01/15/2026",  # Wrong format
        "description": "Test",
        "amount": 100,
        "type": "Credit",
        "category": "Income"
    }
    is_valid, errors = validate_transaction(invalid_date_tx)
    assert not is_valid, "Invalid date format passed validation"
    print("  ✓ Invalid date format detected")
    
    # Invalid amount
    invalid_amount_tx = {
        "date": "2026-01-15",
        "description": "Test",
        "amount": "not a number",
        "type": "Credit",
        "category": "Income"
    }
    is_valid, errors = validate_transaction(invalid_amount_tx)
    assert not is_valid, "Invalid amount passed validation"
    print("  ✓ Invalid amount detected")
    
    # Invalid type
    invalid_type_tx = {
        "date": "2026-01-15",
        "description": "Test",
        "amount": 100,
        "type": "InvalidType",
        "category": "Income"
    }
    is_valid, errors = validate_transaction(invalid_type_tx)
    assert not is_valid, "Invalid type passed validation"
    print("  ✓ Invalid type detected")
    
    print("✅ test_validate_transaction PASSED\n")


def test_detect_duplicates():
    """Test duplicate detection."""
    print("Testing detect_duplicates...")
    
    transactions = [
        {"date": "2026-01-15", "description": "Amazon", "amount": -45.99},
        {"date": "2026-01-15", "description": "Amazon", "amount": -45.99},  # Duplicate
        {"date": "2026-01-16", "description": "Amazon", "amount": -45.99},  # Different date
        {"date": "2026-01-15", "description": "Starbucks", "amount": -5.50},
    ]
    
    duplicates = detect_duplicates(transactions, threshold=0.1)
    assert len(duplicates) == 1, f"Expected 1 duplicate pair, found {len(duplicates)}"
    assert duplicates[0] == (0, 1), f"Expected indices (0, 1), got {duplicates[0]}"
    print(f"  ✓ Detected {len(duplicates)} duplicate pair")
    
    # Test with larger time threshold
    duplicates_2day = detect_duplicates(transactions, threshold=2)
    # Should find: (0,1) same day, (0,2) 1 day apart, (1,2) 1 day apart = 3 pairs
    assert len(duplicates_2day) == 3, f"Expected 3 duplicate pairs with 2-day threshold, found {len(duplicates_2day)}"
    print(f"  ✓ Detected {len(duplicates_2day)} duplicate pairs with 2-day threshold")
    
    print("✅ test_detect_duplicates PASSED\n")


def test_sanitize_description():
    """Test description sanitization."""
    print("Testing sanitize_description...")
    
    # Remove transaction IDs
    desc1 = "AMAZON.COM #123456 PURCHASE"
    cleaned1 = sanitize_description(desc1)
    assert "#123456" not in cleaned1, f"Transaction ID not removed: {cleaned1}"
    print(f"  ✓ Removed transaction ID: '{desc1}' → '{cleaned1}'")
    
    # Remove excessive whitespace
    desc2 = "STARBUCKS     STORE    #5678"
    cleaned2 = sanitize_description(desc2)
    assert "  " not in cleaned2, f"Excessive whitespace not removed: {cleaned2}"
    print(f"  ✓ Removed whitespace: '{desc2}' → '{cleaned2}'")
    
    # Handle empty/None
    cleaned3 = sanitize_description("")
    assert cleaned3 == "Unknown Transaction", f"Empty string not handled: {cleaned3}"
    print(f"  ✓ Empty string handled: '' → '{cleaned3}'")
    
    # Proper capitalization
    desc4 = "whole foods market"
    cleaned4 = sanitize_description(desc4)
    assert cleaned4 == "Whole Foods Market", f"Capitalization failed: {cleaned4}"
    print(f"  ✓ Capitalized: '{desc4}' → '{cleaned4}'")
    
    print("✅ test_sanitize_description PASSED\n")


def test_validate_api_key():
    """Test API key validation."""
    print("Testing validate_api_key...")
    
    # Valid key
    valid_key = "sk-ant-api03-abc123def456ghi789"
    is_valid, error = validate_api_key(valid_key)
    assert is_valid, f"Valid API key rejected: {error}"
    print("  ✓ Valid API key accepted")
    
    # Empty key
    is_valid, error = validate_api_key("")
    assert not is_valid, "Empty API key accepted"
    assert "empty" in error.lower(), f"Expected 'empty' in error, got: {error}"
    print(f"  ✓ Empty key rejected: {error}")
    
    # Wrong prefix
    wrong_prefix = "api-key-123456"
    is_valid, error = validate_api_key(wrong_prefix)
    assert not is_valid, "Wrong prefix accepted"
    assert "sk-ant-" in error, f"Expected 'sk-ant-' in error, got: {error}"
    print(f"  ✓ Wrong prefix rejected: {error}")
    
    # Too short
    short_key = "sk-ant-123"
    is_valid, error = validate_api_key(short_key)
    assert not is_valid, "Short key accepted"
    assert "short" in error.lower(), f"Expected 'short' in error, got: {error}"
    print(f"  ✓ Short key rejected: {error}")
    
    print("✅ test_validate_api_key PASSED\n")


def test_standardize_bank_name():
    """Test bank name standardization."""
    print("Testing standardize_bank_name...")
    
    test_cases = [
        ("JPMorgan Chase", "Chase"),
        ("chase bank", "Chase"),
        ("BANK OF AMERICA", "Bank of America"),
        ("bofa", "Bank of America"),
        ("Wells Fargo Bank", "Wells Fargo"),
        ("AMEX", "American Express"),
        ("capitalone", "Capital One"),
        ("Random Bank", "Random Bank"),  # Unknown bank, should be title-cased
    ]
    
    for input_name, expected in test_cases:
        result = standardize_bank_name(input_name)
        assert result == expected, f"'{input_name}' → expected '{expected}', got '{result}'"
        print(f"  ✓ '{input_name}' → '{result}'")
    
    print("✅ test_standardize_bank_name PASSED\n")


def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("Running FinSight Validators Test Suite")
    print("=" * 60 + "\n")
    
    try:
        test_validate_transaction()
        test_detect_duplicates()
        test_sanitize_description()
        test_validate_api_key()
        test_standardize_bank_name()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
