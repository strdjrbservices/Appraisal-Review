from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from .services import extract_fields_from_pdf, FIELD_SECTIONS, SUBJECT_FIELDS
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import SignUpForm, UpdateFileReviewForm
from .utils import _extract_from_html_file
from asgiref.sync import sync_to_async
from .comparison import compare_data_sets, compare_1004d, compare_revised_vs_old
from django.views.decorators.csrf import csrf_exempt
import fitz  # PyMuPDF
from django.http import JsonResponse
import re
import asyncio
import json

def register_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful! Please wait for an admin to approve your account.')
            return redirect('login')
    else:
        form = SignUpForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('upload_pdf')
            else: # The user is None
                # The backend returns None for both bad passwords and unapproved users.
                # We can provide a more specific message for unapproved users if we check their status.
                user_exists = get_user_model().objects.filter(username=username).first()
                if user_exists and hasattr(user_exists, 'profile') and not user_exists.profile.is_approved:
                    messages.error(request, 'Your account has not been approved by an administrator yet. Please wait for approval.')
                else:
                    messages.error(request, 'Invalid username or password.')
    form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')

# The view to handle the initial PDF upload
@login_required
async def upload_pdf(request):
    if request.method == 'POST' and request.FILES.get('pdf_file'):
        pdf_file = request.FILES['pdf_file']
        html_file = request.FILES.get('html_file') # Use .get() to make it optional
        purchase_copy_file = request.FILES.get('purchase_copy_file')
        engagement_letter_file = request.FILES.get('engagement_letter_file')
        fs = FileSystemStorage()

        # Save PDF file
        pdf_filename = await sync_to_async(fs.save)(pdf_file.name, pdf_file)
        pdf_path = await sync_to_async(fs.path)(pdf_filename)

        html_data = None
        purchase_data = None
        engagement_data = None
        html_filename_for_context = None
        purchase_filename_for_context = None
        engagement_filename_for_context = None

        # Process HTML file only if it exists
        if html_file:
            html_filename = await sync_to_async(fs.save)(html_file.name, html_file)
            html_filename_for_context = html_file.name
            html_path = await sync_to_async(fs.path)(html_filename)
            # Extract data from the HTML file
            html_data = await sync_to_async(_extract_from_html_file)(html_path)
        
        if purchase_copy_file:
            purchase_filename = await sync_to_async(fs.save)(purchase_copy_file.name, purchase_copy_file)
            purchase_filename_for_context = purchase_copy_file.name
            purchase_path = await sync_to_async(fs.path)(purchase_filename)
            # A simple text extraction might be enough for now
            purchase_data = await extract_fields_from_pdf(purchase_path, 'contract')

        if engagement_letter_file:
            engagement_filename = await sync_to_async(fs.save)(engagement_letter_file.name, engagement_letter_file)
            engagement_filename_for_context = engagement_letter_file.name
            engagement_path = await sync_to_async(fs.path)(engagement_filename)
            # Use 'report_details' for generic extraction from the engagement letter
            extracted_engagement_data = await extract_fields_from_pdf(engagement_path, 'report_details', custom_prompt="Extract the 'Appraisal Fee' or 'Total Fee' from this document.")
            # Ensure we have a valid dictionary to pass to the template
            if 'error' not in extracted_engagement_data:
                engagement_data = {'addendum': extracted_engagement_data}

        # Extract base information to show in the popup
        base_info = await extract_fields_from_pdf(pdf_path, 'base_info')

        # Create display names for the buttons
        sections_for_template = {
            key: key.replace('_', ' ').title() 
            for key in FIELD_SECTIONS.keys() if key not in ['uniform_report', 'addendum', 'appraisal_id', 'additional_comments', 'base_info']
        }

        # Render the home page with section buttons and data from both files
        context = {
            'filename': pdf_filename, 
            'html_filename': html_filename_for_context,
            'purchase_filename': purchase_filename_for_context,
            'engagement_filename': engagement_filename_for_context,
            'sections': sections_for_template, 
            'base_info': base_info, 
            'html_data': html_data,
            'purchase_data': purchase_data,
            'engagement_data': engagement_data
        }
        return await sync_to_async(render)(request, 'home.html', context)

    return await sync_to_async(render)(request, 'upload.html')

@login_required
async def update_file_review_upload_view(request):
    """Handles the GET request to display the update file review upload form."""
    form = UpdateFileReviewForm()
    return await sync_to_async(render)(request, 'update_file_review_upload.html', {'form': form})

@login_required
async def update_file_review_process_view(request):
    """
    Handles the POST request from the upload form to prepare the dashboard,
    and the GET request from the dashboard to run the comparison.
    """
    fs = FileSystemStorage()

    # Handle GET request from the dashboard to run the comparison
    if request.method == 'GET' and request.GET.get('revised_filename'):
        revised_filename = request.GET.get('revised_filename')
        old_filename = request.GET.get('old_filename')

        revised_path = await sync_to_async(fs.path)(revised_filename)
        old_path = await sync_to_async(fs.path)(old_filename)

        # This part is now simplified as optional files are not passed from the dashboard GET request.
        # If they are needed for the summary, the logic would need to be adjusted to pass their filenames too.
        comparison_results = await compare_revised_vs_old(revised_path, old_path, {})

        context = {
            'results': comparison_results,
            'revised_filename': revised_filename,
            'old_filename': old_filename
        }
        return await sync_to_async(render)(request, 'update_file_review_results.html', context)

    # Handle POST request from the initial upload form
    if request.method == 'POST':
        form = UpdateFileReviewForm(request.POST, request.FILES)
        if await sync_to_async(form.is_valid)():
            revised_report_file = form.cleaned_data['revised_report']
            old_report_file = form.cleaned_data['old_report']

            revised_filename = await sync_to_async(fs.save)(revised_report_file.name, revised_report_file)
            old_filename = await sync_to_async(fs.save)(old_report_file.name, old_report_file)
            revised_path = await sync_to_async(fs.path)(revised_filename)

            # Process optional files and extract their data for the dashboard
            optional_files = {}
            html_data, purchase_data, engagement_data = None, None, None

            for field_name in ['order_form', 'purchase_copy', 'engagement_letter']:
                file = form.cleaned_data.get(field_name)
                if file:
                    filename = await sync_to_async(fs.save)(file.name, file)
                    path = await sync_to_async(fs.path)(filename)
                    optional_files[field_name] = {'path': path, 'name': filename}

                    if field_name == 'order_form':
                        html_data = await sync_to_async(_extract_from_html_file)(path)
                    elif field_name == 'purchase_copy':
                        purchase_data = await extract_fields_from_pdf(path, 'contract')
                    elif field_name == 'engagement_letter':
                        extracted_engagement_data = await extract_fields_from_pdf(path, 'report_details', custom_prompt="Extract the 'Appraisal Fee' or 'Total Fee' from this document.")
                        if 'error' not in extracted_engagement_data:
                            engagement_data = {'addendum': extracted_engagement_data}

            # Extract base info from the revised report for the dashboard display
            base_info = await extract_fields_from_pdf(revised_path, 'base_info')

            # Create display names for the section buttons
            sections_for_template = {
                key: key.replace('_', ' ').title()
                for key in FIELD_SECTIONS.keys() if key not in ['uniform_report', 'addendum', 'appraisal_id', 'additional_comments', 'base_info', 'd1004']
            }

            context = {
                'revised_filename': revised_filename,
                'old_filename': old_filename,
                'base_info': base_info,
                'sections': sections_for_template,
                'optional_files': optional_files,
                'html_data': html_data,
                'purchase_data': purchase_data,
                'engagement_data': engagement_data,
            }
            return await sync_to_async(render)(request, 'update_file_review_dashboard.html', context)

            # Import here to avoid circular dependency
            comparison_results = await compare_revised_vs_old(revised_path, old_path, optional_files)

            context = {
                'results': comparison_results,
                'revised_filename': revised_filename,
                'old_filename': old_filename
            }
            return await sync_to_async(render)(request, 'update_file_review_results.html', context)
    return await sync_to_async(redirect)('update_file_review_upload')

@login_required
def d1004_file_review_upload_view(request):
    """Handles the GET request to display the 1004D file review upload form."""
    return render(request, 'd1004_file_review_upload.html')

@login_required
async def d1004_file_review_process_view(request):
    """
    Handles the POST from upload to show the dashboard, and the GET from the dashboard
    to process and compare an original appraisal with a 1004D.
    """
    fs = FileSystemStorage()

    # Handle POST request from the initial upload form
    if request.method == 'POST':
        original_pdf = request.FILES['original_pdf']
        d1004_pdf = request.FILES['d1004_pdf']
        html_file = request.FILES.get('html_file')
        purchase_copy_file = request.FILES.get('purchase_copy_file')
        fs = FileSystemStorage()

        original_filename = await sync_to_async(fs.save)(original_pdf.name, original_pdf)
        d1004_filename = await sync_to_async(fs.save)(d1004_pdf.name, d1004_pdf)

        original_pdf_path = await sync_to_async(fs.path)(original_filename)
        d1004_pdf_path = await sync_to_async(fs.path)(d1004_filename)

        html_data = None
        purchase_data = None
        html_filename_for_context = None
        purchase_filename_for_context = None

        if html_file:
            html_filename = await sync_to_async(fs.save)(html_file.name, html_file)
            html_filename_for_context = html_filename
            html_path = await sync_to_async(fs.path)(html_filename)
            html_data = await sync_to_async(_extract_from_html_file)(html_path)
        
        if purchase_copy_file:
            purchase_filename = await sync_to_async(fs.save)(purchase_copy_file.name, purchase_copy_file)
            purchase_filename_for_context = purchase_filename
            purchase_path = await sync_to_async(fs.path)(purchase_filename)
            purchase_data = await extract_fields_from_pdf(purchase_path, 'contract')

        # Extract base info from the original report for the dashboard display
        base_info = await extract_fields_from_pdf(original_pdf_path, 'base_info')

        # Create display names for the section buttons (for the original report)
        sections_for_template = {
            key: key.replace('_', ' ').title()
            for key in FIELD_SECTIONS.keys() if key not in ['uniform_report', 'addendum', 'appraisal_id', 'additional_comments', 'base_info', 'd1004']
        }

        context = {
            'original_filename': original_filename,
            'd1004_filename': d1004_filename,
            'html_filename': html_filename_for_context,
            'purchase_filename': purchase_filename_for_context,
            'base_info': base_info,
            'sections': sections_for_template,
            'html_data': html_data,
            'purchase_data': purchase_data,
        }
        return await sync_to_async(render)(request, 'd1004_file_review_dashboard.html', context)

    # Handle GET request from the dashboard to run the comparison
    if request.method == 'GET' and request.GET.get('original_filename'):
        original_filename = request.GET.get('original_filename')
        d1004_filename = request.GET.get('d1004_filename')
        html_filename = request.GET.get('html_filename')
        purchase_filename = request.GET.get('purchase_filename')
        # Initialize context filenames for the results page
        html_filename_for_context = html_filename
        purchase_filename_for_context = purchase_filename

        original_pdf_path = await sync_to_async(fs.path)(original_filename)
        d1004_pdf_path = await sync_to_async(fs.path)(d1004_filename)

        html_data = None
        if html_filename and await sync_to_async(fs.exists)(html_filename):
            html_path = await sync_to_async(fs.path)(html_filename)
            html_data = await sync_to_async(_extract_from_html_file)(html_path)

        purchase_data = None
        if purchase_filename and await sync_to_async(fs.exists)(purchase_filename):
            purchase_path = await sync_to_async(fs.path)(purchase_filename)
            purchase_data = await extract_fields_from_pdf(purchase_path, 'contract')

        # Perform the comparison
        comparison_results = await compare_1004d(original_pdf_path, d1004_pdf_path, html_data, purchase_data)

        # Add filenames to the results dictionary so they can be accessed in the template for the custom analysis form.
        comparison_results['original_filename'] = original_filename
        comparison_results['d1004_filename'] = d1004_filename
        comparison_results['html_filename'] = html_filename_for_context if html_filename_for_context else ""
        comparison_results['purchase_filename'] = purchase_filename_for_context if purchase_filename_for_context else ""

        context = {
            'results': comparison_results,
        }
        return await sync_to_async(render)(request, 'd1004_result.html', context)

    return await sync_to_async(redirect)('d1004_file_review_upload')

@login_required
async def d1004_custom_analysis_view(request):
    """
    Handles custom analysis prompts for the 1004D review, using context from all uploaded files.
    """
    if request.method == 'POST':
        fs = FileSystemStorage()
        original_filename = request.POST.get('original_filename')
        d1004_filename = request.POST.get('d1004_filename')
        html_filename = request.POST.get('html_filename')
        purchase_filename = request.POST.get('purchase_filename')
        custom_prompt = request.POST.get('custom_prompt')

        if not original_filename or not d1004_filename or not custom_prompt:
            # Handle error: essential data missing
            return await sync_to_async(redirect)('upload_pdf')

        original_pdf_path = await sync_to_async(fs.path)(original_filename)
        d1004_pdf_path = await sync_to_async(fs.path)(d1004_filename)

        # Initialize the list of paths for analysis with the core PDF documents
        pdf_paths_for_analysis = [original_pdf_path, d1004_pdf_path]
        all_files_context_for_prompt = {}

        # 1. Extract HTML data if available to build context
        html_data = None
        if html_filename and await sync_to_async(fs.exists)(html_filename):
            html_file_path = await sync_to_async(fs.path)(html_filename)
            html_data = await sync_to_async(_extract_from_html_file)(html_file_path)
            all_files_context_for_prompt['order_form_data'] = html_data

        # Re-run the initial comparison to get the base results to display on the page
        initial_comparison_results = await compare_1004d(original_pdf_path, d1004_pdf_path, html_data)
        # Add filenames back into results for the template forms
        initial_comparison_results['original_filename'] = original_filename
        initial_comparison_results['d1004_filename'] = d1004_filename
        initial_comparison_results['html_filename'] = html_filename
        initial_comparison_results['purchase_filename'] = purchase_filename

        # Add purchase contract data if available
        if purchase_filename and await sync_to_async(fs.exists)(purchase_filename):
            purchase_file_path = await sync_to_async(fs.path)(purchase_filename)
            purchase_data = await extract_fields_from_pdf(purchase_file_path, 'contract')
            all_files_context_for_prompt['purchase_contract_data'] = purchase_data


        # Call the AI for custom analysis, passing all available documents.
        custom_analysis_results = await extract_fields_from_pdf(
            pdf_paths=pdf_paths_for_analysis,
            section_name='custom_analysis',
            custom_prompt=(
                f"User Query: '''{custom_prompt}'''\n\n"
                "Analyze all provided documents (original appraisal, 1004D form, and HTML order form if present) to answer the user's query. "
                "Use the following pre-processed JSON data as the primary source for your analysis and to cross-reference information. "
                f"Context Data: {json.dumps(all_files_context_for_prompt)}"
            )
        )

        # Render the results page again with the new analysis data
        context = {
            'results': initial_comparison_results,
            'custom_analysis_results': custom_analysis_results,
            'custom_prompt': custom_prompt # Pass the prompt back to display it
        }
        return await sync_to_async(render)(request, 'd1004_result.html', context)

    # Redirect if not a POST request
    return await sync_to_async(redirect)('d1004_file_review_upload')

@login_required
async def update_file_review_custom_analysis_view(request):
    """
    Handles custom analysis prompts for the update file review, using context from all uploaded files.
    """
    if request.method == 'POST':
        fs = FileSystemStorage()
        revised_filename = request.POST.get('revised_filename')
        old_filename = request.POST.get('old_filename')
        order_form_filename = request.POST.get('order_form_filename')
        purchase_copy_filename = request.POST.get('purchase_copy_filename')
        engagement_letter_filename = request.POST.get('engagement_letter_filename')
        custom_prompt = request.POST.get('custom_prompt')

        if not revised_filename or not old_filename or not custom_prompt:
            messages.error(request, "Missing required files or custom prompt for analysis.")
            return await sync_to_async(redirect)('update_file_review_upload')

        pdf_paths_for_analysis = []
        all_files_context_for_prompt = {}
        optional_files_data = {}

        # Add required PDF files
        revised_path = await sync_to_async(fs.path)(revised_filename)
        old_path = await sync_to_async(fs.path)(old_filename)
        pdf_paths_for_analysis.extend([revised_path, old_path])

        # Add optional files and extract data for context
        if order_form_filename and await sync_to_async(fs.exists)(order_form_filename):
            order_form_path = await sync_to_async(fs.path)(order_form_filename)
            html_data = await sync_to_async(_extract_from_html_file)(order_form_path)
            all_files_context_for_prompt['order_form_data'] = html_data
            optional_files_data['order_form'] = {'path': order_form_path, 'name': order_form_filename}
            pdf_paths_for_analysis.append(order_form_path) # Add HTML file path for AI to read

        if purchase_copy_filename and await sync_to_async(fs.exists)(purchase_copy_filename):
            purchase_path = await sync_to_async(fs.path)(purchase_copy_filename)
            purchase_data = await extract_fields_from_pdf(purchase_path, 'contract')
            all_files_context_for_prompt['purchase_contract_data'] = purchase_data
            optional_files_data['purchase_copy'] = {'path': purchase_path, 'name': purchase_copy_filename}
            pdf_paths_for_analysis.append(purchase_path)

        if engagement_letter_filename and await sync_to_async(fs.exists)(engagement_letter_filename):
            engagement_path = await sync_to_async(fs.path)(engagement_letter_filename)
            extracted_engagement_data = await extract_fields_from_pdf(engagement_path, 'report_details', custom_prompt="Extract the 'Appraisal Fee' or 'Total Fee' from this document.")
            if 'error' not in extracted_engagement_data:
                all_files_context_for_prompt['engagement_letter_data'] = extracted_engagement_data
            optional_files_data['engagement_letter'] = {'path': engagement_path, 'name': engagement_letter_filename}
            pdf_paths_for_analysis.append(engagement_path)

        # Re-run the initial comparison to get the base results to display on the page
        initial_comparison_results = await compare_revised_vs_old(revised_path, old_path, optional_files_data)

        # Call the AI for custom analysis, passing all available documents.
        full_custom_prompt = (
            f"User Query: '''{custom_prompt}'''\n\n"
            "Analyze all provided documents (revised appraisal, old appraisal, and any optional files like HTML order form, purchase contract, engagement letter if present) to answer the user's query. "
            "Use the following pre-processed JSON data as the primary source for your analysis and to cross-reference information. "
            f"Context Data: {json.dumps(all_files_context_for_prompt)}"
        )

        custom_analysis_results = await extract_fields_from_pdf(
            pdf_paths=pdf_paths_for_analysis,
            section_name='custom_analysis',
            custom_prompt=full_custom_prompt
        )

        context = {
            'results': initial_comparison_results,
            'custom_analysis_results': custom_analysis_results,
            'custom_prompt': custom_prompt,
            'revised_filename': revised_filename,
            'old_filename': old_filename,
            'order_form_filename': order_form_filename,
            'purchase_copy_filename': purchase_copy_filename,
            'engagement_letter_filename': engagement_letter_filename,
            'html_data': all_files_context_for_prompt.get('order_form_data') # Pass extracted HTML data if available
        }
        return await sync_to_async(render)(request, 'update_file_review_results.html', context)

    messages.error(request, "Invalid request for custom analysis.")
    return await sync_to_async(redirect)('update_file_review_upload')

async def _extract_from_pdf_file(file_path):
    """Extracts data from the PDF file using the Gemini API service."""
    # Extract data from multiple sections of the PDF.
    subject_data = await extract_fields_from_pdf(file_path, 'subject')
    improvements_data = await extract_fields_from_pdf(file_path, 'improvements')
    certification_data = await extract_fields_from_pdf(file_path, 'certification')
    appraisal_id_data = await extract_fields_from_pdf(file_path, 'appraisal_id')

    # Check for errors in the primary 'subject' data extraction
    if 'error' in subject_data:
        return {key: f"N/A (API Error: {subject_data['error']})" for key in [
            'Client/Lender Name', 'Lender Address', 'FHA Case Number', 'Transaction Type',
            'AMC Reg. Number', 'Borrower (and Co-Borrower)', 'Property Type', 'Unit Number',
            'Property Address', 'Property County', 'Appraisal Type', 
            'Assigned to Vendor(s)', 'UAD XML Report'
        ]}
    
    # Map the API response fields to the keys expected by the comparison logic.
    # Helper to safely get data from potentially errored responses.
    def get_data(data_dict, key, default="N/A"):
        if 'error' in data_dict:
            return f"N/A (API Error)"
        return data_dict.get(key, default)

    def find_fha_case_number_manually(path_to_pdf):
        """Scans the top-right of PDF pages for an FHA Case Number."""
        try:
            doc = fitz.open(path_to_pdf)
            # Regex for FHA Case Number format (e.g., 123-4567890)
            fha_regex = re.compile(r'\d{3}-\d{7}')
            # Check the first 5 pages, which is where it usually is
            for page_num in range(min(5, len(doc))):
                page = doc.load_page(page_num)
                # Define a more precise top-right corner (e.g., right 30% of width, top 10% of height)
                rect = fitz.Rect(page.rect.width * 0.7, 0, page.rect.width, page.rect.height * 0.1)
                text = page.get_text("text", clip=rect)
                match = fha_regex.search(text)
                if match:
                    return match.group(0)
        except Exception:
            return None  # Return None if any error occurs
        finally:
            if 'doc' in locals() and doc:
                doc.close()

    def clean_value(value):
        if isinstance(value, str):
            return re.sub(r'[,:;]', '', value)
        return value

    def simplify_transaction_type(value):
        if not isinstance(value, str):
            return value
        if 'purchase' in value.lower():
            return 'Purchase'
        if 'refinance' in value.lower():
            return 'Refinance'
        return value
        
    def determine_appraisal_type(pdf_path, appraisal_id_data):
        """Determines the appraisal type by scanning headers and checking for add-ons."""
        base_form = None
        try:
            doc = fitz.open(pdf_path)
            if len(doc) > 0:
                first_page_text = doc[0].get_text("text").lower()
                if "uniform residential appraisal report" in first_page_text:
                    base_form = "1004" # header as " Uniform Residential Appraisal Report"
                elif "individual condominium unit appraisal report" in first_page_text: # The user requested "Individual Condominium Unit Appraisal Report File", this is close enough and more robust.
                    base_form = "1073"
                elif "multi family" in first_page_text or "multifamily" in first_page_text:
                    base_form = "1025"
            doc.close()
        except Exception:
            base_form = None # Fallback if PDF scanning fails

        # Use the text from the specific field as a primary source for add-ons
        # and a fallback for the base form.
        field_text = get_data(appraisal_id_data, 'This Report is one of the following types:', '')
        if not isinstance(field_text, str):
            field_text = ""

        add_ons = []
        if '1007' in field_text or 'rent schedule' in field_text.lower() or 'str' in field_text.lower() or 'rental' in field_text.lower() or 'SINGLE FAMILY COMPARABLE RENT SCHEDULE' in field_text: # 1007, STR, rental
            add_ons.append("1007")
        if '216' in field_text or 'operating income' in field_text.lower():
            add_ons.append("216")

        if base_form and add_ons:
            return f"{base_form} + {' + '.join(add_ons)}"
        elif base_form:
            return base_form
        elif add_ons:
            # If we only found add-ons, return them.
            return " + ".join(add_ons)
        
        # Fallback to the original text if no keywords were found
        return field_text if field_text else "Not Found"

    # Logic to extract Unit Number for Condos
    unit_number = "N/A"
    pdf_appraisal_type = get_data(appraisal_id_data, 'This Report is one of the following types:', '')
    pdf_property_type = get_data(improvements_data, 'Type', '')
    full_address = get_data(subject_data, 'Property Address', '')

    if 'condo' in str(pdf_appraisal_type).lower() or '1073' in str(pdf_appraisal_type) or 'condo' in str(pdf_property_type).lower():
        # Regex to find common unit number patterns (e.g., Unit 104, #104, Apt 104, Condo 104)
        match = re.search(r'(?i)(?:unit|#|apt|condo)\s*(\w+)', full_address)
        if match:
            unit_number = match.group(1)

    # Get FHA case number from subject data first
    fha_case_number = get_data(subject_data, 'FHA Case Number', None)
    # If not found via API, try manual search as a fallback
    if not fha_case_number or fha_case_number == 'N/A (Not in Subject Section)':
        fha_case_number = find_fha_case_number_manually(file_path) or 'N/A'

    mapped_data = {
        'Client/Lender Name': clean_value(get_data(subject_data, 'Lender/Client')),
        'Lender Address': clean_value(get_data(subject_data, 'Address (Lender/Client)')),
        'FHA Case Number': fha_case_number,
        'Transaction Type': simplify_transaction_type(get_data(subject_data, 'Assignment Type')),
        'AMC Reg. Number': 'N/A (Not in PDF)',
        'Borrower (and Co-Borrower)': get_data(subject_data, 'Borrower'),
        'Property Type': get_data(improvements_data, 'Type'),
        'Unit Number': unit_number,
        'Property Address': (
            f"{get_data(subject_data, 'Property Address', '')}, "
            f"{get_data(subject_data, 'City', '')}, {get_data(subject_data, 'State', '')} "
            f"{get_data(subject_data, 'Zip Code', '')}"
        ).strip(),
        'Property County': get_data(subject_data, 'County'),
        'Appraisal Type': determine_appraisal_type(file_path, appraisal_id_data),
        'Assigned to Vendor(s)': get_data(certification_data, 'Name'),
        'UAD XML Report': 'N/A (Not in PDF)',
    }

    return mapped_data

@login_required
def compare_html_pdf_upload_view(request):
    """Handles the GET request to display the upload form."""
    return render(request, 'compare_html_pdf_upload.html')

@login_required
async def compare_html_pdf_process_view(request):
    """Handles the POST request to process and compare the files."""
    if request.method == 'POST' and request.FILES.get('pdf_file') and request.FILES.get('html_file'):
        pdf_file = request.FILES['pdf_file']
        html_file = request.FILES['html_file']
        fs = FileSystemStorage()

        # Save files
        pdf_filename = await sync_to_async(fs.save)(pdf_file.name, pdf_file)
        html_filename = await sync_to_async(fs.save)(html_file.name, html_file)
        pdf_path = await sync_to_async(fs.path)(pdf_filename)
        html_path = await sync_to_async(fs.path)(html_filename)

        # Extract data using the new helper functions
        html_data = _extract_from_html_file(html_path)
        pdf_data = await _extract_from_pdf_file(pdf_path)

        # Compare the extracted data
        comparison_results = compare_data_sets(html_data, pdf_data)

        context = {
            'pdf_filename': pdf_filename,
            'html_filename': html_filename,
            'results': comparison_results,
            'html_data': html_data,
            'pdf_data': pdf_data,
        }
        return await sync_to_async(render)(request, 'compare_html_pdf_results.html', context)

    # Redirect to the upload page if it's not a POST request
    return await sync_to_async(redirect)('compare_html_pdf_upload')

@login_required
def escalation_check_upload_view(request):
    """Handles the GET request to display the escalation check upload form."""
    return render(request, 'escalation_check_upload.html')

@login_required
async def escalation_check_process_view(request):
    """Handles the POST request to process a PDF for escalation checks."""
    if request.method == 'POST' and request.FILES.get('pdf_file') and request.FILES.get('html_file'):
        pdf_file = request.FILES['pdf_file']
        html_file = request.FILES['html_file']
        purchase_copy_file = request.FILES.get('purchase_copy_file')
        engagement_letter_file = request.FILES.get('engagement_letter_file')
        fs = FileSystemStorage()

        pdf_filename = await sync_to_async(fs.save)(pdf_file.name, pdf_file)
        html_filename = await sync_to_async(fs.save)(html_file.name, html_file)

        pdf_path = await sync_to_async(fs.path)(pdf_filename)
        html_path = await sync_to_async(fs.path)(html_filename)

        # Extract data from the HTML order form.
        order_form_data = await sync_to_async(_extract_from_html_file)(html_path)

        # --- New: Extract structured data from PDF for comparison ---
        pdf_data_for_comparison = await _extract_from_pdf_file(pdf_path)

        # --- New: Compare HTML data against PDF data ---
        order_form_comparison_results = compare_data_sets(order_form_data, pdf_data_for_comparison)

        # --- New Structured Data Extraction ---
        all_data_for_prompt = {
            "order_form_data": order_form_data,
            "appraisal_report_data": {},
            "purchase_contract_data": {},
            "engagement_letter_data": {}
        }

        # Extract from main appraisal PDF
        # We can run these concurrently for better performance
        tasks = [
            extract_fields_from_pdf(pdf_path, 'subject'),
            extract_fields_from_pdf(pdf_path, 'improvements'),
            extract_fields_from_pdf(pdf_path, 'reconciliation'),
            extract_fields_from_pdf(pdf_path, 'certification'),
            extract_fields_from_pdf(pdf_path, 'appraisal_id'),
            extract_fields_from_pdf(pdf_path, 'site'),
            extract_fields_from_pdf(pdf_path, 'neighborhood'),
            extract_fields_from_pdf(pdf_path, 'contract'),
            extract_fields_from_pdf(pdf_path, 'sale_history'),
        ]
        results = await asyncio.gather(*tasks)
        all_data_for_prompt["appraisal_report_data"] = {
            'subject': results[0], 'improvements': results[1], 'reconciliation': results[2],
            'certification': results[3], 'appraisal_id': results[4], 'site': results[5],
            'neighborhood': results[6], 'contract': results[7], 'sale_history': results[8]
        }

        # Process optional files and extract structured data from them
        if purchase_copy_file:
            purchase_filename = await sync_to_async(fs.save)(purchase_copy_file.name, purchase_copy_file)
            purchase_path = await sync_to_async(fs.path)(purchase_filename)
            # Extract key fields from the purchase contract
            all_data_for_prompt['purchase_contract_data'] = await extract_fields_from_pdf(purchase_path, 'contract')

        if engagement_letter_file:
            engagement_filename = await sync_to_async(fs.save)(engagement_letter_file.name, engagement_letter_file)
            engagement_path = await sync_to_async(fs.path)(engagement_filename)
            # A simple text extraction might be enough for an engagement letter to find the fee
            # Or you could create a new 'engagement_letter' section in services.py
            # For now, we'll pass it to a generic extraction.
            all_data_for_prompt['engagement_letter_data'] = await extract_fields_from_pdf(engagement_path, 'addendum') # Re-using addendum for generic text

        # --- End of New Structured Data Extraction ---

        extracted_data = await extract_fields_from_pdf(pdf_path, 'escalation_check', custom_prompt=json.dumps(all_data_for_prompt))

        context = {
            'pdf_filename': pdf_filename,
            'html_filename': html_filename,
            'purchase_filename': purchase_copy_file.name if purchase_copy_file else None,
            'engagement_filename': engagement_letter_file.name if engagement_letter_file else None,
            'results': extracted_data,
            'order_form_comparison_results': order_form_comparison_results, # Add comparison results to context
        }
        return await sync_to_async(render)(request, 'escalation_check_results.html', context)

    # Redirect to the upload page if it's not a POST request
    return await sync_to_async(redirect)('escalation_check_upload')

# The new view to handle extraction for a specific section
@login_required
async def extract_section(request, filename, section_name):
    fs = FileSystemStorage()
    uploaded_file_path = await sync_to_async(fs.path)(filename)

    if not await sync_to_async(fs.exists)(uploaded_file_path):
        return await sync_to_async(render)(request, 'error.html', {'error_message': 'The requested file could not be found. Please upload it again.'})

    # Get custom prompt from POST data if it exists
    custom_prompt = request.POST.get('custom_prompt', None)

    # Handle the initial GET request for the custom analysis page
    if section_name == 'custom_analysis' and request.method == 'GET':
        # Check for FHA case flag from query parameter
        is_fha_case = request.GET.get('fha', 'false') == 'true'
        
        # Define the default prompt for FHA cases
        fha_default_prompt = ""
        if is_fha_case:
            fha_default_prompt = """This is an FHA case. Please verify that all FHA-specific guidelines are met,
1.	FHA case# should be on all pages of the report.
2.	Comment stating that FHA is an additional intended user of the report.
3.	Comment stating whether subject meets the 4000.1 handbook guidelines or not.
4.	Please comment if attic/crawl space was inspected.
5.	Hey guys, if there is a photo of the basement, attic or crawl space in the report, then do not send a request to comment if they inspected.
6.	All amenities (patio, deck or porch) should be included on sketch.
7.	If the subject has well and septic, the appraiser must comment on if the distances meet guidelines. If there is no comment, then a revision must be included to address if well and septic distances meet HUD guidelines.
8.	Storage, barn, outbuilding interior photos
9.	Remaining economic life is not mandatory."""

        sections_for_template = {key: key.replace('_', ' ').title() for key in FIELD_SECTIONS.keys()}
        context = {'data': {}, 'section_title': 'Custom Document Analysis', 'filename': filename, 'section_key': section_name, 'sections': sections_for_template, 'custom_prompt': fha_default_prompt}

        return await sync_to_async(render)(request, 'result.html', context)

    try:
        # Call the async extraction function with the specific section name
        extracted_data = await extract_fields_from_pdf(uploaded_file_path, section_name, custom_prompt=custom_prompt)

        # --- Backend Validation for Neighborhood Description ---
        if section_name == 'neighborhood' and 'error' not in extracted_data:
            # Fetch subject data to determine FHA or Conventional case
            subject_data = await extract_fields_from_pdf(uploaded_file_path, 'subject')
            is_fha_case = False
            if 'error' not in subject_data and subject_data:
                fha_value = subject_data.get('FHA')
                # A non-empty, non-placeholder FHA Case Number indicates an FHA case
                if fha_value and fha_value not in ['N/A', 'null', '--', '']:
                    is_fha_case = True

            # Get the neighborhood description text
            description = extracted_data.get("Neighborhood Description", "").lower()

            # List of forbidden words for conventional loans
            forbidden_words = [
                "good", "average", "easy", "convenient", "conveniently", 
                "low income", "desirable", "gentrified", "gentrification", 
                "regentrified", "regentrification"
            ]

            # Find which forbidden words are in the description
            found_words = [word for word in forbidden_words if word in description]

            if found_words:
                if is_fha_case:
                    extracted_data['backend_validation'] = {'status': 'success', 'message': f"FHA Case: The description contains sensitive words ('{', '.join(found_words)}'), which is acceptable for FHA."}
                else: # Conventional Case
                    extracted_data['backend_validation'] = {'status': 'error', 'message': f"Conventional Case: The description contains forbidden words ('{', '.join(found_words)}'). This is not acceptable."}
        # --- End of Backend Validation ---

        # --- Backend Validation for Sale History ---
        if section_name == 'sale_history' and 'error' not in extracted_data:
            validations = []
            
            def is_empty(val):
                return val is None or val in ['--', 'null', '']

            # Rule 1: Check required fields in Research and Analysis
            required_fields = [
                "I ____ research the sale or transfer history of the subject property and comparable sales.(did/did not)",
                "My research _____ reveal any prior sales or transfers of the subject property for the three years prior to the effective date of this appraisal.(did/did not)",
                "Data Source(s) for subject property research",
                "My research ______ reveal any prior sales or transfers of the comparable sales for the year prior to the date of sale of the comparable sale.(did/did not)",
                "Data Source(s_for_comparable_sales_research)", # Adjusted key from services.py
                "Analysis of prior sale or transfer history of the subject property and comparable sales",
            ]
            missing_fields = [field for field in required_fields if is_empty(extracted_data.get(field))]
            if missing_fields:
                validations.append({'status': 'error', 'message': f"The following required fields are empty: {', '.join(missing_fields)}."})
            else:
                validations.append({'status': 'success', 'message': "All required 'Research and Analysis' fields are filled."})

            # Rule 2: "I ____ research..." must be "did"
            research_performed = extracted_data.get("I ____ research the sale or transfer history of the subject property and comparable sales.(did/did not)")
            if research_performed and str(research_performed).lower() != 'did':
                validations.append({'status': 'error', 'message': f"'I ____ research...' must be 'did', but it is '{research_performed}'."})
            elif research_performed:
                 validations.append({'status': 'success', 'message': "Research was performed ('did')."})

            # Rule 3: Conditional validation for Subject prior sale
            subject_history_found = extracted_data.get("My research _____ reveal any prior sales or transfers of the subject property for the three years prior to the effective date of this appraisal.(did/did not)")
            if subject_history_found and str(subject_history_found).lower() == 'did':
                subject_data = extracted_data.get('subject', {})
                if is_empty(subject_data.get('Date of Prior Sale/Transfer')) or is_empty(subject_data.get('Price of Prior Sale/Transfer')):
                    validations.append({'status': 'error', 'message': "Report indicates a prior sale for the Subject, but 'Date' or 'Price' is missing in the grid."})
                else:
                    validations.append({'status': 'success', 'message': "Subject prior sale details are present as required."})

            # Rule 4: Conditional validation for Comparables' prior sales
            comp_history_found = extracted_data.get("My research ______ reveal any prior sales or transfers of the comparable sales for the year prior to the date of sale of the comparable sale.(did/did not)")
            if comp_history_found and str(comp_history_found).lower() == 'did':
                comparables_data = extracted_data.get('comparables', [])
                at_least_one_comp_has_data = False
                if comparables_data:
                    for comp in comparables_data:
                        if not is_empty(comp.get('Date of Prior Sale/Transfer')) and not is_empty(comp.get('Price of Prior Sale/Transfer')):
                            at_least_one_comp_has_data = True
                            break
                
                if not at_least_one_comp_has_data:
                    validations.append({'status': 'error', 'message': "Report indicates prior sales for Comparables, but no comparable has both 'Date' and 'Price' filled in the grid."})
                else:
                    validations.append({'status': 'success', 'message': "At least one comparable has prior sale details as required."})

            if validations:
                extracted_data['backend_validation_list'] = validations
        # --- End of Sale History Validation ---
        
        # --- FHA Case Detection for Subject Section ---
        is_fha_case = False
        is_rental_form = False
        if section_name == 'subject' and 'error' not in extracted_data:
            subject_data = await extract_fields_from_pdf(uploaded_file_path, 'subject')
            is_fha_case = False
            if 'error' not in subject_data and subject_data:
                fha_value = subject_data.get('FHA')
                # A non-empty, non-placeholder FHA Case Number indicates an FHA case
                if fha_value and fha_value not in ['N/A', 'null', '--', '']:
                    is_fha_case = True
            
            # --- Rental Form (1007) Detection ---
            appraisal_id_data = await extract_fields_from_pdf(uploaded_file_path, 'appraisal_id')
            if appraisal_id_data and 'error' not in appraisal_id_data:
                report_type = (appraisal_id_data.get('This Report is one of the following types:') or '').lower()
                if '1007' in report_type or 'rent schedule' in report_type or 'rental' in report_type:
                    is_rental_form = True

        # Create display names for the sidebar sections
        sections_for_template = {
            key: key.replace('_', ' ').title() 
            for key in FIELD_SECTIONS.keys() if key not in ['uniform_report', 'addendum', 'appraisal_id', 'additional_comments']
        }

        # Flag to show the revision helper for the subject section
        show_revision_helper = section_name.lower() in ['subject', 'contract', 'neighborhood', 'site', 'improvements', 'sales_grid', 'sale_history', 'reconciliation', 'cost_approach', 'rental_grid']

        # Pass the dictionary to the result template
        context = {
            'data': extracted_data,
            'section_title': section_name.replace('_', ' ').title(),
            'filename': filename,
            'section_key': section_name,
            'sections': sections_for_template,
            'custom_prompt': custom_prompt,
            'is_fha_case': is_fha_case,
            'is_rental_form': is_rental_form,
            'show_revision_helper': show_revision_helper,
        }
        return await sync_to_async(render)(request, 'result.html', context)
    except Exception as e:
        return await sync_to_async(render)(request, 'error.html', {'error_message': str(e)})

@login_required
@csrf_exempt
def generate_report(request):
    """
    Receives review session data via POST, logs it, and returns a JSON response.
    This is an API-like view that is called from the client-side script.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Use the authenticated user from the request, not from the client payload.
            report_line = (
                f"User: {request.user.username}, File: {data.get('filename')}, "
                f"Start: {data.get('startTime')}, End: {data.get('endTime')}\n"
            )
            
            # Append the report to a log file.
            # Consider defining this path in settings.py for better management.
            with open("review_report.log", "a") as report_file:
                report_file.write(report_line)
            
            return JsonResponse({'status': 'success', 'message': 'Report generated.'}, status=200)

        except (json.JSONDecodeError, KeyError):
            return JsonResponse({'status': 'error', 'message': 'Invalid data provided.'}, status=400)
        except IOError:
            # Log this server-side error for debugging.
            return JsonResponse({'status': 'error', 'message': 'Could not write to report file.'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
async def get_section_data_api(request, filename, section_name):
    """
    An API endpoint that extracts data for a specific section from a PDF 
    and returns it as JSON.
    """
    fs = FileSystemStorage()
    if not await sync_to_async(fs.exists)(filename):
        return JsonResponse({'error': 'File not found.'}, status=404)

    file_path = await sync_to_async(fs.path)(filename)

    try:
        extracted_data = await extract_fields_from_pdf(file_path, section_name)
        return JsonResponse(extracted_data)
    except Exception as e:
        return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)