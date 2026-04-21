#!/usr/bin/env python3
"""
Cheat Sheet Generator
Converts a text file into a dense, multi-column A4 PDF cheat sheet.
Auto-scales font size to fit all content onto 2 pages (front & back).
"""

import argparse
import math
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

PAGE_W, PAGE_H = A4  # 595.28 x 841.89 points

MARGIN_TOP = 6 * mm
MARGIN_BOTTOM = 6 * mm
MARGIN_LEFT = 6 * mm
MARGIN_RIGHT = 6 * mm

NUM_COLUMNS = 3
COLUMN_GAP = 2 * mm

MAX_PAGES = 2  # front and back
MIN_FONT_SIZE = 5.0  # floor — anything below this is unreadable
MAX_FONT_SIZE = 12.0
LINE_SPACING_FACTOR = 1.1  # multiplied by font size to get line height

# DejaVu Sans Mono has excellent Unicode coverage (subscripts, superscripts,
# arrows, Greek letters, etc.) — register it so those glyphs render natively.
DEJAVU_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
DEJAVU_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEFAULT_FONT = "Courier"  # fallback

import os
if os.path.exists(DEJAVU_MONO):
    pdfmetrics.registerFont(TTFont("DejaVuMono", DEJAVU_MONO))
    DEFAULT_FONT = "DejaVuMono"
elif os.path.exists(DEJAVU_SANS):
    pdfmetrics.registerFont(TTFont("DejaVuSans", DEJAVU_SANS))
    DEFAULT_FONT = "DejaVuSans"


def sanitize_text(text):
    """Light cleanup — only replace chars that even DejaVu can't handle."""
    # Replace non-breaking space with regular space
    text = text.replace('\u00a0', ' ')
    return text


def usable_area():
    """Returns (col_width, col_height, columns_info)."""
    total_w = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT
    total_h = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM
    col_w = (total_w - (NUM_COLUMNS - 1) * COLUMN_GAP) / NUM_COLUMNS
    cols = []
    for i in range(NUM_COLUMNS):
        x = MARGIN_LEFT + i * (col_w + COLUMN_GAP)
        cols.append(x)
    return col_w, total_h, cols


def wrap_line(text, font_name, font_size, max_width):
    """Word-wrap a single logical line into multiple rendered lines."""
    if not text.strip():
        return [""]
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip() if current else word
        w = pdfmetrics.stringWidth(test, font_name, font_size)
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines if lines else [""]


def collapse_lines(raw_lines):
    """Collapse ALL lines into one single continuous string."""
    words = []
    for line in raw_lines:
        stripped = sanitize_text(line.strip())
        if stripped:
            words.append(stripped)
    return [" ".join(words)]


def compute_rendered_lines(raw_lines, font_name, font_size, col_width):
    """Wrap all input lines and return the total list of rendered lines."""
    rendered = []
    for line in raw_lines:
        wrapped = wrap_line(line, font_name, font_size, col_width)
        rendered.extend(wrapped)
    return rendered


def lines_per_column(font_size, col_height):
    """How many lines fit in one column at a given font size."""
    line_h = font_size * LINE_SPACING_FACTOR
    return int(col_height / line_h)


def total_capacity(font_size, col_height):
    """Total number of rendered lines that fit across all pages."""
    lpc = lines_per_column(font_size, col_height)
    return lpc * NUM_COLUMNS * MAX_PAGES


def find_best_font_size(raw_lines, font_name):
    """Binary search for the largest font size that fits everything."""
    col_width, col_height, _ = usable_area()

    lo, hi = MIN_FONT_SIZE, MAX_FONT_SIZE
    best = MIN_FONT_SIZE

    for _ in range(50):  # enough iterations for convergence
        mid = (lo + hi) / 2.0
        rendered = compute_rendered_lines(raw_lines, font_name, mid, col_width)
        cap = total_capacity(mid, col_height)
        if len(rendered) <= cap:
            best = mid
            lo = mid + 0.01
        else:
            hi = mid - 0.01
        if hi - lo < 0.01:
            break

    return best


def generate_pdf(raw_lines, output_path, font_name):
    col_width, col_height, col_xs = usable_area()
    font_size = find_best_font_size(raw_lines, font_name)

    # Clamp to min
    if font_size < MIN_FONT_SIZE:
        font_size = MIN_FONT_SIZE
        print(f"⚠  Content is too long to fit at readable size. "
              f"Using minimum {MIN_FONT_SIZE}pt — some text will be cut off.",
              file=sys.stderr)

    font_size = math.floor(font_size * 10) / 10  # round down to .1

    rendered = compute_rendered_lines(raw_lines, font_name, font_size, col_width)
    line_h = font_size * LINE_SPACING_FACTOR
    lpc = lines_per_column(font_size, col_height)

    c = canvas.Canvas(output_path, pagesize=A4)
    c.setTitle("Cheat Sheet")

    line_idx = 0
    for page in range(MAX_PAGES):
        if page > 0:
            c.showPage()
        c.setFont(font_name, font_size)

        for col_i in range(NUM_COLUMNS):
            x = col_xs[col_i]
            y_start = PAGE_H - MARGIN_TOP - font_size  # top of first line

            for row in range(lpc):
                if line_idx >= len(rendered):
                    break
                y = y_start - row * line_h
                c.drawString(x, y, rendered[line_idx])
                line_idx += 1

    c.save()

    total_lines = len(rendered)
    fitted = min(total_lines, lpc * NUM_COLUMNS * MAX_PAGES)
    print(f"✅ Generated: {output_path}")
    print(f"   Font size : {font_size:.1f}pt")
    print(f"   Lines     : {fitted}/{total_lines} rendered lines across {MAX_PAGES} page(s)")
    print(f"   Columns   : {NUM_COLUMNS} per page")
    if total_lines > fitted:
        print(f"   ⚠  {total_lines - fitted} lines did not fit!")


def main():
    parser = argparse.ArgumentParser(
        description="Convert a text file into a dense A4 cheat sheet PDF."
    )
    parser.add_argument("input", help="Path to the input .txt file")
    parser.add_argument(
        "-o", "--output", default="cheatsheet.pdf",
        help="Output PDF path (default: cheatsheet.pdf)"
    )
    parser.add_argument(
        "-c", "--columns", type=int, default=3,
        help="Number of columns per page (default: 3)"
    )
    parser.add_argument(
        "--min-font", type=float, default=4.0,
        help="Minimum font size in pt (default: 4.0)"
    )
    parser.add_argument(
        "--max-font", type=float, default=12.0,
        help="Maximum font size in pt (default: 12.0)"
    )
    parser.add_argument(
        "--font", default=DEFAULT_FONT,
        help=f"Font name (default: {DEFAULT_FONT})."
    )
    parser.add_argument(
        "--pages", type=int, default=2,
        help="Max pages to use, front+back = 2 (default: 2)"
    )

    args = parser.parse_args()

    global NUM_COLUMNS, MIN_FONT_SIZE, MAX_FONT_SIZE, MAX_PAGES
    NUM_COLUMNS = args.columns
    MIN_FONT_SIZE = args.min_font
    MAX_FONT_SIZE = args.max_font
    MAX_PAGES = args.pages

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            raw_lines = f.read().splitlines()
    except FileNotFoundError:
        print(f"Error: file '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)

    if not raw_lines:
        print("Error: input file is empty.", file=sys.stderr)
        sys.exit(1)

    # Collapse line breaks into flowing paragraphs
    raw_lines = collapse_lines(raw_lines)

    generate_pdf(raw_lines, args.output, args.font)


if __name__ == "__main__":
    main()
