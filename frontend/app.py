import streamlit as st
import requests

st.set_page_config(page_title="PDF Table Extractor", layout="centered")
st.title("📄 PDF Table Extractor")

BACKEND_URL = "http://pdf-backend:8000"

# Initialize state
if "rotation" not in st.session_state:
    st.session_state.rotation = 0
if "page_num" not in st.session_state:
    st.session_state.page_num = 1
if "image_filenames" not in st.session_state:
    st.session_state.image_filenames = []
if "pdf_uploaded" not in st.session_state:
    st.session_state.pdf_uploaded = False
if "last_uploaded_filename" not in st.session_state:
    st.session_state.last_uploaded_filename = ""

def get_detected_boxes(filename, page_number):
    try:
        res = requests.get(
            "http://pdf-backend:8000/detect-tables/",
            params={"file": filename, "page": page_number}
        )
        if res.status_code == 200:
            return res.json().get("boxes", [])
    except Exception as e:
        st.warning(f"Table detection failed: {e}")
    return []

# ==== DISPLAY PAGE PREVIEW WITH RED BOXES ====
if st.session_state.image_filenames:
    selected_filename = st.session_state.image_filenames[st.session_state.page_num - 1]
    image_path = f"/images/{selected_filename}"
    pdf_filename = st.session_state.last_uploaded_filename

    # Get table detection boxes
    boxes = get_detected_boxes(pdf_filename, st.session_state.page_num)

    # Overlay HTML
    overlay_html = ""
    for box in boxes:
        pdf_w, pdf_h = box["width"], box["height"]
        x_ratio = 100 / pdf_w
        y_ratio = 100 / pdf_h

        width_pct = (box["x1"] - box["x0"]) * x_ratio
        height_pct = (box["y1"] - box["y0"]) * y_ratio
        left_pct = box["x0"] * x_ratio
        top_pct = box["y0"] * y_ratio

        overlay_html += f"""
        <div style="
            position: absolute;
            left: {left_pct}%;
            top: {top_pct}%;
            width: {width_pct}%;
            height: {height_pct}%;
            border: 2px solid red;
            box-sizing: border-box;
        "></div>
        """.strip()

    # Final HTML to render image + overlays with rotation
    st.markdown(
        f"""
        <div style="display: flex; justify-content: center;">
            <div style="
                position: relative;
                display: inline-block;
                transform: rotate({st.session_state.rotation}deg);
                transition: transform 0.3s ease;
            ">
                <img src="{image_path}" 
                    alt="Page {st.session_state.page_num}"
                    style="
                        max-height: 60vh;
                        border: 1px solid #ddd;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    ">
                <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;">
                    {overlay_html}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Extra space before button row
st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

# ==== BUTTONS ====
if st.session_state.image_filenames:
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)

    with col1:
        if st.button("↩️", help="Rotate Left"):
            st.session_state.rotation = (st.session_state.rotation - 90) % 360
            st.rerun()

    with col2:
        if st.button("↪️", help="Rotate Right"):
            st.session_state.rotation = (st.session_state.rotation + 90) % 360
            st.rerun()

    with col4:
        st.markdown(
            f"<div style='text-align: center; font-size: 16px; padding-top: 0.4rem; white-space: nowrap;'>"
            f"Page {st.session_state.page_num} of {len(st.session_state.image_filenames)}"
            f"</div>",
            unsafe_allow_html=True
        )

    with col6:
        if st.button("⬅️", help="Previous Page") and st.session_state.page_num > 1:
            st.session_state.page_num -= 1
            st.rerun()

    with col7:
        if st.button("➡️", help="Next Page") and st.session_state.page_num < len(st.session_state.image_filenames):
            st.session_state.page_num += 1
            st.rerun()

# ==== FILE UPLOADER ====
uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file:
    file_changed = uploaded_file.name != st.session_state.last_uploaded_filename

    if not st.session_state.pdf_uploaded or file_changed:
        with st.spinner("Converting to images..."):
            files = {"file": uploaded_file}
            res = requests.post(f"{BACKEND_URL}/convert-pdf/", files=files)

            if res.status_code == 200:
                st.session_state.image_filenames = res.json().get("images", [])
                st.session_state.page_num = 1
                st.session_state.rotation = 0
                st.session_state.pdf_uploaded = True
                st.session_state.last_uploaded_filename = uploaded_file.name
                

                with st.spinner("Preparing Excel export..."):
                    export_res = requests.get(
                        f"{BACKEND_URL}/export-xlsx/",
                        params={"file": uploaded_file.name}
                    )
                    if export_res.status_code == 200:
                        st.session_state.export_xlsx = export_res.content
                        st.download_button(
                            label="📥 Download Extracted Tables (XLSX)",
                            data=export_res.content,
                            file_name=f"{uploaded_file.name.replace('.pdf', '.xlsx')}",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.warning("Could not generate export file.")
                st.rerun()

            else:
                st.error(f"Conversion failed: {res.text}")
                st.session_state.export_xlsx = None

# ==== EXPORT BUTTON ====
if st.session_state.get("export_xlsx"):
    st.download_button(
        label="📥 Download Extracted Tables (XLSX)",
        data=st.session_state.export_xlsx,
        file_name=f"{st.session_state.last_uploaded_filename.replace('.pdf', '.xlsx')}",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
