import os
import docx

def create_demo_docx():
    doc = docx.Document()
    
    doc.add_heading('CONFIDENTIAL SETTLEMENT AND RELEASE AGREEMENT', 0)
    
    doc.add_paragraph(
        "This Confidential Settlement and Release Agreement (the “Agreement”) is made and "
        "entered into effective as of March 28, 2026, by and between Horizon Tech "
        "Solutions LLC, a Delaware corporation with its principal place of business at 1234 "
        "Silicon Boulevard, San Francisco, CA 94107 (“Employer”), and Michael J. Sterling, "
        "an individual residing at 742 Evergreen Terrace, Springfield, IL 62704 (“Employee”)."
    )
    
    doc.add_heading('1. Separation of Employment', level=1)
    doc.add_paragraph(
        "Employee's employment with Employer will terminate effective April 15, 2026 "
        "(the “Separation Date”). Employee agrees to return all company property, including "
        "the Lenovo ThinkPad laptop and the corporate AMEX card ending in 4092, to Sarah "
        "Jenkins, HR Director, by 5:00 PM on the Separation Date."
    )
    
    doc.add_heading('2. Severance Payment', level=1)
    doc.add_paragraph(
        "Provided Employee signs and does not revoke this Agreement, Employer agrees to "
        "pay Employee a severance amount of $85,000.00, less applicable local and federal "
        "taxes. This amount will be deposited into the checking account on file ending in "
        "8391 at Bank of America within fourteen (14) days."
    )
    
    doc.add_heading('3. Contact and Post-Employment Obligations', level=1)
    doc.add_paragraph(
        "If Employer has any questions regarding ongoing projects, Employee agrees to make "
        "themselves reasonably available by phone at (555) 019-8372 or via email at "
        "m.sterling88@gmail.com for a period of thirty (30) days following the Separation Date."
    )

    doc.add_heading('4. General Release', level=1)
    doc.add_paragraph(
        "Employee hereby irrevocably and unconditionally releases Employer and its "
        "subsidiaries, including Global Data Corp., from any and all claims related to "
        "their employment, which was managed primarily by Vice President of Operations, "
        "Amanda V. Carter."
    )

    doc.add_heading('Signatures', level=1)
    doc.add_paragraph("Employer: Horizon Tech Solutions LLC")
    doc.add_paragraph("By: _____________________________")
    doc.add_paragraph("Name: Robert L. Vance, CEO")
    
    doc.add_paragraph("\nEmployee:")
    doc.add_paragraph("By: _____________________________")
    doc.add_paragraph("Name: Michael J. Sterling")
    doc.add_paragraph("SSN: XXX-XX-4819")

    os.makedirs("demo_data", exist_ok=True)
    doc.save('demo_data/Confidential_Agreement_Sterling.docx')
    print("Generated demo_data/Confidential_Agreement_Sterling.docx")

if __name__ == "__main__":
    create_demo_docx()
