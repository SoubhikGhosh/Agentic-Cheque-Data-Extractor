# ==============================================================================
# File: prompts.py
# ==============================================================================
# This file stores the detailed field descriptions and the main prompt template.

def get_prompt_for_fields(field_names):
    """
    Constructs a detailed prompt for the specified field names.
    """
    field_descriptions = {
        "date": (
            "**Objective:** Extract the issue date and standardize it.\n"
            "**Primary Location Strategy:** Target the **top-right corner**, typically within designated DD MM YYYY boxes.\n"
            "**Output Format:** **Strictly YYYY-MM-DD.** Convert all valid inputs to this format."
        ),
        "amount_numeric": (
            "**Objective:** Extract the cheque amount written in figures (courtesy amount).\n"
            "**Primary Location Strategy:** Target the designated box or area on the **right-middle side**.\n"
            "**Extraction Method:** Remove any currency symbols (₹, $), thousands separators (,), and trailing characters ('/-').\n"
            "**Output:** The cleaned, purely numeric amount string (e.g., '1500.00', '12000')."
        ),
    }

    fields_to_include = [f'"{name}":\n{field_descriptions[name]}' for name in field_names if name in field_descriptions]
    fields_list_str = "\n\n".join(fields_to_include)

    extraction_prompt = f"""You are an expert AI assistant for high-accuracy information extraction from scanned cheque images. Your task is to meticulously analyze the provided image and extract specific fields.

**Core Objective:** Extract the following fields from the cheque image: {', '.join(field_names)}.

**Field Definitions & Extraction Guidelines:**

{fields_list_str}

**Confidence Scoring:**
- Assign a confidence score (float, 0.00 to 1.00) for each extracted field.
- **Mandatory:** Provide a brief justification for any score below 0.95.

**Error Handling:**
- If a field cannot be found, set its value to `null` and assign a low confidence score (< 0.5).

**Output Format:**
- Your response **MUST** be a single, valid JSON object.
- **Do NOT** include any explanatory text or markdown formatting.
- The JSON must have a top-level key `"extracted_fields"`: an array of objects.
- Each object must contain: `"field_name"`, `"value"`, `"confidence"`, `"text_segment"`, and `"reason"`.

**Example of one object in the array:**
{{
    "field_name": "amount_numeric",
    "value": "1500.00",
    "confidence": 0.98,
    "text_segment": "1500/-",
    "reason": null
}}

IMPORTANT: Your response must be a valid JSON object starting with {{ and ending with }} and NOTHING ELSE.
"""
    return extraction_prompt
