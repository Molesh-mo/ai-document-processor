"""Automatic checks. Run them with:  pytest -v"""
import processor

CLEAN = """INVOICE
Invoice No: INV-9001
Date: 2026-10-01
Bill To: Test Client (Pty) Ltd
Description: Website design
Total: R1,500.00
"""


def force_practice_mode(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_extracts_fields_from_clean_invoice(monkeypatch):
    force_practice_mode(monkeypatch)
    fields = processor.extract(CLEAN)
    assert fields["invoice_number"] == "INV-9001"
    assert fields["client"] == "Test Client (Pty) Ltd"
    assert fields["date"] == "2026-10-01"
    assert fields["total"] == "1,500.00"
    assert fields["category"] == "services"


def test_clean_invoice_has_no_problems(monkeypatch):
    force_practice_mode(monkeypatch)
    assert processor.validate(processor.extract(CLEAN)) == []


def test_missing_total_is_flagged():
    fields = {"invoice_number": "X1", "client": "A", "date": "2026-10-01", "total": None}
    assert "missing total" in processor.validate(fields)


def test_bad_date_is_flagged():
    fields = {"invoice_number": "X1", "client": "A", "date": "31 October", "total": "100"}
    assert "date is not in YYYY-MM-DD format" in processor.validate(fields)


def test_zero_total_is_flagged():
    fields = {"invoice_number": "X1", "client": "A", "date": "2026-10-01", "total": "0"}
    assert "total must be more than zero" in processor.validate(fields)


def test_duplicate_invoice_is_not_saved_twice(tmp_path):
    db = str(tmp_path / "test.db")
    fields = {"invoice_number": "X1", "client": "A", "date": "2026-10-01", "total": "100", "category": "other"}
    assert processor.save_invoice(fields, [], "a.txt", db) == "OK"
    assert processor.save_invoice(fields, [], "a.txt", db) == "DUPLICATE"


def test_report_adds_up_only_approved_invoices(tmp_path):
    db = str(tmp_path / "test.db")
    good = {"invoice_number": "A", "client": "A", "date": "2026-10-01", "total": "1,000.00", "category": "services"}
    bad = {"invoice_number": "B", "client": "B", "date": "oops", "total": "500", "category": "goods"}
    processor.save_invoice(good, [], "a.txt", db)
    processor.save_invoice(bad, processor.validate(bad), "b.txt", db)
    report = processor.build_report(db)
    assert report["ok_total"] == 1000.0
    assert report["by_status"] == {"OK": 1, "NEEDS REVIEW": 1}
