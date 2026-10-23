"""Generates realistic test fixtures for sloth-sort benchmarking and end-to-end tests."""

import json
import os
from pathlib import Path
import shutil
import time
import docx


def make_simple_pdf(filepath: Path, text: str) -> None:
    """Construct a clean, valid PDF 1.4 with exact byte offsets readable by pypdf."""
    body = (
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )
    # Sanitize parentheses in text for PDF literal string
    safe_text = text.replace("(", "").replace(")", "").replace("\\", "")
    stream_content = f"BT\n/F1 12 Tf\n50 700 Td\n({safe_text}) Tj\nET\n"
    stream_len = len(stream_content)
    obj5 = f"5 0 obj\n<< /Length {stream_len} >>\nstream\n{stream_content}endstream\nendobj\n"

    header = "%PDF-1.4\n"
    part1 = header + body + obj5

    offsets = [0]
    curr = len(header)
    offsets.append(curr)
    curr += len("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    offsets.append(curr)
    curr += len("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    offsets.append(curr)
    curr += len("3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n")
    offsets.append(curr)
    curr += len("4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    offsets.append(curr)

    xref_offset = len(part1)
    xref = "xref\n0 6\n0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n"
    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"

    with open(filepath, "wb") as f:
        f.write((part1 + xref + trailer).encode("latin1"))


def make_simple_docx(filepath: Path, text: str) -> None:
    """Create a minimal .docx document with paragraph text."""
    doc = docx.Document()
    doc.add_paragraph(text)
    doc.save(str(filepath))


# Hand-decided ground truth categories for all 40 fixture files
GROUND_TRUTH = {
    # 25 text-readable files
    "Document (3) final FINAL.txt": "Documents",
    "scan0007.pdf": "Invoices",
    "IMG_20261003_1.txt": "Invoices",
    "scan_receipt_09.txt": "Invoices",
    "New Text Document.txt": "Misc",
    "untitled(2).md": "Study",
    "download (1).csv": "Invoices",
    "Copy of notes.docx": "Documents",
    "final_v2_REAL_final.txt": "Documents",
    "recipe_grandma_apple_pie (1).txt": "Misc",
    "flight_booking_LH492.txt": "Documents",
    "billing_statement_oct2026.txt": "Invoices",
    "chem_hw_assignment3.txt": "Study",
    "calculus_midterm_review_ch4.md": "Study",
    "aws_billing_invoice_2026_09.pdf": "Invoices",
    "apartment_lease_agreement_signed.docx": "Documents",
    "data_analysis_export_q3.csv": "Documents",
    "quick_meeting_memo.txt": "Documents",
    "biology_lab_report_draft.md": "Study",
    "uber_trip_receipt_102026.txt": "Invoices",
    "packing_list_japan_vacation.txt": "Misc",
    "script_backup_database.py": "Code",
    "frontend_deploy_worker.js": "Code",
    "sql_query_customer_churn.txt": "Code",
    "recent_download_note.txt": "Documents",
    # 5 fake installers
    "setup_app_installer (1).exe": "Installers",
    "python_3.14.0_installer_amd64.msi": "Installers",
    "DockerDesktop-4.32.0-universal.dmg": "Installers",
    "vlc_media_player_3.0.20_setup.exe": "Installers",
    "node_v22.10.0_x64.msi": "Installers",
    # 5 fake images
    "IMG_20261019_182045.jpg": "Photos",
    "Screenshot_2026-10-22_114002.png": "Photos",
    "DSC00492_family_vacation.jpg": "Photos",
    "graphic_banner_mockup (copy).png": "Photos",
    "camera_raw_frame_001.jpg": "Photos",
    # 5 odd cases
    "empty_scratch_file.txt": "Misc",
    "notas_de_reunion_en_espanol.txt": "Documents",
    "meeting_notes_regarding_the_quarterly_budget_review_and_team_expansion_plans_for_q4_2026_final_draft_approved.txt": "Documents",
    ".hidden_note.txt": "Misc",
    "movie_trailer_teaser.mp4.crdownload": "Media",
}


def create_fixtures(base_dir: Path | None = None) -> Path:
    """Generate the 40 fixture files in tests/fixtures/messy_folder/ and messy_folder_backup/."""
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent

    fixtures_dir = base_dir / "fixtures"
    messy_dir = fixtures_dir / "messy_folder"
    backup_dir = fixtures_dir / "messy_folder_backup"

    # Reset directories
    if messy_dir.exists():
        shutil.rmtree(messy_dir)
    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    messy_dir.mkdir(parents=True, exist_ok=True)

    # File contents definitions
    text_files = {
        "Document (3) final FINAL.txt": (
            "Annual employment contract agreement between Acme Corporation and Jane Doe. "
            "Terms include confidentiality, intellectual property assignment, compensation, "
            "and standard working hours."
        ),
        "IMG_20261003_1.txt": (
            "Blue Bottle Coffee Receipt\n"
            "Date: 2026-10-03\n"
            "Item: Cappuccino $5.50, Avocado Toast $9.00\n"
            "Subtotal: $14.50\n"
            "Total Paid with Visa: $14.50\n"
            "Thank you for visiting!"
        ),
        "scan_receipt_09.txt": (
            "Blue Bottle Coffee Receipt\n"
            "Date: 2026-10-04\n"
            "Item: Cold Brew $5.50, Croissant $9.00\n"
            "Subtotal: $14.50\n"
            "Total Paid with Visa: $14.50\n"
            "Thank you for visiting!"
        ),
        "New Text Document.txt": (
            "Weekly grocery list:\n"
            "- Whole milk (2 gallons)\n"
            "- Farm fresh eggs (dozen)\n"
            "- Sourdough bread\n"
            "- Olive oil\n"
            "- Organic spinach\n"
            "- Honeycrisp apples"
        ),
        "untitled(2).md": (
            "# CS 101 Lecture 4: Binary Search Trees\n\n"
            "A Binary Search Tree (BST) is a node-based binary tree data structure with the following properties:\n"
            "- The left subtree of a node contains only nodes with keys lesser than the node's key.\n"
            "- The right subtree contains nodes with keys greater.\n"
            "Time complexity for search, insertion, and deletion: O(log n) average, O(n) worst case."
        ),
        "download (1).csv": (
            "Date,Description,Category,Amount,RunningBalance\n"
            "2026-10-01,Direct Deposit Payroll,Income,5200.00,5200.00\n"
            "2026-10-03,Office Depot Equipment,Expense,-245.50,4954.50\n"
            "2026-10-05,Monthly Health Insurance,Benefit,-310.00,4644.50\n"
        ),
        "final_v2_REAL_final.txt": (
            "Jane Doe - Senior Systems Engineer\n"
            "Email: jane.doe@example.com | Phone: 555-0199\n"
            "Experience:\n"
            "- Staff Infrastructure Engineer, CloudScale Inc (2022-Present)\n"
            "- Senior Distributed Systems Developer (2018-2022)\n"
            "Skills: Python, Go, Kubernetes, Linux kernel internals, Distributed consensus."
        ),
        "recipe_grandma_apple_pie (1).txt": (
            "Grandma's Cinnamon Apple Pie Recipe\n\n"
            "Ingredients:\n"
            "- 6 medium Granny Smith apples, peeled and sliced\n"
            "- 3/4 cup granulated sugar\n"
            "- 1 teaspoon ground cinnamon\n"
            "- 1/4 teaspoon ground nutmeg\n"
            "- Double pie crust pastry\n"
            "Directions: Toss apples with spices, fill pie crust, bake at 375 F for 50 minutes."
        ),
        "flight_booking_LH492.txt": (
            "Lufthansa Booking Confirmation\n"
            "Passenger: John Doe\n"
            "Booking Reference: LH-882193\n"
            "Flight: LH492 Frankfurt (FRA) to New York (JFK)\n"
            "Departure: 2026-11-12 10:45 AM | Seat: 14A (Window)\n"
            "Baggage Allowance: 1 checked bag included."
        ),
        "billing_statement_oct2026.txt": (
            "Metropolitan Electric Company - Monthly Utility Statement\n"
            "Account Number: 994-281-019\n"
            "Billing Period: Sep 20, 2026 - Oct 19, 2026\n"
            "Kilowatt-hours used: 640 kWh\n"
            "Total Amount Due: $98.45\n"
            "Payment Due Date: November 10, 2026"
        ),
        "chem_hw_assignment3.txt": (
            "Chemistry 201: Organic Chemistry Homework 3\n"
            "Professor Williams - Due Friday 5:00 PM\n"
            "Problem 1: Draw the major SN2 reaction product for 1-bromobutane with sodium hydroxide.\n"
            "Problem 2: Explain why tertiary alkyl halides prefer SN1 mechanisms over SN2 due to steric hindrance."
        ),
        "calculus_midterm_review_ch4.md": (
            "# Calculus II Midterm Review Notes\n\n"
            "## Key Integration Techniques\n"
            "1. Integration by Parts: integral u dv = u*v - integral v du\n"
            "2. Trigonometric substitution for sqrt(a^2 - x^2)\n"
            "3. Partial fraction decomposition for rational expressions"
        ),
        "data_analysis_export_q3.csv": (
            "Quarter,Department,BudgetAllocated,ActualSpend,Variance\n"
            "Q1,Engineering,1500000,1420000,80000\n"
            "Q2,Engineering,1600000,1580000,20000\n"
            "Q3,Engineering,1650000,1630000,20000\n"
            "Q3,Sales,800000,815000,-15000\n"
        ),
        "quick_meeting_memo.txt": (
            "Internal Memo\n"
            "To: Engineering Team\n"
            "From: Sarah Jenkins, VP of Engineering\n"
            "Subject: Q4 Roadmap Priorities and Sprint Planning\n"
            "Date: October 20, 2026\n\n"
            "Please review the attached project schedule before tomorrow's kickoff session."
        ),
        "biology_lab_report_draft.md": (
            "# Biology 110: Photosynthesis Rate Investigation\n\n"
            "## Abstract\n"
            "This laboratory experiment measured the rate of oxygen bubbles produced by Elodea canadensis "
            "as a function of light distance from 10cm to 50cm."
        ),
        "uber_trip_receipt_102026.txt": (
            "Uber Trip Receipt\n"
            "Total: $28.40\n"
            "Date: October 18, 2026 8:15 PM\n"
            "Trip: SFO International Airport Terminal 2 to Downtown Hotel\n"
            "Driver: Carlos (Toyota Prius)\n"
            "Payment: Apple Pay (Mastercard ending 4410)"
        ),
        "packing_list_japan_vacation.txt": (
            "Japan Vacation Packing Checklist:\n"
            "- Passport and international driving permit\n"
            "- Japan Rail Pass exchange order\n"
            "- Power bank and type A wall adapters\n"
            "- Waterproof walking shoes\n"
            "- Pocket Wi-Fi reservation details"
        ),
        "script_backup_database.py": (
            "#!/usr/bin/env python3\n"
            "import subprocess\n"
            "import sys\n\n"
            "def run_pg_dump(db_name: str, output_file: str) -> None:\n"
            "    cmd = ['pg_dump', '-Fc', '-b', '-v', '-f', output_file, db_name]\n"
            "    subprocess.check_call(cmd)\n\n"
            "if __name__ == '__main__':\n"
            "    run_pg_dump('production_db', 'prod_backup.dump')\n"
        ),
        "frontend_deploy_worker.js": (
            "const { execSync } = require('child_process');\n"
            "console.log('Building production static frontend bundle...');\n"
            "execSync('npm run build', { stdio: 'inherit' });\n"
            "console.log('Deploying to CDN edge storage bucket...');\n"
        ),
        "sql_query_customer_churn.txt": (
            "-- Analytical query to calculate monthly user retention and churn\n"
            "WITH monthly_cohort AS (\n"
            "    SELECT user_id, date_trunc('month', created_at) AS signup_month\n"
            "    FROM users\n"
            ")\n"
            "SELECT signup_month, count(distinct user_id) as total_users\n"
            "FROM monthly_cohort\n"
            "GROUP BY 1 ORDER BY 1 DESC;\n"
        ),
        "recent_download_note.txt": (
            "Quick project notes downloaded just moments ago.\n"
            "Action item: confirm client review meeting for 3 PM."
        ),
        # Odd cases (text based)
        "empty_scratch_file.txt": "",
        "notas_de_reunion_en_espanol.txt": (
            "Acta de reunion de proyecto.\n"
            "Fecha: 22 de octubre de 2026.\n"
            "Participantes: Carlos, Maria, Roberto.\n"
            "Temas tratados: Revision de presupuesto, entrega de prototipos de diseno y validacion de clientes."
        ),
        "meeting_notes_regarding_the_quarterly_budget_review_and_team_expansion_plans_for_q4_2026_final_draft_approved.txt": (
            "Executive Meeting Minutes regarding the 2026 Q4 Budget Review and Team Expansion.\n"
            "Approvals granted for 4 new engineering positions and upgraded server cluster infrastructure."
        ),
        ".hidden_note.txt": (
            "Internal hidden notes file that the scanner must skip automatically."
        ),
    }

    # Write text files
    for filename, content in text_files.items():
        filepath = messy_dir / filename
        filepath.write_text(content, encoding="utf-8")

    # Write generated PDF files
    make_simple_pdf(
        messy_dir / "scan0007.pdf",
        "INVOICE INV-49201 Date 2026-09-15 Client Corp Balance Due: 1250 USD Thank you.",
    )
    make_simple_pdf(
        messy_dir / "aws_billing_invoice_2026_09.pdf",
        "Amazon Web Services Tax Invoice AWS-992144 Amount Due: 342.10 USD Services EC2 S3.",
    )

    # Write generated DOCX files
    make_simple_docx(
        messy_dir / "Copy of notes.docx",
        "Weekly Engineering Sync Meeting Notes. Discussed Q4 sprint goals, database migration status, and CI pipeline fixes.",
    )
    make_simple_docx(
        messy_dir / "apartment_lease_agreement_signed.docx",
        "Residential Lease Agreement between Landlord Smith and Tenant Jones for Apartment 4B. Monthly rent: $1,800.",
    )

    # Write fake installers (5 files)
    installers = [
        "setup_app_installer (1).exe",
        "python_3.14.0_installer_amd64.msi",
        "DockerDesktop-4.32.0-universal.dmg",
        "vlc_media_player_3.0.20_setup.exe",
        "node_v22.10.0_x64.msi",
    ]
    for inst in installers:
        (messy_dir / inst).write_bytes(b"MZ\x90\x00\x03\x00\x00\x00FakeInstallerBinaryHeader")

    # Write fake images (5 files)
    images = [
        "IMG_20261019_182045.jpg",
        "Screenshot_2026-10-22_114002.png",
        "DSC00492_family_vacation.jpg",
        "graphic_banner_mockup (copy).png",
        "camera_raw_frame_001.jpg",
    ]
    for img in images:
        (messy_dir / img).write_bytes(b"\x89PNG\r\n\x1a\nFakeImageHeaderDataBytes")

    # Partial download odd case
    (messy_dir / "movie_trailer_teaser.mp4.crdownload").write_bytes(
        b"ftypmp42IncompleteDownloadStreamBytes12345"
    )

    # Adjust timestamps
    # Set 39 files to 20 minutes ago (1200s), and recent_download_note.txt to current time
    old_time = time.time() - 1200
    for item in messy_dir.iterdir():
        if item.name == "recent_download_note.txt":
            os.utime(item, (time.time(), time.time()))
        else:
            os.utime(item, (old_time, old_time))

    # Save ground_truth.json
    ground_truth_path = fixtures_dir / "ground_truth.json"
    with open(ground_truth_path, "w", encoding="utf-8") as f:
        json.dump(GROUND_TRUTH, f, indent=2)

    # Create backup copy
    shutil.copytree(messy_dir, backup_dir)

    return messy_dir


if __name__ == "__main__":
    messy_path = create_fixtures()
    count = len(list(messy_path.iterdir()))
    print(f"Created {count} fixture files in {messy_path}")
