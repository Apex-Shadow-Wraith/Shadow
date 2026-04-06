"""
ESV Study Bible Epub Processor
Parses the ESV Study Bible epub into structured JSON files for Grimoire ingestion.

Usage:
    python scripts/esv_processor.py

Output:
    training_data/esv/esv_pericopes.json
    training_data/esv/esv_studynotes.json
"""

import json
import re
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

# ── Paths ──
EPUB_PATH = Path(r"C:\Shadow\training_data\esv\ESV Study Bible.epub")
OUTPUT_DIR = Path(r"C:\Shadow\training_data\esv")

# ── Genre mapping by book number ──
GENRE_MAP = {
    range(1, 6): "law",
    range(6, 18): "history",
    range(18, 23): "wisdom",
    range(23, 28): "prophecy_major",
    range(28, 40): "prophecy_minor",
    range(40, 45): "gospel_acts",
    range(45, 66): "epistle",
    range(66, 67): "apocalyptic",
}


def get_genre(book_number):
    """Return genre string for a given book number (1-66)."""
    for num_range, genre in GENRE_MAP.items():
        if book_number in num_range:
            return genre
    return "unknown"


def decode_verse_id(verse_id):
    """
    Decode a verse ID like '01001001' into (book, chapter, verse).
    Used for both v-prefixed IDs and h-prefixed class names.
    """
    if len(verse_id) < 8:
        return None, None, None
    try:
        book = int(verse_id[0:2])
        chapter = int(verse_id[2:5])
        verse = int(verse_id[5:8])
        return book, chapter, verse
    except (ValueError, IndexError):
        return None, None, None


def clean_text_element(section):
    """
    Clean a BeautifulSoup element for biblical text extraction.
    Removes crossrefs, footnotes, study note links. Converts smallcap LORD/GOD.
    Returns cleaned text string.
    """
    # Work on a copy so we don't mutate the original tree
    # (we need the original for verse tracking)
    section_copy = BeautifulSoup(str(section), "html.parser")

    # Remove crossref spans entirely
    for span in section_copy.find_all("span", class_="crossref"):
        span.decompose()

    # Remove footnote spans entirely
    for span in section_copy.find_all("span", class_="footnote"):
        span.decompose()

    # Remove study note links [†] and [^]
    for a_tag in section_copy.find_all("a"):
        text = a_tag.get_text()
        if text.strip() in ("[†]", "[^]", "†", "^"):
            a_tag.decompose()
        elif a_tag.get("href", "").endswith(".studynotes.xhtml") or \
             "studynotes" in a_tag.get("href", ""):
            a_tag.decompose()
        elif a_tag.get("href", "").endswith(".resources.xhtml") or \
             "resources" in a_tag.get("href", ""):
            a_tag.decompose()

    # Convert L<span class="smallcap">ORD</span> → LORD
    # Also handles G<span class="smallcap">OD</span> → GOD
    for span in section_copy.find_all("span", class_="smallcap"):
        # The preceding text node should have the first letter
        span.replace_with(span.get_text())

    # Remove book-name spans but keep text (it contextualizes chapter starts)
    for span in section_copy.find_all("span", class_="book-name"):
        span.replace_with(span.get_text())

    # Get text and normalize whitespace
    text = section_copy.get_text()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_verses_from_section(section):
    """
    Extract all verse identities (book, chapter, verse) found in a section
    by scanning h-class spans and verse-num spans.
    Returns list of (chapter, verse) tuples.
    """
    verses = []

    # Method 1: Parse h{BBCCCVVV} class names on spans
    for span in section.find_all("span"):
        classes = span.get("class", [])
        for cls in classes:
            if re.match(r"^h\d{8,}$", cls):
                _, ch, vs = decode_verse_id(cls[1:])
                if ch is not None and vs is not None:
                    verses.append((ch, vs))

    # Method 2: Parse v-prefixed IDs as backup
    if not verses:
        for elem in section.find_all(id=re.compile(r"^v\d{8,}$")):
            vid = elem.get("id", "")
            _, ch, vs = decode_verse_id(vid[1:])
            if ch is not None and vs is not None:
                verses.append((ch, vs))

    return verses


def get_content_between(start_elem, end_elem):
    """
    Collect all sibling elements between start_elem and end_elem (exclusive).
    Returns a list of elements.
    """
    elements = []
    current = start_elem.next_sibling
    while current and current != end_elem:
        elements.append(current)
        current = current.next_sibling
    return elements


def parse_text_files(epub, text_files, book_number, book_name):
    """
    Parse all text xhtml files for a single book.
    Returns list of pericope dicts.
    """
    pericopes = []
    testament = "OT" if book_number <= 39 else "NT"
    genre = get_genre(book_number)

    for filepath in text_files:
        content = epub.read(filepath).decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")

        # Find all sections (chapters)
        sections = soup.find_all("section")
        if not sections:
            # Fallback: treat body as the section
            sections = [soup.find("body")]
            if not sections or sections[0] is None:
                continue

        for section in sections:
            headers = section.find_all("header")

            if not headers:
                # No pericope boundaries — treat entire section as one block
                verses = extract_verses_from_section(section)
                if not verses:
                    continue
                text = clean_text_element(section)
                if not text:
                    continue
                ch_start, vs_start = verses[0]
                ch_end, vs_end = verses[-1]
                pericopes.append({
                    "book_number": book_number,
                    "book_name": book_name,
                    "chapter": ch_start,
                    "verse_start": vs_start,
                    "verse_end": vs_end,
                    "section_heading": "",
                    "text": text,
                    "testament": testament,
                    "genre": genre,
                })
                continue

            # Process each pericope (header to next header)
            for i, header in enumerate(headers):
                # Extract section heading
                heading_p = header.find("p", class_="heading")
                if heading_p:
                    heading_span = heading_p.find("span")
                    section_heading = heading_span.get_text().strip() if heading_span else heading_p.get_text().strip()
                else:
                    section_heading = header.get_text().strip()

                # Get verse_start from header ID
                heading_id_elem = header.find(id=re.compile(r"^v\d+"))
                if heading_id_elem:
                    vid = heading_id_elem.get("id", "")[1:]  # strip 'v'
                    _, ch_start, vs_start = decode_verse_id(vid)
                else:
                    ch_start, vs_start = None, None

                # Determine the content block: from this header to the next
                if i + 1 < len(headers):
                    next_header = headers[i + 1]
                else:
                    next_header = None

                # Collect content elements between headers
                # The content after a header consists of sibling <p> tags
                # until the next <header>
                content_elements = []
                current = header.next_sibling
                while current:
                    if current == next_header or (hasattr(current, "name") and current.name == "header"):
                        break
                    content_elements.append(current)
                    current = current.next_sibling

                if not content_elements:
                    # Header with no following content — skip
                    if ch_start is not None:
                        pericopes.append({
                            "book_number": book_number,
                            "book_name": book_name,
                            "chapter": ch_start,
                            "verse_start": vs_start,
                            "verse_end": vs_start,
                            "section_heading": section_heading,
                            "text": "",
                            "testament": testament,
                            "genre": genre,
                        })
                    continue

                # Build a temporary container for the content elements
                container = BeautifulSoup("<div></div>", "html.parser").div
                for elem in content_elements:
                    container.append(BeautifulSoup(str(elem), "html.parser"))

                # Extract verses from the content
                verses = extract_verses_from_section(container)

                # Also include the starting verse from the header
                if ch_start is not None and vs_start is not None:
                    all_verses = [(ch_start, vs_start)] + verses
                else:
                    all_verses = verses

                if not all_verses:
                    continue

                # Determine chapter and verse range
                ch_first, vs_first = all_verses[0]
                ch_last, vs_last = all_verses[-1]

                # Clean the text
                text = clean_text_element(container)
                if not text:
                    continue

                pericopes.append({
                    "book_number": book_number,
                    "book_name": book_name,
                    "chapter": ch_first,
                    "verse_start": vs_first,
                    "verse_end": vs_last,
                    "section_heading": section_heading,
                    "text": text,
                    "testament": testament,
                    "genre": genre,
                })

    return pericopes


def parse_verse_range_from_id(note_id):
    """
    Parse a study note ID like 'n01024009' or 'n01001001-01002003'
    into (chapter_start, verse_start, chapter_end, verse_end) and a
    human-readable verse_range string.
    """
    # Strip 'n' prefix
    raw = note_id[1:] if note_id.startswith("n") else note_id

    if "-" in raw:
        parts = raw.split("-")
        _, ch1, vs1 = decode_verse_id(parts[0])
        _, ch2, vs2 = decode_verse_id(parts[1])
        if ch1 is None or ch2 is None:
            return None, None, ""
        if ch1 == ch2:
            verse_range = f"{ch1}:{vs1}–{vs2}"
        else:
            verse_range = f"{ch1}:{vs1}–{ch2}:{vs2}"
        return ch1, vs1, verse_range
    else:
        _, ch, vs = decode_verse_id(raw)
        if ch is None:
            return None, None, ""
        verse_range = f"{ch}:{vs}"
        return ch, vs, verse_range


def clean_note_text(p_tag):
    """Clean a study note paragraph tag into plain text."""
    # Work on a copy
    p_copy = BeautifulSoup(str(p_tag), "html.parser")

    # Remove the "BOOK—NOTE ON" prefix (inside <strong><small>)
    for small in p_copy.find_all("small"):
        text = small.get_text()
        if "NOTE ON" in text.upper():
            # Remove the parent <strong> if it only contains this small
            parent = small.parent
            if parent and parent.name == "strong":
                parent.decompose()
            else:
                small.decompose()

    # Remove crossref spans
    for span in p_copy.find_all("span", class_="crossref"):
        span.decompose()

    # Convert smallcap spans
    for span in p_copy.find_all("span", class_="smallcap"):
        span.replace_with(span.get_text())

    text = p_copy.get_text()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_studynotes_files(epub, note_files, book_name):
    """
    Parse all studynotes xhtml files for a single book.
    Returns list of study note dicts.
    """
    notes = []
    # Classes that start a new note (when they have an ID)
    new_note_classes = {"study-note", "outline-1", "outline-3", "outline-4"}
    # Classes that continue the previous note
    continue_classes = {"study-note-continue"}
    # outline-1 without ID also continues

    for filepath in note_files:
        content = epub.read(filepath).decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")

        for p_tag in soup.find_all("p"):
            p_classes = set(p_tag.get("class", []))
            p_id = p_tag.get("id", "")

            # Check if this starts a new note
            is_new_note = False
            if p_classes & new_note_classes and p_id and p_id.startswith("n"):
                is_new_note = True

            is_continuation = False
            if p_classes & continue_classes:
                is_continuation = True
            elif "outline-1" in p_classes and not p_id:
                is_continuation = True

            if is_new_note:
                chapter, verse, verse_range = parse_verse_range_from_id(p_id)
                if chapter is None:
                    continue
                note_text = clean_note_text(p_tag)
                if note_text:
                    notes.append({
                        "book_name": book_name,
                        "chapter": chapter,
                        "verse_range": verse_range,
                        "note_text": note_text,
                    })
            elif is_continuation and notes:
                # Append to the last note
                extra_text = clean_note_text(p_tag)
                if extra_text:
                    notes[-1]["note_text"] += " " + extra_text

    return notes


def discover_book_files(epub):
    """
    Discover and group all book files from the epub.
    Returns dict: { book_number: { 'name': str, 'text_files': [...], 'note_files': [...] } }
    """
    books = {}
    pattern = re.compile(r"OEBPS/Text/b(\d{2})\.(\d{2})\.([A-Za-z0-9-]+)\.(text|studynotes)\.xhtml")

    for name in sorted(epub.namelist()):
        m = pattern.match(name)
        if not m:
            continue
        book_num = int(m.group(1))
        part_num = int(m.group(2))
        book_name = m.group(3)
        file_type = m.group(4)

        if book_num not in books:
            books[book_num] = {
                "name": book_name,
                "text_files": [],
                "note_files": [],
            }

        if file_type == "text":
            books[book_num]["text_files"].append((part_num, name))
        elif file_type == "studynotes":
            books[book_num]["note_files"].append((part_num, name))

    # Sort files by part number within each book
    for book_num in books:
        books[book_num]["text_files"].sort(key=lambda x: x[0])
        books[book_num]["text_files"] = [f for _, f in books[book_num]["text_files"]]
        books[book_num]["note_files"].sort(key=lambda x: x[0])
        books[book_num]["note_files"] = [f for _, f in books[book_num]["note_files"]]

    return books


def main():
    print(f"Opening epub: {EPUB_PATH}")
    if not EPUB_PATH.exists():
        print(f"ERROR: Epub file not found at {EPUB_PATH}")
        return

    epub = zipfile.ZipFile(str(EPUB_PATH), "r")
    books = discover_book_files(epub)
    print(f"Discovered {len(books)} books\n")

    all_pericopes = []
    all_studynotes = []

    for book_num in sorted(books.keys()):
        book_info = books[book_num]
        book_name = book_info["name"]
        text_files = book_info["text_files"]
        note_files = book_info["note_files"]

        # Parse pericopes from text files
        pericopes = parse_text_files(epub, text_files, book_num, book_name)
        all_pericopes.extend(pericopes)

        # Parse study notes
        studynotes = parse_studynotes_files(epub, note_files, book_name)
        all_studynotes.extend(studynotes)

        print(f"  [{book_num:2d}/66] {book_name:<20s} — {len(pericopes)} pericopes, {len(studynotes)} study notes")

    epub.close()

    # Write output JSON files
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pericopes_path = OUTPUT_DIR / "esv_pericopes.json"
    with open(pericopes_path, "w", encoding="utf-8") as f:
        json.dump(all_pericopes, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {pericopes_path}")

    studynotes_path = OUTPUT_DIR / "esv_studynotes.json"
    with open(studynotes_path, "w", encoding="utf-8") as f:
        json.dump(all_studynotes, f, indent=2, ensure_ascii=False)
    print(f"Wrote {studynotes_path}")

    # Final stats
    print(f"\n{'='*50}")
    print(f"Total pericopes:    {len(all_pericopes)}")
    print(f"Total study notes:  {len(all_studynotes)}")
    print(f"Books processed:    {len(books)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
