#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PowerShell Krypta - Flask-pohjainen suomenkielinen oppimispeli.

Tärkeää: pelaajan lähettämää PowerShell-koodia EI suoriteta. Sitä verrataan
vain ennalta määriteltyihin tekstipohjaisiin tarkistuksiin.
"""

from __future__ import annotations

import hmac
import os
import re
import secrets
import sqlite3
from functools import wraps
from pathlib import Path
from typing import Callable

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(BASE_DIR / "krypta.db")))
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY puuttuu. Luo salainen avain ja aseta se ympäristömuuttujaksi. "
        "Katso README.md."
    )

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
    MAX_CONTENT_LENGTH=16 * 1024,
)


ROOMS = [
    {
        "name": "Aloitushalli",
        "subtitle": "Ensimmäinen yhteys kryptaan",
        "icon": "⌁",
        "description": "Korkea kivihalli hohtaa vihreää valoa. Seinään on kaiverrettu: jokainen mestari aloittaa yhdestä komennosta.",
        "lesson": """PowerShell-komentoja kutsutaan usein cmdleteiksi. Niiden nimet ovat yleensä muotoa Verbi-Substantiivi.

Get-Help näyttää ohjeita.
Get-Command listaa komentoja.
Get-Location näyttää nykyisen sijainnin.

Esimerkiksi: Get-Help Get-ChildItem""",
        "title": "Ensimmäinen loitsu",
        "prompt": "Kirjoita PowerShell-komento, jolla näet nykyisen kansion tai sijainnin.",
        "hint": "Get-Location",
        "success": "Oikein! Löysit nykyisen sijaintisi. Hallin ovi avautuu.",
    },
    {
        "name": "Komentokäytävä",
        "subtitle": "Etsi oikea komento",
        "icon": "⌘",
        "description": "Käytävän seinillä vilkkuu komentojen nimiä. Vanha kompassi osoittaa kohti komentoluetteloa.",
        "lesson": """Get-Command etsii käytettävissä olevia komentoja.

Esimerkkejä:
Get-Command process
Get-Command -Verb Get
Get-Help Get-Process

Parametrit alkavat tavallisesti yhdysmerkillä, kuten -Verb.""",
        "title": "Kadonnut komentoluettelo",
        "prompt": "Millä cmdletillä etsitään PowerShell-komentoja? Kirjoita komento.",
        "hint": "Get-Command",
        "success": "Hienoa! Komentoluettelo löytyi. Eteenpäin!",
    },
    {
        "name": "Muuttujatorni",
        "subtitle": "Tallenna tieto muuttujaan",
        "icon": "◇",
        "description": "Tornissa leijuu valoisia laatikoita. Jokaisessa on muuttujan nimi ja sen sisällä säilytettävä arvo.",
        "lesson": '''PowerShell-muuttujan nimi alkaa dollarimerkillä ($). Arvo asetetaan yhtäsuuruusmerkillä.

$nimi = "Ada"
$ika = 25
Write-Output $nimi

Muuttujan avulla voit käyttää samaa arvoa myöhemmin uudelleen.''',
        "title": "Nimeä taikakristalli",
        "prompt": 'Luo muuttuja nimeltä $nimi ja anna sille tekstiarvo "Ada".',
        "hint": '$nimi = "Ada"',
        "success": "Täydellistä! Kristalli tunnistaa nimesi ja syttyy.",
    },
    {
        "name": "Putkikuilu",
        "subtitle": "Yhdistä komennot putkella",
        "icon": "⇢",
        "description": "Edessäsi virtaa tietojen joki. Sen yli pääsee vain rakentamalla putken, joka kuljettaa tulokset komennolta toiselle.",
        "lesson": """Putki eli pipeline (|) välittää yhden komennon tulokset seuraavalle.

Esimerkki:
Get-Process | Sort-Object CPU -Descending

Tämä hakee prosessit ja järjestää ne CPU-arvon mukaan suurimmasta pienimpään.""",
        "title": "Rakenna tietoputki",
        "prompt": "Kirjoita komento, joka hakee prosessit ja järjestää ne CPU-arvon mukaan laskevaan järjestykseen.",
        "hint": "Get-Process | Sort-Object CPU -Descending",
        "success": "Putki toimii! Tietojen joki kantaa sinut seuraavaan huoneeseen.",
    },
    {
        "name": "Tiedostoluola",
        "subtitle": "Luo kansio",
        "icon": "▤",
        "description": "Luolan seinissä on tuhansia kansioita. Kivinen vartija etsii uutta kansiota nimeltä Raportit.",
        "lesson": '''Get-ChildItem listaa kansion sisällön. Sen aliaksia ovat esimerkiksi dir ja ls.

Uuden kansion voi luoda näin:
New-Item -ItemType Directory -Name "Raportit"

New-Item luo uuden kohteen. -ItemType määrittää kohteen tyypin.''',
        "title": "Avaa uusi kansio",
        "prompt": 'Kirjoita komento, joka luo Raportit-nimisen kansion.',
        "hint": 'New-Item -ItemType Directory -Name "Raportit"',
        "success": "Vartija kumartaa. Raportit-kansio on luotu!",
    },
    {
        "name": "Ehtojen silta",
        "subtitle": "Tee päätös ehdon avulla",
        "icon": "⋈",
        "description": "Sillan keskellä on kaksi ovea. Vain oikein kirjoitettu ehtolause sytyttää vihreän valon.",
        "lesson": '''if suorittaa koodin vain, kun ehto on tosi.

$lampotila = 22
if ($lampotila -gt 20) {
    Write-Output "Lämmintä"
}

Vertailuoperaattoreita: -eq (yhtä suuri), -ne (eri suuri), -gt (suurempi) ja -lt (pienempi).''',
        "title": "Sytytä vihreä valo",
        "prompt": "Kirjoita if-ehto, joka tarkistaa onko $ika suurempi kuin 17. Aaltosulkeiden sisällä ei tarvitse olla sisältöä.",
        "hint": "if ($ika -gt 17) { }",
        "success": "Ehto on tosi! Silta muuttuu vihreäksi.",
    },
    {
        "name": "Komentojen valtaistuin",
        "subtitle": "Viimeinen koetus",
        "icon": "♜",
        "description": "Kryptan viimeisessä salissa komentojen vartija pyytää sinua toistamaan toiminnon jokaiselle listan alkiolle.",
        "lesson": '''foreach käy läpi kokoelman yksi alkio kerrallaan.

$hedelmat = @("omena", "päärynä")
foreach ($hedelma in $hedelmat) {
    Write-Output $hedelma
}

Silmukoita käytetään, kun sama toiminto pitää tehdä monelle arvolle.''',
        "title": "Viimeinen koetus",
        "prompt": "Kirjoita foreach-rivi, joka käy muuttujan $hedelmat läpi käyttäen alkiomuuttujaa $hedelma.",
        "hint": "foreach ($hedelma in $hedelmat) { }",
        "success": "Voitto! Olet läpäissyt PowerShell Kryptan. Osaat nyt cmdletit, muuttujat, putket, tiedostot, ehdot ja silmukat.",
    },
]


def compact(code: str) -> str:
    return re.sub(r"\s+", " ", code.strip()).lower()


def valid_answer(room_index: int, code: str) -> bool:
    """Tarkistaa PowerShell-vastauksen tekstinä. Ei koskaan suorita koodia."""
    value = compact(code)
    if room_index == 0:
        return value.rstrip(";") == "get-location"
    if room_index == 1:
        return value.rstrip(";") == "get-command"
    if room_index == 2:
        return re.search(r'''\$nimi\s*=\s*(["'])Ada\1''', code, re.IGNORECASE) is not None
    if room_index == 3:
        return all(part in value for part in ("get-process", "|", "sort-object", "cpu", "-descending"))
    if room_index == 4:
        return (
            all(part in value for part in ("new-item", "-itemtype", "directory", "-name"))
            and re.search(r'''(["'])Raportit\1''', code, re.IGNORECASE) is not None
        )
    if room_index == 5:
        return re.search(r"\bif\s*\(\s*\$ika\s+-gt\s+17\s*\)\s*\{", code, re.IGNORECASE) is not None
    if room_index == 6:
        return re.search(
            r"\bforeach\s*\(\s*\$hedelma\s+in\s+\$hedelmat\s*\)\s*\{",
            code,
            re.IGNORECASE,
        ) is not None
    return False


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db


@app.teardown_appcontext
def close_db(_error: Exception | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS progress (
            user_id INTEGER NOT NULL,
            room_index INTEGER NOT NULL,
            hints_used INTEGER NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, room_index),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()
    db.close()


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.context_processor
def inject_template_globals():
    return {"csrf_token": csrf_token, "current_username": session.get("username")}


@app.before_request
def check_csrf() -> None:
    if request.method == "POST":
        submitted = request.form.get("_csrf_token", "")
        expected = session.get("_csrf_token", "")
        if not expected or not hmac.compare_digest(submitted, expected):
            abort(400, description="Lomakkeen istunto vanheni. Päivitä sivu ja yritä uudelleen.")


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    )
    return response


def login_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Kirjaudu sisään jatkaaksesi.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def get_progress(user_id: int) -> dict[int, dict]:
    rows = get_db().execute(
        "SELECT room_index, hints_used, completed FROM progress WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {row["room_index"]: dict(row) for row in rows}


def ensure_progress(user_id: int, room_index: int) -> None:
    get_db().execute(
        "INSERT OR IGNORE INTO progress (user_id, room_index) VALUES (?, ?)",
        (user_id, room_index),
    )
    get_db().commit()


def active_room_index(progress: dict[int, dict]) -> int:
    for index in range(len(ROOMS)):
        row = progress.get(index)
        if not row or not row["completed"]:
            return index
    return len(ROOMS) - 1


@app.get("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,24}", username):
            flash("Käyttäjätunnuksen pitää olla 3–24 merkkiä: kirjaimet, numerot, piste, _ tai -.", "error")
        elif len(password) < 10 or len(password) > 128:
            flash("Salasanan pitää olla 10–128 merkkiä pitkä.", "error")
        else:
            try:
                cursor = get_db().execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                get_db().commit()
                session.clear()
                session["user_id"] = cursor.lastrowid
                session["username"] = username
                session.permanent = True
                flash("Tunnus luotu. Tervetuloa kryptaan!", "success")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("Tämä käyttäjätunnus on jo käytössä.", "error")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session.permanent = True
            flash("Kirjautuminen onnistui. Yhteys kryptaan muodostettu.", "success")
            return redirect(url_for("dashboard"))
        flash("Virheellinen käyttäjätunnus tai salasana.", "error")
    return render_template("auth.html", mode="login")


@app.post("/logout")
@login_required
def logout():
    session.clear()
    flash("Kirjauduit ulos.", "success")
    return redirect(url_for("index"))


@app.get("/game")
@login_required
def dashboard():
    user_id = session["user_id"]
    progress = get_progress(user_id)
    active = active_room_index(progress)
    ensure_progress(user_id, active)
    progress = get_progress(user_id)
    completed = sum(1 for item in progress.values() if item["completed"])
    hints = sum(item["hints_used"] for item in progress.values())
    score = max(0, completed * 100 - hints * 10)
    return render_template(
        "dashboard.html",
        rooms=ROOMS,
        progress=progress,
        active=active,
        completed=completed,
        hints=hints,
        score=score,
    )


@app.route("/room/<int:room_index>", methods=["GET", "POST"])
@login_required
def play_room(room_index: int):
    if room_index < 0 or room_index >= len(ROOMS):
        abort(404)
    user_id = session["user_id"]
    progress = get_progress(user_id)
    active = active_room_index(progress)
    if room_index > active:
        flash("Tämä huone on vielä lukittu. Suorita edellinen tehtävä ensin.", "warning")
        return redirect(url_for("dashboard"))

    ensure_progress(user_id, room_index)
    room = ROOMS[room_index]

    if request.method == "POST":
        row = get_progress(user_id).get(room_index, {})
        if row.get("completed"):
            flash("Tämä tehtävä on jo suoritettu.", "success")
            return redirect(url_for("play_room", room_index=room_index))

        action = request.form.get("action", "")
        if action == "hint":
            get_db().execute(
                "UPDATE progress SET hints_used = hints_used + 1 WHERE user_id = ? AND room_index = ?",
                (user_id, room_index),
            )
            get_db().commit()
            flash(f"Vihje: {room['hint']}  (−10 pistettä)", "warning")
        elif action == "answer":
            answer = request.form.get("answer", "")
            if len(answer) > 4000:
                flash("Vastaus on liian pitkä.", "error")
            elif valid_answer(room_index, answer):
                get_db().execute(
                    "UPDATE progress SET completed = 1 WHERE user_id = ? AND room_index = ?",
                    (user_id, room_index),
                )
                get_db().commit()
                flash(room["success"], "success")
                if room_index == len(ROOMS) - 1:
                    flash("🏆 Olet läpäissyt koko PowerShell Kryptan!", "success")
                else:
                    flash("Seuraava huone on nyt avattu.", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Ei aivan. Tarkista oppitunti ja yritä uudelleen.", "error")
        else:
            abort(400)
        return redirect(url_for("play_room", room_index=room_index))

    row = get_progress(user_id).get(room_index, {})
    return render_template("room.html", room=room, room_index=room_index, row=row)


@app.errorhandler(400)
def bad_request(error):
    return render_template(
        "error.html",
        code=400,
        heading="BAD REQUEST",
        message=getattr(error, "description", "Virheellinen pyyntö."),
    ), 400


@app.errorhandler(404)
def not_found(_error):
    return render_template(
        "error.html", code=404, heading="NOT FOUND", message="Sivua ei löytynyt."
    ), 404


init_db()

if __name__ == "__main__":
    # Vain paikalliseen testaukseen. Julkaisussa käytä Gunicornia ja Nginxiä.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
