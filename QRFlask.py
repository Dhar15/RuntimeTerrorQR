from flask import Flask, render_template, request, url_for, send_from_directory, send_file
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
import os, time, warnings, io
from PIL import Image
from pyzbar import pyzbar

UP_FOLDER = os.path.join('static', 'QRcode')
TEAM_FOLDER = os.path.join('static', 'team_qr')
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UP_FOLDER

os.makedirs(UP_FOLDER, exist_ok=True)
os.makedirs(TEAM_FOLDER, exist_ok=True)

# ── Team member data (edit with real details) ──────────────────────────────────
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
    """Convert #rrggbb → (r, g, b). Falls back to black/white on bad input."""
    hex_str = hex_str.lstrip('#')
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (0, 0, 0)


def make_qr(data, fg="#000000", bg="#ffffff", fname=None):
    """Generate a QR PNG, save to UP_FOLDER, return the filename."""
    warnings.filterwarnings("ignore")
    fname = (fname or "temp") + str(time.time())

    fg_rgb = hex_to_rgb(fg)
    bg_rgb = hex_to_rgb(bg)

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H,
                       box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        color_mask=SolidFillColorMask(front_color=fg_rgb, back_color=bg_rgb)
    )

    out_name = fname + ".png"
    out_path = os.path.join(app.config['UPLOAD_FOLDER'], out_name)
    img.save(out_path)
    return out_name


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
        fname    = request.form.get("fname", "") or "qr"

        # ── Build QR data string based on type ──────────────────────────────
        if qr_type == "contact":
            name  = request.form.get("name", "")
            phone = request.form.get("phone", "")
            email = request.form.get("email", "")
            data  = (f"BEGIN:VCARD\nVERSION:3.0\nN:{name}\n"
                     f"TEL:{phone}\nEMAIL:{email}\nEND:VCARD")

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
            url  = request.form.get("url", "").strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            data = url

        else:  # custom
            data = request.form.get("custom_text", "")

        out_name = make_qr(data, fg=fg_color, bg=bg_color, fname=fname)
        app.config['THEFILE'] = out_name
        return render_template("QR.html",
                               user_image=os.path.join(app.config['UPLOAD_FOLDER'], out_name),
                               fname=out_name)

    return render_template("form.html")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    if request.method == "POST":
        file = request.files.get('qr_file')
        if not file or file.filename == '':
            return render_template("upload.html", error="No file selected.")
        ext = file.filename.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED:
            return render_template("upload.html", error="Unsupported file type.")
        try:
            img_bytes = file.read()
            img = Image.open(io.BytesIO(img_bytes))

            # ── Strategy 1: pyzbar on RGB ──────────────────────────────────────
            rgb = img.convert('RGB')
            decoded = pyzbar.decode(rgb)
            if decoded:
                results = [d.data.decode('utf-8', errors='replace') for d in decoded]
                return render_template("upload.html", results=results)

            # ── Strategy 2: pyzbar on grayscale ───────────────────────────────
            gray_pil = img.convert('L')
            decoded = pyzbar.decode(gray_pil)
            if decoded:
                results = [d.data.decode('utf-8', errors='replace') for d in decoded]
                return render_template("upload.html", results=results)

            # ── Strategy 3: pyzbar on contrast-enhanced grayscale ─────────────
            from PIL import ImageEnhance, ImageOps
            enhanced = ImageEnhance.Contrast(gray_pil).enhance(2.5)
            decoded = pyzbar.decode(enhanced)
            if decoded:
                results = [d.data.decode('utf-8', errors='replace') for d in decoded]
                return render_template("upload.html", results=results)

            # ── Strategy 4: pyzbar on inverted image (handles dark-bg QRs) ─────
            inverted = ImageOps.invert(gray_pil)
            decoded = pyzbar.decode(inverted)
            if decoded:
                results = [d.data.decode('utf-8', errors='replace') for d in decoded]
                return render_template("upload.html", results=results)

            # ── Strategy 5: OpenCV QRCodeDetector (handles styled/colored QRs) ─
            import cv2, numpy as np
            cv_img = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
            detector = cv2.QRCodeDetector()

            # try on original
            val, _, _ = detector.detectAndDecode(cv_img)
            if val:
                return render_template("upload.html", results=[val])

            # try on grayscale + Otsu threshold
            gray_cv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray_cv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            val, _, _ = detector.detectAndDecode(thresh)
            if val:
                return render_template("upload.html", results=[val])

            # try on inverted threshold (dark-background QRs)
            val, _, _ = detector.detectAndDecode(cv2.bitwise_not(thresh))
            if val:
                return render_template("upload.html", results=[val])

            return render_template("upload.html", error="Could not decode the QR code. Try a higher-resolution or better-lit image.")
        except Exception as e:
            return render_template("upload.html", error=f"Could not process image: {str(e)}")
    return render_template("upload.html")


@app.route("/QR/<p>")
def QRdown(p):
    return send_from_directory(app.config['UPLOAD_FOLDER'], p, as_attachment=True)


@app.route("/QRIMG/<p>")
def QRIMG(p):
    full = os.path.join(app.config['UPLOAD_FOLDER'], p)
    return render_template("QRIMG.html", user_image="/" + full, fname=p)


# ── Team contact-card QR (generated once, then cached) ────────────────────────
@app.route("/team-qr/<member>")
def team_qr(member):
    m = TEAM.get(member)
    if not m:
        return "Not found", 404
    out_path = os.path.join(TEAM_FOLDER, f"{member}.png")
    if not os.path.exists(out_path):          # generate and cache
        vcard = (f"BEGIN:VCARD\nVERSION:3.0\nN:{m['name']}\n"
                 f"TEL:{m['phone']}\nEMAIL:{m['email']}\nEND:VCARD")
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H,
                           box_size=8, border=3)
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