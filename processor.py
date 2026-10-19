"""AI Document Processor.

Reads an invoice (plain text), extracts the key fields, checks them,
saves them to a small database, and prints a summary report.

With an Anthropic API key it uses Claude to extract the fields.
Without one it runs in practice mode, using simple pattern matching,
so the whole flow can be tested for free.
"""
import json
import os
import re
import sqlite3
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()
MODEL = "claude-haiku-5-5"
DB_PATH = "invoices.db"
REQUIRED = ["invoice_number", "client", "date", "total"]


def is_practice_mode():
    """No API key means practice mode."""
    return not os.getenv("ANTHROPIC_API_KEY")


# ---------- Step 1: extract the fields ----------

def extract_with_rules(text):
    """Practice mode: find the fields with simple patterns instead of Claude."""

    def find(pattern):
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else None

    lowered = text.lower()
    if any(word in lowered for word in ["design", "management", "setup", "consulting"]):
        category = "services"
    elif any(word in lowered for word in ["stock", "goods", "supply", "equipment"]):
        category = "goods"
    else:
        category = "other"

    return {
        "invoice_number": find(r"invoice\s*(?:no|number|#)[:\s]*([A-Z0-9-]+)"),
        "client": find(r"bill to[:\s]*(.+)"),
        "date": find(r"^date[:\s]*(.+)"),
        "total": find(r"^total[:\s]*R?\s*([\d,]+(?:\.\d+)?)"),
        "category": category,
    }


def extract_with_claude(text):
    """Live mode: ask Claude to pull the fields out as JSON."""
    import anthropic

    client = anthropic.Anthropic()
    prompt = f"""Extract data from this invoice. Use ONLY what is written in it.
If a field is missing, use null. Do not guess or invent anything.

Invoice text:
{text}

Reply with ONLY valid JSON using these keys:
"invoice_number" (string),
"client" (string),
"date" (string, exactly as written),
"total" (number, the final total including VAT, no currency symbol),
"category" ("services", "goods" or "other")."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = raw.removeprefix("```json").removesuffix("```").strip()
    return json.loads(raw)


def extract(text):
    return extract_with_rules(text) if is_practice_mode() else extract_with_claude(text)


# ---------- Step 2: check the fields ----------

def validate(fields):
    """Return a list of problems. An empty list means the invoice looks fine."""
    problems = []
    for name in REQUIRED:
        if fields.get(name) in (None, ""):
            problems.append(f"missing {name}")

    total = fields.get("total")
    if total not in (None, ""):
        try:
            if float(str(total).replace(",", "")) <= 0:
                problems.append("total must be more than zero")
        except ValueError:
            problems.append("total is not a number")

    date = fields.get("date")
    if date not in (None, ""):
        try:
            datetime.strptime(str(date), "%Y-%m-%d")
        except ValueError:
            problems.append("date is not in YYYY-MM-DD format")
    return problems


# ---------- Step 3: save to the database ----------

def get_connection(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            client TEXT,
            date TEXT,
            total REAL,
            category TEXT,
            status TEXT,
            problems TEXT,
            source_file TEXT,
            processed_at TEXT
        )"""
    )
    return conn


def save_invoice(fields, problems, source_file, db_path=DB_PATH):
    """Save one invoice. Returns the status: OK, NEEDS REVIEW or DUPLICATE."""
    conn = get_connection(db_path)
    number = fields.get("invoice_number")
    if number:
        exists = conn.execute(
            "SELECT 1 FROM invoices WHERE invoice_number = ?", (number,)
        ).fetchone()
        if exists:
            conn.close()
            return "DUPLICATE"

    status = "OK" if not problems else "NEEDS REVIEW"
    try:
        total = float(str(fields.get("total")).replace(",", ""))
    except (TypeError, ValueError):
        total = None
    conn.execute(
        """INSERT INTO invoices
           (invoice_number, client, date, total, category, status, problems, source_file, processed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            number,
            fields.get("client"),
            fields.get("date"),
            total,
            fields.get("category"),
            status,
            "; ".join(problems),
            source_file,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()
    return status


# ---------- Step 4: the report ----------

def build_report(db_path=DB_PATH):
    """Summarise what is in the database."""
    conn = get_connection(db_path)
    by_status = dict(
        conn.execute("SELECT status, COUNT(*) FROM invoices GROUP BY status").fetchall()
    )
    ok_total = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM invoices WHERE status = 'OK'"
    ).fetchone()[0]
    by_category = dict(
        conn.execute(
            "SELECT category, SUM(total) FROM invoices WHERE status = 'OK' GROUP BY category"
        ).fetchall()
    )
    conn.close()
    return {"by_status": by_status, "ok_total": ok_total, "by_category": by_category}


def print_report(db_path=DB_PATH):
    report = build_report(db_path)
    print("\n--- REPORT ---")
    for status, count in report["by_status"].items():
        print(f"{status}: {count}")
    print(f"Total of approved invoices: R{report['ok_total']:,.2f}")
    for category, amount in report["by_category"].items():
        print(f"  {category}: R{amount:,.2f}")


# ---------- Put it together ----------

def process_file(path, db_path=DB_PATH):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fields = extract(text)
    problems = validate(fields)
    status = save_invoice(fields, problems, os.path.basename(path), db_path)
    print(f"{os.path.basename(path)}: {status}")
    for problem in problems:
        print(f"   - {problem}")
    return status


if __name__ == "__main__":
    print("Mode:", "PRACTICE (pattern matching)" if is_practice_mode() else "LIVE (real Claude)")
    args = sys.argv[1:]
    if not args:
        print("Usage: python processor.py samples\\invoice1.txt   (or: --all samples, --report)")
    elif args[0] == "--report":
        print_report()
    elif args[0] == "--all":
        folder = args[1]
        for name in sorted(os.listdir(folder)):
            if name.endswith(".txt"):
                process_file(os.path.join(folder, name))
        print_report()
    else:
        process_file(args[0])
