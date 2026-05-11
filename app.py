import os
import psycopg2
import psycopg2.extras
from datetime import datetime, date

from flask import Flask, render_template, request, redirect, url_for, flash
from google.cloud import vision


APP_NAME = "えいてぃーちゃん吸ったミックス履歴"

DATABASE_URL = os.environ.get("DATABASE_URL")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL が設定されていません。")

    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mixes (
            id SERIAL PRIMARY KEY,
            smoked_date DATE NOT NULL,
            mix_text TEXT NOT NULL,
            staff_name TEXT,
            rating INTEGER,
            memo TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


def ocr_image(image_file):
    client = vision.ImageAnnotatorClient()

    content = image_file.read()
    image = vision.Image(content=content)

    response = client.text_detection(image=image)

    if response.error.message:
        raise Exception(response.error.message)

    texts = response.text_annotations

    if not texts:
        return ""

    return texts[0].description.strip()


@app.route("/")
def index():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            id,
            smoked_date,
            mix_text,
            staff_name,
            rating,
            memo,
            created_at
        FROM mixes
        ORDER BY smoked_date DESC, id DESC;
    """)

    mixes = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "index.html",
        app_name=APP_NAME,
        mixes=mixes
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    today = date.today().isoformat()

    if request.method == "POST":
        image_file = request.files.get("flavor_card")

        if not image_file or image_file.filename == "":
            flash("フレーバーカード写真を選択してください。")
            return redirect(url_for("add"))

        try:
            mix_text = ocr_image(image_file)
        except Exception as e:
            flash(f"文字起こしに失敗しました: {e}")
            return redirect(url_for("add"))

        return render_template(
            "confirm.html",
            app_name=APP_NAME,
            smoked_date=today,
            mix_text=mix_text
        )

    return render_template(
        "add.html",
        app_name=APP_NAME
    )


@app.route("/save", methods=["POST"])
def save():
    smoked_date = request.form.get("smoked_date", "").strip()
    mix_text = request.form.get("mix_text", "").strip()
    staff_name = request.form.get("staff_name", "").strip()
    rating = request.form.get("rating", "").strip()
    memo = request.form.get("memo", "").strip()

    if not smoked_date:
        flash("吸った日を入力してください。")
        return redirect(url_for("add"))

    if not mix_text:
        flash("ミックス情報を入力してください。")
        return redirect(url_for("add"))

    rating_value = None
    if rating:
        try:
            rating_value = int(rating)
        except ValueError:
            rating_value = None

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO mixes (
            smoked_date,
            mix_text,
            staff_name,
            rating,
            memo,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s);
    """, (
        smoked_date,
        mix_text,
        staff_name,
        rating_value,
        memo,
        datetime.now()
    ))

    conn.commit()

    cur.close()
    conn.close()

    flash("ミックス履歴を保存しました。")
    return redirect(url_for("index"))


@app.route("/delete/<int:mix_id>", methods=["POST"])
def delete(mix_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM mixes WHERE id = %s;", (mix_id,))

    conn.commit()

    cur.close()
    conn.close()

    flash("削除しました。")
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)