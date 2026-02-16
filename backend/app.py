"""
FinSight Flask Web Server
Provides the web interface and API endpoints for the FinSight platform.
"""
import os
import sys
import json
import shutil
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import UPLOAD_DIR, OUTPUT_DIR
from backend.pipeline import run_pipeline

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)

ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/upload", methods=["POST"])
def upload_files():
    """Upload PDF bank statements."""
    if "files" not in request.files:
        return jsonify({"error": "No files provided"}), 400

    # Clear previous uploads
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    uploaded = []
    for file in request.files.getlist("files"):
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_DIR, filename)
            file.save(filepath)
            uploaded.append(filename)

    return jsonify({
        "status": "success",
        "files_uploaded": len(uploaded),
        "filenames": uploaded,
    })


@app.route("/api/process", methods=["POST"])
def process_statements():
    """Run the full analysis pipeline."""
    api_key = request.json.get("api_key") if request.is_json else None

    # Clear previous output
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        result = run_pipeline(UPLOAD_DIR, OUTPUT_DIR, api_key)
        if result is None:
            return jsonify({"error": "No PDF files found"}), 400
        return jsonify({
            "status": "success",
            "processed_files": result["processed_files"],
            "total_transactions": result["total_transactions"],
            "analysis": result["analysis"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/excel")
def download_excel():
    """Download the generated Excel workbook."""
    path = os.path.join(OUTPUT_DIR, "FinSight_Analysis.xlsx")
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return jsonify({"error": "Excel file not found. Run analysis first."}), 404


@app.route("/api/download/report")
def download_report():
    """Download the generated Word report."""
    path = os.path.join(OUTPUT_DIR, "FinSight_Client_Report.docx")
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return jsonify({"error": "Report not found. Run analysis first."}), 404


@app.route("/api/download/analysis")
def download_analysis():
    """Download the raw analysis data as JSON."""
    path = os.path.join(OUTPUT_DIR, "analysis_data.json")
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return jsonify({"error": "Analysis data not found. Run analysis first."}), 404


@app.route("/api/insights", methods=["POST"])
def generate_insights():
    """Generate AI-powered financial insights using extended thinking."""
    try:
        data = request.json
        api_key = data.get("api_key")
        analysis = data.get("analysis", {})
        
        if not api_key:
            return jsonify({"error": "API key required for insights"}), 400
        
        # Import the enhanced AI module
        from backend.ai_enhanced import generate_financial_insights
        
        # Create mock transaction data from analysis
        # In production, you'd retrieve actual transactions
        transactions = []
        
        insights = generate_financial_insights(transactions, api_key)
        return jsonify({"insights": insights})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/query", methods=["POST"])
def natural_language_query():
    """Answer natural language questions about transactions."""
    try:
        data = request.json
        api_key = data.get("api_key")
        query = data.get("query", "")
        analysis = data.get("analysis", {})
        
        if not api_key:
            return jsonify({"error": "API key required for queries"}), 400
        
        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        # Import the enhanced AI module
        from backend.ai_enhanced import natural_language_query as nlq
        
        # Create mock transaction data from analysis
        transactions = []
        
        answer = nlq(transactions, query, api_key)
        return jsonify({"answer": answer})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status")
def status():
    """Check if output files exist."""
    return jsonify({
        "excel_ready": os.path.exists(os.path.join(OUTPUT_DIR, "FinSight_Analysis.xlsx")),
        "report_ready": os.path.exists(os.path.join(OUTPUT_DIR, "FinSight_Client_Report.docx")),
        "analysis_ready": os.path.exists(os.path.join(OUTPUT_DIR, "analysis_data.json")),
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
