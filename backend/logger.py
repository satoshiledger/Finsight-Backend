"""
FinSight Logging Utilities
Centralized logging configuration for the entire application.
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path


# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logger(name: str, level: int = logging.INFO, log_to_file: bool = True) -> logging.Logger:
    """
    Set up a logger with both console and file handlers.
    
    Args:
        name: Logger name (usually __name__)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to a file
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter(
        '%(levelname)s - %(name)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if enabled)
    if log_to_file:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"finsight_{today}.log"
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def log_exception(logger: logging.Logger, exc: Exception, context: str = ""):
    """
    Log an exception with full traceback.
    
    Args:
        logger: Logger instance
        exc: Exception to log
        context: Additional context about where the exception occurred
    """
    import traceback
    
    error_msg = f"{context}: {type(exc).__name__}: {str(exc)}" if context else f"{type(exc).__name__}: {str(exc)}"
    logger.error(error_msg)
    logger.debug("".join(traceback.format_tb(exc.__traceback__)))


def log_transaction_batch(logger: logging.Logger, transactions: list, operation: str):
    """
    Log a batch of transaction operations.
    
    Args:
        logger: Logger instance
        transactions: List of transactions
        operation: Description of the operation (e.g., "extracted", "classified")
    """
    logger.info(f"{len(transactions)} transactions {operation}")
    
    if logger.level <= logging.DEBUG:
        # Log sample transactions in debug mode
        sample_size = min(3, len(transactions))
        for tx in transactions[:sample_size]:
            logger.debug(f"  {tx.get('date', 'N/A')} | {tx.get('description', 'N/A')[:50]} | ${tx.get('amount', 0):.2f}")
        
        if len(transactions) > sample_size:
            logger.debug(f"  ... and {len(transactions) - sample_size} more")


# Create a default application logger
app_logger = setup_logger("finsight", level=logging.INFO)


if __name__ == "__main__":
    # Test the logger
    test_logger = setup_logger("test", level=logging.DEBUG)
    
    test_logger.debug("This is a debug message")
    test_logger.info("This is an info message")
    test_logger.warning("This is a warning message")
    test_logger.error("This is an error message")
    test_logger.critical("This is a critical message")
    
    try:
        raise ValueError("Test exception")
    except Exception as e:
        log_exception(test_logger, e, "Testing exception logging")
    
    print(f"\nLog file created at: {LOGS_DIR}")
