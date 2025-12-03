import fitz  # PyMuPDF
import difflib
from bs4 import BeautifulSoup
import re
import os
import asyncio
from .services import extract_fields_from_pdf

async def _extract_market_value_from_api(pdf_path):
    """
    Extracts the final opinion of market value from a PDF document using the API.
    """
    try:
        # Call the async extraction function for the 'reconciliation' section
        reconciliation_data = await extract_fields_from_pdf(pdf_path, 'reconciliation')
        if 'error' in reconciliation_data:
            return f"API Error: {reconciliation_data['error']}"
        
        # Get the value from the new field we added
        market_value = reconciliation_data.get("Opinion of Market Value $")
        if market_value:
            # Format it consistently as a dollar amount
            return f"${market_value.strip()}"
        return "Not Found"
    except Exception as e:
        return f"Extraction Error: {str(e)}"

async def compare_pdfs(pdf1_path, pdf2_path, html_data=None, purchase_data=None, engagement_data=None):
    """
    Compares two PDF files page by page based on text content.

    Args:
        pdf1_path (str): The file path for the first PDF.
        pdf2_path (str): The file path for the second PDF.
    Returns:
        dict: A dictionary containing the comparison results. This is now an async function.
    """
    try:
        # Run API extractions and PDF text comparison concurrently
        market_value_1_task = _extract_market_value_from_api(pdf1_path)
        market_value_2_task = _extract_market_value_from_api(pdf2_path)

        # --- Automatic Revision Check Logic ---
        rejection_reason = None
        revision_check_results = None
        tasks = {
            'market_value_1': market_value_1_task,
            'market_value_2': market_value_2_task,
        }

        # 1. If an HTML file was processed, extract rejection reason from its content
        if html_data:
            html_content = html_data.get('html_content', '')
            if html_content:
                # Use regex to find the rejection reason text
                match = re.search(r"Report Rejection Reason(?:</strong>|</b>|:)\s*<br>\s*(.*?)\s*<", html_content, re.IGNORECASE | re.DOTALL)
                if match:
                    rejection_reason = match.group(1).strip()
        
        # 2. If a reason was found, create a task to run the revision check on the new (revised) PDF
        if rejection_reason:    
            tasks['revision_check'] = extract_fields_from_pdf(
                pdf_paths=[pdf1_path], # Check against the revised report (pdf1)
                section_name='revision_check',
                custom_prompt=rejection_reason
            )
            
        # Await all async tasks
        results = await asyncio.gather(*tasks.values())
        results_dict = dict(zip(tasks.keys(), results))
    
        market_value_1 = results_dict.get('market_value_1')
        market_value_2 = results_dict.get('market_value_2')
        revision_check_results = results_dict.get('revision_check')
            
        with fitz.open(pdf1_path) as pdf1, fitz.open(pdf2_path) as pdf2:
            page_count_1 = len(pdf1)
            page_count_2 = len(pdf2)
            max_pages = min(page_count_1, page_count_2)
            differing_pages = []
            diff_generator = difflib.HtmlDiff(tabsize=4, wrapcolumn=80)
            for i in range(max_pages):
                text1 = pdf1[i].get_text().strip()
                text2 = pdf2[i].get_text().strip()
                if text1 != text2:
                    diff_html = diff_generator.make_table(
                        text1.splitlines(), text2.splitlines(),
                        fromdesc='PDF 1', todesc='PDF 2'
                    )
                    differing_pages.append({'page_number': i + 1, 'diff_html': diff_html})
            extra_pages_1 = list(range(min(page_count_1, page_count_2) + 1, page_count_1 + 1))
            extra_pages_2 = list(range(min(page_count_1, page_count_2) + 1, page_count_2 + 1))
            return {
                'filename1': os.path.basename(pdf1_path),
                'filename2': os.path.basename(pdf2_path),
                'market_value_1': market_value_1,
                'market_value_2': market_value_2,
                'page_count_1': page_count_1,
                'page_count_2': page_count_2,
                'differing_pages': differing_pages,
                'extra_pages_1': extra_pages_1,
                'extra_pages_2': extra_pages_2,
                'html_data': html_data,
                'purchase_data': purchase_data,
                'engagement_data': engagement_data,
                'rejection_reason': rejection_reason,
                'revision_check_results': revision_check_results,
            }
    except Exception as e:
        return {'error': f"Failed to compare PDFs. Error: {str(e)}"}

def extract_fields_from_html(html_path, fields_to_extract):
    """
    Extracts specified fields from a simple HTML file.
    Assumes a structure where a field label is followed by its value,
    often in a table (e.g., <th>Label</th><td>Value</td>).
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    extracted_data = {}
    for field in fields_to_extract:
        found_value = None
        # Find elements (th, td, div, etc.) containing the field text
        label_element = soup.find(lambda tag: tag.name in ['th', 'td', 'label', 'strong'] and field.lower() in tag.get_text().lower())

        if label_element:
            # Try to find the value in the next sibling element (common in tables)
            next_sibling = label_element.find_next_sibling()
            if next_sibling:
                found_value = next_sibling.get_text(strip=True)

        extracted_data[field] = found_value if found_value else "Not Found"

    return extracted_data

def compare_data_sets(pdf_data, html_data):
    """
    Compares two dictionaries of extracted data (from PDF and HTML).
    """
    comparison_results = []
    all_keys = sorted(list(set(pdf_data.keys()) | set(html_data.keys())))

    for key in all_keys:
        # Initialize diff generator for highlighting differences
        diff_generator = difflib.HtmlDiff(tabsize=4, wrapcolumn=80)

        pdf_value = pdf_data.get(key) 
        html_value = html_data.get(key)

        # Default match status
        is_match = False

        # Fields to check for substring containment
        substring_match_fields = ['Appraisal Type', 'Transaction Type']

        # Fields for address/name matching (ignore all spaces)
        space_agnostic_fields = ['Client/Lender Name', 'Lender Address', 'Property Address']

        # Normalize for comparison
        def normalize_string(value):
            if value is None:
                return ""
            # Convert to string, remove commas, colons, semicolons, and extra whitespace
            s = str(value)
            s = re.sub(r'[,:;]', '', s)
            s = re.sub(r'\s+', ' ', s).strip()
            return s.lower()

        def normalize_space_agnostic(value):
            if value is None:
                return ""
            # Remove all spaces and special characters, then lowercase
            s = str(value)
            s = re.sub(r'[,:;\s]', '', s)
            return s.lower()

        pdf_norm = normalize_string(pdf_value)
        html_norm = normalize_string(html_value)

        # Special handling for Unit Number
        if key == 'Unit Number':
            # Extract unit number from HTML address for comparison
            html_address = html_data.get('Property Address', '')
            html_unit_match = re.search(r'(?i)(?:unit|#|apt|condo)\s*(\w+)', str(html_address))
            html_value = html_unit_match.group(1) if html_unit_match else "N/A"
            pdf_norm = normalize_string(pdf_value)
            html_norm = normalize_string(html_value)
            is_match = pdf_norm == html_norm
        elif key == 'Assigned to Vendor(s)':
            pdf_parts = pdf_norm.split()
            html_parts = html_norm.split()
            if len(html_parts) >= 2:
                # Check if first and last names from HTML are in PDF
                first_name_match = html_parts[0] in pdf_parts
                last_name_match = html_parts[-1] in pdf_parts
                is_match = first_name_match and last_name_match
            else:
                is_match = html_norm in pdf_norm
        elif key == 'Appraisal Type':
            # Special, more intelligent logic for Appraisal Type
            def get_appraisal_keywords(value_str):
                """Extracts a set of keywords from the appraisal type string."""
                if not isinstance(value_str, str):
                    return set()
                
                s = value_str.lower()
                keywords = set()
                if '1007' in s or 'str rental' in s or 'rent schedule' in s:
                    keywords.add('1007')
                if '216' in s or 'operating income' in s:
                    keywords.add('216')
                return keywords

            pdf_keywords = get_appraisal_keywords(pdf_value)
            html_keywords = get_appraisal_keywords(html_value)

            # Match if the keywords found in the HTML are a subset of (or equal to) the keywords in the PDF.
            is_match = html_keywords.issubset(pdf_keywords)
        elif key in substring_match_fields:
            is_match = html_norm in pdf_norm
        elif key in space_agnostic_fields:
            is_match = normalize_space_agnostic(pdf_value) == normalize_space_agnostic(html_value)
        else:
            is_match = pdf_norm == html_norm

        # If there's no match, generate an HTML diff to show in the UI
        diff_html = None
        if not is_match:
            diff_html = diff_generator.make_table(
                str(pdf_value or "").splitlines(),
                str(html_value or "").splitlines(),
                fromdesc='PDF Value',
                todesc='HTML Value'
            )

        comparison_results.append({
            'field': key,
            'pdf_value': pdf_value, 
            'html_value': html_value,
            'match': is_match,
            'diff_html': diff_html
        })
    return comparison_results

async def compare_1004d(original_pdf_path, d1004_pdf_path, html_data=None, purchase_data=None):
    """
    Performs a comprehensive review of a 1004D form against an original appraisal,
    an HTML order form, and a purchase contract.
    """
    # This will hold the structured data for the template
    comparison_data = {'checks': []} 

    def add_result(check, status, message):
        comparison_data['checks'].append({"check": check, "status": status, "message": message})

    try:
        # --- 1. Data Extraction ---
        tasks = {
            'oa_subject': extract_fields_from_pdf(original_pdf_path, 'subject'),
            'oa_contract': extract_fields_from_pdf(original_pdf_path, 'contract'),
            'oa_recon': extract_fields_from_pdf(original_pdf_path, 'reconciliation'),
            'oa_cert': extract_fields_from_pdf(original_pdf_path, 'certification'),
            'd1004_data': extract_fields_from_pdf(d1004_pdf_path, 'd1004'),
        }
        extracted = await asyncio.gather(*tasks.values())
        data = dict(zip(tasks.keys(), extracted))

        # Check for major extraction errors
        for name, d in data.items():
            if 'error' in d:
                return {'error': f"An error occurred during data extraction for '{name}'. Details: {d['error']}"}

        oa_subject = data['oa_subject']
        oa_contract = data['oa_contract']
        oa_recon = data['oa_recon']
        oa_cert = data['oa_cert']
        d1004 = data['d1004_data']

        # --- 2. Validation Logic ---

        # Helper for safe comparison
        def safe_compare(val1, val2):
            v1 = str(val1 or '').strip().lower()
            v2 = str(val2 or '').strip().lower()
            return v1 == v2
        
        def normalize_address(addr_str):
            if not addr_str: return ""
            # Remove commas, periods, and extra whitespace, then lowercase
            return re.sub(r'[.,]', '', addr_str).strip().lower()

        # 2.1 Completeness Check
        missing_fields = [k for k, v in d1004.items() if v is None and "checkbox" not in k]
        if not missing_fields:
            add_result("1004D Completeness", "Passed", "All required fields appear to be filled.")
        else:
            add_result("1004D Completeness", "Failed", f"The following fields are missing in the 1004D: {', '.join(missing_fields)}")

        # 2.1b Subject Info Match
        oa_full_address = f"{oa_subject.get('Property Address', '')} {oa_subject.get('City', '')} {oa_subject.get('State', '')} {oa_subject.get('Zip Code', '')}"
        d1004_full_address = f"{d1004.get('Property Address', '')} {d1004.get('City', '')} {d1004.get('State', '')} {d1004.get('Zip Code', '')}"
        if safe_compare(normalize_address(oa_full_address), normalize_address(d1004_full_address)):
             add_result("Property Address Match", "Passed", f"Addresses match: {d1004.get('Property Address')}")
        else:
            add_result("Property Address Match", "Failed", f"Mismatch: Original shows '{oa_subject.get('Property Address')}', 1004D shows '{d1004.get('Property Address')}'")

        if safe_compare(d1004.get("Borrower"), oa_subject.get("Borrower")):
            add_result("Borrower Name Match", "Passed", f"Borrower names match: {oa_subject.get('Borrower')}")
        else:
            add_result("Borrower Name Match", "Failed", f"Mismatch: 1004D shows '{d1004.get('Borrower')}', Original Appraisal shows '{oa_subject.get('Borrower')}'")


        # 2.2 Contract Info Match
        if safe_compare(d1004.get("Contract Price $"), oa_contract.get("Contract Price $")):
            add_result("Contract Price Match", "Passed", f"Contract prices match: {oa_contract.get('Contract Price $')}")
        else:
            add_result("Contract Price Match", "Failed", f"Mismatch: 1004D shows '{d1004.get('Contract Price $')}', Original Appraisal shows '{oa_contract.get('Contract Price $')}'")

        if safe_compare(d1004.get("Date of Contract"), oa_contract.get("Date of Contract")):
            add_result("Contract Date Match", "Passed", f"Contract dates match: {oa_contract.get('Date of Contract')}")
        else:
            add_result("Contract Date Match", "Failed", f"Mismatch: 1004D shows '{d1004.get('Date of Contract')}', Original Appraisal shows '{oa_contract.get('Date of Contract')}'")

        # 2.3 Value & Date Match
        if safe_compare(d1004.get("Effective Date of Original Appraisal"), oa_recon.get("Effective Date of Value")):
            add_result("Effective Date Match", "Passed", f"Effective dates match: {oa_recon.get('Effective Date of Value')}")
        else:
            add_result("Effective Date Match", "Failed", f"Mismatch: 1004D shows '{d1004.get('Effective Date of Original Appraisal')}', Original Appraisal shows '{oa_recon.get('Effective Date of Value')}'")

        if safe_compare(d1004.get("Original Appraised Value $"), oa_recon.get("Opinion of Market Value $")):
            add_result("Original Appraised Value Match", "Passed", f"Values match: {oa_recon.get('Opinion of Market Value $')}")
        else:
            add_result("Original Appraised Value Match", "Failed", f"Mismatch: 1004D shows '{d1004.get('Original Appraised Value $')}', Original Appraisal shows '{oa_recon.get('Opinion of Market Value $')}'")

        # 2.4 Original Appraiser/Lender Match
        if safe_compare(d1004.get("Original Appraiser"), oa_cert.get("Name")):
            add_result("Original Appraiser Match", "Passed", f"Appraiser names match: {oa_cert.get('Name')}")
        else:
            add_result("Original Appraiser Match", "Failed", f"Mismatch: 1004D shows '{d1004.get('Original Appraiser')}', Original Appraisal shows '{oa_cert.get('Name')}'")

        if safe_compare(d1004.get("Original Lender/Client"), oa_subject.get("Lender/Client")):
            add_result("Original Lender/Client Match", "Passed", f"Lender/Client names match: {oa_subject.get('Lender/Client')}")
        else:
            add_result("Original Lender/Client Match", "Failed", f"Mismatch: 1004D shows '{d1004.get('Original Lender/Client')}', Original Appraisal shows '{oa_subject.get('Lender/Client')}'")

        # 2.5 Conditional Logic for 1004D Type
        is_summary_update = d1004.get("SUMMARY APPRAISAL UPDATE REPORT (checkbox)") == "Yes"
        is_cert_completion = d1004.get("CERTIFICATION OF COMPLETION (checkbox)") == "Yes"

        if not is_summary_update and not is_cert_completion:
            add_result("Report Type Check", "Failed", "Neither 'Summary Appraisal Update' nor 'Certification of Completion' box is checked.")
        elif is_summary_update:
            add_result("Report Type Check", "Passed", "Report type is 'Summary Appraisal Update'.")
            market_decline_q = d1004.get("HAS THE MARKET VALUE OF THE SUBJECT PROPERTY DECLINED SINCE THE EFFECTIVE DATE OF THE PRIOR APPRAISAL? (Yes/No)")
            if market_decline_q in ["Yes", "No"]:
                add_result("Market Decline Question", "Passed", f"Question answered: '{market_decline_q}'")
            else:
                add_result("Market Decline Question", "Failed", "The market decline question is not answered.")
        elif is_cert_completion:
            add_result("Report Type Check", "Passed", "Report type is 'Certification of Completion'.")
            improvements_q = d1004.get("HAVE THE IMPROVEMENTS BEEN COMPLETED IN ACCORDANCE WITH THE REQUIREMENTS AND CONDITIONS STATED IN THE ORIGINAL APPRAISAL REPORT? (Yes/No)")
            if improvements_q == "Yes":
                add_result("Improvements Completion Question", "Passed", "Question answered: 'Yes'.")
                # You can add logic here to compare repairs if you extract them from the recon section.
                add_result("Repairs Verification", "Info", "Manual check needed to confirm 1004D repairs match original report's reconciliation section.")
            elif improvements_q == "No":
                add_result("Improvements Completion Question", "Passed", "Question answered: 'No'.")
                impact_desc = d1004.get("If No, describe the impact on the opinion of market value")
                if impact_desc:
                    add_result("Impact Description", "Passed", f"Impact on value is described: '{impact_desc}'")
                else:
                    add_result("Impact Description", "Failed", "Improvements were not completed as required, but the impact on value is not described.")
            else:
                add_result("Improvements Completion Question", "Failed", "The improvements completion question is not answered.")

        # 2.6 Signature Section
        if is_summary_update:
            if d1004.get("Date of Signature and Report"):
                add_result("Signature Date (Update)", "Passed", f"Effective date is present: {d1004.get('Date of Signature and Report')}")
            else:
                add_result("Signature Date (Update)", "Failed", "Effective date is required for an Appraisal Update but is missing.")
        if is_cert_completion:
            if d1004.get("Date of Inspection (for Certification of Completion)"):
                add_result("Inspection Date (Completion)", "Passed", f"Date of inspection is present: {d1004.get('Date of Inspection (for Certification of Completion)')}")
            else:
                add_result("Inspection Date (Completion)", "Failed", "Date of inspection is required for a Final Inspection but is missing.")

        # 2.7 HTML Order Form vs. 1004D
        if html_data:
            html_lender = html_data.get("Client/Lender Name", "Not Found")
            d1004_lender = d1004.get("Original Lender/Client")
            if safe_compare(d1004_lender, html_lender):
                add_result("Lender Name vs. Order Form", "Passed", f"Lender name on 1004D and Order Form match: {d1004_lender}")
            else:
                add_result("Lender Name vs. Order Form", "Failed", f"Mismatch: 1004D shows '{d1004_lender}', Order Form shows '{html_lender}'")
        else:
            add_result("Order Form Comparison", "Skipped", "HTML Order Form not provided; comparisons against it cannot be performed.")

        # Add all extracted data to the results for re-rendering if needed
        comparison_data['extracted_data'] = {
            'oa_subject': oa_subject,
            'oa_contract': oa_contract,
            'oa_recon': oa_recon,
            'oa_cert': oa_cert,
            'd1004_data': d1004,
            'html_data': html_data,
            'purchase_data': purchase_data
        }
        return comparison_data
    except Exception as e:
        return {'error': f"An unexpected error occurred during the 1004D review process: {str(e)}"}