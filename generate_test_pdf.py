from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def create_sample_pdf(filename="storage/sample_uploads/test_invoice.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=1, spaceAfter=20)
    story.append(Paragraph("TAX INVOICE", title_style))

    # Header / Vendor / Buyer Details
    header_data = [
        [
            Paragraph("<b>Vendor:</b><br/>Acme Solutions Pvt Ltd<br/>GSTIN: 27AAACA12341Z1<br/>Mumbai, MH"),
            Paragraph("<b>Invoice No:</b> INV-2026-089<br/><b>Date:</b> 2026-08-25<br/><b>Buyer:</b> Enterprise Systems Ltd<br/><b>Buyer GSTIN:</b> 27BBBCT99991Z5")
        ]
    ]
    header_table = Table(header_data, colWidths=[250, 250])
    story.append(header_table)
    story.append(Spacer(1, 20))

    # Items Table
    items_data = [
        ["Description", "Qty", "Unit Price (INR)", "Total (INR)"],
        ["Cloud Architecture Consultation", "2", "15000.00", "30000.00"],
        ["Automated Security Assessment", "1", "25000.00", "25000.00"],
        ["Subtotal", "", "", "55000.00"],
        ["Tax (18% GST)", "", "", "9900.00"],
        ["Grand Total", "", "", "64900.00"]
    ]

    items_table = Table(items_data, colWidths=[220, 50, 110, 120])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    
    story.append(items_table)
    doc.build(story)
    print(f"Sample PDF created successfully at: {filename}")

if __name__ == "__main__":
    create_sample_pdf()