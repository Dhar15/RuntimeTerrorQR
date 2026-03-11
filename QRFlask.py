from flask import Flask, render_template, request, send_file
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
import os, time, warnings, io, base64
from PIL import Image
from pyzbar import pyzbar

# Team QRs are the only thing cached to disk (they never change)
TEAM_FOLDER = os.path.join('static', 'team_qr')
app = Flask(__name__)
os.makedirs(TEAM_FOLDER, exist_ok=True)

# ── Team member data ───────────────────────────────────────────────────────────
TEAM = {
    "kshitij": {
        "name": "Kshitij Dhar", "phone": "+910000000001",
        "email": "kshitij@example.com", "role": "Frontend Designer",
        "img": "kshitij.jpeg"
    },
    "pratyush": {
        "name": "M. Pratyush", "phone": "+910000000002",
        "email": "pratyush@example.com", "role": "Frontend Handler",
        "img": "pratyush.jpg"
    },
    "aditya": {
        "name": "Aditya R Singh", "phone": "+910000000003",
        "email": "aditya@example.com", "role": "Backend Developer",
        "img": "aditya.jpeg"
    },
    "abhishek": {
        "name": "Abhishek Bhalotia", "phone": "+910000000004",
        "email": "abhishek@example.com", "role": "Backend Handler",
        "img": "abhishek.jpeg"
    },
}


def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (0, 0, 0)


def make_qr_b64(data, fg="#000000", bg="#ffffff"):
    """Generate a QR code entirely in memory. Returns a base64 PNG string."""
    warnings.filterwarnings("ignore")
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10, border=4
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        color_mask=SolidFillColorMask(
            front_color=hex_to_rgb(fg),
            back_color=hex_to_rgb(bg)
        )
    )
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("terror.html")


@app.route("/about")
def about():
    return render_template("about.html", team=TEAM)


@app.route("/form", methods=["POST", "GET"])
def form():
    if request.method == "POST":
        qr_type  = request.form.get("qr_type", "contact")
        fg_color = request.form.get("fg_color", "#000000")
        bg_color = request.form.get("bg_color", "#ffffff")
        fname    = (request.form.get("fname", "") or "qr").strip()

        if qr_type == "contact":
            name  = request.form.get("name", "")
            phone = request.form.get("phone", "")
            email = request.form.get("email", "")
            data  = f"BEGIN:VCARD\nVERSION:3.0\nN:{name}\nTEL:{phone}\nEMAIL:{email}\nEND:VCARD"

        elif qr_type == "whatsapp":
            phone   = request.form.get("wa_phone", "").strip().lstrip("+")
            message = request.form.get("wa_message", "")
            data    = f"https://wa.me/{phone}?text={message}"

        elif qr_type == "email":
            to      = request.form.get("email_to", "")
            subject = request.form.get("email_subject", "")
            body    = request.form.get("email_body", "")
            data    = f"mailto:{to}?subject={subject}&body={body}"

        elif qr_type == "url":
            url = request.form.get("url", "").strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            data = url

        else:  # custom
            data = request.form.get("custom_text", "").strip()
            if not data:
                return render_template("form.html", error="Custom text cannot be empty.")

        try:
            qr_b64 = make_qr_b64(data, fg=fg_color, bg=bg_color)
        except Exception as e:
            return render_template("form.html", error=f"QR generation failed: {str(e)}")

        return render_template("QRIMG.html", qr_b64=qr_b64, fname=fname)

    return render_template("form.html")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    if request.method == "POST":
        file = request.files.get('qr_file')
        if not file or file.filename == '':
            return render_template("upload.html", error="No file selected.")
        if file.filename.rsplit('.', 1)[-1].lower() not in ALLOWED:
            return render_template("upload.html", error="Unsupported file type.")
        try:
            img_bytes = file.read()
            img = Image.open(io.BytesIO(img_bytes))

            # Strategy 1: pyzbar on RGB
            rgb = img.convert('RGB')
            decoded = pyzbar.decode(rgb)
            if decoded:
                return render_template("upload.html", results=[d.data.decode('utf-8', errors='replace') for d in decoded])

            # Strategy 2: pyzbar on grayscale
            gray_pil = img.convert('L')
            decoded = pyzbar.decode(gray_pil)
            if decoded:
                return render_template("upload.html", results=[d.data.decode('utf-8', errors='replace') for d in decoded])

            # Strategy 3: contrast-enhanced grayscale
            from PIL import ImageEnhance, ImageOps
            enhanced = ImageEnhance.Contrast(gray_pil).enhance(2.5)
            decoded = pyzbar.decode(enhanced)
            if decoded:
                return render_template("upload.html", results=[d.data.decode('utf-8', errors='replace') for d in decoded])

            # Strategy 4: inverted (dark-bg QRs)
            decoded = pyzbar.decode(ImageOps.invert(gray_pil))
            if decoded:
                return render_template("upload.html", results=[d.data.decode('utf-8', errors='replace') for d in decoded])

            # Strategy 5: OpenCV
            import cv2, numpy as np
            cv_img   = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
            detector = cv2.QRCodeDetector()

            val, _, _ = detector.detectAndDecode(cv_img)
            if val:
                return render_template("upload.html", results=[val])

            gray_cv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray_cv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            val, _, _ = detector.detectAndDecode(thresh)
            if val:
                return render_template("upload.html", results=[val])

            val, _, _ = detector.detectAndDecode(cv2.bitwise_not(thresh))
            if val:
                return render_template("upload.html", results=[val])

            return render_template("upload.html", error="Could not decode the QR code. Try a higher-resolution or better-lit image.")
        except Exception as e:
            return render_template("upload.html", error=f"Could not process image: {str(e)}")
    return render_template("upload.html")


# ── Team QRs: generated once, cached to disk, served as PNG ───────────────────
@app.route("/team-qr/<member>")
def team_qr(member):
    m = TEAM.get(member)
    if not m:
        return "Not found", 404
    out_path = os.path.join(TEAM_FOLDER, f"{member}.png")
    if not os.path.exists(out_path):
        vcard = f"BEGIN:VCARD\nVERSION:3.0\nN:{m['name']}\nTEL:{m['phone']}\nEMAIL:{m['email']}\nEND:VCARD"
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=8, border=3)
        qr.add_data(vcard)
        qr.make(fit=True)
        img = qr.make_image(
            image_factory=StyledPilImage,
            color_mask=SolidFillColorMask(front_color=(0, 229, 200), back_color=(14, 21, 32))
        )
        img.save(out_path)
    return send_file(out_path, mimetype='image/png')


@app.route("/suggestion", methods=["POST", "GET"])
def suggestion():
    if request.method == "POST":
        fb     = request.form.get("feedback", "")
        name   = request.form.get("name", "Anonymous")
        rating = request.form.get("rating", "Not rated")
        with open("feedback.txt", "a") as f:
            f.write(f"\n\nFEEDBACK AT {time.ctime()}")
            f.write(f"\nFROM : {name}  |  RATING : {rating}/5\n{fb}\nDONE")
        return render_template("suggestion.html", thankyou=True)
    return render_template("suggestion.html")


if __name__ == '__main__':
    app.run(debug=True)