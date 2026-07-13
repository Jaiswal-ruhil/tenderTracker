"""
template_generator.py
~~~~~~~~~~~~~~~~~~
Utility to generate pre-filled HTML and PDF compliance templates for tenders.
Supports falling back to raw HTML/Markdown files if external PDF engines are not installed.
"""

import os
import re
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

# 1. Bidder Undertaking HTML template
UNDERTAKING_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; color: #333; }
    h1 { text-align: center; text-transform: uppercase; font-size: 20px; margin-bottom: 30px; color: #111; }
    .details-table { width: 100%; border-collapse: collapse; margin-top: 20px; margin-bottom: 20px; }
    .details-table td { padding: 10px; border: 1px solid #ccc; font-size: 14px; }
    .details-table td.label { font-weight: bold; width: 30%; background-color: #f9f9f9; }
    .content { text-align: justify; margin-top: 20px; font-size: 14px; }
    .content ol { padding-left: 20px; }
    .content li { margin-bottom: 8px; }
    .signature-section { margin-top: 60px; float: right; width: 300px; text-align: left; }
    .signature-line { margin-top: 50px; border-top: 1px solid #000; }
</style>
</head>
<body>
    <h1>Bidder Undertaking</h1>
    <p>To,</p>
    <p><strong>The Buyer / Department</strong><br>
    {department}</p>
    
    <p><strong>Subject:</strong> Undertaking regarding compliance of tender terms and conditions.</p>
    
    <p>Dear Sir/Madam,</p>
    
    <div class="content">
        <p>I/We, the undersigned, hereby submit our bid for the tender/bid described below, in response to the invitation for bid:</p>
        
        <table class="details-table">
            <tr>
                <td class="label">Bid Number</td>
                <td>{bid_no}</td>
            </tr>
            <tr>
                <td class="label">Tender Category</td>
                <td>{category}</td>
            </tr>
            <tr>
                <td class="label">Firm Name</td>
                <td>{firm_name}</td>
            </tr>
            <tr>
                <td class="label">Firm Address</td>
                <td>{firm_address}</td>
            </tr>
            <tr>
                <td class="label">Date</td>
                <td>{date}</td>
            </tr>
        </table>
        
        <p>I/We hereby declare and undertake that:</p>
        <ol>
            <li>We have read and understood all the terms, conditions, specifications, and instructions of the bid document, and we agree to comply with them completely without any deviations.</li>
            <li>We are not blacklisted, debarred, or suspended by any government department, public sector undertaking, or autonomous body of India.</li>
            <li>All documents, certificates, and information submitted by us in this bid are genuine, true, and correct. In case any document or information is found to be false or fabricated, we understand we are liable for disqualification and further penal action under GeM General Terms and Conditions (GTC).</li>
            <li>We comply with the restrictions under Rule 144(xi) of General Financial Rules (GFR) 2017 regarding bidder from a country sharing a land border with India.</li>
        </ol>
    </div>
    
    <div class="signature-section">
        <p>For and on behalf of:<br>
        <strong>{firm_name}</strong></p>
        <div class="signature-line"></div>
        <p><strong>Authorized Signatory</strong><br>
        Name: {signatory_name}<br>
        Designation: {signatory_designation}</p>
    </div>
</body>
</html>
"""

# 2. General Bidder Declaration HTML template
DECLARATION_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; color: #333; }
    h1 { text-align: center; text-transform: uppercase; font-size: 20px; margin-bottom: 30px; color: #111; }
    .content { text-align: justify; margin-top: 20px; font-size: 14px; }
    .content ol { padding-left: 20px; }
    .content li { margin-bottom: 10px; }
    .signature-section { margin-top: 60px; float: right; width: 300px; text-align: left; }
    .signature-line { margin-top: 50px; border-top: 1px solid #000; }
</style>
</head>
<body>
    <h1>Bidder Declaration</h1>
    <p>To,</p>
    <p><strong>The Buyer / Department</strong><br>
    {department}</p>
    
    <p><strong>Tender/Bid Number:</strong> {bid_no}</p>
    <p><strong>Tender Category:</strong> {category}</p>
    
    <div class="content">
        <p>Dear Sir/Madam,</p>
        <p>I/We do hereby declare and state the following in connection with our submission of bid for the above-mentioned tender:</p>
        
        <ol>
            <li>We, <strong>{firm_name}</strong> (address: {firm_address}), confirm that we have fully verified the requirements, specifications, and delivery schedule of the items/services requested.</li>
            <li>We declare that we possess the necessary financial capacity, technical infrastructure, and human resources required to execute the contract as per the specified timelines.</li>
            <li>We accept all standard and additional terms and conditions laid down in the GeM bid document, including General Terms and Conditions (GTC) and Additional Terms and Conditions (ATC).</li>
            <li>We certify that the prices quoted by us in this bid are competitive, realistic, and justified in line with market rates.</li>
        </ol>
    </div>
    
    <div class="signature-section">
        <p>For and on behalf of:<br>
        <strong>{firm_name}</strong></p>
        <div class="signature-line"></div>
        <p><strong>Authorized Signatory</strong><br>
        Name: {signatory_name}<br>
        Designation: {signatory_designation}<br>
        Date: {date}</p>
    </div>
</body>
</html>
"""

# 3. Affidavit Template (Non-Blacklisting)
AFFIDAVIT_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; color: #333; }
    h1 { text-align: center; text-transform: uppercase; font-size: 20px; margin-bottom: 10px; color: #111; }
    .content { text-align: justify; margin-top: 30px; font-size: 14px; }
    .content ol { padding-left: 20px; }
    .content li { margin-bottom: 12px; }
    .signature-section { margin-top: 60px; float: right; width: 300px; text-align: left; }
    .signature-line { margin-top: 50px; border-top: 1px solid #000; }
    .verification { margin-top: 250px; text-align: justify; font-size: 14px; border-top: 1px dashed #ccc; padding-top: 20px; }
</style>
</head>
<body>
    <h1>Affidavit</h1>
    <p style="text-align: center; font-style: italic; margin-bottom: 30px;">(To be submitted on non-judicial stamp paper of appropriate value)</p>
    
    <div class="content">
        <p>I, <strong>{signatory_name}</strong>, Son/Daughter/Wife of Shri ________________________, aged about _____ years, resident of {firm_address}, in the capacity of {signatory_designation} of <strong>{firm_name}</strong>, do hereby solemnly affirm and state as under:</p>
        
        <ol>
            <li>That I am the authorized signatory of <strong>{firm_name}</strong> and am competent to sign this affidavit.</li>
            <li>That <strong>{firm_name}</strong> has participated in the tender/bid process for Bid Number <strong>{bid_no}</strong> for the category <strong>{category}</strong>.</li>
            <li>That our firm <strong>{firm_name}</strong> has not been blacklisted, debarred, or suspended by the Government of India, any State Government, public sector undertaking, or autonomous body, nor has any contract been terminated due to default.</li>
            <li>That there is no pending criminal case or investigation against the firm or its directors/partners.</li>
            <li>That all statements and information provided in our bid are true, and we accept all terms and conditions of the bid.</li>
        </ol>
    </div>
    
    <div class="signature-section">
        <p><strong>Deponent</strong></p>
        <div class="signature-line"></div>
        <p>Name: {signatory_name}<br>
        Designation: {signatory_designation}<br>
        Firm: {firm_name}</p>
    </div>
    
    <div class="verification">
        <p><strong>Verification:</strong></p>
        <p>Verified at ________________ on this _____ day of ____________ 20___, that the contents of the above affidavit are true and correct to the best of my knowledge and belief, and nothing material has been concealed therefrom.</p>
        <div style="margin-top: 50px; float: right; width: 300px;">
            <p><strong>Deponent</strong></p>
        </div>
    </div>
</body>
</html>
"""

# 4. Make in India (MII) Certificate Template
MII_CERTIFICATE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; color: #333; }
    h1 { text-align: center; text-transform: uppercase; font-size: 18px; margin-bottom: 30px; color: #111; }
    .content { text-align: justify; margin-top: 20px; font-size: 14px; }
    .content ol { padding-left: 20px; }
    .content li { margin-bottom: 12px; }
    .signature-section { margin-top: 60px; float: right; width: 300px; text-align: left; }
    .signature-line { margin-top: 50px; border-top: 1px solid #000; }
</style>
</head>
<body>
    <h1>Self-Certificate under Make in India policy</h1>
    <p style="text-align: center; font-style: italic; margin-bottom: 20px;">(In line with Public Procurement (Preference to Make in India) Order, 2017)</p>
    
    <p>To,</p>
    <p><strong>The Buyer / Department</strong><br>
    {department}</p>
    
    <p><strong>Subject:</strong> Self-Certificate for Local Content in Tender No: <strong>{bid_no}</strong></p>
    
    <div class="content">
        <p>Dear Sir/Madam,</p>
        <p>I/We, <strong>{signatory_name}</strong>, in my/our capacity as {signatory_designation} of <strong>{firm_name}</strong>, do hereby certify and declare that:</p>
        
        <ol>
            <li>We meet the 'Local Content' requirement for the items offered in the bid <strong>{bid_no}</strong>.</li>
            <li>The percentage of local content in the offered products is <strong>{local_content_percentage}%</strong> (Class-I Local Supplier details: &gt;= 50%, Class-II Local Supplier details: &gt;= 20%).</li>
            <li>The local value addition is made at the following location/address: <strong>{local_content_location}</strong>.</li>
            <li>We understand that false declarations will be in breach of the Code of Integrity under Rule 175(1)(i)(h) of the General Financial Rules for which a bidder or its successors can be debarred for up to two years as per Rule 151 (iii) of the General Financial Rules along with such other actions as may be permissible under law.</li>
        </ol>
    </div>
    
    <div class="signature-section">
        <p>For and on behalf of:<br>
        <strong>{firm_name}</strong></p>
        <div class="signature-line"></div>
        <p><strong>Authorized Signatory</strong><br>
        Name: {signatory_name}<br>
        Designation: {signatory_designation}<br>
        Date: {date}</p>
    </div>
</body>
</html>
"""

TEMPLATE_MAP = {
    "bidder_undertaking": UNDERTAKING_TEMPLATE,
    "declaration": DECLARATION_TEMPLATE,
    "affidavit": AFFIDAVIT_TEMPLATE,
    "mii_certificate": MII_CERTIFICATE_TEMPLATE
}

def render_template(template_str: str, context: Dict[str, Any]) -> str:
    """Safely replaces placeholders in format {variable_name} with context values."""
    default_context = {
        "bid_no": "N/A",
        "category": "General",
        "firm_name": "Unnamed Firm",
        "firm_address": "N/A",
        "department": "Government of India (GeM Portal)",
        "date": datetime.now().strftime("%d-%m-%Y"),
        "signatory_name": "Authorized Representative",
        "signatory_designation": "Proprietor / Partner / Director",
        "local_content_percentage": "50",
        "local_content_location": "Works Address / Factory Premises"
    }
    
    # Merge default context with provided context
    merged = {**default_context, **{k: v for k, v in context.items() if v is not None}}
    
    # Simple regex-based replacement to handle missing values without KeyError
    def replacer(match):
        key = match.group(1)
        return str(merged.get(key, f"{{{key}}}"))
        
    return re.sub(r'\{([a-zA-Z0-9_]+)\}', replacer, template_str)


def generate_document(
    output_dir: str,
    template_type: str,
    context: Dict[str, Any]
) -> Tuple[bool, str, Optional[str]]:
    """
    Generates a pre-filled compliance document from templates.
    Writes HTML file and attempts to compile it into PDF.
    
    Supported template_types:
        - bidder_undertaking
        - declaration
        - affidavit
        - mii_certificate
    
    Returns:
        Tuple[bool, str, Optional[str]]: (success_status, path_to_file, warning_message_if_any)
    """
    clean_type = template_type.lower().strip()
    if clean_type not in TEMPLATE_MAP:
        raise ValueError(
            f"Unsupported template type: {template_type}. "
            f"Supported types: {list(TEMPLATE_MAP.keys())}"
        )
        
    os.makedirs(output_dir, exist_ok=True)
    
    template_str = TEMPLATE_MAP[clean_type]
    html_content = render_template(template_str, context)
    
    # Paths for output files
    html_path = os.path.join(output_dir, f"{clean_type}.html")
    pdf_path = os.path.join(output_dir, f"{clean_type}.pdf")
    
    # 1. Write the HTML file
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    # 2. Try compiling to PDF via WeasyPrint
    try:
        import weasyprint
        weasyprint.HTML(string=html_content).write_pdf(pdf_path)
        return True, pdf_path, None
    except ImportError:
        pass
    except Exception as e:
        pass
        
    # 3. Try compiling to PDF via pdfkit (requires wkhtmltopdf binary)
    try:
        import pdfkit
        pdfkit.from_string(html_content, pdf_path)
        return True, pdf_path, None
    except ImportError:
        pass
    except Exception as e:
        pass
        
    # If all PDF compilers failed, return the HTML file path with a warning
    warning = (
        f"Document template generated successfully as HTML ({clean_type}.html), but could not compile to PDF. "
        "Please install WeasyPrint (`pip install weasyprint`) or pdfkit (`pip install pdfkit` and install wkhtmltopdf) "
        "to enable automated PDF generation."
    )
    return True, html_path, warning
