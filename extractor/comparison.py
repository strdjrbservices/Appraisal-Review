import fitz  # PyMuPDF
import difflib
from bs4 import BeautifulSoup
import re
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

async def compare_pdfs(pdf1_path, pdf2_path):
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
        
        # Await all async tasks
        market_value_1, market_value_2 = await asyncio.gather(
            market_value_1_task,
            market_value_2_task
        )
        
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
            extra_pages_1 = list(range(max_pages + 1, page_count_1 + 1))
            extra_pages_2 = list(range(max_pages + 1, page_count_2 + 1))
            return {
                'market_value_1': market_value_1,
                'market_value_2': market_value_2,
                'page_count_1': page_count_1,
                'page_count_2': page_count_2,
                'differing_pages': differing_pages,
                'extra_pages_1': extra_pages_1,
                'extra_pages_2': extra_pages_2,
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