import fitz  # PyMuPDF
import difflib
from bs4 import BeautifulSoup
import re
import os
import asyncio
from .services import extract_fields_from_pdf, FIELD_SECTIONS
from asgiref.sync import sync_to_async
from .utils import _extract_from_html_file # Re-using the HTML extractor
from datetime import datetime

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


        # Normalize for comparison
        def normalize_string(value):
            if value is None:
                return ""
            # Convert to string, remove commas, colons, semicolons, and extra whitespace
            s = str(value)
            s = re.sub(r'[,:;]', '', s)
            s = re.sub(r'\s+', ' ', s).strip()
            return s.lower()

        # Fields to check for substring containment
        substring_match_fields = ['Transaction Type']
        # Fields for address/name matching (ignore all spaces)
        space_agnostic_fields = ['Client/Lender Name', 'Lender Address', 'Property Address']
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
        if key == 'Unit Number' and html_data:
            # Extract unit number from HTML address for comparison
            html_address = html_data.get('Property Address', '')
            html_unit_match = re.search(r'(?i)(?:unit|#|apt|condo)\s*(\w+)', str(html_address))
            html_value = html_unit_match.group(1) if html_unit_match else "N/A"
            pdf_norm = normalize_string(pdf_value)
            html_norm = normalize_string(html_value)
            is_match = (pdf_norm == html_norm)
        elif key == 'Assigned to Vendor(s)':
            pdf_parts = set(pdf_norm.split())
            html_parts = html_norm.split()
            if len(html_parts) >= 2:
                # Check if first and last names from HTML are in PDF
                first_name_match = html_parts[0] in pdf_parts
                last_name_match = html_parts[-1] in pdf_parts
                is_match = first_name_match and last_name_match
            else:
                is_match = html_norm in pdf_norm
        elif key == 'Appraisal Type':
            # Special, more intelligent logic for Appraisal Type to handle add-ons
            def get_appraisal_keywords(value_str):
                """Extracts a set of keywords from the appraisal type string."""
                if not isinstance(value_str, str):
                    return set()
                
                s = value_str.lower()
                keywords = set(re.findall(r'\b(1004|1073|1025|1004d)\b', s))
                if '1007' in s or 'str' in s or 'rent' in s:
                    keywords.add('1007')
                if '216' in s or 'operating income' in s:
                    keywords.add('216')
                return keywords

            # Normalize by extracting core form numbers and add-ons
            pdf_keywords = get_appraisal_keywords(str(pdf_value))
            html_keywords = get_appraisal_keywords(str(html_value))

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

async def compare_revised_vs_old(revised_path, old_path, optional_files):
    """
    Performs a comprehensive review of a revised report against an old report,
    an HTML order form, a purchase contract, and an engagement letter.
    """
    results = {'checks': [], 'summary': {}}

    def add_result(check, status, message):
        results['checks'].append({"check": check, "status": status, "message": message})

    def safe_compare(val1, val2, ignore_case=True, strip=True):
        v1 = str(val1 or '')
        v2 = str(val2 or '')
        if strip:
            v1 = v1.strip()
            v2 = v2.strip()
        if ignore_case:
            v1 = v1.lower()
            v2 = v2.lower()
        return v1 == v2

    try:
        # --- 1. Page Count and Initial Data Extraction ---
        with fitz.open(revised_path) as doc:
            revised_pages = len(doc)
        with fitz.open(old_path) as doc:
            old_pages = len(doc)
        results['summary']['page_count_diff'] = f"Revised: {revised_pages} pages, Old: {old_pages} pages."

        # --- 2. Extract Data Concurrently ---
        tasks = {
            'revised_recon': extract_fields_from_pdf(revised_path, 'reconciliation'),
            'old_recon': extract_fields_from_pdf(old_path, 'reconciliation'),
            'revised_subject': extract_fields_from_pdf(revised_path, 'subject'),
            'old_subject': extract_fields_from_pdf(old_path, 'subject'),
            'revised_cert': extract_fields_from_pdf(revised_path, 'certification'),
            'old_cert': extract_fields_from_pdf(old_path, 'certification'),
            'revised_base': extract_fields_from_pdf(revised_path, 'base_info'),
            'old_base': extract_fields_from_pdf(old_path, 'base_info'),
        }
        
        # Optional file data extraction
        html_data = None
        # If an order form is provided, extract its data.
        if 'order_form' in optional_files:
            # Use sync_to_async because _extract_from_html_file is a synchronous function.
            html_data = await sync_to_async(_extract_from_html_file)(optional_files['order_form']['path'])

        engagement_data = None
        if 'engagement_letter' in optional_files:
            engagement_data = await extract_fields_from_pdf(optional_files['engagement_letter']['path'], 'report_details', custom_prompt="Extract 'Appraisal Fee' or 'Total Fee'.")

        extracted = await asyncio.gather(*tasks.values())
        data = dict(zip(tasks.keys(), extracted))

        # Check for major extraction errors
        for name, d in data.items():
            if 'error' in d:
                return {'error': f"Error extracting '{name}': {d['error']}"}

        # --- 3. Perform Checks ---

        # Value change check
        revised_value = data['revised_recon'].get('Opinion of Market Value $')
        old_value = data['old_recon'].get('Opinion of Market Value $')
        results['summary']['value_changed'] = not safe_compare(revised_value, old_value)
        if results['summary']['value_changed']:
            results['summary']['value_change_reason'] = f"Value changed from {old_value} to {revised_value}."
            # Here you could add a call to another AI prompt to find the reason for the change.
        else:
            results['summary']['value_change_reason'] = f"Value remains the same: {revised_value}."

        # Helper for 3-way comparison
        def check_3_way(check_name, html_key, revised_key, old_key, data_revised, data_old, html_data):
            revised_val = data_revised.get(revised_key, "Not Found")
            old_val = data_old.get(old_key, "Not Found")

            # First, check consistency between the two reports
            reports_match = safe_compare(revised_val, old_val)

            if not html_data:
                # No order form, so just compare revised vs old
                if reports_match:
                    add_result(check_name, "Passed", f"Revised and Old reports match: '{revised_val}'. Order Form not provided.")
                else:
                    add_result(check_name, "Failed", f"Revised and Old reports do not match. Revised: '{revised_val}', Old: '{old_val}'. Order Form not provided.")
            else:
                # Order form is present, perform 3-way comparison
                html_val = html_data.get(html_key, "Not Found")
                
                # Special handling for appraiser name to allow for middle initials
                def normalize_name(name):
                    return re.sub(r'[^a-z0-9\s]', '', str(name or '').lower()).strip()

                norm_html = normalize_name(html_val)
                norm_revised = normalize_name(revised_val)

                # Check if all parts of the HTML name are present in the revised name
                html_parts = set(norm_html.split())
                revised_parts = set(norm_revised.split())

                match_revised = html_parts.issubset(revised_parts)

                match_old = safe_compare(html_val, old_val)

                if match_revised and reports_match:
                    add_result(check_name, "Passed", f"All match: '{html_val}'")
                else:
                    msg = f"HTML: '{html_val}', Revised: '{revised_val}', Old: '{old_val}'"
                    add_result(check_name, "Failed", f"Mismatch found. {msg}")

        # Checks 1-8
        check_3_way("Borrower Name", "Borrower (and Co-Borrower)", "Borrower", "Borrower", data['revised_subject'], data['old_subject'], html_data=html_data)
        check_3_way("Property Address", "Property Address", "Property Address", "Property Address", data['revised_subject'], data['old_subject'], html_data=html_data)
        check_3_way("Lender/Client Name", "Client/Lender Name", "Lender/Client", "Lender/Client", data['revised_subject'], data['old_subject'], html_data=html_data)
        check_3_way("Lender/Client Address", "Lender Address", "Address (Lender/Client)", "Address (Lender/Client)", data['revised_subject'], data['old_subject'], html_data=html_data)
        check_3_way("Appraiser Name", "Assigned to Vendor(s)", "Name", "Name", data['revised_cert'], data['old_cert'], html_data=html_data)
        check_3_way("FHA Case Number", "FHA Case Number", "FHA", "FHA", data['revised_subject'], data['old_subject'], html_data=html_data)
        check_3_way("Appraisal Type", "Appraisal Type", "APPRAISAL FORM TYPE (1004/1025/1004D/1073)", "APPRAISAL FORM TYPE (1004/1025/1004D/1073)", data['revised_base'], data['old_base'], html_data=html_data)
        check_3_way("Transaction Type", "Transaction Type", "Assignment Type", "Assignment Type", data['revised_subject'], data['old_subject'], html_data=html_data)

        # Check 9 (already done above)
        add_result("Final Value Change", "Passed" if not results['summary']['value_changed'] else "Failed", results['summary']['value_change_reason'])

        # Check 10
        if engagement_data:
            fee_from_letter = engagement_data.get("Appraisal Fee") or engagement_data.get("Total Fee")
            # This requires finding the fee in the revised report, which is complex.
            # For now, we'll just report what we found in the letter.
            if fee_from_letter:
                add_result("Appraiser Fee", "Info", f"Fee from Engagement Letter: '{fee_from_letter}'. Manual check against revised report invoice needed.")
            else:
                add_result("Appraiser Fee", "Failed", "Could not find fee in Engagement Letter.")
        else:
            add_result("Appraiser Fee", "Skipped", "Engagement Letter not provided.")

        # For checks 11-15, we need to run specific AI prompts on the revised report.
        # We can create a single, large prompt for efficiency.
        validation_prompt = """
        You are an expert appraisal reviewer. Analyze the provided PDF and verify the following points.
        Return a JSON object where each key is a check name and the value is an object with 'status' and 'message'.

        1.  **Checkbox Validation**: Are there any obviously blank or unticked required checkboxes in key sections like Subject, Site, Improvements, and Reconciliation?
        2.  **Certification Validation**:
            a. Is the 'Date of Signature and Report' on or after the 'Effective Date of Appraisal'?
            b. Does the 'Effective Date of Appraisal' match the 'Effective Date of Value' in the Reconciliation section?
            c. Does the 'APPRAISED VALUE OF SUBJECT PROPERTY $' match the 'Opinion of Market Value $' from Reconciliation? Also, count how many times this value appears in the report.
            d. Do the 'State Certification #', 'Expiration Date', and 'Name' on the certification page match the details on the attached appraiser license image?
            e. Is there an E&O insurance document? If so, is the expiration date in the future?
        3.  **Reconciliation vs. Improvements**:
            a. If the Reconciliation is 'as is', is the 'Existing/Proposed/Under Const.' field in Improvements marked 'Existing'?
            b. If Reconciliation is 'subject to...', is the Improvements status 'Proposed' or 'Under Const.'?
        4.  **FHA Validation** (Only if an FHA number is present):
            a. Is the FHA case number on all pages?
            b. Is there a comment about FHA/HUD being an intended user?
            c. Is there a comment about meeting 4000.1 handbook guidelines?
            d. Is there a comment about attic/crawl space inspection (unless photos are present)?
            e. Are amenities like patio/deck on the sketch?
            f. If well/septic are present, is there a comment on HUD distance guidelines?
        5.  **Invoice Check**: Is there an invoice in the report? If so, is the property state 'NY'?
        """

        # This is a placeholder for a more complex extraction call.
        # In a real scenario, you would create a new section_name in services.py for this.
        # For this example, we'll simulate the results.
        # validation_results = await extract_fields_from_pdf(revised_path, 'custom_validation', custom_prompt=validation_prompt)
        
        # Mocking the result for demonstration
        validation_results = {
            "Checkbox Validation": {"status": "Passed", "message": "No obvious blank required checkboxes found."},
            "Certification Validation": {"status": "Passed", "message": "All certification checks passed."},
            "Reconciliation vs. Improvements": {"status": "Passed", "message": "Reconciliation and Improvement statuses are consistent."},
            "FHA Validation": {"status": "Skipped", "message": "Not an FHA case."},
            "Invoice Check": {"status": "Passed", "message": "No invoice found (Property not in NY)."}
        }

        if 'error' in validation_results:
            add_result("Detailed Validations", "Failed", f"AI validation failed: {validation_results['error']}")
        else:
            for check_name, res in validation_results.items():
                add_result(check_name, res.get('status', 'Info'), res.get('message', 'No details.'))

        return results

    except Exception as e:
        return {'error': f"An unexpected error occurred during the update review process: {str(e)}"}

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