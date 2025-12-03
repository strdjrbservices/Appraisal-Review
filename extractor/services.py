from google import genai
import json
from django.conf import settings
import logging # Import logging module
from google.api_core import exceptions as google_exceptions
import os
import asyncio

BASE_FIELD = [
    "APPRAISAL FORM TYPE (1004/1025/1004D/1073)",
    "Additional Form (1007/216/Rental/STR)",
    "ANSI Standard Confirmation",
    "Reasonable Exposure Time Comment",
    "Prior Service Certification"
]

# SUBJECT
SUBJECT_FIELDS = [
    'FHA','Property Address', 'City', 'County', 'State', 'Zip Code', 'Borrower', 'Owner of Public Record',
    'Legal Description', "Assessor's Parcel #", 'Tax Year', 'R.E. Taxes $', 'Neighborhood Name', 'Map Reference',
    'Census Tract', 'Occupant', 'Special Assessments $', 'PUD', 'HOA $', 'HOA(per year/per month)',
    'Property Rights Appraised', 'Assignment Type', 'Lender/Client', 'Address (Lender/Client)',
    'Offered for Sale in Last 12 Months', 'Report data source(s) used, offering price(s), and date(s)',
]

# CONTRACT
CONTRACT_FIELDS = [
    'I _____ analyze the contract for sale for the subject purchase transaction.', 
    'Explain the results of the analysis of the contract for sale or why the analysis was not performed.',
    'Contract Price $', 'Date of Contract', 'Is the property seller the owner of public record?(Yes/No)', 'Data Source(s)',
    'Is there any financial assistance (loan charges, sale concessions, gift or downpay i etc.) to be paid by any party on behalf of the borrower?(Yes/No)',
    'If Yes, report the total dollar amount and describe the items to be paid.',
]

# NEIGHBORHOOD
NEIGHBORHOOD_FIELDS = [
    "Location", "Built-Up", "Growth", "Property Values", "Demand/Supply",
    "Marketing Time", "One-Unit", "2-4 Unit", "Multi-Family", "Commercial", "Other", "Present Land Use Other Description", "one unit housing price(high,low,pred)", "one unit housing age(high,low,pred)",
    "Neighborhood Boundaries", "Neighborhood Description", "Market Conditions:",
]

# SITE
SITE_FIELDS = [
    "Dimensions", "Area", "Shape", "View", "Specific Zoning Classification", "Zoning Description",
    "Zoning Compliance", "Zoning Compliance Comment", "Is the highest and best use of subject property as improved (or as proposed per plans and specifications) the present use?",
    "Electricity", "Gas", "Water", "Sanitary Sewer", "Street", "Alley", "FEMA Special Flood Hazard Area",
    "FEMA Flood Zone", "FEMA Map #", "FEMA Map Date", "Are the utilities and off-site improvements typical for the market area?",
    "Are there any adverse site conditions or external factors (easements, encroachments, environmental conditions, land uses, etc.)(Yes/No)?",
    "If Yes, describe",
]

# IMPROVEMENTS
IMPROVEMENTS_FIELDS = [
    "Units", "# of Stories", "Type", "One with Accessory Unit (ADU)", "Existing/Proposed/Under Const.",
    "Design (Style)", "Year Built", "Effective Age (Yrs)", "Foundation Type",
    "Basement Area sq.ft.", "Basement Finish",
    "Evidence of", "Foundation Walls (Material/Condition)",
    "Exterior Walls (Material/Condition)", "Roof Surface (Material/Condition)",
    "Gutters & Downspouts (Material/Condition)", "Window Type (Material/Condition)",
    "Storm Sash/Insulated", "Screens", "Floors (Material/Condition)", "Walls (Material/Condition)",
    "Trim/Finish (Material/Condition)", "Bath Floor (Material/Condition)", "Bath Wainscot (Material/Condition)",
    "Attic", "Heating Type", "Fuel", "Cooling Type",
    "Fireplace(s) #", "Patio/Deck", "Pool", "Woodstove(s) #", "Fence", "Porch", "Other Amenities",
    "Car Storage", "Driveway # of Cars", "Driveway Surface", "Garage # of Cars", "Carport # of Cars",
    "Garage (Att./Det./Built-in)", "Appliances (Refrigerator,Range/Oven, Dishwasher, Disposal, Microwave, Washer/Dryer, Other (describe))",
    "Finished area above grade Rooms", "Finished area above grade Bedrooms",
    "Finished area above grade Bath(s)", "Square Feet of Gross Living Area Above Grade",
    "Additional features", "Describe the condition of the property",
    "Are there any physical deficiencies or adverse conditions that affect the livability, soundness, or structural integrity of the property?", "If Yes, describe",
    "Does the property generally conform to the neighborhood (functional utility, style, condition, use, construction, etc.)?", "If No, describe",
]

# This list defines the fields for a single property in the sales comparison grid (both subject and comparables).
# The prompt will instruct the AI to use this for the subject and for each comparable found.
SALES_COMPARISON_APPROACH_FIELDS = [
    "Address", 
    "Proximity to Subject", 
    "Sale Price", 
    "Sale Price/Gross Liv. Area",
    "Data Source(s)", 
    "Verification Source(s)",
    "Sale or Financing Concessions", "Sale or Financing Concessions Adjustment",
    "Date of Sale/Time", "Date of Sale/Time Adjustment",
    "Location", "Location Adjustment",
    "Leasehold/Fee Simple", "Leasehold/Fee Simple Adjustment",
    "Site", "Site Adjustment",
    "View", "View Adjustment",
    "Design (Style)", "Design (Style) Adjustment",
    "Quality of Construction", "Quality of Construction Adjustment",
    "Actual Age", "Actual Age Adjustment",
    "Condition", "Condition Adjustment",
    "Total Rooms", "Bedrooms", "Baths",
    "Gross Living Area", "Gross Living Area Adjustment",
    "Basement & Finished Rooms Below Grade", "Basement & Finished Rooms Below Grade Adjustment",
    "Functional Utility", "Functional Utility Adjustment",
    "Heating/Cooling", "Heating/Cooling Adjustment",
    "Energy Efficient Items", "Energy Efficient Items Adjustment",
    "Garage/Carport", "Garage/Carport Adjustment",
    "Porch/Patio/Deck", "Porch/Patio/Deck Adjustment",
    "Net Adjustment (Total)", "Adjusted Sale Price of Comparable",
]

SALES_COMPARISON_APPROACH_FIELDS_ADJUSTMENT = [
    "Address", 
    "Proximity to Subject", 
    "Sale Price", 
    "Sale Price/Gross Liv. Area",
    "Data Source(s)", 
    "Verification Source(s)",
    "Sale or Financing Concessions Adjustment",
    "Date of Sale/Time Adjustment",
    "Location Adjustment",
    "Leasehold/Fee Simple Adjustment",
    "Site Adjustment",
    "View Adjustment",
    "Design (Style) Adjustment",
    "Quality of Construction Adjustment",
    "Actual Age Adjustment",
    "Condition Adjustment",
    "Gross Living Area Adjustment",
    "Basement & Finished Rooms Below Grade Adjustment",
    "Functional Utility Adjustment",
    "Heating/Cooling Adjustment",
    "Energy Efficient Items Adjustment",
    "Garage/Carport Adjustment",
    "Porch/Patio/Deck Adjustment",
    "Net Adjustment (Total)", 
    "Adjusted Sale Price of Comparable",
]

# RENTAL GRID
RENTAL_GRID_FIELDS = [
    "Address",
    "Proximity to Subject",
    "Date Lease Begins",
    "Date Lease Expires",
    "Monthly Rental",
    "Less: Utilities, Furniture",
    "Adjusted Monthly Rent",
    "Data Source",
    "RENT ADJUSTMENTS",
    "Rent Concessions",
    "Location/View",
    "Design and Appeal",
    "Age/Condition",
    "Total room count",
    "Bdrms count",
    "Baths count",
    "Gross Living Area",
    "Other (e.g., basement, etc.)",
    "Other:",
    "Net Adj. (total)",
]

# SALE HISTORY (MERGED)
SALE_HISTORY_FIELDS = [
    # From former Sales Transfer section
    "I ____ research the sale or transfer history of the subject property and comparable sales.(did/did not)",
    "If not, explain",
    "My research _____ reveal any prior sales or transfers of the subject property for the three years prior to the effective date of this appraisal.(did/did not)",
    "Data Source(s) for subject property research",
    "My research ______ reveal any prior sales or transfers of the comparable sales for the year prior to the date of sale of the comparable sale.(did/did not)",
    "Data Source(s) for comparable sales research",
    # From both sections
    "Analysis of prior sale or transfer history of the subject property and comparable sales",
    # From former Sale History grid
    "Date of Prior Sale/Transfer",
    "Price of Prior Sale/Transfer",
    "Data Source(s)",
    "Effective Date of Data Source(s)",
]

# RECONCILIATION
RECONCILIATION_FIELDS = [
    "Indicated Value by: Sales Comparison Approach $", 
    "Cost Approach (if developed) $", "Income Approach (if developed) $",
    "This appraisal is made ('as is', 'subject to completion per plans and specifications on the basis of a hypothetical condition that the improvements have been completed', 'subject to the following repairs or alterations on the basis of a hypothetical condition that the repairs or alterations have been completed', or 'subject to the following required inspection based on the extraordinary assumption that the condition or deficiency does not require alteration or repair:')",
    "Opinion of Market Value $",
    "Effective Date of Value"
]

# COST APPROACH
COST_APPROACH_FIELDS = [
    # Header/Support Fields
    "Support for the opinion of site value (summary of comparable land sales or other methods for estimating site value)",
    "ESTIMATED (REPRODUCTION / REPLACEMENT COST NEW)",
    "Source of cost data",
    "Quality rating from cost service",
    "Effective date of cost data",
    # Cost Calculation Fields
    "Opinion of Site Value",
    "Dwelling",
    "Garage/Carport",
    "Total Estimate of Cost-New",
    "Depreciation",
    "Depreciated Cost of Improvements",
    "As-is Value of Site Improvements",
    "Indicated Value By Cost Approach",
    # Comments and Other Fields
    "Comments on Cost Approach (gross living area calculations, depreciation, etc.)",
    "Estimated Remaining Economic Life (HUD and VA only)",
]

# MERGED REPORT DETAILS
REPORT_DETAILS_FIELDS = [
    # From UNIFORM_REPORT_FIELDS
    "SCOPE OF WORK:",
    "INTENDED USE:",
    "INTENDED USER:",
    "DEFINITION OF MARKET VALUE:",
    "STATEMENT OF ASSUMPTIONS AND LIMITING CONDITIONS:",
    # From ADDENDUM_FIELDS
    "SUPPLEMENTAL ADDENDUM",
    "E&O Insurance Expiration Date",
    "ADDITIONAL COMMENTS",
    "APPRAISER'S CERTIFICATION:",
    "SUPERVISORY APPRAISER'S CERTIFICATION:",
    "Analysis/Comments",
    "GENERAL INFORMATION ON ANY REQUIRED REPAIRS",
    "UNIFORM APPRAISAL DATASET (UAD) DEFINITIONS ADDENDUM",
    # From APPRAISAL_ID_FIELDS
    "This Report is one of the following types:",
    "Comments on Standards Rule 2-3",
    "Reasonable Exposure Time",
    "Comments on Appraisal and Report Identification",
]

#IMAGE
IMAGE_FIELDS =[

    "include bedroom, bed, bathroom, bath, half bath, kitchen, lobby, foyer, living room count with label and photo,please explan and match the floor plan with photo and improvement section, GLA",
    "please match comparable address in sales comparison approach and comparable photos, please make sure comp phto are not same, also find front, rear, street photo and make sure it is not same, capture any additionbal photo for adu according to check mark",
    "please match comparable address in sales comparison approach and comparable photos, please make sure comp phto are not same, also find front, rear, street photo and make sure it is not same, capture any additionbal photo for adu according to check mark, please match the same in location map, areial map should have subject address, please check signature section details of appraiser in appraiser license copy for accuracy"

]

INCOME_APPROACH_FIELDS = [
    "Estimated Monthly Market Rent $",
    "X Gross Rent Multiplier = $",
    "Indicated Value by Income Approach"
]

# PUD INFORMATION
PUD_INFO_FIELDS = [
    "Is the developer/builder in control of the Homeowners' Association (HOA)?", "Unit type(s)",
    "Provide the following information for PUDs ONLY if the developer/builder is in control of the HOA and the subject property is an attached dwelling unit.",
    "Legal Name of Project", "Total number of phases", "Total number of units", "Total number of units sold",
    "Total number of units rented", "Total number of units for sale", "Data source(s)", "Was the project created by the conversion of existing building(s) into a PUD?", " If Yes, date of conversion", "Does the project contain any multi-dwelling units? Yes No Data", "Are the units, common elements, and recreation facilities complete?", "If No, describe the status of completion.", "Are the common elements leased to or by the Homeowners' Association?",
    "If Yes, describe the rental terms and options.", "Describe common elements and recreational facilities."
]

# CERTIFICATION
CERTIFICATION_FIELDS = [
    "Signature", "Name", "Company Name", "Company Address", "Telephone Number", "Email Address", "Date of Signature and Report",
    "Effective Date of Appraisal", "State Certification # or State License # or Other (describe)", "State # or State",
    "Expiration Date of Certification or License", "ADDRESS OF PROPERTY APPRAISED", "APPRAISED VALUE OF SUBJECT PROPERTY $",
    "LENDER/CLIENT Name",
    "Lender/Client Company Name",
    "Lender/Client Company Address",
    "Lender/Client Email Address",
    "Appraiser Name on License",
    "License Number on License",
    "License State on License",
    "License Expiration Date on License",
    "E&O Expiration Date on Document",
]

# APPRAISAL ID
APPRAISAL_ID_FIELDS = [
    "This Report is one of the following types:",
    "Comments on Standards Rule 2-3",
    "Reasonable Exposure Time",
    "Comments on Appraisal and Report Identification",
]

# MARKET CONDITIONS
MARKET_CONDITIONS_FIELDS = [
    # Inventory Analysis Grid
    "Inventory Analysis Total # of Comparable Sales (Settled)",
    "Inventory Analysis Absorption Rate (Total Sales/Months)",
    "Inventory Analysis Total # of Comparable Active Listings",
    "Inventory Analysis Months of Housing Supply (Total Listings/Ab.Rate)",
    # Median Sale & List Price Grid
    "Median Sale & List Price, DOM, Sale/List % Median Comparable Sale Price",
    "Median Sale & List Price, DOM, Sale/List % Median Comparable Sales Days on Market",
    "Median Sale & List Price, DOM, Sale/List % Median Comparable List Price",
    "Median Sale & List Price, DOM, Sale/List % Median Comparable Listings Days on Market",
    "Median Sale & List Price, DOM, Sale/List % Median Sale Price as % of List Price",
    # Additional Market Fields
    "Seller-(developer, builder, etc.) paid financial assistance prevalent?",
    "Explain in detail the seller concessions trends for the past 12 months (e.g., seller contributions increased from 3% to 5%, increasing use of buydowns, closing costs, condo fees, options, etc.).",
    "Are foreclosure sales (REO sales) a factor in the market?", "If yes, explain (including the trends in listings and sales of foreclosed properties).",
    "Cite data sources for above information.",
    "Summarize the above information as support for your conclusions in the Neighborhood section of the appraisal report form. If you used any additional information, such as an analysis of pending sales and/or expired and withdrawn listings, to formulate your conclusions, provide both an explanation and support for your conclusions."
]

# CONDO
CONDO_FIELDS = [
    # Subject Project Data Grid
    "Subject Project Data Total # of Comparable Sales (Settled)",
    "Subject Project Data Absorption Rate (Total Sales/Months)",
    "Subject Project Data Total # of Comparable Active Listings",
    "Subject Project Data Months of Unit Supply (Total Listings/Ab.Rate)",
    # Additional Condo Fields
    "Are foreclosure sales (REO sales) a factor in the project?",
    "If yes, indicate the number of REO listings and explain the trends in listings and sales of foreclosed properties.",
    "Summarize the above trends and address the impact on the subject unit and project.",
]

# STATE REQUIREMENT
STATE_REQUIREMENT_FIELDS = [
    "Appraiser Fee Disclosure",
    "AMC License Disclosure",
    "AMC Fee Disclosure",
    "Smoke/CO Detector Requirements",
    "Water Heater Strapping",
    "State-Specific Legal Statements",
    "Invoice Copy Requirement",
]

# CLIENT/LENDER REQUIREMENTS (Combined for all clients)
CLIENT_LENDER_REQUIREMENTS_FIELDS = [
    # Visio
    "Report Condition (As Is)",
    "Repairs with 'As Is' Condition",
    "STR Comps for 1007 STR",
    "Occupancy for 1007 Orders",
    "Occupancy for 1025 Form",
    # Ice Lender Holdings LLC
    "Value vs. Listing/Contract Price (10% Rule)",
    "USPAP Compliance Addendum",
    "FIRREA Statement",
    "Required Photographs (Mechanicals, Kitchen, Roof)",
    "Kitchen Photo Refrigerator Check",
    "Comparable Distance Guideline (Urban)",
    "Comparable Distance Guideline (Suburban)",
    "Comparable Distance Guideline (Rural)",
    # Hometown Equity
    "Smoke/CO Detector Installation and Photos",
    # BPL Mortgage, LLC
    "Smoke/CO Detector Presence (BPL)",
    "Value vs. Listing/Contract Price (10% Rule - BPL)",
    "Increase in Value Since Prior Sale",
    "Cost to Cure for Repairs",
    "Cost Approach Completion",
    "Room Photo Requirement (2 per room)",
    "Bedroom Photo Labeling",
    "Comparable Distance Guideline (Urban/Suburban - BPL)",
    "Comparable Distance Guideline (Rural - BPL)",
    "Multi-Family Unit Count Consistency",
    "Heating System Functionality",
    "Quality and Condition Ratings (Q/C)",
    # Plaza Home Mortgage Inc
    "Invoice in Report (NY Only)",
    "Client Email Address Present",
    "SSR Score Check",
    # CIVIC
    "As-Is Value Order (2-Value Reports)",
    "Freddie Unacceptable Practices Review",
    # Temple View Capital Funding, LP
    "Report Completion Basis (Temple View)",
    "ARV Comps Gridded (Temple View)",
    "As-Is Comps and Value Comments (Temple View)",
    # LoanDepot.com
    "Reviewer Instructions (LoanDepot)",
    # The Loan Store
    "Reviewer Instructions (The Loan Store)",
    "Double Strapped Water Heater (UT Only)",
    # GFL Capital Mortgage
    "Value vs. Purchase Price (GFL)",
    # Cardinal Financial Company
    "1004MC Requirement (Cardinal)",
    # OCMBC
    "Smoke/CO Detector Comments (OCMBC)",
    "Water Heater Strapping Comments (OCMBC)",
    # Paramount Residential Mortgage Group
    "Reviewer Instructions (Paramount)",
    # Arc Home LLC
    "Short-Term Rental Regulations (Arc Home)",
    # CV3 Financial
    "Borrower Name Handling (CV3)",
    # Nationwide Mortgage Bankers, Inc.
    "Hurricane Damage Statement (FL)",
    "Hurricane Damage Statement (GA, NC, SC, TN, VA)",
    # Logan Finance Corporation
    "Smoke/CO Detector and Photos (Logan Finance)",

]
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # New American Funding, LLC
    "1004MC Requirement (NAF)",
    "Health and Safety Issues (NAF)",
    "Reviewer Instructions (NAF)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Haus Capital Corp
    "'Subject-To' Condition Advisory (Haus Capital)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Equity Wave Lending, Inc
    "Intended User Statement (Equity Wave)",
    "Intended Use Statement (Equity Wave)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Foundation Mortgage
    "STR 1007 Form Requirement (Foundation Mortgage)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Rain City Capital, LLC
    "Health and Safety Subject To (Rain City)",
    "2-Value Report Format (Rain City)",
    "Cost to Cure for Cosmetic Items (Rain City)",
    "1004MC Requirement (Rain City)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # East Coast Capital Corp
    "Cost Approach Requirement (East Coast Capital)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Malama Funding LLC (formerly Lend with Aloha)
    "Report Completion Basis (Malama Funding)",
    "ARV Comps Gridded (Malama Funding)",
    "As-Is Comps and Value Comments (Malama Funding)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # National Loan Funding LLC / Easy Street Capital, LLC
    "Prior Services Statement (National Loan/Easy Street)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Kind Lending LLC
    "ENV Requirement (Kind Lending)",
    "1004MC Requirement (Kind Lending)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Dart Bank
    "ENV Requirement (Dart Bank)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Futures Financial (for Richel Francis)
    "As-is with ARV Report Condition (Futures Financial)",
    "Desktop Report Condition (Futures Financial)",
])

# 1004D FORM
D1004_FIELDS = [
    "Property Address", "Unit #", "City", "State", "Zip Code",
    "Legal Description", "County",
    "Borrower",
    "Contract Price $", "Date of Contract",
    "Effective Date of Original Appraisal",
    "Property Rights Appraised",
    "Original Appraised Value $",
    "Original Appraiser", "Company Name",
    "Original Lender/Client", "Address",
    "SUMMARY APPRAISAL UPDATE REPORT (checkbox)",
    "HAS THE MARKET VALUE OF THE SUBJECT PROPERTY DECLINED SINCE THE EFFECTIVE DATE OF THE PRIOR APPRAISAL? (Yes/No)",
    "My opinion of the market value of the subject property as of the effective date of this appraisal update is",
    "CERTIFICATION OF COMPLETION (checkbox)",
    "HAVE THE IMPROVEMENTS BEEN COMPLETED IN ACCORDANCE WITH THE REQUIREMENTS AND CONDITIONS STATED IN THE ORIGINAL APPRAISAL REPORT? (Yes/No)",
    "If No, describe the impact on the opinion of market value",
    "Date of Inspection (for Certification of Completion)",
    "Date of Signature and Report",
]

CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Champions Funding LLC
    "E&O Insurance Attached (Champions)",
    "Value vs. Predominant Value (Champions)",
    "Smoke/CO Detector Check (Champions)",
    "Stove in Kitchen Photo (Champions)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Deephaven Mortgage LLC
    "1004MC Requirement (Deephaven)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Loanguys.com inc
    "QC Ratings Requirement (Loanguys)",
])
CLIENT_LENDER_REQUIREMENTS_FIELDS.extend([
    # Eastview Investment Partners
    "Desk Review Escalation (Eastview)",
    "Desk Review Form Type (Eastview)",
])

# ESCALATION CHECK
ESCALATION_CHECK_FIELDS = {
    "Order Form vs. Report Mismatches": [
        "Verify Assignment Type matches between Order Form and Report.",
        "Verify Appraisal Type matches between Order Form and Report.",
        "Verify Appraiser Name matches between Order Form and Report.",
        "Verify Lender/Client Name matches between Order Form and Report.",
        "Verify Appraiser Fee matches between Engagement Letter and Report/Invoice."
    ],
    "Critical Report Conditions": [
        "Check if 'Zoning Compliance' in the Site section is marked as 'Illegal'.",
        "Check if 'Highest and Best Use' in the Site section is marked as 'No'.",
        "Check if 'Physical Deficiencies' in the Improvements section is 'Yes' but the report is made 'As-Is' in Reconciliation.",
        "Check if photos or comments indicate multiple repairs are needed, but the report is made 'As-Is'."
    ],
    "Value and Price Analysis": [
        "Check if the final appraised value is more than 10% higher than the lowest unadjusted comparable sale price.",
        "Check if the final appraised value is higher than the subject's list price, purchase price, and most recent prior sale price.",
        "Check if the appraised value is significantly higher than the purchase price and if an explanation is provided.",
        "Check if there has been a significant increase in value since the subject's prior sale and if an explanation is provided."
    ],
    "Sales Grid and Adjustments": [
        "Check for any single adjustment in the sales grid that appears drastically large relative to the sale price.",
        "Check if the subject's 'Location' in the sales grid is marked as 'Commercial'.",
        "Check if any 'Date of Sale/Time' adjustments are present and if a detailed explanation based on market data is provided."
    ],
    "Property and Data Consistency": [
        "Check if the subject property's address is also used as a comparable or rental property.",
        "For a 1004 (Single Family) report, check if there is evidence of more than one kitchen and if its legality is discussed.",
        "Verify the report's 'Effective Date' matches the 'Inspection Date' from the order form or other records.",
        "Check if the appraiser listed on the order form signed as the 'Supervisory Appraiser' instead of the primary appraiser."
    ],
    "Loan and Form Type Compliance": [
        "If the order form specifies a USDA loan, verify the report is not completed on an FHA form (e.g., 1004 FHA).",
    ],
    "Prohibited Language": [
        "Search the 'Neighborhood Description' for the phrase 'average condition' in a non-FHA report."
    ]
}

# consistancy
consistancy = [
    "Property Address match with sales grid, subject photos address, location map, and aerial map",
    "All Comparables Address from sales grid match with photos address, location map",
    "Total Room count, bed count, bath count and GLA of improvement section match with sales grid, photos, and building sketch",
    
]

# CUSTOM ANALYSIS
CUSTOM_ANALYSIS_FIELDS = [
    "User-defined query" # This is a placeholder
]
# A dictionary to map section names to their corresponding field lists
FIELD_SECTIONS = {
    "base_info": BASE_FIELD,
    "subject": SUBJECT_FIELDS,
    "contract": CONTRACT_FIELDS,
    "neighborhood": NEIGHBORHOOD_FIELDS,
    "site": SITE_FIELDS,
    "improvements": IMPROVEMENTS_FIELDS,
    "sales_grid_adjustment": SALES_COMPARISON_APPROACH_FIELDS_ADJUSTMENT,
    "sales_grid": SALES_COMPARISON_APPROACH_FIELDS,
    "rental_grid": RENTAL_GRID_FIELDS,
    "sale_history": SALE_HISTORY_FIELDS,
    "reconciliation": RECONCILIATION_FIELDS,
    "cost_approach": COST_APPROACH_FIELDS,
    "income_approach": INCOME_APPROACH_FIELDS,
    "report_details": REPORT_DETAILS_FIELDS,
    "pud_info": PUD_INFO_FIELDS,
    "appraisal_id": APPRAISAL_ID_FIELDS,
    "certification": CERTIFICATION_FIELDS,
    "market_conditions": MARKET_CONDITIONS_FIELDS,
    "condo": CONDO_FIELDS,
    "state_requirement": STATE_REQUIREMENT_FIELDS,
    "client_lender_requirements": CLIENT_LENDER_REQUIREMENTS_FIELDS,
    "escalation_check": ESCALATION_CHECK_FIELDS,
    "d1004": D1004_FIELDS,
    "custom_analysis": CUSTOM_ANALYSIS_FIELDS,
}

logger = logging.getLogger(__name__)

async def extract_fields_from_pdf(pdf_paths, section_name: str, custom_prompt: str = None):
    # Configure the client with a longer timeout to handle large PDF processing.
    # Set a 5-minute (300 seconds) timeout.
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    # Ensure pdf_paths is a list
    if isinstance(pdf_paths, str):
        pdf_paths = [pdf_paths]

    # Get the correct field list based on the section name
    fields_to_extract = FIELD_SECTIONS.get(section_name.lower(), [])
    # Allow sections with complex prompts even if their field list is a placeholder or used differently
    if not fields_to_extract and section_name.lower() not in ['sales_grid', 'sale_history', 'improvements', 'custom_analysis', 'client_lender_requirements', 'report_details']:
        return {"error": f"Invalid section name provided: {section_name}"}

    prompt = ""
    if section_name.lower() == 'subject':
        prompt = f"""
        You are an expert at extracting information from the "Subject" section of a real estate appraisal report. # No change here, just for context
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object where the keys are the field names and the values are the extracted data.

        **Instructions:**
        1.  **Be Thorough:** Extract data for every field listed.
        2.  **Use Null for Missing Data:** If a field is not found, is not applicable, or has no value (e.g., '--', 'N/A', or blank), use `null` as its value. Do not invent data.
        3.  **Handle Complex Fields:**
            *   For fields "Occupant" if checkbox is marked/selected on 'Owner', 'Tenant', or 'Vacant',then extract 'Owner', 'Tenant', or 'Vacant'. 
            *   For fields "PUD" if checkbox is marked/selected, then the fields "HOA $" and "HOA(per year/per month)" must be extracted. If "PUD" checkbox is unmarked/unselected, these HOA-related fields should be `blank`.
            *   For fields "Assignment Type" if checkbox is marked/selected on 'Purchase Transaction', 'Refinance Transaction', or 'Other (describe)',then extract 'Purchase Transaction', 'Refinance Transaction', or 'Other (describe)'.
            *   For yes/no questions like "Is the subject property currently offered for sale or has it been offered for sale in the twelve months prior to the effective date of this appraisal?", extract the "Yes" or "No" answer. 
            *   The subsequent field "Report data source(s) used, offering price(s), and date(s)" should contain the corresponding explanation if the answer was "Yes". If the answer is "No", the explanation field should be `null`.
            *   For the "FHA" field, extract the FHA case number if it is present in the report. If no FHA number is found, the value must be `null`.
        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "Property Address": "123 Main St",
            "City": "Anytown",
            "County": "Sample County",
            "FHA": "123-4567890",
            "State": "CA",
            "Zip Code": "12345",
            "Borrower": "John Doe",
            "Assignment Type": "Purchase Transaction",
            "Offered for Sale in Last 12 Months": "No",
            "Report data source(s) used, offering price(s), and date(s)": null,
            "PUD": "Yes",
            "...": "..." 
        }}
        """
    elif section_name.lower() == 'base_info':
        prompt = f"""You are an expert at identifying the main form type and key certification statements from a real estate appraisal report.
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object where the keys are the field names and the values are the extracted data.

        **Instructions:**
        1.  **Be Thorough:** Extract data for every field listed.
        2.  **Use Null for Missing Data:** If a field is not found or its value cannot be determined, use `null` as its value.
        3.  **Specific Field Instructions:**
            *   **APPRAISAL FORM TYPE**: Identify the main form number (e.g., "1004", "1073", "1025", "1004D") from the report's title or headers.
            *   **Additional Form**: Identify any add-on forms mentioned, such as "1007", "216", "Rent Schedule", or "STR". If none are found, the value should be "None".
            *   **ANSI Standard Confirmation**: Look for a statement like "I did/did not measure..." and extract only "did" or "did not".
            *   **Reasonable Exposure Time Comment**: Find the comment for "Reasonable Exposure Time" and extract the full text.
            *   **Prior Service Certification**: Find the statement like "I have/have not performed services..." and extract only "have" or "have not".

        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "APPRAISAL FORM TYPE (1004/1025/1004D/1073)": "1004",
            "Additional Form (1007/216/Rental/STR)": "1007/Rental",
            "ANSI Standard Confirmation": "did",
            "Reasonable Exposure Time Comment": "The reasonable exposure time is estimated to be under 3 months.",
            "Prior Service Certification": "have not"
        }}
        """
    elif section_name.lower() == 'sale_history':
        prompt = f"""
        You are an expert at extracting information from appraisal reports, focusing on the "Sale or Transfer History" section.
        This section contains both general statements about research and a grid detailing prior sales for the subject and comparables.

        Your output must be a single, valid JSON object.

        The JSON object must contain the following top-level keys:
        1.  `"subject"`: A JSON object for the subject property's sale history grid data.
        2.  `"comparables"`: A JSON array of objects, one for each comparable property's sale history grid data.
        3.  All other fields from the "Fields to Extract" list below should be top-level keys in the JSON object.

        **Instructions:**
        1.  **Grid Data:** For the subject and each comparable, extract the prior sale details into the `subject` and `comparables` objects. If a property has multiple prior sales, extract the most recent one. Maintain the original sequence of comparables.
        2.  **General Statements:** Extract the text for the general research statements and analysis as top-level key-value pairs.
        3.  **Handle (did/did not):** For fields with "(did/did not)", extract only the selected word ("did" or "did not").
        4.  **Use Null for Missing Data:** If any field, grid cell, or value is not found, is blank, or is not applicable, use `null` as its value.

        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "I ____ research the sale or transfer history...": "did",
            "My research _____ reveal any prior sales or transfers of the subject property...": "did not",
            "subject": {{
                "Date of Prior Sale/Transfer": "01/15/2021",
                "Price of Prior Sale/Transfer": "$450,000",
                "Effective Date of Data Source(s)": "01/15/2021"
            }},
            "comparables": [
                {{ "Date of Prior Sale/Transfer": null, "Price of Prior Sale/Transfer": null, ... }}
            ],
            "Analysis of prior sale or transfer history of the subject property and comparable sales": "The subject property was not sold in the last three years. Comp 1 sold 11 months ago..."
        }}"""
    elif section_name.lower() == 'improvements':
        prompt = f"""
        You are an expert at extracting information from the "Improvements" section of an appraisal report.
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object where the keys are the field names and the values are the extracted data.

        **Instructions:**
        1.  **Be Thorough:** Extract data for every field listed.
        2.  **Use Null for Missing Data:** If a field is not found, is not applicable, or has no value (e.g., '--', 'N/A', or blank), use `null` as its value. Do not invent data.
        3.  **Handle Complex Fields:**
            *   For fields like "Appliances", list all items that are checked or mentioned (e.g., "Refrigerator, Range/Oven, Dishwasher").
            *   For fields with "(Material/Condition)", capture both aspects if available (e.g., "Brick/Good").
            *   For "Fuel", capture all listed types, especially combinations like "Gas/Electric".
            *   For yes/no questions, extract the "Yes" or "No" answer. The subsequent "If Yes, describe" or "If No, describe" fields should contain the corresponding explanation.
            *   For field like "Basement Finish", value 0 or more than 0 %
            *   **Distinguish "Units" from "Type":** The "Units" field should be the numerical count of total units (e.g., "1", "2"). The "Type" field describes the property configuration. If the "Type" is "One with Accessory Unit", the "Units" field should still be "1", as an ADU does not make it a 2-unit property in this context.
            *   **Accessory Unit (ADU):** The field "One with Accessory Unit (ADU)" is a checkbox. If it is checked, extract "Yes". If it is not checked, extract "No". This is separate from the "Type" field.
            *   **Car Storage Logic:**
                *   If "None" is selected for "Car Storage", all other car storage fields ('Driveway # of Cars', 'Garage # of Cars', 'Carport # of Cars', etc.) must be `null`.
                *   If "Garage" is selected, "Garage # of Cars" and "Garage (Att./Det./Built-in)" must have values.
                *   If "Driveway" is selected, "Driveway # of Cars" must have a value.
                *   If "Carport" is selected, "Carport # of Cars" must have a value.
                *   If a storage type is NOT selected, its corresponding fields should be `null`. For example, if "Garage" is not part of the "Car Storage" value, then "Garage # of Cars" should be `null`.
            *   **ADU Verification:** If "One with Accessory Unit (ADU)" is "Yes", this implies there should be evidence in the sales grid, photos, and building sketch. While you don't need to verify this, extracting the "Yes" value correctly is critical.
            
        **Fields to Extract:**
        In addition to the fields below, include a top-level key named `"adu_validation"` in your JSON output. This key should contain an object with the following structure:
        {{
            "status": "Passed", "Passed with Comments", or "Failed",
            "message": "A detailed explanation of the validation result."
        }}

        **ADU Validation Logic:**
        1.  Check if the "One with Accessory Unit" box is marked "Yes".
        2.  If "Yes", verify that the accessory unit has **both a kitchen (with a stove) and a bath** by checking photos and descriptions.
            *   **PASS:** If both are present, set `status` to "Passed" and `message` to "ADU box is checked and unit appears to qualify with a kitchen and bath."
            *   **FAIL:** If either a kitchen (with stove) or a bath is missing, set `status` to "Failed" and `message` to "ADU box is checked, but the unit appears to lack a full kitchen with a stove or a bath. Please verify."
        3.  If "Yes", check the building sketch for interior access between the main unit and the ADU.
            *   If there is **no interior access**, verify that the ADU is listed as a separate line item in the improvements section or sales grid. If it's not, set `status` to "Failed" and `message` to "ADU has no interior access and must be listed as a separate line item, but was not."
        4.  If the "One with Accessory Unit" box is **NOT** checked, but you find evidence of a second dwelling with a kitchen and bath, set `status` to "Failed" and `message` to "ADU box is unchecked, but evidence of a qualifying accessory unit was found. Please verify."
        5.  **Kitchenette Check:** Search the document for any room labeled "kitchenette".
            *   If a "kitchenette" is found and photos show it **contains a stove**, set `status` to "Failed" and `message` to "On page [page number], a room labeled as 'kitchenette' has a stove. Please advise."

        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "Units": "1",
            "Year Built": "1995",
            "Exterior Walls (Material/Condition)": "Vinyl Siding/Average",
            "Appliances (Refrigerator,Range/Oven, Dishwasher, Disposal, Microwave, Washer/Dryer, Other (describe))": "Refrigerator, Range/Oven, Dishwasher",
            "One with Accessory Unit (ADU)": "Yes",
            "Are there any physical deficiencies or adverse conditions that affect the livability, soundness, or structural integrity of the property?": "No",
            "If Yes, describe": null,
            "Does the property generally conform to the neighborhood (functional utility, style, condition, use, construction, etc.)?": "Yes",
            "If No, describe": null,
            "Square Feet of Gross Living Area Above Grade": "1850",
            "adu_validation": {{
                "status": "Failed",
                "message": "ADU box is checked, but the unit appears to lack a full kitchen with a stove. Please verify."
            }},
            "...": "..."
        }}
        """
    elif section_name.lower() == 'neighborhood':
        prompt = f"""
        You are an expert at extracting information from the "Neighborhood" section of a real estate appraisal report.
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object where the keys are the field names and the values are the extracted data.

        **Instructions:**
        1.  **Be Thorough:** Extract data for every field listed.
        2.  **Use Null for Missing Data:** If a field is not found, is not applicable, or has no value (e.g., '--', 'N/A', or blank), use `null` as its value.
        3.  **Conditional Extraction for "Other" Land Use:**
            *   First, find the percentage value for the "Other" field in the "Present Land Use" table.
            *   **If and only if this percentage is greater than 0%**, you must find the description for this "Other" category (e.g., "Vacant", "Garden", "Open Space") and extract it into the "Present Land Use Other Description" field.
            *   If the "Other" percentage is 0% or not present, the "Present Land Use Other Description" field must be `null`.

        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "Location": "Urban",
            "Property Values": "Stable",
            "One-Unit": "85%",
            "2-4 Unit": "5%",
            "Multi-Family": "5%",
            "Commercial": "0%",
            "Other": "5%",
            "Present Land Use Other Description": "Primarily vacant residential lots.",
            "Neighborhood Description": "The neighborhood is a well-established residential area...",
            "one unit housing price(high,low,pred)": "High: 350, Low: 50, Pred: 295",
            "one unit housing age(high,low,pred)": "High: 350, Low: 50, Pred: 295"
            "...": "..."
        }}
        """
    elif section_name.lower() == 'contract':
        prompt = f"""
        You are an expert at extracting information from the "Contract" section of a real estate appraisal report.
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object where the keys are the field names and the values are the extracted data.

        **Instructions:**
        1.  **Be Thorough:** Extract data for every field listed. 
        2.  **Use Null for Missing Data:** If a field is not found, is not applicable, or has no value (e.g., '--', 'N/A', or blank), use `null` as its value. Do not invent data.
        3.  **Handle Complex Fields:**
            *   For the field "I _____ analyze the contract for sale for the subject purchase transaction.", if the checkbox is marked/selected as "did" or "did not", extract only the selected word ("did" or "did not"). If neither checkbox is selected, the value must be `null`.
            *   For the separate field "Explain the results of the analysis of the contract for sale or why the analysis was not performed.", extract the full text explanation. If the analysis "did not" happen, this field should contain the reason why. If it "did" happen, it should contain the results.
            *   For yes/no questions like "Is the property seller the owner of public record?(Yes/No)" and "Is there any financial assistance (loan charges, sale concessions, gift or downpayment assistance, etc.) to be paid by any party on behalf of the borrower?(Yes/No)", if the checkbox is marked/selected as "Yes" or "No", extract only the selected word ("Yes" or "No"). If neither checkbox is selected, the value must be `null`.
 
        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "I _____ analyze the contract for sale for the subject purchase transaction.": "did",
            "Explain the results of the analysis of the contract for sale or why the analysis was not performed.": "The contract is dated 05/15/2024 for a price of $550,000. No concessions were noted.",
            "Contract Price $": "550,000",
            "Is there any financial assistance (loan charges, sale concessions, gift or downpay i etc.) to be paid by any party on behalf of the borrower?(Yes/No)": "No",
            "If Yes, report the total dollar amount and describe the items to be paid.": null,
            "...": "..."
        }}
        """
    elif section_name.lower() == 'site':
        prompt = f"""
        You are an expert at extracting information from the "Site" section of a real estate appraisal report.
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object where the keys are the field names and the values are the extracted data.

        **Instructions:**
        1.  **Be Thorough:** Extract data for every field listed.
        2.  **Use Null for Missing Data:** If a field is not found, is not applicable, or has no value (e.g., '--', 'N/A', or blank), use `null` as its value. Do not invent data.
        3.  **Handle Complex Fields:**
            *   For yes/no questions, extract the "Yes" or "No" answer.
            *   For the field "Are there any adverse site conditions...", if the answer is "Yes", you must extract the explanation into the "If Yes, describe" field. If the answer is "No", the "If Yes, describe" field should be `null`.
            *   For fields like "Zoning Compliance", extract the specific classification (e.g., "Legal", "Legal Nonconforming", "Illegal", "No Zoning").
            *   **Conditional Extraction for "Zoning Compliance Comment":** If the value for "Zoning Compliance" is "No Zoning" or "Legal Nonconforming", you must find and extract the accompanying comment, which often discusses rebuild rights, into the "Zoning Compliance Comment" field. If "Zoning Compliance" is any other value (like "Legal" or "Illegal"), the "Zoning Compliance Comment" field must be `null`.

            *   For the "Street" field, you must extract both its status (Public or Private) and its surface type (e.g., Asphalt, Concrete, Dirt). The final value should be in the format "Status/Type", for example, "Public/Asphalt".
            *   For utility fields ("Electricity", "Gas", "Water", "Sanitary Sewer"), if "Other" is selected, you must include the accompanying description (e.g., "Other - Solar", "Other - Septic"). If no description is provided with "Other", extract just "Other".

        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "Dimensions": "80x120",
            "Area": "9,600 Sq. Ft.",
            "Zoning Compliance": "Legal",
            "Zoning Compliance Comment": null,
            "Is the highest and best use of subject property as improved (or as proposed per plans and specifications) the present use?": "Yes",
            "FEMA Special Flood Hazard Area": "No",
            "FEMA Flood Zone": "X",
            "Are there any adverse site conditions or external factors (easements, encroachments, environmental conditions, land uses, etc.)?": "Yes",
            "If Yes, describe": "Minor utility easement noted along the rear property line. No adverse impact observed.",
            "Street": "Public/Asphalt",
            "...": "..."
        }}
        """
    elif section_name.lower() == 'sales_grid':
        prompt = f"""
        You are an expert at extracting information from appraisal reports, focusing on the Sales Comparison Approach grid.
        Analyze the provided PDF document to extract data for the Subject property, all Comparable properties, and the summary/history fields related to the sales comparison approach.
        
        Your output must be a single, valid JSON object with the following top-level keys:
        1.  `"subject"`: A JSON object for the subject property.
        2.  `"comparables"`: A JSON array of objects, one for each comparable property.
        3.  `"Indicated Value by Sales Comparison Approach"`: The final indicated value.

        **Instructions:**
        1.  **Extract All Comparables:** You must find and extract data for **all** comparable properties in the grid. Maintain their original sequence.
        2.  **Use Null for Missing Data:** If a field is not found, is blank, or has no value (e.g., '--', 'N/A'), use `null` as its value.
        3.  **Handle Adjustments Accurately:**
            *   For all fields ending in "Adjustment", extract the precise monetary value.
            *   Negative values are often shown in parentheses, like `($2,000)`. You must extract these with a negative sign, like `-$2,000`.
            *   Positive values may or may not have a `+` sign.
            *   If an adjustment is `$0` or blank, extract it as such.
        4.  **Handle Complex Text:** For fields like "Basement & Finished Rooms Below Grade", capture the entire text value (e.g., "1000sf / 500sf Rec Room").

        **Fields for Subject and each Comparable:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of a comparable's adjustment field:**
        "Condition Adjustment": "-$5,000"
        """
    elif section_name.lower() == 'rental_grid':
        prompt = f"""
        You are an expert at extracting information from appraisal reports, focusing on the Rental Comparison grid.
        Analyze the provided PDF document to extract data for the Subject property, all Comparable rental properties, and the summary fields at the bottom of the section.

        Your output must be a single, valid JSON object with the following top-level keys:
        1.  `"subject"`: A JSON object for the subject property's rental data.
        2.  `"comparables"`: A JSON array of objects, one for each comparable rental property.
        3.  `"Indicated Monthly Market Rent"`: The final indicated monthly market rent for the subject.
        4.  `"Comments on market data..."`: The full text of the comments on market data, including vacancy, trends, and support for adjustments.
        5.  `"Final Reconciliation of Market Rent:"`: The full text of the final reconciliation of market rent.

        **Instructions:**
        1.  **Extract All Comparables:** You must find and extract data for **all** comparable rental properties in the grid. Maintain their original sequence.
        2.  **Use Null for Missing Data:** If a field is not found, is blank, or has no value (e.g., '--', 'N/A'), use `null` as its value.
        3.  **Handle Adjustments:** For adjustment fields (like "Rent Concessions", "Location/View", etc.), extract the precise monetary value. Negative values are often in parentheses, like `($50)`; extract these with a negative sign, like `-$50`.

        **Fields for Subject and each Comparable:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "subject": {{ "Address": "123 Main St", "Monthly Rental": null, "Location/View": null, ... }},
            "comparables": [
                {{ "Address": "456 Oak Ave", "Monthly Rental": "$2,500", "Location/View": "-$50", ... }},
                {{ "Address": "789 Pine Ln", "Monthly Rental": "$2,400", "Location/View": "$0", ... }}
            ],
            "Indicated Monthly Market Rent": "$2,450",
            "Comments on market data...": "The rental market is stable with low vacancy rates (estimated at 3%). Rents have been increasing slightly over the past year. Adjustments are based on market data from the local MLS.",
            "Final Reconciliation of Market Rent:": "After considering all comparables and giving most weight to Comp 2 due to its similarity, the market rent is reconciled to $2,450 per month."
        }}
        """

    elif section_name.lower() == 'sales_grid_adjustment':
        prompt = f"""
        You are an expert AI assistant specializing in real estate appraisal review. Your task is to analyze the Sales Comparison Approach grid for adjustment consistency.
        Analyze the provided PDF document to extract data for the Subject property and all Comparable properties, and then provide a summary of adjustment consistency.

        Your output must be a single, valid JSON object with the following top-level keys:
        1.  `"subject"`: A JSON object for the subject property's data from the grid.
        2.  `"comparables"`: A JSON array of objects, one for each comparable property.
        3.  `"adjustment_analysis"`: A JSON object containing your analysis of the adjustments. This object should have two keys:
            *   `"summary"`: A high-level summary of your findings (e.g., "Adjustments appear consistent," or "Inconsistencies found in Condition and GLA adjustments.").
            *   `"details"`: An array of strings, where each string is a detailed explanation of a specific finding (consistent or inconsistent).

        **Instructions:**
        1.  **Extract Data:** For the subject and each comparable, extract all fields listed below. If a field is blank, empty, or not applicable (e.g., '--'), use `null` as its value. Pay close attention to negative adjustments in parentheses.
        2.  **Perform Detailed Validation and Analysis:**
            *   **Sale Price Bracketing:** Find the final "Opinion of Market Value" from the Reconciliation section. Verify if this value is bracketed by the sale prices of the comparables (i.e., the final value is not lower than the lowest comp sale price and not higher than the highest comp sale price). Report this as a finding.
            *   **Blank Field Check:** For each comparable, verify that the following fields are NOT blank or null: `Sale Price/Gross Liv. Area`, `Data Source(s)`, and `Verification Source(s)`. Report any comparables with missing data for these fields.
            *   **Data Source Content:** For the `Data Source(s)` field, verify it contains a value (e.g., 'MLS# 12345') or at least the word 'Unknown'. Report if it's blank.
            *   **Financing Concessions:** For each comparable, if `Sale or Financing Concessions` is '0', 'none', or contains 'conv', the `Sale or Financing Concessions Adjustment` must be '0' or blank. If `Sale or Financing Concessions` is a non-zero value (e.g., '$5,000'), the adjustment must be negative with the same absolute value (e.g., '-$5,000'). Report any mismatches.
            *   **Date of Sale / Time Adjustment:** Find the 'Date of Contract' from the Contract section. For each comparable, verify that its 'Date of Sale/Time' is after the 'Date of Contract'. If a `Date of Sale/Time Adjustment` is present for any comparable, verify that a comment explaining the time adjustment exists elsewhere in the report (e.g., in an addendum). Report any issues.
            *   **Location Adjustment:** If the subject's `Location` is 'A' and a comparable's is 'N', verify that a negative adjustment is applied. If the subject is 'N' and a comp is 'A', verify a positive adjustment. Report on the consistency of this logic.
            *   **Leasehold/Fee Simple Adjustment:** If a comparable's `Leasehold/Fee Simple` value is different from the subject's, verify that an adjustment (either '0' or another value) is present.
            *   **General Adjustment Consistency:** For all other features (View, Design, Quality, Condition, etc.), an adjustment is consistent if the same dollar amount is applied for the same feature difference from the subject. For example, if Comp 1 and Comp 2 both have a 'Superior' view compared to the subject's 'Average' view, their 'View Adjustment' should be identical. Report any inconsistencies.
            *   **GLA Adjustment:** Calculate the adjustment rate per square foot for each comparable (`Gross Living Area Adjustment` / difference in GLA from subject). Report if this rate is consistent across all comparables.
            *   **Basement Adjustment:** If the subject has a basement and a comparable does not, a positive adjustment should be made. If the subject has no basement and a comparable does, a negative adjustment should be made. Report on the consistency of this logic.
            *   **Net and Gross Adjustments:**
                *   **Net Adjustment:** For each comparable, sum all individual adjustments. Verify this sum equals the `Net Adjustment (Total)`. Report any calculation errors.
                *   **Gross Adjustment:** For each comparable, sum the absolute values of all individual adjustments. Calculate the Gross Adjustment Percentage (Gross Adjustment / Sale Price). Report if this percentage exceeds 15% for any comparable.
            *   **Adjusted Sale Price:** For each comparable, calculate `Sale Price + Net Adjustment (Total)`. Verify this equals the `Adjusted Sale Price of Comparable`. Report any calculation errors.
        3.  **Report All Findings:** In the `"details"` array, report the outcome of each validation check. For inconsistencies, clearly describe the discrepancy.

        **Fields to Extract for Subject and each Comparable:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "subject": {{ "Address": "123 Main St", "Condition": "Good", "Gross Living Area": "1850", ... }},
            "comparables": [
                {{ "Address": "456 Oak Ave", "Condition": "Average", "Condition Adjustment": "-$3,000", ... }},
                {{ "Address": "789 Pine Ln", "Condition": "Good", "Condition Adjustment": "$0", ... }},
                {{ "Address": "101 Maple Dr", "Condition": "Average", "Condition Adjustment": "-$5,000", ... }}
            ],
            "adjustment_analysis": {{
                "summary": "Inconsistencies found in Condition and Financing Concession adjustments. Sale price is not bracketed.",
                "details": [
                    "Sale Price Bracketing: Failed. The final appraised value of $560,000 is higher than the highest comparable sale price of $555,000.",
                    "Blank Field Check: Passed. All required fields are filled for all comparables.",
                    "Financing Concessions: Inconsistent. Comp 2 had concessions of $3,000 but the adjustment was $0 instead of -$3,000.",
                    "Condition Adjustment: Inconsistent. Comp 1 received a -$3,000 adjustment for 'Average' condition, while Comp 3 received a -$5,000 adjustment for the same 'Average' condition.",
                    "GLA Adjustment: Consistent. A rate of $50/sq. ft. was applied across all comparables.",
                    "Location Adjustment: Not applied. All comparables were in a similar location to the subject.",
                    "Net/Gross Adjustments: Failed. Comp 1 Gross Adjustment Percentage is 18%, which exceeds the 15% guideline.",
                    "Adjusted Sale Price: Failed. Comp 2 Adjusted Sale Price is calculated as $545,000 but is listed as $540,000 in the grid."
                ]
            }}
        }}
        """
    elif section_name.lower() == 'market_conditions':
        prompt = f"""
        You are an expert at extracting information from the "Market Conditions" addendum (Form 1004MC) of a real estate appraisal report.
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object.

        **Instructions:**
        1.  **Handle Grid Data:** For fields that represent a row in the Market Conditions grid (e.g., "Inventory Analysis Total # of Comparable Sales (Settled)"), create a nested JSON object. The keys of this nested object should be the time periods ("Prior 7–12 Months", "Prior 4–6 Months", "Current – 3 Months", "Overall Trend"), and the values should be the data from the corresponding cells in the grid. For the "Overall Trend" column, extract the text of the selected checkbox (e.g., "Increasing", "Decreasing", "Stable").
        2.  **Handle Yes/No Questions:** For yes/no questions, extract the "Yes" or "No" answer. The subsequent explanation field (e.g., "If yes, explain...") should contain the corresponding text. If the answer is "No", the explanation field should be `null`.
        3.  **Use Null for Missing Data:** If any field or grid cell is not found, is not applicable, or has no value (e.g., '--', 'N/A', or blank), use `null` as its value. Do not invent data.

        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "Inventory Analysis Total # of Comparable Sales (Settled)": {{
                "Prior 7–12 Months": "150",
                "Prior 4–6 Months": "80",
                "Current – 3 Months": "45",
                "Overall Trend": "Decreasing"
            }},
            "Median Sale & List Price, DOM, Sale/List % Median Comparable Sale Price": {{
                "Prior 7–12 Months": "$500,000",
                "Prior 4–6 Months": "$510,000",
                "Current – 3 Months": "$515,000",
                "Overall Trend": "Increasing"
            }},
            "Are foreclosure sales (REO sales) a factor in the market?": "Yes",
            "If yes, explain (including the trends in listings and sales of foreclosed properties).": "REO sales make up 5% of the market, a trend that has been stable over the last 6 months.",
            "Summarize the above information as support for your conclusions in the Neighborhood section...": "The market shows increasing prices despite a decrease in sales volume, indicating strong demand and limited inventory...",
            "...": "..."
        }}
        """
    elif section_name.lower() == 'condo':
        prompt = f"""
        You are an expert at extracting information from the "Project Information" section for condominiums in a real estate appraisal report.
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object.

        **Instructions:**
        1.  **Handle Grid Data:** For fields that represent a row in the "Subject Project Data" grid (e.g., "Subject Project Data Total # of Comparable Sales (Settled)"), create a nested JSON object. The keys of this nested object should be the time periods ("Prior 7–12 Months", "Prior 4–6 Months", "Current – 3 Months", "Overall Trend"), and the values should be the data from the corresponding cells in the grid. For the "Overall Trend" column, extract the text of the selected checkbox (e.g., "Increasing", "Decreasing", "Stable").
        2.  **Handle Yes/No Questions:** For yes/no questions, extract the "Yes" or "No" answer. The subsequent explanation field (e.g., "If yes, indicate...") should contain the corresponding text. If the answer is "No", the explanation field should be `null`.
        3.  **Use Null for Missing Data:** If any field or grid cell is not found, is not applicable, or has no value (e.g., '--', 'N/A', or blank), use `null` as its value. Do not invent data.

        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "Subject Project Data Total # of Comparable Sales (Settled)": {{
                "Prior 7–12 Months": "25",
                "Prior 4–6 Months": "15",
                "Current – 3 Months": "10",
                "Overall Trend": "Decreasing"
            }},
            "Subject Project Data Absorption Rate (Total Sales/Months)": {{
                "Prior 7–12 Months": "4.2",
                "Prior 4–6 Months": "5.0",
                "Current – 3 Months": "3.3",
                "Overall Trend": "Stable"
            }},
            "Are foreclosure sales (REO sales) a factor in the project?": "No",
            "If yes, indicate the number of REO listings and explain the trends in listings and sales of foreclosed properties.": null,
            "Summarize the above trends and address the impact on the subject unit and project.": "The project shows stable absorption despite a decrease in sales volume. Foreclosures are not a significant factor.",
            "...": "..."
        }}
        """
    elif section_name.lower() == 'cost_approach':
        prompt = f"""You are an expert at extracting information from the "Cost Approach" section of a real estate appraisal report.
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object where the keys are the field names and the values are the extracted data.

        **Instructions:**
        1.  **Be Thorough:** Extract data for every field listed. This includes supporting text fields, the main cost calculation table, and additional comments. The field "ESTIMATED (REPRODUCTION / REPLACEMENT COST NEW)" is a checkbox, so extract the selected option (e.g., "REPRODUCTION" or "REPLACEMENT").
        2.  **Use Null for Missing Data:** If a field is not found, is not applicable, or has no value (e.g., '--', 'N/A', or is blank), use `null` as its value. Do not invent data.
        3.  **Handle Monetary Values:** For fields representing costs or values (e.g., "Opinion of Site Value", "Dwelling", "Indicated Value By Cost Approach"), extract the full monetary value, including any currency symbols or commas (e.g., "$120,000").
        4.  **Handle Descriptive Text:** For descriptive fields (e.g., "Support for the opinion of site value...", "Comments on Cost Approach..."), extract the complete text content.
        5.  **Handle the "ESTIMATED" field:** The word "ESTIMATED" often appears as a header for the cost calculation table. If you find this word, extract it as the value for the "ESTIMATED" field. If it's not present, use `null`.

        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "Support for the opinion of site value (summary of comparable land sales or other methods for estimating site value)": "Based on analysis of three comparable land sales in the subject's market area.",
            "ESTIMATED (REPRODUCTION / REPLACEMENT COST NEW)": "REPLACEMENT",
            "Source of cost data": "Marshall & Swift",
            "Quality rating from cost service": "Average",
            "Effective date of cost data": "01/2024",
            "Opinion of Site Value": "$100,000",
            "Dwelling": "$350,000",
            "Garage/Carport": "$25,000",
            "Total Estimate of Cost-New": "$475,000",
            "Depreciation": "$50,000",
            "Depreciated Cost of Improvements": "$425,000",
            "As-is Value of Site Improvements": "$10,000",
            "Indicated Value By Cost Approach": "$535,000",
            "Comments on Cost Approach (gross living area calculations, depreciation, etc.)": "Depreciation estimated using the age-life method. GLA calculations are consistent with the building sketch.",
            "Estimated Remaining Economic Life (HUD and VA only)": "50 Years"
        }}
        """
    elif section_name.lower() == 'custom_analysis':
        if not custom_prompt:
            return {} # Return empty dict if no prompt; view handles rendering the form page.
        prompt = f"""You are an expert AI assistant specializing in real estate appraisal report analysis.
        You have been provided with one or more documents (like an original appraisal, a 1004D, an order form, etc.) and a specific query from a user.
        Analyze all provided documents and context thoroughly to answer the user's query.

        **User's Query:**
        "{custom_prompt}"

        **Your Task:**
        Provide a structured and comprehensive answer to the user's query based on the content of all provided documents.
        Format your response as a single, valid JSON object with the following keys:

        1.  `"query_summary"`: A brief, one-sentence summary of the user's original query.
        2.  `"findings"`: A JSON array of objects. Each object should represent a specific data point or piece of evidence found in the document that relates to the query. Each object in the array should have these keys:
            *   `"finding_title"`: A short, descriptive title for the finding (e.g., "GLA in Improvements Section", "Comparable 1 Address").
            *   `"finding_detail"`: The specific data or text extracted from the document (e.g., "1,850 sq. ft.", "123 Oak St").
            *   `"source_location"`: The section, page number, or document name where this information was found (e.g., "Improvements Section, Page 3", "Sales Grid in original_appraisal.pdf").
        3.  `"analysis_summary"`: A concise summary that synthesizes the findings and directly answers the user's query. State whether the issue is "Corrected", "Not Corrected", "Addressed", or "Not Addressed". If corrected or addressed, reference the addendum page or section where the change is present. Highlight any deviations or disagreements you have with the provided information.

        **Example for query "Check GLA consistency":**
        {{
            "query_summary": "Checking for discrepancies in Gross Living Area (GLA) across the report.",
            "findings": [
                {{
                    "finding_title": "GLA in Improvements Section",
                    "finding_detail": "1,850 sq. ft.",
                    "source_location": "Improvements, Page 2"
                }},
                {{
                    "finding_title": "GLA in Sales Grid (Subject)",
                    "finding_detail": "1,850 sq. ft.",
                    "source_location": "Sales Comparison Approach"
                }}
            ],
            "analysis_summary": "The Gross Living Area (GLA) is consistently reported as 1,850 sq. ft. in both the Improvements section and the Sales Comparison Approach grid. No discrepancies were found."
        }}
        """
    elif section_name.lower() == 'state_requirement':
        # This is a two-step process. First, we need to get the state.
        # We will make a preliminary, quick call to get only the state from the subject section.
        state_prompt = "Extract only the property's state from the 'Subject' section of the report. Return a single JSON object with one key, 'State'. Example: {\"State\": \"CA\"}"
        pdf_path = pdf_paths[0] if pdf_paths else None
        try:
            # Use asyncio.to_thread for the synchronous client call within the async function
            if pdf_path and os.path.exists(pdf_path):
                prelim_file = await asyncio.to_thread(client.files.upload, file=pdf_path)
                while prelim_file.state.name == "PROCESSING":
                    await asyncio.sleep(5)
                    prelim_file = await asyncio.to_thread(client.files.get, name=prelim_file.name)
            else:
                return {"error": "PDF file for state extraction not found."}
            if prelim_file.state.name != "ACTIVE":
                 return {"error": f"File processing failed for state extraction. State: {prelim_file.state.name}"}

            state_response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[prelim_file, state_prompt],
            )
            state_data = json.loads(state_response.text.strip().lstrip("```json").rstrip("```"))
            subject_state = state_data.get("State", "Unknown")

            # Now, build the main prompt with the state information.
            prompt = f"""
            You are an expert AI assistant specializing in state-specific compliance for real estate appraisal reports.
            The subject property is in the state of **{subject_state}**.
            Your task is to verify if the report complies with the requirements for this state.

            Your output must be a single, valid JSON object where the keys are the field names from the "Fields to Verify" list below. The value for each key must be a string detailing your findings.

            **Instructions:**
            For each field, search the entire document and report your findings.
            - If a required item is found, state what was found and where (e.g., "Fee of $500 disclosed on page 3 in the certification.").
            - If a required item is NOT found, explicitly state that (e.g., "Requirement applies for {subject_state}, but no disclosure was found in the report.").
            - If a requirement does not apply to **{subject_state}**, state that (e.g., "This requirement does not apply to {subject_state}.").

            **State-Specific Rules to Apply:**
            - **Appraiser Fee Disclosure**: Required for AZ, CO, CT, GA, IL, LA, NJ, NV, NM, ND, OH, UT, VA, VT, WV.
            - **AMC License Disclosure**: Required for GA, IL, MT, NJ, OH, VT. For IL, the number should be 558000312 with expiration 12/31/2026.
            - **AMC Fee Disclosure**: Required for NV, NM, UT.
            - **Smoke/CO Detector Requirements**: Check for comments in CA, IL, VA, WI.
            - **Water Heater Strapping**: Check for comments on double strapping in CA & UT.
            - **State-Specific Legal Statements**: For IL, verify the presence of the full Home Inspector License Act statement.
            - **Invoice Copy Requirement**: Check for an invoice copy in NY reports.

            **Fields to Verify:**
            {json.dumps(fields_to_extract, indent=2)}

            **Example JSON Output for a report in Illinois (IL):**
            {{
                "Appraiser Fee Disclosure": "Requirement applies for IL. A fee of $650 was found in the certification section on page 5.",
                "AMC License Disclosure": "Requirement applies for IL. License #558000312 and expiration 12/31/2026 were found on page 5.",
                "State-Specific Legal Statements": "Requirement applies for IL. The full required Home Inspector License Act statement was found in the addendum on page 8."
            }}
            """
        except Exception as e:
            return {"error": f"Failed to get state for compliance check: {str(e)}"}

    elif section_name.lower() == 'client_lender_requirements':
        prompt = f"""
        You are an expert AI assistant specializing in client-specific compliance for real estate appraisal reports.
        Your task is to identify the client and verify if the report complies with their specific requirements.

        **Your output must be a single, valid JSON object.** The keys of the JSON object must be the field names from the "Fields to Verify" list below. The value for each key must be a string detailing your findings.

        **Instructions:**
        1.  **First, identify the Lender/Client.** Search the "Subject" and "Certification" sections for the Lender/Client name. The client will be one of: "Visio Lending", "Ice Lender Holdings LLC", "Hometown Equity" (which includes "theLender"), "BPL Mortgage, LLC", "Plaza Home Mortgage Inc", "CIVIC", "Capital Funding Financial LLC", "Temple View", "LoanDepot.com", "The Loan Store", "GFL Capital Mortgage", "Cardinal Financial Company", "OCMBC", "Paramount Residential Mortgage Group", "Arc Home LLC", "CV3 Financial", "Nationwide Mortgage Bankers, Inc.", "Logan Finance", "New American Funding", "Haus Capital", "Equity Wave Lending, Inc", "FOUNDATION MORTGAGE", "Rain City Capital, LLC", "East Coast Capital Corp", "Malama Funding LLC" (which includes "Lend with Aloha LLC"), "National Loan Funding LLC", "Easy Street Capital, LLC", "Kind Lending LLC", "Dart Bank", "Futures Financial", "Champions Funding LLC", "Deephaven Mortgage LLC", "Loanguys.com inc", or "Eastview Investment Partners".
        2.  **Apply Rules:** Based on the identified client, perform the checks listed under their name.
        3.  **Use "N/A":** For any check that belongs to other clients, the value should be "N/A - Rule does not apply to this client." If the client cannot be identified, all fields should be "N/A - Client not identified."

        ---
        **Rules for "Visio Lending"**
        *(If client is Visio, apply these. For other clients' fields, use "N/A")*

        - **Report Condition (As Is):** Check "Reconciliation" section. Report if not 'as is'.
        - **Repairs with 'As Is' Condition:** Even if 'as is', search for any mention of repairs (e.g., in "Improvements", addenda). Report if found.
        - **STR Comps for 1007 STR:** If a 1007 STR form is present, verify all comps are STRs.
        - **Occupancy for 1007 Orders:** If a 1007 form is present, "Occupant" in "Subject" section must be 'Vacant' or 'Tenant', not 'Owner'.
        - **Occupancy for 1025 Form:** If a 1025 form, "Occupant" can be 'Owner' but 'Tenant' or 'Vacant' must also be checked.

        ---
        **Rules for "Hometown Equity / theLender"**
        *(If client name contains "Hometown Equity" or "theLender", apply these. For other clients' fields, use "N/A")*

        - **Smoke/CO Detector Installation and Photos:**
            *   **Action:** The appraiser MUST comment on the presence of ALL smoke and CO detectors and provide photos of them. Search the entire report (especially "Improvements" section, addenda, and photo descriptions) for these comments. Review all photos to find images of the detectors.
            *   **Finding:** Report if both comments AND photos for smoke/CO detectors are present. If either is missing, it is a failure.
            *   **Example:** "Passed: Report includes comments on smoke/CO detectors and photos are present." OR "Failed: Comments on smoke/CO detectors were found, but photos are missing. This requires a revision." OR "Failed: No comments or photos of smoke/CO detectors were found. This requires a revision."

        ---
        **Rules for "Ice Lender Holdings LLC"**
        *(If client is Ice Lender, apply these. For other clients' fields, use "N/A")*

        - **Report Condition (As Is):** Check "Reconciliation" section. Report if not 'as is'.

        - **Value vs. Listing/Contract Price (10% Rule):**
            *   **Action:** Find the final "Opinion of Market Value" (Reconciliation). Find the "Contract Price" (Contract section) or "Listing Price" (Subject section, if offered for sale).
            *   **Finding:** Calculate if the final value is more than 10% higher than the contract/listing price. Report the values and the percentage difference.
            *   **Example:** "Failed: Final Value ($550k) is 10% higher than Contract Price ($500k). Escalate." OR "Passed: Final Value ($510k) is within 10% of Contract Price ($500k)."

        - **USPAP Compliance Addendum:**
            *   **Action:** Search the entire document, especially the addenda, for a page titled "USPAP Compliance Addendum".
            *   **Finding:** Report if the addendum is present or not.
            *   **Example:** "Passed: USPAP Compliance Addendum found on page 12." OR "Failed: USPAP Compliance Addendum is missing from the report."

        - **FIRREA Statement:**
            *   **Action:** Search the document (especially certification and addenda) for text indicating the report was prepared in accordance with FIRREA (Financial Institutions Reform, Recovery, and Enforcement Act of 1989).
            *   **Finding:** Report if the statement is present or not.
            *   **Example:** "Passed: FIRREA compliance statement found in the appraiser's certification." OR "Failed: FIRREA compliance statement is missing."

        - **Required Photographs (Mechanicals, Kitchen, Roof):**
            *   **Action:** Review all photos. Look for images explicitly labeled or clearly showing mechanical systems (HVAC, water heater), the full kitchen, and the roof.
            *   **Finding:** Report which required photos are present and which are missing.
            *   **Example:** "Passed: Photos for kitchen, roof, and HVAC system are present." OR "Failed: Photo of the roof is missing."

        - **Kitchen Photo Refrigerator Check:**
            *   **Action:** Examine the kitchen photo(s).
            *   **Finding:** Report if a refrigerator is visible in the kitchen photo. If not, check the report comments for an explanation.
            *   **Example:** "Passed: Refrigerator is visible in the kitchen photo." OR "Failed: Refrigerator is not visible in the kitchen photo and no comment was found."

        - **Comparable Distance Guideline (Urban/Suburban/Rural):**
            *   **Action:** First, determine the market type (Urban, Suburban, or Rural) from the "Neighborhood" section ("Location" field). Then, for each comparable in the "Sales Comparison Approach" grid, check the "Proximity to Subject" distance.
            *   **Finding:** Compare the distance of each comp against the guideline (Urban: 1 mile, Suburban: 3 miles, Rural: 10 miles). Report any comps that exceed the guideline for their market type.
            *   **Example (Urban):** "Passed: All comps are within the 1-mile guideline for an Urban area." OR "Failed: Comp 3 (1.5 miles) exceeds the 1-mile guideline for an Urban area."
            *   **Note:** Only report on the relevant market type. For the other two, the finding should be "N/A - Market is not [type]".

        ---
        **Rules for "BPL Mortgage, LLC"**
        *(If client is BPL, apply these. For other clients' fields, use "N/A")*

        - **Smoke/CO Detector Presence (BPL):**
            *   **Action:** Search the report for any statement addressing if smoke/CO detectors are present and if they are required by law.
            *   **Finding:** Report if this statement is present or missing.

        - **Value vs. Listing/Contract Price (10% Rule - BPL):**
            *   **Action:** Find the final "Opinion of Market Value". Compare it to the "Contract Price" or "Listing Price". If the value is >10% higher, search the report for comments explaining this discrepancy.
            *   **Finding:** Report the percentage difference. If >10%, state whether an explanatory comment was found.

        - **Increase in Value Since Prior Sale:**
            *   **Action:** Find the final "Opinion of Market Value" and the "Price of Prior Sale/Transfer" from the "Sale History" section. If the current value is higher, search for comments explaining the increase (e.g., renovations).
            *   **Finding:** Report if the value has increased and whether an explanation is present.

        - **Cost to Cure for Repairs:**
            *   **Action:** Search for any mention of "repairs" or "deferred maintenance". If found, verify that a "cost to cure" is provided. Exception: A cost to cure is not needed if the only issue is "turning the water on".
            *   **Finding:** Report if repairs are noted and if a cost to cure is appropriately provided or missing.

        - **Cost Approach Completion:**
            *   **Action:** Check the "Cost Approach" section.
            *   **Finding:** Report if the Cost Approach section is completed or if it is blank/not developed.

        - **Room Photo Requirement (2 per room):**
            *   **Action:** Review all interior photos. For each room (bedroom, kitchen, living room, etc.), check if there are at least two photos taken from different angles/opposite sides.
            *   **Finding:** Report if rooms have at least two photos each. Note any rooms that do not meet this requirement.

        - **Bedroom Photo Labeling:**
            *   **Action:** Find all photos labeled as "Bedroom".
            *   **Finding:** Verify that the labels are specific, such as "Bedroom 1", "Bedroom 2", etc., rather than just "Bedroom".

        - **Comparable Distance Guideline (Urban/Suburban - BPL):**
            *   **Action:** If market type is Urban or Suburban, check the "Proximity to Subject" for each comp.
            *   **Finding:** Report any comp exceeding the 1-mile guideline and whether a comment justifying its use is present.

        - **Comparable Distance Guideline (Rural - BPL):**
            *   **Action:** If market type is Rural, check the "Proximity to Subject" for each comp.
            *   **Finding:** Report any comp exceeding the 5-mile guideline and whether a comment justifying its use is present.

        - **Multi-Family Unit Count Consistency:**
            *   **Action:** For multi-family properties, find the number of units for the subject property. Then, for each comparable, find its number of units.
            *   **Finding:** Report if any comparable has a different number of units than the subject.

        - **Heating System Functionality:**
            *   **Action:** Search the report for a comment addressing if the heating system is functioning.
            *   **Finding:** Report if the statement is present. Note if the appraiser commented that it was too hot to test, as this is acceptable.

        - **Quality and Condition Ratings (Q/C):**
            *   **Action:** In the "Sales Comparison Approach" grid, check the "Quality of Construction" and "Condition" rows for both the subject and all comparables.
            *   **Finding:** Verify that the ratings use the "Q1-Q6" and "C1-C6" format. Report if any ratings are missing or use a different format (e.g., "Average", "Good").

        ---
        **Rules for "Plaza Home Mortgage Inc"**
        *(If client is Plaza, apply these. For other clients' fields, use "N/A")*

        - **Invoice in Report (NY Only):**
            *   **Action:** First, determine if the property state is 'NY' (from the Subject section). If it is NY, search the entire document for a page that appears to be an "invoice".
            *   **Finding:** If the state is not NY, report "N/A - Property not in NY." If the state is NY and an invoice is found, report it as a failure. If the state is NY and no invoice is found, report it as passed.
            *   **Example:** "Failed: Property is in NY and an invoice was found on page 15. It must be removed." OR "Passed: Property is in NY and no invoice was found in the report."

        - **Client Email Address Present:**
            *   **Action:** Search the "Certification" section for the "Lender/Client Email Address".
            *   **Finding:** Report whether the email address is present or missing.
            *   **Example:** "Passed: Client email address is present." OR "Failed: Client email address is missing. Reviewer to complete and notify group."

        - **SSR Score Check:**
            *   **Action:** Search the document for a "Submission Summary Report" (SSR). If found, look for the "SSR Score" or a similar risk score.
            *   **Finding:** Report the SSR score if found. If the score is above 4, flag it as a failure for escalation.
            *   **Example:** "N/A: No SSR found in the report." OR "Passed: SSR Score is 3.5, which is within the acceptable threshold." OR "Failed: SSR Score is 4.2, which is above the threshold of 4. Please stop and escalate."

        ---
        **Rules for "CIVIC"**
        *(If client is CIVIC, apply these. For other clients' fields, use "N/A")*

        - **As-Is Value Order (2-Value Reports):**
            *   **Action:** Check if the report is a 2-value report (contains both an "As-Is" value and another value like "As-Repaired" or "As-Completed"), typically in the Reconciliation section.
            *   **Finding:** If it is a 2-value report, confirm that the "As-Is" value is presented before the other value.
            *   **Example:** "Passed: This is a 2-value report and the As-Is value is listed first." OR "Failed: This is a 2-value report, but the As-Repaired value is listed before the As-Is value." OR "N/A: This is not a 2-value report."

        - **Freddie Unacceptable Practices Review:**
            *   **Action:** This is an informational check.
            *   **Finding:** Report that this review is not required for CIVIC.
            *   **Example:** "N/A - Freddie Unacceptable Practices review is not required for CIVIC."

        ---
        **Rules for "Capital Funding Financial LLC"**
        *(If client is Capital Funding Financial, apply these. For other clients' fields, use "N/A")*

        - **As-Is Value Order (2-Value Reports):**
            *   **Action:** Check if the report is a 2-value report (contains both an "As-Is" value and another value like "As-Repaired" or "As-Completed"), typically in the Reconciliation section.
            *   **Finding:** If it is a 2-value report, confirm that the "As-Is" value is presented before the other value. If the As-Repaired value is first, it is a failure.
            *   **Example:** "Passed: This is a 2-value report and the As-Is value is listed first." OR "Failed: This is a 2-value report, but the As-Repaired value is listed before the As-Is value. The client requires the report to be completed for the As-Is value." OR "N/A: This is not a 2-value report."

        ---
        **Rules for "Temple View Capital Funding, LP"**
        *(If client is Temple View, apply these. For other clients' fields, use "N/A". These rules apply to 2-value reports.)*

        - **Report Completion Basis (Temple View):**
            *   **Action:** For 2-value reports, check the "Reconciliation" section.
            *   **Finding:** Verify the report is completed "Subject To" repairs/completion. It should not be "As Is".
            *   **Example:** "Passed: Report is completed 'Subject To' repairs as required." OR "Failed: Report is completed 'As Is', but should be 'Subject To' for Temple View 2-value reports." OR "N/A: Not a 2-value report."

        - **ARV Comps Gridded (Temple View):**
            *   **Action:** For 2-value reports, examine the "Sales Comparison Approach" grid.
            *   **Finding:** Confirm that at least 3 "As-Repaired Value" (ARV) comparables are included in the grid.
            *   **Example:** "Passed: At least 3 ARV comps are gridded." OR "Failed: Only 2 ARV comps were found in the grid. At least 3 are required." OR "N/A: Not a 2-value report."

        - **As-Is Comps and Value Comments (Temple View):**
            *   **Action:** For 2-value reports, search the report (especially addenda and comment sections) for discussion of the "As-Is" value.
            *   **Finding:** Verify that there are comments mentioning at least 3 "As-Is" comparables and an explanation of how the "As-Is" value was reconciled. Note that these comps are not required to be in the main grid.
            *   **Example:** "Passed: Comments found in the addendum detailing 3 As-Is comps and the reconciliation for the As-Is value." OR "Failed: No comments were found describing the As-Is comps or the reconciliation of the As-Is value." OR "N/A: Not a 2-value report."

        ---
        **Rules for "Malama Funding LLC / Lend with Aloha LLC"**
        *(If client is Malama Funding or Lend with Aloha, apply these. For other clients' fields, use "N/A". These rules apply to 2-value reports.)*

        - **Report Completion Basis (Malama Funding):**
            *   **Action:** For 2-value reports, check the "Reconciliation" section.
            *   **Finding:** Verify the report is completed "Subject To" repairs/completion. It should not be "As Is".
            *   **Example:** "Passed: Report is completed 'Subject To' repairs as required." OR "Failed: Report is completed 'As Is', but should be 'Subject To' for 2-value reports." OR "N/A: Not a 2-value report."

        - **ARV Comps Gridded (Malama Funding):**
            *   **Action:** For 2-value reports, examine the "Sales Comparison Approach" grid.
            *   **Finding:** Confirm that at least 3 "As-Repaired Value" (ARV) comparables are included in the grid (typically comps 1-3).
            *   **Example:** "Passed: At least 3 ARV comps are gridded." OR "Failed: Only 2 ARV comps were found in the grid. At least 3 are required." OR "N/A: Not a 2-value report."

        - **As-Is Comps and Value Comments (Malama Funding):**
            *   **Action:** For 2-value reports, search the report (especially addenda and comment sections) for discussion of the "As-Is" value.
            *   **Finding:** Verify that there are comments mentioning "As-Is" comparables and an explanation of how the "As-Is" value was reconciled. Note that these comps are not required to be in the main grid, but comments about them must be present.
            *   **Example:** "Passed: Comments found in the addendum detailing the As-Is comps and the reconciliation for the As-Is value." OR "Failed: No comments were found describing the As-Is comps or the reconciliation of the As-Is value." OR "N/A: Not a 2-value report."


        ---
        **Rules for "Kind Lending LLC"**
        *(If client is Kind Lending, apply these. For other clients' fields, use "N/A")*

        - **ENV Requirement (Kind Lending):**
            *   **Action:** This is an informational check for the reviewer.
            *   **Finding:** Populate this field with the instruction: "Info: An ENV file is no longer required. PDF and XML are sufficient. If an ENV is provided, that is OK."
            *   **Example:** "Info: An ENV file is no longer required. PDF and XML are sufficient. If an ENV is provided, that is OK."

        - **1004MC Requirement (Kind Lending):**
            *   **Action:** This is an informational check for the reviewer.
            *   **Finding:** Populate this field with the instruction: "Info: A 1004MC form is not required for this client."
            *   **Example:** "Info: A 1004MC form is not required for this client."



        ---
        **Rules for "Dart Bank"**
        *(If client is Dart Bank, apply these. For other clients' fields, use "N/A")*

        - **ENV Requirement (Dart Bank):**
            *   **Action:** This is an informational check for the reviewer.
            *   **Finding:** Populate this field with the instruction: "Info: An ENV file is no longer required. A PDF is sufficient."
            *   **Example:** "Info: An ENV file is no longer required. A PDF is sufficient."





        ---
        **Rules for "Futures Financial" (for Richel Francis orders)**
        *(If client is Futures Financial, apply these. For other clients' fields, use "N/A")*

        - **As-is with ARV Report Condition (Futures Financial):**
            *   **Action:** First, verify this order is for "FRANCIS, Richel" by searching for the name in the report (e.g., appraiser, client contact). If the name is not found, this rule is N/A. If the name is found, check if the product type is "As-is with ARV". If so, verify the report is completed "as-is" and that two values ("As-Is" and "ARV") are present in the Reconciliation section.
            *   **Finding:** Report on the findings.
            *   **Example:** "Passed: This is an 'As-is with ARV' product for Richel Francis. The report is correctly completed 'as-is' and contains two values." OR "Failed: This is an 'As-is with ARV' product, but only one value was found." OR "N/A - Not an 'As-is with ARV' product type." OR "N/A - Order not for FRANCIS, Richel."

        - **Desktop Report Condition (Futures Financial):**
            *   **Action:** First, verify this order is for "FRANCIS, Richel" by searching for the name in the report. If the name is not found, this rule is N/A. If the name is found, check if the product type is "Desktop". If so, verify the report is completed "subject-to" in the Reconciliation section.
            *   **Finding:** Report on the findings.
            *   **Example:** "Passed: This is a 'Desktop' product for Richel Francis, and the report is correctly completed 'subject-to'." OR "Failed: This is a 'Desktop' product, but the report is completed 'as-is' instead of 'subject-to'." OR "N/A - Not a 'Desktop' product type." OR "N/A - Order not for FRANCIS, Richel."








        ---
        **Rules for "Champions Funding LLC"**
        *(If client is Champions Funding, apply these. For other clients' fields, use "N/A")*

        - **E&O Insurance Attached (Champions):**
            *   **Action:** Search the entire document for a page that appears to be an "E&O" or "Errors and Omissions" insurance declaration page.
            *   **Finding:** Report if the E&O insurance document is found. If it is not found, it is a failure.
            *   **Example:** "Passed: E&O insurance declaration found on page 15." OR "Failed: Per client instructions for their assignments, please attach appraiser's E&O to the report."

        - **Value vs. Predominant Value (Champions):**
            *   **Action:** Get the final "Opinion of Market Value" from the Reconciliation section. Get the "predominant" price from the "one unit housing price(high,low,pred)" field in the Neighborhood section. Calculate if the market value is 10% higher or 10% lower than the predominant value. If it is outside this range, search the report for a comment explaining the difference (e.g., under/over improvement, marketability impact).
            *   **Finding:** If the value is outside the 10% range and no comment is found, provide the specific failure message. Otherwise, report as passed.
            *   **Example (Higher):** "Failed: Appraised value is higher than Predominant value. Appraiser to comment whether it is an over improvement and if there is any impact on the value and marketability of the subject property."
            *   **Example (Lower):** "Failed: Appraised value is lower than Predominant value. Appraiser to comment whether it is an under improvement and if there is any impact on the value and marketability of the subject property."
            *   **Example (Pass):** "Passed: Appraised value is within 10% of the predominant value."

        - **Smoke/CO Detector Check (Champions):**
            *   **Action:** Search the report (addenda, improvements section) for any comment addressing the presence and requirement of smoke/CO detectors.
            *   **Finding:** If no comment is found, it is a failure.
            *   **Example:** "Passed: A comment regarding smoke/CO detectors was found in the addendum." OR "Failed: Please address if smoke/co detectors were present and required."

        - **Stove in Kitchen Photo (Champions):**
            *   **Action:** Review all photos labeled "Kitchen".
            *   **Finding:** Verify that a stove/range is clearly visible in at least one of the kitchen photos. If not visible, it is a failure.
            *   **Example:** "Passed: A stove is visible in the kitchen photo." OR "Failed: The stove must be viewable in the kitchen photo."










        ---
        **Rules for "Deephaven Mortgage LLC"**
        *(If client is Deephaven, apply these. For other clients' fields, use "N/A")*

        - **1004MC Requirement (Deephaven):**
            *   **Action:** This is an informational check for the reviewer.
            *   **Finding:** Populate this field with the instruction: "Info: A 1004MC form is not required for this client."
            *   **Example:** "Info: A 1004MC form is not required for this client."





        ---
        **Rules for "Loanguys.com inc"**
        *(If client is Loanguys.com, apply these. For other clients' fields, use "N/A")*

        - **QC Ratings Requirement (Loanguys):**
            *   **Action:** In the "Sales Comparison Approach" grid, check the "Quality of Construction" and "Condition" rows for both the subject and all comparables.
            *   **Finding:** Verify that all ratings use the "Q1-Q6" and "C1-C6" format. If any rating uses a different format (e.g., "Average", "Good", "Fair"), it is a failure.
            *   **Example:** "Passed: All Quality and Condition ratings use the required Q/C format." OR "Failed: Per client requirement, please include ""Q"" and ""C"" ratings for ""Quality"" and ""Condition"" for the subject and all comps."





        ---
        **Rules for "Eastview Investment Partners"**
        *(If client is Eastview, apply these. For other clients' fields, use "N/A")*

        - **Desk Review Escalation (Eastview):**
            *   **Action:** Determine if the report is a Desk Review (e.g., Form 2006, FRE 1033, or "Desk Review" in the title).
            *   **Finding:** If it is a desk review, this field should contain an escalation instruction. If not, it should be N/A.
            *   **Example:** "Escalate: All desk review reports for this client must be escalated." OR "N/A - Not a desk review report."

        - **Desk Review Form Type (Eastview):**
            *   **Action:** Determine if the report is a "Desk Review (2006) short form".
            *   **Finding:** If the report is a Desk Review (2006) short form, it is a failure. If it is another type of desk review (like FRE 1033), it is a pass. For all other report types, this is N/A.
            *   **Example:** "Failed: The client requires the FRE 1033 Desk Review to be completed. Please provide the FRE 1033 form." OR "Passed: The correct FRE 1033 Desk Review form was used." OR "N/A - Not a desk review report."





        ---
        **Rules for "LoanDepot.com"**
        *(If client is LoanDepot, apply these. For other clients' fields, use "N/A")*

        - **Reviewer Instructions (LoanDepot):**
            *   **Action:** This is an informational check for the reviewer.
            *   **Finding:** Populate this field with the following instructions: "Reviewer Reminders: 1. Do not escalate; just reject or complete as needed. 2. For ENV files, do not refer to page numbers in revision language. Only use page numbers for regular XML/PDF reports."
            *   **Example:** "Reviewer Reminders: 1. Do not escalate; just reject or complete as needed. 2. For ENV files, do not refer to page numbers in revision language. Only use page numbers for regular XML/PDF reports."

        ---
        **Rules for "The Loan Store"**
        *(If client is The Loan Store, apply these. For other clients' fields, use "N/A")*

        - **Reviewer Instructions (The Loan Store):**
            *   **Action:** This is an informational check for the reviewer.
            *   **Finding:** Populate this field with the following instructions: "Reviewer Reminders: 1. For ENV files, do not use page numbers in revisions. 2. If the product is only a 1007 Rent Schedule, an ENV is not required (PDF only is OK)."
            *   **Example:** "Reviewer Reminders: 1. For ENV files, do not use page numbers in revisions. 2. If the product is only a 1007 Rent Schedule, an ENV is not required (PDF only is OK)."

        - **Double Strapped Water Heater (UT Only):**
            *   **Action:** First, determine if the property state is 'UT' (from the Subject section). If it is UT, search the report (especially Improvements section and photos) for comments or evidence that the water heater is double-strapped.
            *   **Finding:** If the state is not UT, report "N/A - Property not in UT." If the state is UT, report whether the double-strapping is confirmed or not addressed.
            *   **Example:** "Passed: Property is in UT and report confirms water heater is double-strapped." OR "Failed: Property is in UT, but the report does not address if the water heater is double-strapped."

        ---
        **Rules for "GFL Capital Mortgage"**
        *(If client is GFL Capital Mortgage, apply these. For other clients' fields, use "N/A")*

        - **Value vs. Purchase Price (GFL):**
            *   **Action:** First, check if this is a purchase transaction. If so, find the final "Opinion of Market Value" (Reconciliation section) and the "Contract Price" (Contract section).
            *   **Finding:** Compare the final value to the purchase price. If the final value is lower, report it as a failure.
            *   **Example:** "N/A: Not a purchase transaction." OR "Passed: Final Value ($505k) is not lower than Purchase Price ($500k)." OR "Failed: Final Value ($495k) is lower than Purchase Price ($500k). Please advise."

        ---
        **Rules for "Cardinal Financial Company"**
        *(If client is Cardinal Financial, apply these. For other clients' fields, use "N/A")*

        - **1004MC Requirement (Cardinal):**
            *   **Action:** This is an informational check for the reviewer.
            *   **Finding:** Populate this field with the following instruction: "Info: A 1004MC form is not required for Cardinal Financial Company."
            *   **Example:** "Info: A 1004MC form is not required for Cardinal Financial Company."

        ---
        **Rules for "OCMBC"**
        *(If client is OCMBC, apply these. For other clients' fields, use "N/A")*

        - **Smoke/CO Detector Comments (OCMBC):**
            *   **Action:** Search the report (especially "Improvements" section and addenda) for a comment addressing whether smoke/CO detectors were present.
            *   **Finding:** Report if a comment about the presence or absence of smoke/CO detectors is found.
            *   **Example:** "Passed: Report comments that smoke detectors were present." OR "Failed: No comment was found regarding the presence of smoke/CO detectors."

        - **Water Heater Strapping Comments (OCMBC):**
            *   **Action:** Search the report (especially "Improvements" section and addenda) for a comment addressing if the water heater is double strapped and if this is required by law.
            *   **Finding:** Report if a comment about water heater strapping is found.
            *   **Example:** "Passed: Report comments that the water heater is double strapped as required by law." OR "Failed: No comment was found regarding water heater strapping."

        ---
        **Rules for "Paramount Residential Mortgage Group"**
        *(If client is Paramount, apply these. For other clients' fields, use "N/A")*

        - **Reviewer Instructions (Paramount):**
            *   **Action:** This is an informational check for the reviewer.
            *   **Finding:** Populate this field with the following instruction: "Info: If the only revision needed is to remove 'INC' from the lender name 'Paramount Residential Mortgage Group', you can disregard the revision and submit the report."
            *   **Example:** "Info: If the only revision needed is to remove 'INC' from the lender name 'Paramount Residential Mortgage Group', you can disregard the revision and submit the report."

        ---
        **Rules for "Arc Home LLC"**
        *(If client is Arc Home, apply these. For other clients' fields, use "N/A")*

        - **Short-Term Rental Regulations (Arc Home):**
            *   **Action:** First, identify the product type by searching the report for "Short term rental" or "STR". If it is an STR product, search the report (especially zoning, addenda, and comments) for discussion of local short-term rental regulations, zoning requirements, and licensing.
            *   **Finding:** If it is not an STR product, report "N/A - Not a Short-Term Rental product." If it is an STR product, report whether the required comments on regulations are present. If missing, flag for escalation.
            *   **Example:** "Failed: This is an STR product, but the report does not address local short-term rental regulations or licensing requirements. Please escalate." OR "Passed: This is an STR product, and the report addresses local regulations in the zoning addendum."

        ---
        **Rules for "CV3 Financial"**
        *(If client is CV3, apply these. For other clients' fields, use "N/A")*

        - **Borrower Name Handling (CV3):**
            *   **Action:** Check the "Borrower" field in the "Subject" section. It should contain an entity name (e.g., end with "LLC", "Inc.", "Corp.", etc.). Then, search the report addenda for a comment mentioning the "individual borrower's name".
            *   **Finding:** Report if the borrower field contains an entity name and if the addendum comment for the individual borrower is present.
            *   **Example:** "Passed: Borrower field is an entity ('Lindsey Estates LLC') and a comment for the individual borrower was found in the addendum." OR "Failed: The 'Borrower' field contains an individual's name, not an entity name. It should be the entity name, with the individual's name in an addendum." OR "Failed: The 'Borrower' field is an entity, but no comment was found in the addendum for the individual borrower."

        - **Freddie Unacceptable Practices Review:**
            *   **Action:** This is an informational check. This rule also applies to CIVIC.
            *   **Finding:** Report that this review is not required for CV3.
            *   **Example:** "N/A - Freddie Unacceptable Practices review is not required for CV3."

        ---
        **Rules for "Nationwide Mortgage Bankers, Inc."**
        *(If client is Nationwide, apply these. For other clients' fields, use "N/A")*

        - **Hurricane Damage Statement (FL):**
            *   **Action:** First, determine if the property state is 'FL'. If it is, search the report for any mention of "Hurricane Helene" or "Hurricane Milton".
            *   **Finding:** If the state is not FL, report "N/A - Property not in FL." If the state is FL, report whether a statement about damage from these hurricanes is present or missing.
            *   **Example:** "Failed: Property is in FL, but the report does not address damage from Hurricane Helene or Milton." OR "Passed: Property is in FL, and the report confirms no damage from recent hurricanes."

        - **Hurricane Damage Statement (GA, NC, SC, TN, VA):**
            *   **Action:** First, determine if the property state is one of 'GA', 'NC', 'SC', 'TN', or 'VA'. If it is, search the report for any mention of "Hurricane Helene".
            *   **Finding:** If the state is not in this list, report "N/A - Property not in the specified states." If the state is in the list, report whether a statement about damage from this hurricane is present or missing.
            *   **Example:** "Failed: Property is in GA, but the report does not address damage from Hurricane Helene." OR "Passed: Property is in GA, and the report confirms no damage from Hurricane Helene."

        ---
        **Rules for "Logan Finance Corporation / Logan Finance"**
        *(If client is Logan Finance, apply these. For other clients' fields, use "N/A")*

        - **Smoke/CO Detector and Photos (Logan Finance):**
            *   **Action:** Search the report (especially "Improvements" section, addenda, and photo descriptions) for comments about the presence of smoke and carbon monoxide (CO) detectors. Also, review all photos to find images of these detectors.
            *   **Finding:** Report whether both commentary and photos for smoke/CO detectors are present. If either is missing, it is a failure.
            *   **Example:** "Passed: Report includes comments on smoke/CO detectors and photos are present." OR "Failed: Report does not mention smoke/CO detectors, and no photos were found. Please confirm if present/required and include photos."

        ---
        **Rules for "New American Funding, LLC" (NAF)**
        *(If client is NAF, apply these. For other clients' fields, use "N/A")*

        - **1004MC Requirement (NAF):**
            *   **Action:** This is an informational check for the reviewer.
            *   **Finding:** Populate this field with the instruction: "Info: A 1004MC form is not required for New American Funding."
            *   **Example:** "Info: A 1004MC form is not required for New American Funding."

        - **Health and Safety Issues (NAF):**
            *   **Action:** Search the report for any mention of health and safety issues (e.g., "exposed wiring", "missing handrail", "peeling paint", "smoke detectors", "water heater straps"). If any such issues are found, check if the report is made "subject to" their repair in the Reconciliation section.
            *   **Finding:** Report if health and safety issues are found and whether they are correctly made "subject to repair".
            *   **Example:** "Passed: Peeling paint was noted and the report is correctly made 'subject to repair'." OR "Failed: Missing smoke detectors were noted, but the report is made 'as is'. It should be 'subject to repair'." OR "Passed: No health and safety issues were noted."

        - **Reviewer Instructions (NAF):**
            *   **Action:** This is an informational check for the reviewer.
            *   **Finding:** Populate this field with the following instruction: "ROV Handling: For Coast to Coast (C2C) and Fastapp orders, if this is a revised report for an ROV, review it but DO NOT COMPLETE. Escalate with the message 'ROV is good to go' and wait for approval to complete."
            *   **Example:** "ROV Handling: For Coast to Coast (C2C) and Fastapp orders, if this is a revised report for an ROV, review it but DO NOT COMPLETE. Escalate with the message 'ROV is good to go' and wait for approval to complete."

        ---
        **Rules for "Haus Capital Corp"**
        *(If client is Haus Capital, apply these. For other clients' fields, use "N/A")*

        - **'Subject-To' Condition Advisory (Haus Capital):**
            *   **Action:** Check the "Reconciliation" section to see if the appraisal is made "subject to" any conditions (repairs, completion, etc.).
            *   **Finding:** If the report is made "subject to", populate this field with an advisory message for the reviewer. If it is "as is", report that no advisory is needed.
            *   **Example:** "Advisory: The report is made 'Subject To'. Please advise." OR "Passed: The report is made 'as is', no advisory needed."

        **Fields to Verify:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example JSON Output (if Lender is Ice Lender):**
        {{
            "Report Condition (As Is)": "Passed: Report is made 'as is'.",
            "Repairs with 'As Is' Condition": "N/A - Rule does not apply to this client.",
            "STR Comps for 1007 STR": "N/A - Rule does not apply to this client.",
            "Occupancy for 1007 Orders": "N/A - Rule does not apply to this client.",
            "Smoke/CO Detector Installation and Photos": "N/A - Rule does not apply to this client.",
            "Smoke/CO Detector Presence (BPL)": "N/A - Rule does not apply to this client.",
            "Invoice in Report (NY Only)": "N/A - Rule does not apply to this client.",
            "As-Is Value Order (2-Value Reports)": "N/A - Rule does not apply to this client.",
            "Hurricane Damage Statement (FL)": "N/A - Rule does not apply to this client.",
            "Intended User Statement (Equity Wave)": "N/A - Rule does not apply to this client.",
            "Intended Use Statement (Equity Wave)": "N/A - Rule does not apply to this client.",
            "Health and Safety Subject To (Rain City)": "N/A - Rule does not apply to this client.",
            "2-Value Report Format (Rain City)": "N/A - Rule does not apply to this client.",
            "Cost to Cure for Cosmetic Items (Rain City)": "N/A - Rule does not apply to this client.",
            "1004MC Requirement (Rain City)": "N/A - Rule does not apply to this client.",
            "Cost Approach Requirement (East Coast Capital)": "N/A - Rule does not apply to this client.",
            "Report Completion Basis (Malama Funding)": "N/A - Rule does not apply to this client.",
            "ARV Comps Gridded (Malama Funding)": "N/A - Rule does not apply to this client.",
            "As-Is Comps and Value Comments (Malama Funding)": "N/A - Rule does not apply to this client.",
            "ENV Requirement (Kind Lending)": "N/A - Rule does not apply to this client.",
            "1004MC Requirement (Kind Lending)": "N/A - Rule does not apply to this client.",
            "As-is with ARV Report Condition (Futures Financial)": "N/A - Rule does not apply to this client.",
            "Desktop Report Condition (Futures Financial)": "N/A - Rule does not apply to this client.",
            "ENV Requirement (Dart Bank)": "N/A - Rule does not apply to this client.",
            "E&O Insurance Attached (Champions)": "N/A - Rule does not apply to this client.",
            "Value vs. Predominant Value (Champions)": "N/A - Rule does not apply to this client.",
            "Smoke/CO Detector Check (Champions)": "N/A - Rule does not apply to this client.",
            "Stove in Kitchen Photo (Champions)": "N/A - Rule does not apply to this client.",
            "1004MC Requirement (Deephaven)": "N/A - Rule does not apply to this client.",
            "Desk Review Escalation (Eastview)": "N/A - Rule does not apply to this client.",
            "Desk Review Form Type (Eastview)": "N/A - Rule does not apply to this client.",
            "QC Ratings Requirement (Loanguys)": "N/A - Rule does not apply to this client.",
            "Prior Services Statement (National Loan/Easy Street)": "N/A - Rule does not apply to this client.",
            "Appraiser Fee Paid Status (Rain City)": "N/A - Rule does not apply to this client.",
            "STR 1007 Form Requirement (Foundation Mortgage)": "N/A - Rule does not apply to this client.",
            "'Subject-To' Condition Advisory (Haus Capital)": "N/A - Rule does not apply to this client.",
            "1004MC Requirement (NAF)": "N/A - Rule does not apply to this client.",
            "Health and Safety Issues (NAF)": "N/A - Rule does not apply to this client.",
            "Reviewer Instructions (NAF)": "N/A - Rule does not apply to this client.",
            "Smoke/CO Detector and Photos (Logan Finance)": "N/A - Rule does not apply to this client.",
            "Hurricane Damage Statement (GA, NC, SC, TN, VA)": "N/A - Rule does not apply to this client.",
            "Borrower Name Handling (CV3)": "N/A - Rule does not apply to this client.",
            "Reviewer Instructions (The Loan Store)": "N/A - Rule does not apply to this client.",
            "Short-Term Rental Regulations (Arc Home)": "N/A - Rule does not apply to this client.",
            "Reviewer Instructions (Paramount)": "N/A - Rule does not apply to this client.",
            "Smoke/CO Detector Comments (OCMBC)": "N/A - Rule does not apply to this client.",
            "Water Heater Strapping Comments (OCMBC)": "N/A - Rule does not apply to this client.",
            "1004MC Requirement (Cardinal)": "N/A - Rule does not apply to this client.",
            "Value vs. Purchase Price (GFL)": "N/A - Rule does not apply to this client.",
            "Double Strapped Water Heater (UT Only)": "N/A - Rule does not apply to this client.",
            "Reviewer Instructions (LoanDepot)": "N/A - Rule does not apply to this client.",
            "Report Completion Basis (Temple View)": "N/A - Rule does not apply to this client.",
            "ARV Comps Gridded (Temple View)": "N/A - Rule does not apply to this client.",
            "As-Is Comps and Value Comments (Temple View)": "N/A - Rule does not apply to this client.",
            "Freddie Unacceptable Practices Review": "N/A - Rule does not apply to this client.",
            "Occupancy for 1025 Form": "N/A - Rule does not apply to this client.",
            "Value vs. Listing/Contract Price (10% Rule)": "Failed: Final Value ($335k) is 11.7% higher than Contract Price ($300k).",
            "USPAP Compliance Addendum": "Passed: USPAP Compliance Addendum found on page 15.",
            "FIRREA Statement": "Failed: FIRREA compliance statement is missing.",
            "Required Photographs (Mechanicals, Kitchen, Roof)": "Passed: Photos for kitchen, roof, and HVAC are present.",
            "Kitchen Photo Refrigerator Check": "Passed: Refrigerator is visible in the kitchen photo.",
            "Comparable Distance Guideline (Urban)": "N/A - Market is not Urban.",
            "Comparable Distance Guideline (Suburban)": "Failed: Comp 2 (3.5 miles) exceeds the 3-mile guideline for a Suburban area.",
            "Comparable Distance Guideline (Rural)": "N/A - Market is not Rural.",
            "Increase in Value Since Prior Sale": "N/A - Rule does not apply to this client.",
            "Cost to Cure for Repairs": "N/A - Rule does not apply to this client.",
            "Cost Approach Completion": "N/A - Rule does not apply to this client.",
            "Room Photo Requirement (2 per room)": "N/A - Rule does not apply to this client.",
            "Bedroom Photo Labeling": "N/A - Rule does not apply to this client.",
            "Comparable Distance Guideline (Urban/Suburban - BPL)": "N/A - Rule does not apply to this client.",
            "Comparable Distance Guideline (Rural - BPL)": "N/A - Rule does not apply to this client.",
            "Multi-Family Unit Count Consistency": "N/A - Rule does not apply to this client.",
            "Heating System Functionality": "N/A - Rule does not apply to this client.",
            "Quality and Condition Ratings (Q/C)": "N/A - Rule does not apply to this client.",
            "Client Email Address Present": "N/A - Rule does not apply to this client.",
            "SSR Score Check": "N/A - Rule does not apply to this client."
        }}
        """
    elif section_name.lower() == 'escalation_check':
        prompt = f"""You are an expert AI assistant for real estate appraisal quality control. Your task is to perform a series of critical escalation checks by comparing information from an external "Order Form" and other documents against the main appraisal report PDF.

        You will be provided with external data from various sources as a JSON object within this prompt.

        Your output must be a single, valid JSON object where the keys are the full text of the escalation checks listed below, and the values are your findings.

        **Instructions:**
        1.  **Analyze All Provided Data:** You will receive a JSON object containing structured data from the 'Order Form', the 'Appraisal Report' itself, and optionally from a 'Purchase Contract' and 'Engagement Letter'. Use all available data to perform your checks.
        2.  **Verify Each Check:** For each item in the "Escalation Checks to Perform" list, analyze and compare the relevant data points from the provided JSON.
        3.  **Format Your Findings:**
            *   If a check **passes** (no issue found), the value must be a string starting with "Passed:", followed by a brief explanation.
            *   If a check **fails** (an issue is found), the value must be a string starting with "Failed:", followed by a clear explanation of the discrepancy, citing the conflicting values and their sources (e.g., "Order Form vs. Report").
            *   If a check is **not applicable** (e.g., a purchase-related check on a refinance order), the value must be "N/A: [Reason]".

        ---
        **External Data Provided by User (Example Structure):**
        {{
            "order_form_data": {{ "Assignment Type": "Purchase", "Appraisal Type": "1004+1007", ... }},
            "appraisal_report_data": {{ "subject": {{...}}, "improvements": {{...}}, "reconciliation": {{...}}, ... }},
            "purchase_contract_data": {{ "Contract Price $": "500,000", ... }},
            "engagement_letter_data": {{ "Appraiser Fee": "$450", ... }}
        }}
        ---

        **Detailed Logic for Checks:**

        - **Assignment Type Mismatch:** Compare Order Form "Assignment Type" with the "Assignment Type" field in the report's Subject section.
        - **Appraisal Type Mismatch:** Compare `order_form_data['Appraisal Type']` with the form number (e.g., 1004, 1025) from `appraisal_report_data['appraisal_id']['This Report is one of the following types:']`.
        - **Appraiser Name Mismatch:** Compare `order_form_data['Assigned to Vendor(s)']` with `appraisal_report_data['certification']['Name']`.
        - **Repairs vs. 'As-Is' Condition:**
            1.  Analyze all photos and text comments for evidence of needed repairs (e.g., "peeling paint", "broken window", "water damage", "deferred maintenance").
            2.  Check the Reconciliation section for the appraisal condition ('as is' or 'subject to').
            3.  If repairs are evident but the condition is 'as is', this is a failure.
        - **Appraiser as Supervisor:** Check if the Order Form "Appraiser Name" appears in the "Supervisory Appraiser" signature block instead of the primary appraiser block. Also check against the name in the Engagement Letter if provided.
        - **Lender Name Change:** Find the "Lender/Client" name in the report's Subject and Certification sections. Report if it has been changed from the expected name (e.g., "Easy Street Capital").
        - **Fee Mismatch:** Compare `engagement_letter_data['Appraiser Fee']` with any fee mentioned in the appraisal report, particularly in an invoice or addendum.
        - **'Average' Condition Comment:** Search the "Neighborhood Description" for the exact phrase "average condition". If found, it's a failure.
        - **Value vs. List/Purchase/Prior Sale:** Find the final "Opinion of Market Value". Compare it against the "Contract Price" (Contract section), "Listing Price" (if any), and "Price of Prior Sale/Transfer" (Sale History section). Report if the final value is higher than all of these.
        - **1004D Mismatches:** For 1004D forms, verify if the report includes "Final Inspection" and/or "Appraisal Update" and if this matches `order_form_data['Appraisal Type']`.
        - **Loan/Appraisal Type Mismatch (USDA/FHA):** Compare the Order Form "Loan Type" with the appraisal form type used (e.g., a USDA loan should not be on an FHA form).
        - **'Illegal' Zoning/Use:** Search the entire report for the word "Illegal", especially in the "Site" section under "Zoning Compliance". If found, it's a failure.
        - **Multiple Kitchens:** If the form is a 1004 (single-family), search the "Improvements" section and photos for evidence of more than one kitchen. If found, verify if there is a comment addressing whether the additional kitchens are permitted.
        - **Effective Date vs. Inspection Date:** Compare the Order Form "Inspection Date" with the "Effective Date of Appraisal" in the Reconciliation/Certification sections. The effective date should typically match or be very close to the inspection date.
        - **Value vs. Unadjusted Sales Price:** Find the final "Opinion of Market Value". Find the "Sale Price" for each comparable in the sales grid. Calculate if the final value is more than 10% higher than the *lowest* unadjusted comp sale price.
        - **Drastic Adjustments:** In the sales grid, review all adjustment columns. Flag any single adjustment that seems unusually large relative to the sale price (e.g., a $50,000 adjustment on a $200,000 home).
        - **Subject Location as 'Commercial':** In the sales grid, check the "Location" row for the Subject property. If it is marked "Commercial", it is a failure.
        - **Value Higher than Purchase Price:** For purchase transactions, if the "Opinion of Market Value" is higher than the "Contract Price", verify that a comment explaining this difference exists in the report.
        - **Increase in Value Since Prior Sale:** If the "Opinion of Market Value" is significantly higher than a recent "Price of Prior Sale/Transfer", verify that a comment explaining the increase (e.g., due to renovations or market changes) exists.
        - **Address Duplication:** Check if the subject property's address is used as a comparable sale or rental comparable. This is a failure.
        - **Highest and Best Use 'NO':** In the "Site" section, find the question "Is the highest and best use...". If the answer is "No", it is a failure.
        - **Physical Deficiencies 'YES' vs. 'As-Is':** In the "Improvements" section, find the question "Are there any physical deficiencies...". If the answer is "Yes" but the report is made "as-is" in the Reconciliation section, it is a failure.
        - **Time Adjustments Commentary:** If any `Date of Sale/Time Adjustment` is present in the sales grid, search the report (especially addenda) for a detailed comment explaining how the adjustment was derived, referencing market data.

        **Escalation Checks to Perform:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example JSON Output:**
        {{
            "The order form indicates Assignment Type as ‘Purchase’ however the report is marked on Refinance transaction, please verify.": "Failed: Mismatch found. Order form is 'Purchase', but the report's Assignment Type is 'Refinance Transaction'.",
            "The order form shows appraisal type as 1004+1007 however the report is completed on 1025, please advise.": "Passed: Report is correctly completed on Form 1004 and includes a 1007 addendum.",
            "Per the photos, the subject has multiple repairs however the report made As-is, please advise.": "Failed: Photos on page 8 show significant peeling paint on the exterior, but the report is made 'as-is' in the Reconciliation section.",
            "The final value is higher than list price, purchase price and prior sale price, please advise.": "Passed: Final value of $550,000 is bracketed by the contract price of $545,000 and the listing price of $555,000.",
            "If the highest and best use is marked NO then escalate as: Highest and best use is marked NO, please refer the snap and advise": "Passed: Highest and best use is marked 'Yes' in the Site section."
        }}
        """

    elif section_name.lower() == 'revision_check':
        prompt = f"""
        You are an expert AI assistant specializing in real estate appraisal review.
        You have been given a revised appraisal report and the original rejection reason.
        Your task is to determine if the rejection reason has been addressed in the revised report.

        **Original Rejection Reason:**
        "{custom_prompt}"

        **Your Task:**
        1.  Carefully read the rejection reason to understand what needed to be fixed.
        2.  Thoroughly analyze the provided revised appraisal report PDF to find where the correction was made.
        3.  Provide a structured JSON response summarizing your findings.

        **JSON Output Format:**
        Your output must be a single, valid JSON object with the following keys:
        - `"status"`: A string, either "Corrected", "Partially Corrected", or "Not Corrected".
        - `"summary"`: A one-sentence summary of your conclusion.
        - `"details"`: A detailed explanation of your findings. Describe what you looked for, what you found (or didn't find), and on which page or section the change is located.

        **Example JSON Output:**
        {{
            "status": "Corrected",
            "summary": "The borrower's name has been successfully corrected in the Subject section.",
            "details": "The rejection reason stated that the borrower's name was misspelled. I have verified on page 1 in the 'Subject' section that the borrower's name has been updated from 'Jhon Doe' to 'John Doe', which resolves the issue."
        }}
        {{
            "status": "Not Corrected",
            "summary": "The missing cost approach was not added to the revised report.",
            "details": "The rejection reason required the Cost Approach to be completed. I have scanned the entire revised document and confirmed that the Cost Approach section on page 3 remains blank. The revision has not been addressed."
        }}
        """

    elif section_name.lower() == 'reconciliation':
        prompt = f"""
        You are an expert at extracting information from the "Reconciliation" section of a real estate appraisal report.
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object where the keys are the field names and the values are the extracted data.

        **Instructions:**
        1.  **Be Thorough:** Extract data for every field listed.
        2.  **Use Null for Missing Data:** If a field is not found, is not applicable, or has no value, use `null` as its value.
        3.  **Specific Extraction for Market Value:**
            *   Find the long sentence that states "...my (our) opinion of the market value... is $_______, as of ________...".
            *   From this sentence, extract only the dollar amount (e.g., "550,000") into the `"Opinion of Market Value $"` field. This value is sometimes also labeled "Appraised Value".
            *   Extract the date (e.g., "05/20/2024") into the `"Effective Date of Value"` field.

        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "Indicated Value by: Sales Comparison Approach $": "550,000",
            "Opinion of Market Value $": "550,000",
            "Effective Date of Value": "05/20/2024",
            "...": "..."
        }}
        """
    elif section_name.lower() == 'report_details':
        prompt = f"""
        You are an expert AI assistant specializing in real estate appraisal report review.
        Your task is to scan the entire document and verify if specific sections and comments are present.

        Your output must be a single, valid JSON object where the keys are the field names listed below.
        The value for each key must be either "Present" or "Missing".

        **Instructions:**
        1.  **Be Thorough:** For each field in the list, search the entire PDF document.
        2.  **Check for Presence:** If you find a section, header, or comment that matches the field name, its value in the JSON should be "Present".
        3.  **Mark as Missing:** If you cannot find any content corresponding to a field name after searching the entire document, its value must be "Missing".

        **Fields to Verify:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example JSON Output:**
        {{ "SCOPE OF WORK:": "Present", "SUPPLEMENTAL ADDENDUM": "Missing", "Reasonable Exposure Time": "Present", ... }}
        """
    elif section_name.lower() == 'certification':
        prompt = f"""
        You are an expert at extracting information from the "Appraiser's Certification" section of a real estate appraisal report. You must also find the appraiser's license, which is often attached as one of the last pages of the document.
        Additionally, you must find the E&O (Errors and Omissions) insurance policy document, which is also typically attached.

        Your output must be a single, valid JSON object.

        **Instructions:**
        1.  **Extract Certification Data:** From the main "Appraiser's Certification" page, extract the values for the standard certification fields.
        2.  **Find and Extract License Data:** Search the document (usually near the end) for an image or page that is the appraiser's state license. From this license, extract the following details:
        3.  **Find and Extract E&O Insurance Data:** Search the document for the E&O insurance declaration page. From this page, extract the policy's expiration date.
        4.  **Use Null for Missing Data:** If any field from the certification, license, or E&O document is not found, is not applicable, or has no value, use `null` as its value. If no license or E&O page is found, all their respective fields must be `null`.
            *   The appraiser's full name as it appears on the license.
            *   The license number.
            *   The state that issued the license.
            *   The expiration date of the license.
        3.  **Use Null for Missing Data:** If any field from the certification or the license is not found, is not applicable, or has no value, use `null` as its value. If no license page is found in the document, all license-specific fields must be `null`.

        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "Name": "John M. Appraiser",
            "State Certification # or State License #": "42RC00123400",
            "Expiration Date of Certification or License": "12/31/2025",
            "Appraiser Name on License": "John Michael Appraiser",
            "License Number on License": "42RC00123400",
            "License State on License": "NJ",
            "License Expiration Date on License": "12/31/2025",
            "E&O Expiration Date on Document": "06/30/2026",
            "...": "..."
        }}
        """
    elif section_name.lower() == 'd1004':
        prompt = f"""
        You are an expert at extracting information from appraisal update and completion reports, specifically Form 1004D.
        Analyze the provided PDF document and extract the values for all fields listed below.

        Your output must be a single, valid JSON object where the keys are the field names and the values are the extracted data.

        **Instructions:**
        1.  **Be Thorough:** Extract data for every field listed.
        2.  **Use Null for Missing Data:** If a field is not found, is not applicable, or has no value (e.g., '--', 'N/A', or blank), use `null` as its value.
        3.  **Handle Checkboxes:**
            *   For fields like "SUMMARY APPRAISAL UPDATE REPORT (checkbox)" and "CERTIFICATION OF COMPLETION (checkbox)", if the box is checked, extract "Yes". If it is not checked, extract "No".
        4.  **Handle Yes/No Questions:**
            *   For questions like "HAS THE MARKET VALUE... DECLINED..." and "HAVE THE IMPROVEMENTS BEEN COMPLETED...", extract the "Yes" or "No" answer.
            *   If the answer to "HAVE THE IMPROVEMENTS BEEN COMPLETED..." is "No", you must extract the explanation into the "If No, describe the impact on the opinion of market value" field. If the answer is "Yes", this field should be `null`.

        **Fields to Extract:**
        {json.dumps(fields_to_extract, indent=2)}

        **Example of the final JSON structure:**
        {{
            "Property Address": "123 Main St",
            "Original Appraised Value $": "500,000",
            "SUMMARY APPRAISAL UPDATE REPORT (checkbox)": "Yes",
            "HAS THE MARKET VALUE OF THE SUBJECT PROPERTY DECLINED SINCE THE EFFECTIVE DATE OF THE PRIOR APPRAISAL? (Yes/No)": "No",
            "CERTIFICATION OF COMPLETION (checkbox)": "No",
            "HAVE THE IMPROVEMENTS BEEN COMPLETED IN ACCORDANCE WITH THE REQUIREMENTS AND CONDITIONS STATED IN THE ORIGINAL APPRAISAL REPORT? (Yes/No)": null,
            "If No, describe the impact on the opinion of market value": null,
            "...": "..."
        }}
        """
    else:
        prompt = f"""
        You are an expert at extracting information from appraisal reports.
        Analyze the provided PDF document and extract the values for the following fields for the '{section_name}' section.
        Return the result as a single, valid JSON object. The keys of the JSON object should be the field names,
        and the values should be the extracted data from the document.
        If a field is not found or its value cannot be determined, use `null` as its value.

        Fields to extract:
        {json.dumps(fields_to_extract, indent=2)}
        """
    

    uploaded_files_for_prompt = []
    try:
        # Upload all provided PDF files
        for path in pdf_paths:
            if not os.path.exists(path):
                logger.warning(f"File not found during extraction: {path}")
                continue
            
            uploaded_file = await asyncio.to_thread(
                client.files.upload,
                file=path
            )
            uploaded_files_for_prompt.append(uploaded_file)

        # Wait for all files to be active
        for i, uploaded_file in enumerate(uploaded_files_for_prompt):
            while uploaded_file.state.name == "PROCESSING":
                logger.info(f"Waiting for file {uploaded_file.name} to be processed...")
                await asyncio.sleep(10)
                uploaded_file = await asyncio.to_thread(client.files.get, name=uploaded_file.name)
                uploaded_files_for_prompt[i] = uploaded_file # Update the list with the new status

            if uploaded_file.state.name != "ACTIVE":
                logger.error(f"File {uploaded_file.name} is not in an ACTIVE state. Current state: {uploaded_file.state.name}")
                return {"error": f"File processing failed for {uploaded_file.name}. State: {uploaded_file.state.name}"}
            logger.info(f"File {uploaded_file.name} is now ACTIVE.")

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[*uploaded_files_for_prompt, prompt],
        )

        # The model's response text should be a JSON string. We parse it into a Python dict.
        # We also clean up potential markdown code fences.
        cleaned_text = response.text.strip().lstrip("```json").rstrip("```")
        return json.loads(cleaned_text)

    except (google_exceptions.GoogleAPIError, json.JSONDecodeError, Exception) as e:
        logger.error(f"An error occurred during PDF extraction: {e}", exc_info=True)
        # Return an error dictionary that can be displayed to the user
        return {"error": f"An error occurred during extraction: {str(e)}"}  