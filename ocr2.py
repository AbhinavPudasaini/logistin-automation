from unstract.llmwhisperer import LLMWhispererClientV2
from unstract.llmwhisperer.client_v2 import LLMWhispererClientException
import re


# def call_ocr(path:str):
#     try:
#         whisper = client.whisper(
#             file_path=f"{path}",
#             wait_for_completion=True,
#             wait_timeout=200,
#             mode="table"
#         )

#         return whisper

#     except LLMWhispererClientException as e:
#         print("OCR failed:", e)
#         raise

# -------------------------------
# 1️⃣ REBUILD CLEAN TEXT
# -------------------------------

def normalize_text(text: str) -> str:
    text = text.replace("\x0c", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def rebuild_text_from_lines(result_text, line_metadata):
    """
    Uses vertical position only (since x is unavailable)
    """
    lines = result_text.split("\n")

    merged = list(zip(line_metadata, lines))

    # Sort top → bottom using base_y
    merged.sort(key=lambda x: x[0][1])

    rebuilt = []
    prev_y = None

    for meta, line in merged:
        page, base_y, height, page_height = meta
        line = line.strip()

        if not line:
            continue

        # Detect section breaks using vertical gaps
        if prev_y is not None and (base_y - prev_y) > (height * 1.3):
            rebuilt.append("")

        rebuilt.append(line)
        prev_y = base_y

    return normalize_text("\n".join(rebuilt))


def process_invoice_image(file_path: str) -> str:
    """
    Process an invoice/receipt image using OCR.
    Uses LLMWhisperer from ocr2.py logic.
    
    Args:
        file_path: Path to the image/invoice file
        
    Returns:
        Extracted text from the image
    """
    
    from unstract.llmwhisperer import LLMWhispererClientV2
    from unstract.llmwhisperer.client_v2 import LLMWhispererClientException
    import re
    # Initialize the client
    client = LLMWhispererClientV2(
        api_key="api"
    )
    
    try:
        whisper = client.whisper(
            file_path=file_path,
            wait_for_completion=True,
            wait_timeout=200,
            mode="table"
        )
        print("this is whisper : ", whisper)
    except LLMWhispererClientException as e:
        print("OCR failed:", e)
        raise
    
    # Normalize and rebuild text
    def normalize_text(text: str) -> str:
        text = text.replace("\x0c", "")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def rebuild_text_from_lines(result_text, line_metadata):
        lines = result_text.split("\n")
        merged = list(zip(line_metadata, lines))
        merged.sort(key=lambda x: x[0][1])
        
        rebuilt = []
        prev_y = None

        for meta, line in merged:
            page, base_y, height, page_height = meta
            line = line.strip()
 
            if not line:
                continue

            if prev_y is not None and (base_y - prev_y) > (height * 1.3):
                rebuilt.append("")

            rebuilt.append(line)
            prev_y = base_y

        return normalize_text("\n".join(rebuilt))
    
    clean_text = rebuild_text_from_lines(
        whisper["extraction"]["result_text"],
        whisper["extraction"]["line_metadata"]
    )
    
    return clean_text

# clean_text = rebuild_text_from_lines(
#     whisper["extraction"]["result_text"],
#     whisper["extraction"]["line_metadata"]
# )

print("\n======= CLEAN OCR TEXT =======\n")

# -------------------------------
# 2️⃣ STRUCTURED EXTRACTION (LLM-READY)
# -------------------------------

# def extract_invoice_fields(text: str) -> dict:
#     """
#     Lightweight rule + anchor extraction.
#     Can later be replaced by LLM JSON extraction.
#     """

#     def find(pattern):
#         m = re.search(pattern, text, re.IGNORECASE)
#         return m.group(1).strip() if m else None

#     return {
#         "receipt_number": find(r"No\.\s*([A-Z0-9]+)"),
#         "payment_mode": find(r"\b(Online|Cash|UPI|Card)\b"),
#         "utr_number": find(r"UTRNO[:\s]*([A-Z0-9]+)"),
#         "date": find(r"Date[:\s]*([0-9./-]+)"),
#         "amount_numeric": find(r"Rs\.?\s*([0-9,]+)"),
#         "amount_words": find(r"Rupees\s+(.*?)\s+only"),
#         "payer_name": find(r"from\s+Mr\.\s*/\s*Mrs\.\s*(.*)"),
#         "address": find(r"Address[:\s]*(.*)"),
#         "purpose": find(r"towards\s+(.*)")
#     }


# invoice_data = extract_invoice_fields(clean_text)

# print("\n======= EXTRACTED DATA =======\n")
# for k, v in invoice_data.items():
#     print(f"{k}: {v}")
