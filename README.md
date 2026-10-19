# AI Document Processor

A Python tool that reads invoices (plain text), extracts the key fields with Claude, checks them, saves them to a SQLite database, and prints a summary report. Anything that looks wrong is flagged for a human instead of being trusted.

## The problem
Typing invoice details into a spreadsheet by hand is slow and error-prone, and mistakes (wrong dates, missing totals, duplicates) go unnoticed.

## What it does
1. Reads an invoice file
2. Extracts the invoice number, client, date, total and category (Claude in live mode, pattern matching in practice mode)
3. Validates the result: missing fields, bad dates, zero or non-numeric totals
4. Saves it to a SQLite database, marked OK or NEEDS REVIEW
5. Detects duplicate invoice numbers and refuses to save them twice
6. Prints a report: counts by status and totals for approved invoices

## Practice mode
With no API key set, the tool runs in practice mode and extracts fields with simple patterns, so the whole flow can be tested for free. With `ANTHROPIC_API_KEY` set, it uses Claude (Haiku 5.5) instead and is told to use only what is written in the document and to return null for anything missing.

## Tests
Seven automated tests check extraction, validation, duplicate detection and the report totals. Run `pytest -v` and every test should say PASSED.

## How to run it
1. `py -3.14 -m venv venv`
2. `venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. `python processor.py --all samples` (processes the three fake sample invoices and prints the report)
5. `pytest -v` (runs the automatic checks)
6. Optional: copy `.env.example` to `.env` and add your own Anthropic API key to use live Claude

All sample invoices are made up. No real client data is used.

## Tools used
Python 3.14, Anthropic Claude API, SQLite, pytest, python-dotenv

## What I learned
- How to design a small pipeline with separate steps (extract, validate, save, report), so each step can be tested on its own.
- Why AI output should be checked before it is trusted: the validation step catches missing or malformed fields, and bad invoices are marked NEEDS REVIEW instead of being saved as fine.
- How to write automated tests so I can prove the tool works.

## What I'd improve next
- Read PDF invoices, not only plain text
- Trigger it from a webhook or an email inbox and write to Google Sheets
- Add tests that run against live Claude output

## Built by
Molebogeng Matipwili, AI automation specialist. Built with Claude's help while learning Python.
