import os
import glob
import re
import pdfplumber
import pandas as pd
import logging
import traceback
from django.db import transaction
from django.conf import settings
from .models import Recipe
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional
from django.core.cache import cache

# Configure logger for this module
logger = logging.getLogger("service_commercial.fiches_techniques.pages.services")

# Debug mode flag
DEBUG_MODE = getattr(settings, "RECIPE_DEBUG_MODE", True)
DETAILED_ERRORS = getattr(settings, "RECIPE_DETAILED_ERRORS", True)


HEADINGS = {
    "ingredients": [
        "ingredients / ingrédients",
        "ingredients list / liste des ingrédients",
        "ingredients",
        "ingrédients",
        "liste des ingrédients",
    ],
    "allergens": [
        "allergens / allergènes",
        "allergens list / liste des allergènes",
        "allergens",
        "allergènes",
        "liste des allergènes",
    ],
    "claims": ["claims / allégations", "claims", "allégations"],
    "nutrition": [
        "average nutritional values / valeurs nutritionnelles moyennes",
        "average nutrition declaration / déclaration nutritionnelle moyennes",
        "nutrition declaration / déclaration nutritionnelle",
        "valeurs nutritionnelles moyennes",
        "nutrition",
    ],
    "food_category": [
        "food category / catégorie de denrées alimentaires",
        "food category",
        "catégorie de denrées alimentaires",
    ],
}


# -----------------------------
# Helpers: PDF reading
# -----------------------------
def read_pdf_lines(pdf_path: str) -> List[str]:
    """
    Return a list of non-empty lines from the entire PDF, stripped of extra whitespace.
    (Kept for heading detection.)
    """
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                page_lines = text.splitlines()
                page_lines = [ln.strip() for ln in page_lines if ln.strip()]
                lines.extend(page_lines)
    return lines


def read_pdf_fulltext(pdf_path: str) -> str:
    """
    Return raw concatenated text of the PDF (page-by-page) preserving newlines.
    """
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def read_first_page_lines(pdf_path: str) -> List[str]:
    """
    Return non-empty, stripped lines of the FIRST page only.
    """
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            return []
        text = pdf.pages[0].extract_text() or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines


# -----------------------------
# Helpers: headings / sections
# -----------------------------
def heading_exists(lines: List[str], heading_key: str, headings_dict: Dict) -> bool:
    variants = headings_dict.get(heading_key, [])
    for line in lines:
        line_lower = line.lower()
        if any(var in line_lower for var in variants):
            return True
    return False


def _find_heading_positions(full_text: str, variants: List[str]) -> List[tuple]:
    positions = []
    low = full_text.lower()
    for var in variants:
        start = 0
        while True:
            idx = low.find(var, start)
            if idx == -1:
                break
            positions.append((idx, var))
            start = idx + len(var)
    positions.sort(key=lambda x: x[0])
    return positions


def find_section_text(
    full_text: str, heading_key: str, next_heading_key: str, headings_dict: Dict
) -> str:
    start_variants = headings_dict.get(heading_key, [])
    end_variants = headings_dict.get(next_heading_key, [])

    start_positions = _find_heading_positions(full_text, start_variants)
    if not start_positions:
        return ""
    start_idx = start_positions[0][0]

    after_heading = full_text.find("\n", start_idx)
    if after_heading == -1:
        after_heading = start_idx + len(start_positions[0][1])
    else:
        after_heading = after_heading + 1

    tail_text = full_text[after_heading:]
    end_positions = _find_heading_positions(tail_text, end_variants)
    if not end_positions:
        return tail_text.strip()

    end_idx_rel = end_positions[0][0]
    section = tail_text[:end_idx_rel]
    return section.strip()


def clean_text_inline(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# -----------------------------
# Language split: keep English paragraph
# -----------------------------
_FRENCH_CHARS = "éèêëàâîïôöùûüçœÉÈÊËÀÂÎÏÔÖÙÛÜÇŒ"
_FRENCH_CLUES = [
    r"\bde\b",
    r"\bdes\b",
    r"\bdu\b",
    r"\bet\b",
    r"\baux?\b",
    r"\blait\b",
    r"\bsoja\b",
    r"\bfruits?\s+à\s+coques\b",
    r"\bédulcorant\b",
    r"\bémulsifiant\b",
    r"\bcorrecteurs?\s+d['']acidité\b",
    r"\bharômes?\b",
]


def split_keep_english_paragraph(section_text: str) -> str:
    if not section_text:
        return ""

    text = section_text.replace("\r", "")
    paragraphs = re.split(r"\n\s*\n", text.strip())
    if len(paragraphs) >= 2:
        return clean_text_inline(paragraphs[0])

    idxs = []
    for ch in _FRENCH_CHARS:
        pos = text.find(ch)
        if pos != -1:
            idxs.append(pos)
    low = text.lower()
    for clue in _FRENCH_CLUES:
        m = re.search(clue, low)
        if m:
            idxs.append(m.start())
    if idxs:
        cut = max(0, min(idxs))
        candidate = text[:cut].strip()
        if candidate:
            return clean_text_inline(candidate)

    return clean_text_inline(text)


# -----------------------------
# Robust splitting & parsing utilities
# -----------------------------
def normalize_punctuation(s: str) -> str:
    if not s:
        return s
    s = s.replace("\uff1a", ":").replace("\ufe55", ":").replace("\u02d0", ":")
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("\xa0", " ")
    return s


def split_top_level(s: str, sep: str) -> list:
    parts = []
    buf = []
    depth = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == sep and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def find_top_level_colon(s: str) -> int:
    depth = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            return i
    return -1


def remove_label_prefix_top_level(elem: str) -> str:
    idx = find_top_level_colon(elem)
    if idx != -1:
        return elem[idx + 1 :].strip()
    return elem.strip()


def extract_parenthetical_chunks_recursive(elem: str):
    chunks = []
    main = elem
    pattern = re.compile(r"\(([^()]*)\)")
    while True:
        changed = False

        def _collect(m):
            inner = m.group(1).strip()
            if inner:
                chunks.append(inner)
            return ""

        new_main = pattern.sub(_collect, main)
        if new_main != main:
            main = new_main
            changed = True
        if not changed:
            break
    return main.strip(), chunks


def split_top_level_commas(s: str) -> list:
    return split_top_level(s, ",")


# -----------------------------
# Stopwords / cleaning / dedup
# -----------------------------
STOPWORDS = {
    "and",
    "or",
    "with",
    "without",
    "of",
    "the",
    "a",
    "an",
    "to",
    "from",
    "by",
    "for",
    "in",
    "on",
    "that",
    "which",
    "as",
    "is",
    "are",
    "be",
    "may",
    "made",
    "contains",
    "contain",
    "containing",
    "including",
    "include",
    "manufactured",
    "equipment",
    "processes",
    "processed",
    "see",
    "bold",
    "natural",
    "flavour",
    "flavor",
}

UNITS = {"g", "mg", "µg", "mcg", "kg", "kcal", "kj"}


def _remove_percentages_numbers_units(t: str) -> str:
    t = re.sub(r"\b\d+[.,]?\d*\s*%\b", "", t)
    t = re.sub(r"\b\d+[.,]?\d*\b", "", t)
    t = re.sub(r"\b(?:" + "|".join(UNITS) + r")\b", "", t, flags=re.IGNORECASE)
    return t


def _clean_keyword(token: str) -> str:
    t = token.strip().strip(".,;:()[]{}\"'" "'`´")
    t = t.replace("\xa0", " ")
    t = _remove_percentages_numbers_units(t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _is_stopword_like(tok: str) -> bool:
    low = tok.lower()
    if low in STOPWORDS:
        return True
    if not re.search(r"[A-Za-z]", low):
        return True
    return False


def _canonicalize_for_dedup(tok: str) -> str:
    low = tok.lower().strip()
    words = low.split()
    canon_words = []
    for w in words:
        if len(w) == 1:
            canon_words.append(w)
            continue
        w_clean = re.sub(r"[^\w\-]", "", w)
        if len(w_clean) > 3:
            if (
                w_clean.endswith("es")
                and not w_clean.endswith("ses")
                and not w_clean.endswith("xes")
            ):
                w_clean = w_clean[:-2]
            elif w_clean.endswith("s") and not w_clean.endswith("ss"):
                w_clean = w_clean[:-1]
        canon_words.append(w_clean)
    canon = " ".join(canon_words).strip()
    return canon


# -----------------------------
# Core keyword parser
# -----------------------------
def parse_keywords_from_paragraph(eng_paragraph: str) -> List[str]:
    if not eng_paragraph:
        return []

    txt = normalize_punctuation(eng_paragraph)
    raw_elems = split_top_level(txt, ";")
    if not raw_elems:
        raw_elems = [txt.strip()]

    keywords = []
    seen = set()

    def _push(tok: str):
        k = _clean_keyword(tok)
        if not k:
            return
        k = re.sub(
            r"^(and|with|contains|containing)\b[:\s]*", "", k, flags=re.IGNORECASE
        ).strip()
        if not k:
            return
        if _is_stopword_like(k):
            return
        canon = _canonicalize_for_dedup(k)
        if not canon:
            return
        if canon not in seen:
            seen.add(canon)
            keywords.append(k)

    def _split_and_push(piece: str):
        body = remove_label_prefix_top_level(piece)
        main_no_paren, paren_chunks = extract_parenthetical_chunks_recursive(body)

        main_no_paren = normalize_punctuation(main_no_paren)
        for part in split_top_level_commas(main_no_paren):
            subparts = [
                sp.strip()
                for sp in re.split(r"\band\b", part, flags=re.IGNORECASE)
                if sp.strip()
            ]
            if not subparts:
                subparts = [part.strip()]
            for sp in subparts:
                sp = remove_label_prefix_top_level(sp)
                _push(sp)

        for chunk in paren_chunks:
            chunk = normalize_punctuation(chunk)
            for sub in split_top_level(chunk, ";"):
                for sub2 in split_top_level_commas(sub):
                    pieces = [
                        p.strip()
                        for p in re.split(r"\band\b", sub2, flags=re.IGNORECASE)
                        if p.strip()
                    ]
                    if not pieces:
                        pieces = [sub2.strip()]
                    for p in pieces:
                        p = remove_label_prefix_top_level(p)
                        _push(p)

    for elem in raw_elems:
        if not elem:
            continue
        _split_and_push(elem)

    return keywords


# -----------------------------
# Domain-specific: Portion, Product ID & Name
# -----------------------------
def extract_portion_size(full_text: str) -> str:
    """
    Extract the portion/serving size (in grams) from a product data sheet.

    Robust to formats like:
      - "Portion : 1 sachet 25 g."
      - "Serving size : 1 packet 25 g."
      - "Serving size : 1 packet = 2 wafers : 40,4 g."
      - "Portion : 1 sachet = 2 gaufrettes : 40,4 g"

    Strategy:
      • Work line-by-line only on lines that contain 'Portion' or 'Serving size'.
      • On each such line, capture all occurrences of "<number> g" where 'g' is a unit,
        i.e. not followed by a letter (so it won't match 'gaufrettes').
      • Return the right-most match on the line.
    """
    if not full_text:
        return ""

    import re

    # Normalize weird spaces from PDFs
    text = full_text.replace("\u00a0", " ").replace(  # no-break space
        "\u202f", " "
    )  # narrow no-break space

    # Only keep lines that can possibly carry the info
    candidate_lines = []
    for line in text.splitlines():
        if re.search(r"\b(Portion|Serving\s*size)\b", line, flags=re.IGNORECASE):
            candidate_lines.append(line)

    # Pattern: number then 'g' as a **unit** (not the start of a word like gaufrettes)
    unit_pat = re.compile(r"(\d+(?:[,.]\d+)?)\s*g(?![A-Za-z])\.?", flags=re.IGNORECASE)

    # Search each candidate line; pick the **last** match on that line
    for line in candidate_lines:
        matches = unit_pat.findall(line)
        if matches:
            captured = matches[-1].strip().replace(",", ".")
            return f"{captured} g"

    # Fallback: scan entire text (still using the unit-safe pattern), pick the last
    matches = unit_pat.findall(text)
    if matches:
        captured = matches[-1].strip().replace(",", ".")
        return f"{captured} g"

    return ""


# STRICT ID pattern — now supports any leading letter (T, L, etc.)
_ID_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z]\d{3}[A-Z]\d{2}V\d{1,2}(?![A-Za-z0-9])")


def _looks_english(s: str) -> bool:
    """Heuristic: prefer a line without accented French letters."""
    return not bool(re.search(r"[éèêëàâîïôöùûüçœÉÈÊËÀÂÎÏÔÖÙÛÜÇŒ]", s))


def extract_product_id_and_name_from_header(pdf_path: str) -> tuple:
    """
    Reads ONLY the first page lines, finds ID with strict regex,
    then takes the nearest non-empty line above it as the English product name,
    skipping a likely French line if present.
    Returns (product_id, product_name_en) or (None, None) if not found.
    """
    lines = read_first_page_lines(pdf_path)
    if not lines:
        return None, None

    # Find first occurrence of the ID on the first page
    id_line_idx = -1
    product_id = None
    for i, ln in enumerate(lines):
        m = _ID_RE.search(ln.replace("\xa0", " ").replace("–", "-").replace("—", "-"))
        if m:
            product_id = m.group(0)
            id_line_idx = i
            break

    if not product_id:
        return None, None

    # Find English product name above ID line
    product_name = None
    for j in range(id_line_idx - 1, -1, -1):
        if not lines[j].strip():
            continue
        if _looks_english(lines[j]):
            product_name = lines[j].strip()
            break
    if not product_name:
        for j in range(id_line_idx - 1, -1, -1):
            if lines[j].strip():
                product_name = lines[j].strip()
                break

    return (product_id if product_id else None, product_name if product_name else None)


def extract_product_id_from_anywhere(text: str) -> Optional[str]:
    """
    Secondary fallback: search the whole text for the strict ID pattern.
    Returns None if not found (no random tokens).
    """
    m = _ID_RE.search(text.replace("\xa0", " ").replace("–", "-").replace("—", "-"))
    return m.group(0) if m else None


# -----------------------------
# Allergen-specific sanitization
# -----------------------------
def sanitize_allergens_sentence(text: str) -> str:
    if not text:
        return text
    t = text
    t = re.sub(r"\s*\(?\bsee\s+in\s+bold\b\)?\s*", " ", t, flags=re.IGNORECASE)
    m = re.search(r"\bmanufactured\s+on\b", t, flags=re.IGNORECASE)
    if m:
        t = t[: m.start()]
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = t.rstrip(" .;,-")
    return t


def safe_decimal(value: str) -> Optional[Decimal]:
    """Safely convert string to Decimal, return None if invalid."""
    if not value:
        return None
    try:
        return Decimal(value.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def extract_protein_source(ingredients_list: List[str]) -> tuple:
    """
    Extract protein sources from ingredients list and return cleaned ingredients + protein source.
    Returns (cleaned_ingredients_list, protein_source)
    """
    protein_sources = []
    cleaned_ingredients = []

    protein_patterns = [
        r"\b(\w+\s+protein(?:s)?)\b",  # "milk proteins", "vegetable protein"
        r"\b(protein(?:s)?\s+\w+)\b",  # "protein isolate", "proteins concentrate"
    ]

    for ingredient in ingredients_list:
        found_protein = False
        ingredient_lower = ingredient.lower()

        for pattern in protein_patterns:
            matches = re.findall(pattern, ingredient_lower, re.IGNORECASE)
            if matches:
                for match in matches:
                    protein_sources.append(match.strip())
                found_protein = True
                break

        # If no protein found in this ingredient, keep it in the cleaned list
        if not found_protein:
            cleaned_ingredients.append(ingredient)

    # Remove duplicates and join protein sources
    unique_proteins = list(
        dict.fromkeys(protein_sources)
    )  # Preserve order while removing duplicates
    protein_source = "; ".join(unique_proteins) if unique_proteins else ""

    return cleaned_ingredients, protein_source


def process_single_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Processes a single PDF and returns a dictionary with extracted data.
    Enhanced with comprehensive error handling and logging.
    """
    filename = os.path.basename(pdf_path)
    logger.info(f"Starting processing of PDF: {filename}")

    result = {
        "source_file": pdf_path,
        "product_id": "",
        "product_name": "",
        "processing_errors": [],
        "warnings": [],
    }

    try:
        # Step 1: Read PDF content
        logger.debug(f"Reading PDF content from: {filename}")
        try:
            lines_all = read_pdf_lines(pdf_path)
            full_text = read_pdf_fulltext(pdf_path)
            logger.debug(
                f"Successfully read PDF content. Lines count: {len(lines_all)}, Text length: {len(full_text)}"
            )
        except Exception as e:
            error_msg = f"Failed to read PDF content: {str(e)}"
            logger.error(f"{filename}: {error_msg}")
            result["processing_errors"].append(error_msg)
            if DETAILED_ERRORS:
                result["processing_errors"].append(
                    f"Traceback: {traceback.format_exc()}"
                )
            return result

        # Step 2: Extract portion size
        logger.debug(f"Extracting portion size from: {filename}")
        try:
            portion_size = extract_portion_size(full_text)
            result["portion_size"] = portion_size if portion_size else None
            if portion_size:
                logger.debug(f"{filename}: Found portion size: {portion_size}")
            else:
                result["warnings"].append("No portion size found")
                logger.warning(f"{filename}: No portion size found")
        except Exception as e:
            error_msg = f"Error extracting portion size: {str(e)}"
            logger.error(f"{filename}: {error_msg}")
            result["processing_errors"].append(error_msg)
            result["portion_size"] = None

        # Step 3: Extract ingredients and protein source
        logger.debug(f"Extracting ingredients from: {filename}")
        try:
            raw_ingredients_text = find_section_text(
                full_text, "ingredients", "allergens", HEADINGS
            )
            eng_ingredients_par = split_keep_english_paragraph(raw_ingredients_text)
            full_ingredients_list = parse_keywords_from_paragraph(eng_ingredients_par)

            # Extract protein sources and get cleaned ingredients
            cleaned_ingredients_list, protein_source = extract_protein_source(
                full_ingredients_list
            )

            result["ingredients_raw"] = eng_ingredients_par
            result["ingredients_list"] = cleaned_ingredients_list
            result["protein_source"] = protein_source

            logger.debug(
                f"{filename}: Found {len(cleaned_ingredients_list)} ingredients"
            )
            if protein_source:
                logger.debug(f"{filename}: Found protein source: {protein_source}")
            else:
                result["warnings"].append("No protein source identified")

        except Exception as e:
            error_msg = f"Error extracting ingredients: {str(e)}"
            logger.error(f"{filename}: {error_msg}")
            result["processing_errors"].append(error_msg)
            result["ingredients_raw"] = ""
            result["ingredients_list"] = []
            result["protein_source"] = ""

        # Step 4: Extract allergens
        logger.debug(f"Extracting allergens from: {filename}")
        try:
            if heading_exists(lines_all, "claims", HEADINGS):
                raw_allergens_text = find_section_text(
                    full_text, "allergens", "claims", HEADINGS
                )
            else:
                raw_allergens_text = find_section_text(
                    full_text, "allergens", "food_category", HEADINGS
                )

            eng_allergens_par = split_keep_english_paragraph(raw_allergens_text)
            eng_allergens_par = sanitize_allergens_sentence(eng_allergens_par)
            allergens_list = parse_keywords_from_paragraph(eng_allergens_par)

            result["allergens"] = "; ".join(allergens_list) if allergens_list else ""
            logger.debug(f"{filename}: Found {len(allergens_list)} allergens")

        except Exception as e:
            error_msg = f"Error extracting allergens: {str(e)}"
            logger.error(f"{filename}: {error_msg}")
            result["processing_errors"].append(error_msg)
            result["allergens"] = ""

        # Step 5: Extract nutrition information
        logger.debug(f"Extracting nutrition information from: {filename}")
        try:
            raw_nutrition = find_section_text(
                full_text, "nutrition", "ingredients", HEADINGS
            )
            nutrition_table = clean_text_inline(raw_nutrition)

            nutrition_found = False

            # Flexible label patterns (per 100g / per portion expected as two numbers)
            nutritional_patterns = [
                ("Kcal", r"kcal", "kcal_100g"),
                # Support KJ, Kjoules, Kilojoules (case-insensitive, optional hyphen/space)
                ("KJ", r"(?:k[\s\-]?j(?:oules)?|kilojoules)", "kj_100g"),
                (
                    "Matières grasses (g)",
                    r"Mati[eè]res?\s+grasses?\s*\(g\)",
                    "matieres_grasses_100g",
                ),
                ("Lipides (g)", r"Lipides?\s*\(g\)", "lipides_100g"),
                (
                    "dont acides gras saturés (g)",
                    r"dont\s+acides?\s+gras\s+satur[eé]s?\s*\(g\)",
                    "acides_gras_satures_100g",
                ),
                ("Glucides (g)", r"Glucides?\s*\(g\)", "glucides_100g"),
                ("dont sucres (g)", r"dont\s+sucres?\s*\(g\)", "sucres_100g"),
                ("dont amidon (g)", r"dont\s+amidon\s*\(g\)", "amidon_100g"),
                (
                    "Fibres alimentaires (g)",
                    r"Fibres?\s+alimentaires?\s*\(g\)",
                    "fibres_100g",
                ),
                ("Protéines (g)", r"Prot[eé]ines?\s*\(g\)", "proteines_100g"),
                ("Sel (g)", r"Sel\s*\(g\)", "sel_100g"),
            ]

            for label_name, pattern, field_name in nutritional_patterns:
                try:
                    match = re.search(
                        rf"{pattern}\s+([\d.,]+)\s+([\d.,]+)",
                        nutrition_table,
                        flags=re.IGNORECASE,
                    )
                    if match:
                        val_100g = match.group(1).replace(",", ".")
                        result[field_name] = safe_decimal(val_100g)
                        nutrition_found = True
                        logger.debug(f"{filename}: Found {label_name}: {val_100g}")
                except Exception as e:
                    logger.warning(f"{filename}: Error parsing {label_name}: {str(e)}")
                    result["warnings"].append(f"Error parsing {label_name}: {str(e)}")

            if not nutrition_found:
                result["warnings"].append("No nutrition information found")
                logger.warning(f"{filename}: No nutrition information found")

        except Exception as e:
            error_msg = f"Error extracting nutrition information: {str(e)}"
            logger.error(f"{filename}: {error_msg}")
            result["processing_errors"].append(error_msg)

        # Step 6: Extract product ID and name
        logger.debug(f"Extracting product ID and name from: {filename}")
        try:
            product_id, product_name = extract_product_id_and_name_from_header(pdf_path)
            if not product_id:
                # Fallback: scan whole text for the strict ID pattern
                product_id = extract_product_id_from_anywhere(full_text)

            result["product_id"] = product_id or ""
            result["product_name"] = product_name or ""

            if product_id:
                logger.info(
                    f"{filename}: Successfully extracted product ID: {product_id}"
                )
            else:
                error_msg = "No product ID found - this is required for processing"
                logger.error(f"{filename}: {error_msg}")
                result["processing_errors"].append(error_msg)

            if product_name:
                logger.debug(f"{filename}: Found product name: {product_name}")
            else:
                result["warnings"].append("No product name found")

        except Exception as e:
            error_msg = f"Error extracting product ID/name: {str(e)}"
            logger.error(f"{filename}: {error_msg}")
            result["processing_errors"].append(error_msg)
            result["product_id"] = ""
            result["product_name"] = ""

        # Log final status
        if result["processing_errors"]:
            logger.error(
                f"{filename}: Processing completed with {len(result['processing_errors'])} errors"
            )
        elif result["warnings"]:
            logger.warning(
                f"{filename}: Processing completed with {len(result['warnings'])} warnings"
            )
        else:
            logger.info(f"{filename}: Processing completed successfully")

        return result

    except Exception as e:
        error_msg = f"Unexpected error during PDF processing: {str(e)}"
        logger.error(f"{filename}: {error_msg}")
        result["processing_errors"].append(error_msg)
        if DETAILED_ERRORS:
            result["processing_errors"].append(f"Traceback: {traceback.format_exc()}")
        return result


def save_recipe_to_db(recipe_data: Dict[str, Any]) -> tuple:
    """Save or update a recipe in the database."""
    product_id = recipe_data.get("product_id", "")

    if not product_id:
        raise ValueError("Product ID is required")

    # Get or create recipe
    recipe, created = Recipe.objects.get_or_create(
        product_id=product_id, defaults=recipe_data
    )

    if not created:
        # Update existing recipe
        for key, value in recipe_data.items():
            setattr(recipe, key, value)
        recipe.save()

    return recipe, created


@transaction.atomic
def process_all_pdfs_in_data(
    data_folder: str, task_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Recursively finds all .pdf files in data_folder, processes them, and saves to database.
    Returns statistics about the processing.
    Enhanced with comprehensive error handling and logging.
    """
    logger.info(f"Starting batch PDF processing from directory: {data_folder}")

    if not os.path.exists(data_folder):
        error_msg = f"Directory '{data_folder}' does not exist"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    stats = {
        "total_files": 0,
        "processed_files": 0,
        "created_recipes": 0,
        "updated_recipes": 0,
        "errors": [],
        "warnings": [],
        "detailed_errors": {},  # filename -> list of errors
        "file_stats": {},  # filename -> processing stats
    }

    def update_progress(
        current: int, total: int, message: str, errors: List[str] = None
    ):
        """Update progress in cache if task_id is provided."""
        if task_id:
            progress_data = {
                "status": "processing",
                "current": current,
                "total": total,
                "message": message,
                "errors": errors or [],
            }
            cache.set(f"progress_{task_id}", progress_data, timeout=3600)

    # Find all PDF files
    logger.info("Scanning for PDF files...")
    update_progress(0, 0, "Scanning for PDF files...")
    pdf_files = []
    try:
        for root, dirs, files in os.walk(data_folder):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, file))
    except Exception as e:
        error_msg = f"Error scanning directory: {str(e)}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
        return stats

    stats["total_files"] = len(pdf_files)
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    update_progress(
        0, len(pdf_files), f"Found {len(pdf_files)} PDF files. Starting processing..."
    )

    for i, pdf_path in enumerate(pdf_files, 1):
        current_file = os.path.basename(pdf_path)
        logger.info(f"Processing file {i}/{len(pdf_files)}: {current_file}")
        update_progress(i - 1, len(pdf_files), f"Processing {current_file}...")

        try:
            # Process the PDF
            recipe_data = process_single_pdf(pdf_path)

            # Store file-specific stats
            stats["file_stats"][current_file] = {
                "product_id": recipe_data.get("product_id", ""),
                "product_name": recipe_data.get("product_name", ""),
                "processing_errors": recipe_data.get("processing_errors", []),
                "warnings": recipe_data.get("warnings", []),
                "status": "processed" if recipe_data.get("product_id") else "failed",
            }

            # Add file-level warnings to global warnings
            if recipe_data.get("warnings"):
                for warning in recipe_data["warnings"]:
                    warning_msg = f"{current_file}: {warning}"
                    stats["warnings"].append(warning_msg)
                    logger.warning(warning_msg)

            # Check for processing errors
            if recipe_data.get("processing_errors"):
                stats["detailed_errors"][current_file] = recipe_data[
                    "processing_errors"
                ]
                for error in recipe_data["processing_errors"]:
                    error_msg = f"{current_file}: {error}"
                    stats["errors"].append(error_msg)
                    logger.error(error_msg)

            # Try to save to database if we have a product ID
            if recipe_data.get("product_id"):
                try:
                    # Clean the recipe data before saving (remove processing metadata)
                    clean_recipe_data = {
                        k: v
                        for k, v in recipe_data.items()
                        if k not in ["processing_errors", "warnings"]
                    }

                    recipe, created = save_recipe_to_db(clean_recipe_data)

                    if created:
                        stats["created_recipes"] += 1
                        logger.info(
                            f"{current_file}: Created new recipe with ID {recipe_data['product_id']}"
                        )
                    else:
                        stats["updated_recipes"] += 1
                        logger.info(
                            f"{current_file}: Updated existing recipe with ID {recipe_data['product_id']}"
                        )

                    stats["processed_files"] += 1
                    stats["file_stats"][current_file]["status"] = "saved"

                    update_progress(
                        i,
                        len(pdf_files),
                        f"Processed {current_file} ✓ (Created: {stats['created_recipes']}, Updated: {stats['updated_recipes']})",
                        stats["errors"],
                    )

                except Exception as db_error:
                    error_msg = f"Database error for {current_file}: {str(db_error)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
                    stats["file_stats"][current_file]["status"] = "db_error"
                    if DETAILED_ERRORS:
                        stats["errors"].append(
                            f"DB Error Traceback: {traceback.format_exc()}"
                        )

                    update_progress(
                        i,
                        len(pdf_files),
                        f"Database error in {current_file}: {str(db_error)}",
                        stats["errors"],
                    )
            else:
                error_msg = (
                    f"No product ID found in {current_file} - cannot save to database"
                )
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                stats["file_stats"][current_file]["status"] = "no_product_id"

                update_progress(
                    i,
                    len(pdf_files),
                    f"Error in {current_file}: No product ID found",
                    stats["errors"],
                )

        except Exception as e:
            error_msg = f"Unexpected error processing {current_file}: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            stats["file_stats"][current_file] = {"status": "exception", "error": str(e)}

            if DETAILED_ERRORS:
                detailed_error = (
                    f"Exception in {current_file}: {traceback.format_exc()}"
                )
                stats["errors"].append(detailed_error)
                logger.error(detailed_error)

            update_progress(
                i, len(pdf_files), f"Error in {current_file}: {str(e)}", stats["errors"]
            )

    # Final logging
    logger.info(
        f"Batch processing completed. Processed: {stats['processed_files']}/{stats['total_files']}"
    )
    logger.info(
        f"Created: {stats['created_recipes']}, Updated: {stats['updated_recipes']}"
    )
    logger.info(f"Errors: {len(stats['errors'])}, Warnings: {len(stats['warnings'])}")

    if stats["errors"]:
        logger.error("Processing completed with errors. See detailed error log.")

    return stats
