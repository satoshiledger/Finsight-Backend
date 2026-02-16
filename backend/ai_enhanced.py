"""
FinSight Enhanced AI Classifier
Advanced features using Anthropic API:
- Prompt caching for cost reduction
- Batch processing for multiple statements
- Vision API for scanned statements
- Extended thinking for complex analysis
- Natural language insights generation
"""
import os
import re
import json
import base64
from typing import List, Dict, Optional, Tuple
from backend.config import CATEGORIES, ANTHROPIC_MODEL
from backend.logger import setup_logger, log_exception
from backend.validators import validate_transaction, sanitize_description

logger = setup_logger(__name__)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.warning("Anthropic library not installed. AI classification will be unavailable.")


# Cached system prompt for categories (reused across requests)
def get_cached_category_prompt() -> List[Dict]:
    """
    Returns the category definitions with cache control.
    This reduces costs by ~90% for repeated requests.
    """
    category_list = json.dumps({k: v for k, v in CATEGORIES.items()}, indent=2)
    
    return [
        {
            "type": "text",
            "text": f"""You are a financial transaction classifier. Use these categories:

{category_list}

Rules:
1. Extract ALL transactions from the statement
2. Use YYYY-MM-DD format for dates
3. Positive amounts = credits/deposits, negative = debits/charges
4. Classify each transaction into category and sub-classification
5. Return ONLY valid JSON array, no markdown fences""",
            "cache_control": {"type": "ephemeral"}  # Cache this for 5 minutes
        }
    ]


def classify_with_ai_cached(statement_text: str, bank: str, account_type: str, api_key: str = None) -> list:
    """
    Enhanced AI classification with prompt caching.
    90% cost reduction on cache hits.
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        logger.info("AI classification unavailable, using rule-based fallback")
        from backend.ai_classifier import classify_with_rules
        return classify_with_rules(statement_text, bank, account_type)

    logger.info(f"Using AI classification with prompt caching for {bank} {account_type}")
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=get_cached_category_prompt(),  # Cached prompt
            messages=[{
                "role": "user",
                "content": f"""Bank: {bank}
Account Type: {account_type}

Statement text:
{statement_text[:8000]}"""
            }]
        )

        # Log cache performance
        usage = response.usage
        if hasattr(usage, 'cache_read_input_tokens') and usage.cache_read_input_tokens > 0:
            logger.info(f"Cache hit! Saved {usage.cache_read_input_tokens} tokens")
        
        response_text = response.content[0].text.strip()
        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

        transactions = json.loads(response_text)
        
        # Validate and clean
        validated = []
        for tx in transactions:
            if "description" in tx:
                tx["description"] = sanitize_description(tx["description"])
            is_valid, errors = validate_transaction(tx)
            if is_valid:
                validated.append(tx)
            else:
                logger.warning(f"Invalid transaction: {errors}")
        
        logger.info(f"Classified {len(validated)} transactions (cache-enabled)")
        return validated

    except Exception as e:
        log_exception(logger, e, "AI classification error")
        from backend.ai_classifier import classify_with_rules
        return classify_with_rules(statement_text, bank, account_type)


def classify_with_vision(image_path: str, bank: str, account_type: str, api_key: str = None) -> list:
    """
    Extract transactions from scanned/photographed bank statements using Vision API.
    Supports: JPG, PNG, GIF, WebP
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        logger.error("Vision API unavailable - API key required")
        return []

    logger.info(f"Using Vision API for {image_path}")
    client = anthropic.Anthropic(api_key=api_key)

    # Read and encode image
    try:
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        # Detect media type
        ext = image_path.lower().split('.')[-1]
        media_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')

    except Exception as e:
        log_exception(logger, e, f"Failed to read image {image_path}")
        return []

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=get_cached_category_prompt(),
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": f"""This is a {bank} {account_type} statement image.
Extract ALL visible transactions and return as JSON array."""
                    }
                ]
            }]
        )

        response_text = response.content[0].text.strip()
        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

        transactions = json.loads(response_text)
        
        validated = []
        for tx in transactions:
            if "description" in tx:
                tx["description"] = sanitize_description(tx["description"])
            is_valid, errors = validate_transaction(tx)
            if is_valid:
                validated.append(tx)
        
        logger.info(f"Vision API extracted {len(validated)} transactions from image")
        return validated

    except Exception as e:
        log_exception(logger, e, "Vision API error")
        return []


def create_batch_requests(statements: List[Dict], api_key: str = None) -> Optional[str]:
    """
    Create a batch processing job for multiple statements.
    50% cheaper than regular API, processes within 24 hours.
    
    Args:
        statements: List of statement dicts with 'text', 'bank', 'account_type'
        api_key: Anthropic API key
        
    Returns:
        Batch ID for checking status later
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        logger.error("Batch API unavailable")
        return None

    logger.info(f"Creating batch job for {len(statements)} statements")
    client = anthropic.Anthropic(api_key=api_key)

    # Prepare batch requests
    requests = []
    category_prompt = get_cached_category_prompt()[0]["text"]
    
    for i, stmt in enumerate(statements):
        requests.append({
            "custom_id": f"statement_{i}_{stmt.get('bank', 'unknown')}",
            "params": {
                "model": ANTHROPIC_MODEL,
                "max_tokens": 4096,
                "system": category_prompt,
                "messages": [{
                    "role": "user",
                    "content": f"""Bank: {stmt.get('bank', 'Unknown')}
Account Type: {stmt.get('account_type', 'Unknown')}

{stmt.get('text', '')[:8000]}"""
                }]
            }
        })

    try:
        batch = client.messages.batches.create(requests=requests)
        logger.info(f"Batch created: {batch.id} - Status: {batch.processing_status}")
        return batch.id
    except Exception as e:
        log_exception(logger, e, "Batch creation failed")
        return None


def get_batch_results(batch_id: str, api_key: str = None) -> Optional[List[Dict]]:
    """
    Retrieve results from a completed batch job.
    
    Args:
        batch_id: The batch ID from create_batch_requests
        api_key: Anthropic API key
        
    Returns:
        List of transaction lists (one per statement) or None if not ready
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        return None

    client = anthropic.Anthropic(api_key=api_key)

    try:
        batch = client.messages.batches.retrieve(batch_id)
        logger.info(f"Batch {batch_id} status: {batch.processing_status}")
        
        if batch.processing_status != "ended":
            logger.info(f"Batch not ready. Status: {batch.processing_status}")
            return None

        # Retrieve results
        all_results = []
        for result in client.messages.batches.results(batch_id):
            if result.result.type == "succeeded":
                response_text = result.result.message.content[0].text
                response_text = re.sub(r'^```json\s*', '', response_text)
                response_text = re.sub(r'\s*```$', '', response_text)
                
                try:
                    transactions = json.loads(response_text)
                    validated = []
                    for tx in transactions:
                        if "description" in tx:
                            tx["description"] = sanitize_description(tx["description"])
                        is_valid, _ = validate_transaction(tx)
                        if is_valid:
                            validated.append(tx)
                    all_results.append(validated)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse batch result: {result.custom_id}")
                    all_results.append([])
            else:
                logger.error(f"Batch request failed: {result.custom_id}")
                all_results.append([])

        logger.info(f"Retrieved {len(all_results)} results from batch")
        return all_results

    except Exception as e:
        log_exception(logger, e, "Batch retrieval failed")
        return None


def generate_financial_insights(transactions: List[Dict], api_key: str = None) -> str:
    """
    Use extended thinking to generate deep financial insights.
    
    Args:
        transactions: List of all transactions
        api_key: Anthropic API key
        
    Returns:
        Detailed financial analysis and recommendations
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        return "AI insights unavailable - API key required"

    logger.info("Generating financial insights with extended thinking")
    client = anthropic.Anthropic(api_key=api_key)

    # Prepare transaction summary
    total_income = sum(tx['amount'] for tx in transactions if tx['amount'] > 0)
    total_expenses = sum(abs(tx['amount']) for tx in transactions if tx['amount'] < 0)
    
    # Category breakdown
    from collections import defaultdict
    by_category = defaultdict(float)
    for tx in transactions:
        if tx['amount'] < 0:
            by_category[tx.get('category', 'Other')] += abs(tx['amount'])
    
    summary = {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_savings": total_income - total_expenses,
        "category_breakdown": dict(by_category),
        "transaction_count": len(transactions)
    }

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=16000,
            thinking={
                "type": "enabled",
                "budget_tokens": 10000
            },
            messages=[{
                "role": "user",
                "content": f"""You are a financial advisor analyzing spending patterns.

Financial Summary:
{json.dumps(summary, indent=2)}

Sample Transactions (first 10):
{json.dumps(transactions[:10], indent=2)}

Provide:
1. Key spending insights and patterns
2. Areas of concern or opportunity
3. Specific, actionable recommendations
4. Long-term financial strategy suggestions

Be specific, personalized, and practical."""
            }]
        )

        # Extract the text response (skip thinking blocks)
        insights = ""
        for block in response.content:
            if block.type == "text":
                insights += block.text + "\n"
        
        logger.info("Financial insights generated successfully")
        return insights.strip()

    except Exception as e:
        log_exception(logger, e, "Insights generation failed")
        return "Unable to generate insights at this time."


def natural_language_query(transactions: List[Dict], query: str, api_key: str = None) -> str:
    """
    Answer natural language questions about transactions.
    
    Example queries:
    - "Show me all restaurant spending over $50 in January"
    - "What's my biggest expense category?"
    - "How much did I spend on coffee this month?"
    
    Args:
        transactions: List of all transactions
        query: Natural language question
        api_key: Anthropic API key
        
    Returns:
        Answer in natural language
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        return "AI query unavailable - API key required"

    logger.info(f"Processing natural language query: {query}")
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""You are analyzing financial transactions.

All Transactions:
{json.dumps(transactions, indent=2)}

User Question: {query}

Provide a clear, concise answer with specific numbers and details."""
            }]
        )

        answer = response.content[0].text
        logger.info("Natural language query answered")
        return answer

    except Exception as e:
        log_exception(logger, e, "Natural language query failed")
        return "Unable to process query at this time."


def explain_validation_error(transaction: Dict, errors: List[str], api_key: str = None) -> str:
    """
    Use Claude to explain validation errors in plain English.
    
    Args:
        transaction: The invalid transaction
        errors: List of validation errors
        api_key: Anthropic API key
        
    Returns:
        Human-friendly explanation
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not HAS_ANTHROPIC:
        return f"Validation errors: {', '.join(errors)}"

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": f"""Explain these transaction validation errors in plain English:

Transaction: {json.dumps(transaction, indent=2)}
Errors: {errors}

Provide a brief, helpful explanation a non-technical user would understand."""
            }]
        )

        explanation = response.content[0].text
        return explanation

    except Exception as e:
        return f"Validation errors: {', '.join(errors)}"
