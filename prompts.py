# ==============================================================================
# File: prompts.py
# ==============================================================================
# No changes are needed in this file.

def get_extraction_from_crop_prompt(field_name):
    """
    Creates a prompt that asks Gemini to extract data from a pre-cropped image.
    This includes the detailed instructions for the specific field.
    """
    field_descriptions = {
        "date": (
            "**Objective:** Extract the issue date and standardize it.\n"
            "**Note:** This image is a small crop focusing only on the date area.\n"
            "**Output Format:** **Strictly युवराज-MM-DD.** Convert all valid inputs to this format."
        ),
        "amount_numeric": (
            "**Objective:** Extract the cheque amount written in figures (courtesy amount).\n"
            "**Note:** This image is a small crop focusing only on the amount box.\n"
            "**Extraction Method:** Remove any currency symbols, thousands separators, and trailing characters.\n"
            "**Output:** The cleaned, purely numeric amount string (e.g., '1500.00', '12000')."
        ),
    }

    description = field_descriptions.get(field_name, "Extract the text content from this image.")

    extraction_prompt = f"""You are an expert AI assistant specializing in high-accuracy OCR from pre-cropped images.

**Objective:** Extract the `{field_name}` from this image.

**Field-Specific Guidelines:**
{description}

**Confidence Scoring:**
- Assign a confidence score (float, 0.00 to 1.00).
- Provide a brief justification for any score below 0.95.

**Output Format:**
- Your response **MUST** be a single, valid JSON object.
- It must contain: `"value"`, `"confidence"`, `"text_segment"`, and `"reason"`.

**Example Response:**
{{
    "value": "5000.00",
    "confidence": 0.99,
    "text_segment": "5,000/-",
    "reason": null
}}

IMPORTANT: Your response must be a valid JSON object and NOTHING ELSE.
"""
    return extraction_prompt
