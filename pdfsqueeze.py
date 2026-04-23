#!/usr/bin/env python3
"""
PDF/Image Squeezer
Takes a PDF or images and tiles all pages onto 2 A4 sheets.
Auto-calculates the optimal grid layout to fit everything.
"""

import argparse
import math
import sys
import os
import fitz  # PyMuPDF

A4_W = 595.28  # points
A4_H = 841.89  # points
MARGIN = 8  # points (~3mm)
GAP = 4  # points between tiles


def load_pages(input_paths):
    """Load pages from PDFs and images. Returns list of (fitz.Document, page_index) tuples."""
    pages = []
    for path in input_paths:
        if not os.path.exists(path):
            print(f"Error: '{path}' not found.", file=sys.stderr)
            sys.exit(1)

        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            doc = fitz.open(path)
            for i in range(len(doc)):
                pages.append((doc, i))
        elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif", ".webp"):
            # Convert image to a single-page PDF in memory
            img_doc = fitz.open()
            img = fitz.open(path)
            pdfbytes = img.convert_to_pdf()
            img.close()
            pdf_doc = fitz.open("pdf", pdfbytes)
            page = pdf_doc.load_page(0)
            img_doc.insert_pdf(pdf_doc)
            pdf_doc.close()
            pages.append((img_doc, 0))
        else:
            print(f"Warning: skipping unsupported file '{path}'", file=sys.stderr)

    return pages


def calc_grid(total_pages, max_sheets):
    """Calculate optimal grid (cols, rows) per sheet to fit all pages."""
    pages_per_sheet = math.ceil(total_pages / max_sheets)

    # Find the most balanced grid
    best_cols, best_rows = 1, pages_per_sheet
    best_ratio_diff = float('inf')

    # Target aspect ratio of a single cell should roughly match
    # the source page aspect ratio (portrait A4-ish)
    target_ratio = A4_H / A4_W  # ~1.414 for portrait

    usable_w = A4_W - 2 * MARGIN
    usable_h = A4_H - 2 * MARGIN

    for cols in range(1, pages_per_sheet + 1):
        rows = math.ceil(pages_per_sheet / cols)
        if cols * rows < pages_per_sheet:
            continue

        cell_w = (usable_w - (cols - 1) * GAP) / cols
        cell_h = (usable_h - (rows - 1) * GAP) / rows

        if cell_w <= 0 or cell_h <= 0:
            continue

        cell_ratio = cell_h / cell_w
        ratio_diff = abs(cell_ratio - target_ratio)

        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_cols = cols
            best_rows = rows

    return best_cols, best_rows


def squeeze(input_paths, output_path, max_sheets):
    pages = load_pages(input_paths)
    total = len(pages)

    if total == 0:
        print("Error: no pages found in input.", file=sys.stderr)
        sys.exit(1)

    cols, rows = calc_grid(total, max_sheets)
    pages_per_sheet = cols * rows

    usable_w = A4_W - 2 * MARGIN
    usable_h = A4_H - 2 * MARGIN
    cell_w = (usable_w - (cols - 1) * GAP) / cols
    cell_h = (usable_h - (rows - 1) * GAP) / rows

    out_doc = fitz.open()
    page_idx = 0

    for sheet in range(max_sheets):
        if page_idx >= total:
            break

        out_page = out_doc.new_page(width=A4_W, height=A4_H)

        for slot in range(pages_per_sheet):
            if page_idx >= total:
                break

            row = slot // cols
            col = slot % cols
            x0 = MARGIN + col * (cell_w + GAP)
            y0 = MARGIN + row * (cell_h + GAP)

            src_doc, src_page_idx = pages[page_idx]
            src_page = src_doc.load_page(src_page_idx)
            src_rect = src_page.rect

            # Scale to fit cell while maintaining aspect ratio
            scale_x = cell_w / src_rect.width
            scale_y = cell_h / src_rect.height
            scale = min(scale_x, scale_y)

            rendered_w = src_rect.width * scale
            rendered_h = src_rect.height * scale

            # Center within cell
            offset_x = x0 + (cell_w - rendered_w) / 2
            offset_y = y0 + (cell_h - rendered_h) / 2

            target_rect = fitz.Rect(
                offset_x, offset_y,
                offset_x + rendered_w, offset_y + rendered_h
            )

            out_page.show_pdf_page(target_rect, src_doc, src_page_idx)
            page_idx += 1

    out_doc.save(output_path)
    out_doc.close()

    sheets_used = min(max_sheets, math.ceil(total / pages_per_sheet))
    print(f"✅ Generated: {output_path}")
    print(f"   Input pages : {total}")
    print(f"   Grid        : {cols}x{rows} per sheet")
    print(f"   Sheets used : {sheets_used}")
    if page_idx < total:
        print(f"   ⚠  {total - page_idx} pages did not fit!")


def main():
    parser = argparse.ArgumentParser(
        description="Squeeze PDF pages or images onto 2 A4 sheets."
    )
    parser.add_argument(
        "inputs", nargs="+",
        help="Input PDF file(s) or image file(s)"
    )
    parser.add_argument(
        "-o", "--output", default="squeezed.pdf",
        help="Output PDF path (default: squeezed.pdf)"
    )
    parser.add_argument(
        "--sheets", type=int, default=2,
        help="Max A4 sheets to use (default: 2)"
    )

    args = parser.parse_args()
    squeeze(args.inputs, args.output, args.sheets)


if __name__ == "__main__":
    main()
