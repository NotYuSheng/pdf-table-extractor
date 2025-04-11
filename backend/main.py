from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pdf2image import convert_from_path
import pdfplumber
import pandas as pd
import os
import shutil
import re
from difflib import SequenceMatcher
from collections import defaultdict

app = FastAPI()

# Directory to store preview images
IMAGE_OUTPUT_DIR = "/data/images"
os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)

# Directory to store original uploaded PDFs
PDF_INPUT_DIR = "/data/pdfs"
os.makedirs(PDF_INPUT_DIR, exist_ok=True)

# Directory to store exported Excel files
EXPORT_DIR = "/data/exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

def clean_sheet_name(name):
    name = re.sub(r'[\\/*?:\[\]]', '', name)
    return name.strip()[:31]

def is_probably_same_header(row, header):
    if not header or not row or len(row) != len(header):
        return False
    match_ratio = SequenceMatcher(None, ",".join(row), ",".join(header)).ratio()
    return match_ratio > 0.9

@app.post("/convert-pdf/")
async def convert_pdf(file: UploadFile = File(...)):
    """
    Converts a PDF to individual PNG images (one per page).
    Stores images in IMAGE_OUTPUT_DIR and saves original PDF in PDF_INPUT_DIR.
    Returns list of image filenames.
    """
    temp_path = f"/tmp/{file.filename}"
    saved_pdf_path = os.path.join(PDF_INPUT_DIR, file.filename)

    # Save uploaded PDF to temp and to permanent storage
    with open(temp_path, "wb") as temp_file:
        shutil.copyfileobj(file.file, temp_file)

    shutil.copy(temp_path, saved_pdf_path)

    try:
        images = convert_from_path(temp_path)
        filenames = []

        for i, image in enumerate(images):
            image_filename = f"{file.filename}_page_{i + 1}.png"
            image_path = os.path.join(IMAGE_OUTPUT_DIR, image_filename)
            image.save(image_path, "PNG")
            filenames.append(image_filename)

        return {"images": filenames}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        os.remove(temp_path)

# Serve static image files for frontend access
app.mount("/images", StaticFiles(directory=IMAGE_OUTPUT_DIR), name="images")

@app.get("/export-xlsx/")
def export_xlsx(file: str = Query(...)):
    pdf_path = os.path.join(PDF_INPUT_DIR, file)
    export_path = os.path.join(EXPORT_DIR, f"{os.path.splitext(file)[0]}.xlsx")

    if not os.path.exists(pdf_path):
        return JSONResponse(status_code=404, content={"error": "PDF file not found."})

    try:
        with pdfplumber.open(pdf_path) as pdf:
            table_meta = {}
            table_chains = {}

            # Step 1: Build table metadata and detect continuation chains
            for page_num, page in enumerate(pdf.pages):
                words = page.extract_words(use_text_flow=True)
                tables = page.find_tables()

                for idx, table in enumerate(tables):
                    x0, top, x1, bottom = table.bbox

                    # Detect header (same logic as before)
                    header_text = ""
                    nearest_y_above = 0
                    nearest_y_below = float("inf")
                    line_above, line_below = [], []

                    for word in words:
                        if word["bottom"] < top:
                            if word["bottom"] > nearest_y_above:
                                nearest_y_above = word["bottom"]
                                line_above = [w for w in words if abs(w["bottom"] - word["bottom"]) < 2]
                        elif word["top"] > bottom:
                            if word["top"] < nearest_y_below:
                                nearest_y_below = word["top"]
                                line_below = [w for w in words if abs(w["top"] - word["top"]) < 2]

                    if line_above:
                        header_text = " ".join(w["text"] for w in sorted(line_above, key=lambda x: x["x0"]))
                    elif line_below:
                        header_text = " ".join(w["text"] for w in sorted(line_below, key=lambda x: x["x0"]))

                    # Detect continuation
                    root = (page_num, idx)
                    if page_num > 0:
                        prev_tables = pdf.pages[page_num - 1].find_tables()
                        for p_idx, prev_table in enumerate(prev_tables):
                            prev_x0, _, prev_x1, prev_bottom = prev_table.bbox
                            same_x = abs(x0 - prev_x0) < 5 and abs(x1 - prev_x1) < 5
                            prev_near_bottom = prev_bottom > (page.height - 100)
                            curr_near_top = top < 100
                            if same_x and prev_near_bottom and curr_near_top:
                                root = table_chains.get((page_num - 1, p_idx), (page_num - 1, p_idx))
                                break

                    table_meta[(page_num, idx)] = {
                        "page": page_num,
                        "index": idx,
                        "header": header_text,
                        "bbox": table.bbox,
                        "data": table.extract()
                    }
                    table_chains[(page_num, idx)] = root

            # Step 2: Group tables by root
            grouped_tables = defaultdict(list)
            for key, root in table_chains.items():
                grouped_tables[root].append(key)

            # Step 3: Merge and export grouped tables
            with pd.ExcelWriter(export_path, engine="xlsxwriter") as writer:
                for root, keys in grouped_tables.items():
                    root_meta = table_meta[root]
                    header = None
                    all_rows = []

                    for i, key in enumerate(keys):
                        data = table_meta[key]["data"]
                        if not data:
                            continue
                        if i == 0:
                            header, *rows = data
                        else:
                            maybe_header, *rest = data
                            if is_probably_same_header(maybe_header, header):
                                rows = rest
                            else:
                                rows = [maybe_header] + rest
                        all_rows.extend(rows)

                    if header and all(len(r) == len(header) for r in all_rows):
                        df = pd.DataFrame(all_rows, columns=header)
                        sheet_name = clean_sheet_name(root_meta["header"] or f"Table_Page_{root[0] + 1}_{root[1] + 1}")
                        df.to_excel(writer, sheet_name=sheet_name, index=False)

        return FileResponse(export_path, filename=os.path.basename(export_path), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/detect-tables/")
def detect_tables(file: str = Query(...), page: int = Query(...)):
    """
    Detects tables on a specific page of a PDF using pdfplumber.
    Returns a list of bounding boxes with original PDF dimensions and nearest section header.
    Adds continuation detection from previous page based on position.
    """
    pdf_path = os.path.join(PDF_INPUT_DIR, file)

    if not os.path.exists(pdf_path):
        return JSONResponse(status_code=404, content={"error": "PDF file not found."})

    try:
        boxes = []
        previous_page_tables = []

        with pdfplumber.open(pdf_path) as pdf:
            if page < 1 or page > len(pdf.pages):
                return JSONResponse(status_code=400, content={"error": "Invalid page number."})

            # Get previous page tables if not on the first page
            if page > 1:
                prev_page = pdf.pages[page - 2]
                previous_page_tables = prev_page.find_tables()

            page_obj = pdf.pages[page - 1]
            words = page_obj.extract_words(use_text_flow=True)
            tables = page_obj.find_tables()

            for idx, table in enumerate(tables):
                x0, top, x1, bottom = table.bbox

                # Extract header (same logic as before)
                header_text = ""
                nearest_y_above = 0
                nearest_y_below = float("inf")
                line_above = []
                line_below = []

                for word in words:
                    if word["bottom"] < top:
                        if word["bottom"] > nearest_y_above:
                            nearest_y_above = word["bottom"]
                            line_above = [w for w in words if abs(w["bottom"] - word["bottom"]) < 2]
                    elif word["top"] > bottom:
                        if word["top"] < nearest_y_below:
                            nearest_y_below = word["top"]
                            line_below = [w for w in words if abs(w["top"] - word["top"]) < 2]

                if line_above:
                    header_text = " ".join(w["text"] for w in sorted(line_above, key=lambda x: x["x0"]))
                elif line_below:
                    header_text = " ".join(w["text"] for w in sorted(line_below, key=lambda x: x["x0"]))

                # Check for continuation from previous page
                continuation = False
                continued_from = None

                if previous_page_tables:
                    for p_idx, prev_table in enumerate(previous_page_tables):
                        prev_x0, prev_top, prev_x1, prev_bottom = prev_table.bbox

                        same_x = abs(x0 - prev_x0) < 5 and abs(x1 - prev_x1) < 5
                        prev_near_bottom = prev_bottom > (prev_table.page.height - 100)
                        curr_near_top = top < 100

                        if same_x and prev_near_bottom and curr_near_top:
                            continuation = True
                            continued_from = {"page": page - 1, "table_index": p_idx}
                            break

                boxes.append({
                    "x0": x0,
                    "y0": top,
                    "x1": x1,
                    "y1": bottom,
                    "width": page_obj.width,
                    "height": page_obj.height,
                    "header": header_text,
                    "continuation": continuation,
                    "continued_from": continued_from
                })

        return {"boxes": boxes}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
