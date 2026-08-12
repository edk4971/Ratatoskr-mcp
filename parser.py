import re
from lxml import etree
from typing import Tuple, Optional
import mwparserfromhell


def _strip_wikitext(wikitext_str: str) -> str:
    """Recursively strip wikitext syntax, handling nested templates."""
    if not wikitext_str:
        return ""
    wc = mwparserfromhell.parse(wikitext_str)
    result = _extract_value(wc)
    return result.strip() if result else ""


def _extract_value(wc) -> Optional[str]:
    """Extract a clean text value from wikicode, handling nested templates."""
    if not wc:
        return ""

    # If it's a template, try to extract meaningful content
    templates = list(wc.filter_templates())
    if templates:
        parts = []
        for tpl in templates:
            tpl_result = _extract_template_value(tpl)
            if tpl_result:
                parts.append(tpl_result)

        # If we got content from templates, return joined result
        if parts:
            return " ".join(parts)

    # Otherwise, strip code to get plain text (handles links, etc.)
    text = wc.strip_code().strip()
    if text:
        return text

    # Fallback: try raw string
    return None


def _extract_template_value(tpl) -> Optional[str]:
    """Extract a meaningful value from a nested template."""
    name = tpl.name.strip()
    params = list(tpl.params)

    # Date-related templates: extract only positional numeric params
    if any(kw in name.lower() for kw in ['birth', 'death', 'date', 'year', 'month']):
        date_parts = []
        for p in params:
            pname = p.name.strip() if p.name else ""
            pval = p.value.strip()
            # Only take positional params (empty name or digits) that are simple numbers
            if pname.isdigit() or (pname == "" and not any(c.isalpha() for c in str(p.name))):
                stripped = mwparserfromhell.parse(pval).strip_code().strip()
                # Only keep pure numbers for date components
                if stripped and re.match(r'^\d+$', stripped):
                    date_parts.append(stripped)
        if date_parts:
            # For death date templates with 6 params (birth + death), take last 3
            if len(date_parts) == 6:
                return f"{date_parts[3]} {date_parts[4]} {date_parts[5]}"
            return " ".join(date_parts)

    # Non-date templates: try to extract first few meaningful params
    if name.startswith("Infobox"):
        parts = []
        for p in params:
            pname = p.name.strip() if p.name else ""
            pval = p.value.strip() if p.value else ""
            if pname.isdigit():
                stripped = mwparserfromhell.parse(pval).strip_code().strip()
                if stripped:
                    parts.append(stripped)
            elif pname and pname.lower() not in ('color', 'background', 'border'):
                stripped = mwparserfromhell.parse(pval).strip_code().strip()
                if stripped:
                    parts.append(f"{pname}: {stripped}")
            elif not pname and pval:
                stripped = mwparserfromhell.parse(pval).strip_code().strip()
                if stripped:
                    parts.append(stripped)
        if parts:
            return " ".join(parts[:3])

    # Generic templates: convert to string, parse, then strip
    try:
        result = mwparserfromhell.parse(str(tpl)).strip_code().strip()
        if result:
            return result
    except Exception:
        pass
    return None


def _process_infobox_param(val):
    """Process a single infobox parameter value, handling nested structures."""
    if val is None:
        return ""

    val_str = val.strip() if hasattr(val, 'strip') else ""
    if not val_str:
        return ""

    # Check if it's a Wikicode object (from param.value)
    if hasattr(val, 'strip_code'):
        root = val
    else:
        root = mwparserfromhell.parse(val_str)

    # Get direct text content (handles links, plain text, etc.)
    text = root.strip_code().strip()

    # Check for wrapper templates that need special handling
    wrappers = [str(t) for t in root.filter_templates()]
    has_plainlist = any('plainlist' in w.lower() for w in wrappers)
    has_collapsible = any('collapsible' in w.lower() for w in wrappers)
    has_marriage = any('marriage' in w.lower() for w in wrappers)
    has_indented = any('Indented plainlist' in w for w in wrappers)

    if has_plainlist or has_indented:
        # Extract text, remove bullet markers, clean up
        cleaned = text.replace('*', '').replace('* ', '').strip()
        # Clean up multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned)
        if cleaned:
            return cleaned
        # Try getting content from nested templates
        inner_templates = list(root.filter_templates())
        if inner_templates:
            parts = []
            for tpl in inner_templates:
                result = _extract_template_value(tpl)
                if result:
                    parts.append(result)
            if parts:
                return ", ".join(parts)
        return text if text else ""

    if has_collapsible:
        # For collapsible lists, try to extract inner content
        inner_text = text
        if inner_text:
            inner_text = re.sub(r'\s+', ' ', inner_text).strip()
            return inner_text
        # Try to get content from nested templates
        inner_templates = list(root.filter_templates())
        if inner_templates:
            parts = []
            for tpl in inner_templates:
                result = _extract_template_value(tpl)
                if result:
                    parts.append(result)
            if parts:
                return "; ".join(parts[:5])
        return ""

    if has_marriage:
        # Extract marriage info: person name and dates
        parts = []
        # Get direct links (names)
        links = list(root.filter_wikilinks())

        def _link_text(link):
            try:
                return mwparserfromhell.parse(str(link)).strip_code().strip()
            except Exception:
                return ""

        names = [_link_text(link) for link in links if _link_text(link)]
        # Get templates (marriage dates)
        marriage_templates = [t for t in root.filter_templates() if t.name.strip().lower() == 'marriage']
        for mt in marriage_templates:
            mp = list(mt.params)
            if mp:
                name = mp[0].value.strip() if mp[0].value else ""
                date_parts = []
                for p in mp[1:4]:  # Take up to 3 date params
                    if p.value:
                        dp = p.value.strip()
                        if dp and re.match(r'^\d{4}$', dp):
                            date_parts.append(dp)
                if date_parts:
                    date_str = "–".join(date_parts)
                else:
                    date_str = ""
                # Check for end= param
                end_val = ""
                for p in mp:
                    if hasattr(p, 'name') and p.name and p.name.strip().lower() == 'end':
                        end_val = p.value.strip() if p.value else ""
                        break
                if name and date_str:
                    if end_val:
                        parts.append(f"{name} ({date_str}, {end_val})")
                    else:
                        parts.append(f"{name} ({date_str})")
                elif name:
                    parts.append(name)
                elif date_str:
                    parts.append(date_str)

        if parts:
            return ", ".join(parts)
        return text if text else ""

    # Standard processing for other values
    if text:
        return text

    # Try nested templates
    nested = list(root.filter_templates())
    if nested:
        parts = []
        for tpl in nested:
            tpl_result = _extract_template_value(tpl)
            if tpl_result:
                parts.append(tpl_result)
        if parts:
            return " ".join(parts)
    return val_str.strip() if hasattr(val, 'strip') else str(val).strip()


class WikipediaParser:
    def __init__(self, max_words: int = 1000, include_infobox: bool = True):
        self.max_words = max_words
        self.include_infobox = include_infobox

    def parse_page_stream(self, xml_bytes: bytes, db_title: str) -> Tuple[str, str, str, Optional[str]]:
        """
        Parses a block of XML containing multiple <page> elements.
        Returns (title, infobox_md, body_md, redirect_to) for the first matching page.
        redirect_to is the target title if this is a redirect page, else None.
        """
        wrapped_xml = b"<data>" + xml_bytes + b"</data>"

        try:
            root = etree.fromstring(wrapped_xml)
        except Exception as e:
            print(f"DEBUG: XML parse error: {e}")
            return "", "", "", None

        target_node = None
        title = ""

        # 1. Find the correct page — two passes:
        #    Pass 1: case-sensitive exact match (avoids grabbing a redirect page
        #    like "Quantum Mechanics" when we want the article "Quantum mechanics")
        #    Pass 2: case-insensitive fallback
        db_title_clean = db_title.strip()
        for pass_case_sensitive in (True, False):
            for page in root.xpath(".//*[local-name()='page']"):
                title_elems = page.xpath(".//*[local-name()='title']")
                for title_elem in title_elems:
                    if title_elem.text is not None:
                        title_text = title_elem.text.strip()
                        if pass_case_sensitive:
                            if title_text == db_title_clean:
                                target_node = page
                                title = title_text
                                break
                        else:
                            if title_text.lower() == db_title_clean.lower():
                                target_node = page
                                title = title_text
                                break
                if target_node is not None:
                    break
            if target_node is not None:
                break

        if target_node is None:
            return "", "", "", None

        # 1b. Check for <redirect title="..." /> — MediaWiki redirect pages
        redirect_elems = target_node.xpath(".//*[local-name()='redirect']")
        if redirect_elems:
            redirect_title = redirect_elems[0].get("title")
            if redirect_title:
                return title, "", "", redirect_title

        # 2. Extract the raw Wikitext
        text_elems = target_node.xpath(".//*[local-name()='text']")
        if not text_elems or text_elems[0].text is None:
            return title, "", "", None

        raw_wikitext = text_elems[0].text

        # 3. Parse the Wikitext using mwparserfromhell
        wikicode = mwparserfromhell.parse(raw_wikitext)

        infobox_md = ""
        body_md = ""

        # 4. Extract Infobox
        if self.include_infobox:
            templates = list(wikicode.filter_templates())
            for tpl in templates:
                tpl_name = tpl.name.strip()
                if tpl_name.lower().startswith("infobox"):
                    infobox_items = []
                    for param in tpl.params:
                        pval_str = param.value.strip() if param.value else ""
                        if pval_str or param.name:  # Include params with empty values too
                            clean_val = _process_infobox_param(param.value)
                            pname = param.name.strip() if param.name else ""
                            if pname:
                                infobox_items.append(f"**{pname}**: {clean_val}")
                            elif clean_val:
                                infobox_items.append(clean_val)

                    if infobox_items:
                        infobox_md = "\n".join(infobox_items)

                    try:
                        wikicode.remove(tpl)
                    except ValueError:
                        pass
                    break

        # 5. Extract Body Text — lead section only (before the first == heading)
        sections = wikicode.get_sections(include_lead=True, flat=True)
        lead = sections[0] if sections else wikicode
        body_md = lead.strip_code()

        # Clean up excessive newlines
        body_md = "\n".join(line for line in body_md.splitlines() if line.strip())

        return title, infobox_md, body_md, None
