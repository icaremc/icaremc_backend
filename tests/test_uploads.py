import io
import os


def test_upload_image_png(client):
    file_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    files = {"file": ("avatar.png", io.BytesIO(file_bytes), "image/png")}
    res = client.post("/api/v1/uploads/", files=files)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "url" in data
    assert data["url"].startswith("/static/uploads/")
    assert data["url"].endswith(".png")
    assert data["file_name"] == "avatar.png"
    assert data["mime_type"] == "image/png"
    assert data["size"] == len(file_bytes)


def test_upload_pdf_document(client):
    pdf_bytes = b"%PDF-1.4 sample content"
    files = {"file": ("medical_report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    res = client.post("/api/v1/uploads/", files=files)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["url"].startswith("/static/uploads/")
    assert data["url"].endswith(".pdf")
    assert data["file_name"] == "medical_report.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["size"] == len(pdf_bytes)


def test_upload_octet_stream_image_fallback(client):
    # Tests when client sends generic octet-stream MIME type with image extension
    img_bytes = b"sample_jpg_bytes"
    files = {"file": ("photo.jpg", io.BytesIO(img_bytes), "application/octet-stream")}
    res = client.post("/api/v1/uploads/", files=files)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["url"].endswith(".jpg")
    assert data["file_name"] == "photo.jpg"


def test_upload_without_trailing_slash(client):
    pdf_bytes = b"%PDF-1.5 test document"
    files = {"file": ("license.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    res = client.post("/api/v1/uploads", files=files)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["url"].endswith(".pdf")


def test_upload_disallowed_executable_rejected(client):
    exe_bytes = b"MZ\x90\x00executable content"
    files = {"file": ("malware.exe", io.BytesIO(exe_bytes), "application/x-msdos-program")}
    res = client.post("/api/v1/uploads/", files=files)
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]


def test_upload_file_accessible_via_static_mount(client):
    test_content = b"sample printable text document"
    files = {"file": ("notes.txt", io.BytesIO(test_content), "text/plain")}
    res = client.post("/api/v1/uploads/", files=files)
    assert res.status_code == 200
    file_url = res.json()["url"]

    # Verify static mount serves the file
    static_res = client.get(file_url)
    assert static_res.status_code == 200
    assert static_res.content == test_content
