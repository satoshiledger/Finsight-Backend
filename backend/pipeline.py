"""
FinSight Main Pipeline
Orchestrates the full workflow: PDF → Extract → Classify → Excel → Analysis → Word Report
"""
import os
import sys
import json
import subprocess

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import UPLOAD_DIR, OUTPUT_DIR
from backend.pdf_processor import process_all_pdfs
from backend.ai_classifier import process_statement_transactions
from backend.excel_generator import generate_workbook
from backend.budget_analyzer import analyze_budget


def run_pipeline(upload_dir: str = None, output_dir: str = None, api_key: str = None):
    """
    Run the full FinSight pipeline.

    Args:
        upload_dir: Directory containing PDF bank statements
        output_dir: Directory for output files (Excel, Word, organized PDFs)
        api_key: Anthropic API key (optional, falls back to env var or rule-based)
    """
    upload_dir = upload_dir or UPLOAD_DIR
    output_dir = output_dir or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  FinSight Financial Document Analyzer")
    print("=" * 60)

    # Step 1: Process PDFs
    print("\n📄 Step 1: Processing PDF statements...")
    processed_files = process_all_pdfs(upload_dir, output_dir)

    if not processed_files:
        print("  ✗ No PDF files found in upload directory.")
        print(f"    Place PDF bank statements in: {upload_dir}")
        return None

    print(f"  ✓ {len(processed_files)} statements processed and organized")

    # Step 2: Extract and classify transactions
    print("\n🔍 Step 2: Extracting and classifying transactions...")
    all_transactions = []
    for pf in processed_files:
        print(f"  Processing: {pf['bank']} — {pf['period_label']}...")
        transactions = process_statement_transactions(pf, api_key)
        all_transactions.extend(transactions)
        print(f"    → {len(transactions)} transactions extracted")

    print(f"  ✓ Total: {len(all_transactions)} transactions across {len(processed_files)} statements")

    # Step 3: Budget analysis
    print("\n📊 Step 3: Analyzing budget and generating recommendations...")
    budget_analysis = analyze_budget(all_transactions)
    budget_analysis["total_transactions"] = len(all_transactions)

    print(f"  ✓ Monthly Income: ${budget_analysis['avg_monthly_income']:,.2f}")
    print(f"  ✓ Monthly Expenses: ${budget_analysis['avg_monthly_expenses']:,.2f}")
    print(f"  ✓ Savings Rate: {budget_analysis['savings_rate']*100:.1f}%")
    print(f"  ✓ {len(budget_analysis['recommendations'])} savings recommendations generated")

    # Step 4: Generate Excel workbook
    print("\n📗 Step 4: Generating Excel workbook...")
    excel_path = os.path.join(output_dir, "FinSight_Analysis.xlsx")
    generate_workbook(processed_files, all_transactions, budget_analysis, excel_path)
    print(f"  ✓ Workbook saved: {excel_path}")

    # Step 5: Generate Word report
    print("\n📘 Step 5: Generating Word report...")
    analysis_json_path = os.path.join(output_dir, "analysis_data.json")
    with open(analysis_json_path, "w") as f:
        json.dump(budget_analysis, f, indent=2, default=str)

    report_path = os.path.join(output_dir, "FinSight_Client_Report.docx")
    report_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_generator.js")

    try:
        result = subprocess.run(
            ["node", report_script, analysis_json_path, report_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"  ✓ Report saved: {report_path}")
        else:
            print(f"  ✗ Report generation error: {result.stderr}")
    except FileNotFoundError:
        print("  ✗ Node.js not found. Install Node.js to generate Word reports.")
    except subprocess.TimeoutExpired:
        print("  ✗ Report generation timed out.")

    # Summary
    print("\n" + "=" * 60)
    print("  ✅ Pipeline Complete!")
    print("=" * 60)
    print(f"\n  Output files:")
    print(f"    📁 Organized statements: {os.path.join(output_dir, 'organized_statements')}/")
    print(f"    📗 Excel workbook:       {excel_path}")
    print(f"    📘 Client report:        {report_path}")
    print(f"    📊 Analysis data:        {analysis_json_path}")

    return {
        "processed_files": len(processed_files),
        "total_transactions": len(all_transactions),
        "excel_path": excel_path,
        "report_path": report_path,
        "analysis": budget_analysis,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FinSight Financial Document Analyzer")
    parser.add_argument("--input", "-i", default=UPLOAD_DIR, help="Directory with PDF bank statements")
    parser.add_argument("--output", "-o", default=OUTPUT_DIR, help="Output directory")
    parser.add_argument("--api-key", "-k", default=None, help="Anthropic API key")
    args = parser.parse_args()

    run_pipeline(args.input, args.output, args.api_key)
