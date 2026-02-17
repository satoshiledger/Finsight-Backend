"""
FinSight Transfer Detector - PRODUCTION VERSION
Identifies cross-account transfers to avoid double-counting.
"""
from datetime import datetime, timedelta
from backend.logger import setup_logger

logger = setup_logger(__name__)


class TransferDetector:
    """Detects transfers between accounts."""
    
    @staticmethod
    def find_transfers(all_transactions: list) -> list:
        """Find matching transfers across accounts."""
        transfers = []
        processed = set()
        
        for i, tx1 in enumerate(all_transactions):
            if i in processed:
                continue
            
            if tx1.get('category') and 'Transfer' in tx1.get('category', ''):
                processed.add(i)
                continue
            
            for j, tx2 in enumerate(all_transactions[i+1:], i+1):
                if j in processed:
                    continue
                
                if TransferDetector._is_transfer_pair(tx1, tx2):
                    transfers.append((tx1, tx2))
                    processed.add(i)
                    processed.add(j)
                    
                    tx1['category'] = 'Transfer'
                    tx1['is_transfer'] = True
                    tx2['category'] = 'Transfer'
                    tx2['is_transfer'] = True
                    
                    logger.info(f"Transfer: {tx1.get('description')} ↔ {tx2.get('description')}")
                    break
        
        return transfers
    
    @staticmethod
    def _is_transfer_pair(tx1: dict, tx2: dict) -> bool:
        """Check if two transactions form a transfer pair."""
        amt1 = tx1.get('amount', 0)
        amt2 = tx2.get('amount', 0)
        
        # Opposite signs
        if (amt1 > 0 and amt2 > 0) or (amt1 < 0 and amt2 < 0):
            return False
        
        # Similar amounts (within $0.50)
        if abs(abs(amt1) - abs(amt2)) > 0.50:
            return False
        
        # Similar dates (within 3 days)
        try:
            date1 = datetime.strptime(tx1.get('date', ''), '%Y-%m-%d')
            date2 = datetime.strptime(tx2.get('date', ''), '%Y-%m-%d')
            if abs((date1 - date2).days) > 3:
                return False
        except:
            pass
        
        # Transfer keywords
        transfer_keywords = [
            'payment', 'autopay', 'thank you', 'transfer',
            'online payment', 'mobile payment', 'bill payment'
        ]
        
        desc1 = tx1.get('description', '').lower()
        desc2 = tx2.get('description', '').lower()
        
        has_keywords = any(kw in desc1 or kw in desc2 for kw in transfer_keywords)
        
        return has_keywords
    
    @staticmethod
    def mark_transfers_in_transactions(transactions: list, processed_files: list) -> list:
        """Main entry: mark transfers in transaction list."""
        # Add account identifier
        for tx in transactions:
            for pf in processed_files:
                if (tx.get('bank') == pf.get('bank') and 
                    tx.get('period_label') == pf.get('period_label')):
                    tx['account_id'] = f"{pf.get('bank')}_{pf.get('account_type')}_{pf.get('account_number', 'Unknown')}"
                    tx['account_type'] = pf.get('account_type')
                    tx['account_name'] = f"{pf.get('bank')} {pf.get('account_type')} ...{str(pf.get('account_number', ''))[-4:]}"
                    break
        
        transfer_pairs = TransferDetector.find_transfers(transactions)
        logger.info(f"Detected {len(transfer_pairs)} transfer pairs")
        
        return transactions
