import re
from bs4 import BeautifulSoup

def _extract_from_html_file(file_path):
    """Extracts data from the HTML file using BeautifulSoup."""
    data = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'html.parser')

        def get_text_from_label(label_text, default="N/A"): 
            """Finds a label by its text and returns the text of a nearby value element."""
            # Case-insensitive search for the label text in common tags
            label_element = soup.find(lambda tag: tag.name in ['label', 'strong', 'th', 'td', 'div'] and label_text.lower() in tag.get_text().lower())
            
            if label_element:
                # Strategy 1: Look for a 'view-label-info' class in a sibling or parent's sibling
                current = label_element
                for _ in range(3): # Check up to 3 levels up
                    sibling = current.find_next_sibling()
                    if sibling:
                        value_span = sibling.find(class_='view-label-info')
                        if value_span:
                            return value_span.get_text(strip=True)
                        # If no span, but the sibling has text, it might be the value
                        if sibling.get_text(strip=True):
                            return sibling.get_text(strip=True)
                    current = current.parent
                    if not current:
                        break

                # Strategy 2: Look for a specific 'view-label-info' span in a sibling container (original logic)
                parent_container = label_element.find_parent(class_=re.compile(r'col-\d+'))
                if parent_container and parent_container.find_next_sibling(class_=re.compile(r'col-\d+')):
                    value_span = parent_container.find_next_sibling().find('span', class_='view-label-info')
                    if value_span:
                        return value_span.get_text(strip=True)

                # Strategy 3: Look for the next sibling element (common in table structures <td>Label</td><td>Value</td>)
                next_sibling = label_element.find_next_sibling()
                if next_sibling:
                    if next_sibling.get_text(strip=True):
                        return next_sibling.get_text(strip=True)

            return default

        data['Client/Lender Name'] = get_text_from_label('Client Name')
        data['Lender Address'] = get_text_from_label('Client Address') # Corrected label text to match HTML
        data['FHA Case Number'] = get_text_from_label('FHA Case Number')
        data['Transaction Type'] = get_text_from_label('Transaction Type')
        data['AMC Reg. Number'] = get_text_from_label('AMC Reg. Number') # Using 'Borrower Name' was too generic and was matching other elements.
        data['Borrower (and Co-Borrower)'] = get_text_from_label('Borrower (and Co-Borrower)')
        data['Property Type'] = get_text_from_label('Property Type')
        data['Property Address'] = get_text_from_label('Property Address')
        data['Property County'] = get_text_from_label('Property County')
        data['Appraisal Type'] = get_text_from_label('Appraisal Type')
        data['Assigned to Vendor(s)'] = get_text_from_label('Assigned to Vendor(s)')

        uad_xml_link = soup.find(id='ctl00_cphBody_lnkAppraisalXMLFile')
        data['UAD XML Report'] = uad_xml_link.get_text(strip=True) if uad_xml_link else "N/A"

    except FileNotFoundError:
        data = {field: "N/A (HTML File Error)" for field in data.keys()}
    except Exception as e:
        fields = ['Client/Lender Name', 'Lender Address', 'FHA Case Number',
              'Transaction Type', 'AMC Reg. Number', 'Borrower (and Co-Borrower)',
              'Property Type', 'Property Address', 'Property County',
              'Appraisal Type', 'Assigned to Vendor(s)', 'UAD XML Report']
        data = {field: "N/A (HTML Processing Error)" for field in fields}
    return data