"""Student performance demo powered by a locally trained scikit-learn model."""

from __future__ import annotations

import hmac
import json
import math
import os
import secrets
from functools import wraps
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, g, make_response, redirect, render_template, request, session, url_for

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "model" / "student_model.joblib"
FEATURES = ["study_hours", "attendance", "previous_score"]
load_dotenv(ROOT / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
AUTH_COOKIE_SECURE = os.environ.get("AUTH_COOKIE_SECURE", "false").lower() == "true"
ACCESS_COOKIE = "auraed_access_token"
REFRESH_COOKIE = "auraed_refresh_token"
app.config["SESSION_COOKIE_SECURE"] = AUTH_COOKIE_SECURE


class SupabaseAuthError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class SupabaseUnavailableError(Exception):
    pass


class SupabaseDatabaseError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _supabase_request(endpoint, method="GET", payload=None, access_token=None):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise SupabaseUnavailableError(
            "Supabase isn't configured yet. Add SUPABASE_URL and SUPABASE_ANON_KEY to your .env file."
        )

    headers = {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(
        f"{SUPABASE_URL}/auth/v1/{endpoint}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(req, timeout=10) as response:
            response_body = response.read()
    except HTTPError as exc:
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            error_body = {}
        message = (
            error_body.get("msg")
            or error_body.get("message")
            or error_body.get("error_description")
            or "Supabase authentication request failed."
        )
        raise SupabaseAuthError(exc.code, message) from exc
    except (TimeoutError, URLError, OSError) as exc:
        raise SupabaseUnavailableError("Couldn't reach Supabase. Check your connection and try again.") from exc

    if not response_body:
        return {}
    try:
        return json.loads(response_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SupabaseUnavailableError("Supabase returned an unreadable response.") from exc


def _save_student_prediction(user_id, access_token, enrollment, study_hours, percentage, attendance, predicted):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise SupabaseUnavailableError(
            "Supabase isn't configured yet. Add SUPABASE_URL and SUPABASE_ANON_KEY to your .env file."
        )

    record = {
        "user_id": user_id,
        "enrollment_no": enrollment,
        "study_hours": study_hours,
        "percentage": percentage,
        "attendance": attendance,
        "predicted_percentage": predicted,
    }
    req = Request(
        f"{SUPABASE_URL}/rest/v1/student_predictions",
        data=json.dumps(record).encode("utf-8"),
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=10):
            return
    except HTTPError as exc:
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            error_body = {}
        message = (
            error_body.get("message")
            or error_body.get("details")
            or "Supabase rejected the student record. Check the table and Row Level Security setup."
        )
        raise SupabaseDatabaseError(exc.code, message) from exc
    except (TimeoutError, URLError, OSError) as exc:
        raise SupabaseUnavailableError(
            "Couldn't save the student record because Supabase is unreachable. Please try again."
        ) from exc


def _csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def _valid_csrf_token():
    submitted = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    return bool(submitted and expected and hmac.compare_digest(submitted, expected))


def _set_auth_cookies(response, tokens):
    response.set_cookie(
        ACCESS_COOKIE,
        tokens["access_token"],
        max_age=max(1, int(tokens.get("expires_in", 3600))),
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="Lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        tokens["refresh_token"],
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="Lax",
        path="/",
    )


def _clear_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, secure=AUTH_COOKIE_SECURE, httponly=True, samesite="Lax", path="/")
    response.delete_cookie(REFRESH_COOKIE, secure=AUTH_COOKIE_SECURE, httponly=True, samesite="Lax", path="/")
    return response


def _authenticated_user():
    access_token = request.cookies.get(ACCESS_COOKIE)
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if access_token:
        try:
            return _supabase_request("user", access_token=access_token), None
        except SupabaseAuthError as exc:
            if exc.status != 401:
                raise
    if not refresh_token:
        message = "Your session has expired. Please sign in again." if access_token else "Please sign in to continue."
        raise SupabaseAuthError(401, message)
    tokens = _supabase_request(
        "token?grant_type=refresh_token",
        method="POST",
        payload={"refresh_token": refresh_token},
    )
    user = _supabase_request("user", access_token=tokens["access_token"])
    return user, tokens


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            g.user, refreshed_tokens = _authenticated_user()
        except SupabaseAuthError as exc:
            if exc.status in (400, 401, 403):
                expired = bool(request.cookies.get(ACCESS_COOKIE) or request.cookies.get(REFRESH_COOKIE))
                response = make_response(
                    redirect(url_for("login", expired="1") if expired else url_for("login"))
                )
                return _clear_auth_cookies(response)
            error = "Supabase is temporarily unavailable. Please try again."
            return render_template("login.html", error=error, csrf_token=_csrf_token(), configured=True), 503
        except SupabaseUnavailableError as exc:
            return render_template(
                "login.html", error=str(exc), csrf_token=_csrf_token(), configured=False
            ), 503

        g.access_token = (
            refreshed_tokens["access_token"]
            if refreshed_tokens
            else request.cookies[ACCESS_COOKIE]
        )
        response = make_response(view(*args, **kwargs))
        if refreshed_tokens:
            _set_auth_cookies(response, refreshed_tokens)
        return response

    return wrapped


def load_model():
    if not MODEL_PATH.exists():
        return None
    return joblib.load(MODEL_PATH)


@app.get("/")
@login_required
def home():
    ready = MODEL_PATH.exists()
    return render_template(
        "index.html",
        model_ready=ready,
        user_email=g.user.get("email", ""),
        csrf_token=_csrf_token(),
        form_values={},
    )


@app.route("/login", methods=("GET", "POST"))
def login():
    error = None
    if request.method == "POST":
        if not _valid_csrf_token():
            return render_template(
                "login.html",
                error="This sign-in form expired. Refresh the page and try again.",
                csrf_token=_csrf_token(),
                configured=bool(SUPABASE_URL and SUPABASE_ANON_KEY),
            ), 400
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email or not password:
            error = "Enter your email and password."
        elif not SUPABASE_URL or not SUPABASE_ANON_KEY:
            error = "Supabase isn't configured yet. Add SUPABASE_URL and SUPABASE_ANON_KEY to your .env file."
        else:
            try:
                tokens = _supabase_request(
                    "token?grant_type=password",
                    method="POST",
                    payload={"email": email, "password": password},
                )
                if not tokens.get("access_token") or not tokens.get("refresh_token"):
                    raise SupabaseUnavailableError("Supabase didn't return a complete sign-in session.")
                session.clear()
                session["csrf_token"] = secrets.token_urlsafe(32)
                response = make_response(redirect(url_for("home")))
                _set_auth_cookies(response, tokens)
                return response
            except SupabaseAuthError as exc:
                if exc.status in (400, 401):
                    error = "We couldn't sign you in. Check your email and password."
                elif exc.status == 429:
                    error = "Too many sign-in attempts. Please wait a moment and try again."
                else:
                    error = "Supabase is temporarily unavailable. Please try again."
            except SupabaseUnavailableError as exc:
                error = str(exc)

    if request.args.get("expired") == "1":
        error = "Your session has expired. Please sign in again."
    return render_template(
        "login.html",
        error=error,
        csrf_token=_csrf_token(),
        configured=bool(SUPABASE_URL and SUPABASE_ANON_KEY),
    )


@app.post("/logout")
def logout():
    if not _valid_csrf_token():
        return render_template(
            "login.html",
            error="This sign-out form expired. Refresh the page and try again.",
            csrf_token=_csrf_token(),
            configured=bool(SUPABASE_URL and SUPABASE_ANON_KEY),
        ), 400
    access_token = request.cookies.get(ACCESS_COOKIE)
    error = None
    if access_token and SUPABASE_URL and SUPABASE_ANON_KEY:
        try:
            _supabase_request("logout", method="POST", access_token=access_token)
        except SupabaseAuthError as exc:
            if exc.status not in (400, 401, 403):
                error = "You were signed out on this device, but Supabase couldn't revoke the session."
        except SupabaseUnavailableError:
            error = "You were signed out on this device, but Supabase couldn't revoke the session."

    session.clear()
    response = make_response(
        render_template("login.html", error=error, csrf_token=_csrf_token(),
                        configured=bool(SUPABASE_URL and SUPABASE_ANON_KEY))
        if error else redirect(url_for("login"))
    )
    return _clear_auth_cookies(response)


@app.post("/predict")
@login_required
def predict():
    form_values = {
        "enrollment_no": request.form.get("enrollment_no", "").strip(),
        "study_hours": request.form.get("study_hours", ""),
        "percentage": request.form.get("percentage", ""),
        "attendance": request.form.get("attendance", ""),
    }
    if not _valid_csrf_token():
        return render_template(
            "index.html",
            model_ready=MODEL_PATH.exists(),
            error="This form expired. Refresh the page and submit your details again.",
            user_email=g.user.get("email", ""),
            csrf_token=_csrf_token(),
            form_values=form_values,
        ), 400

    try:
        enrollment = form_values["enrollment_no"]
        if not enrollment or len(enrollment) > 32:
            raise ValueError("Enter a valid enrollment number (up to 32 characters).")

        hours = float(form_values["study_hours"])
        percentage = float(form_values["percentage"])
        attendance = float(form_values["attendance"])
        if not all(math.isfinite(value) for value in (hours, percentage, attendance)):
            raise ValueError("Enter valid numeric values for study hours, percentage, and attendance.")
        if not 0 <= hours <= 24:
            raise ValueError("Study hours must be between 0 and 24.")
        if not 0 <= attendance <= 100:
            raise ValueError("Attendance must be between 0 and 100%.")
        if not 0 <= percentage <= 100:
            raise ValueError("Percentage must be between 0 and 100.")

        model = load_model()
        if model is None:
            raise RuntimeError("The model has not been generated yet. Run python train.py first.")

        predicted = float(model.predict(pd.DataFrame([[hours, attendance, percentage]], columns=FEATURES))[0])
        score = round(float(np.clip(predicted, 0, 100)))
        _save_student_prediction(
            g.user["id"],
            g.access_token,
            enrollment,
            hours,
            percentage,
            attendance,
            score,
        )
        passed = score >= 50
        status = "On track" if score >= 75 else ("Building momentum" if passed else "Needs support")
        message = (
            "Strong habits are showing up in your forecast. Keep the rhythm going."
            if score >= 75 else
            "You have a foundation to build on. A little more consistency can move the needle."
            if passed else
            "A focused study plan and regular check-ins can help improve this outlook."
        )
        share_text = f"My projected final score is {score}/100 ({status}). See your own forecast: {request.url_root}"
        return render_template(
            "result.html", score=score, enrollment=enrollment, status=status,
            message=message, passed=passed, whatsapp_url="https://wa.me/?text=" + quote(share_text),
            user_email=g.user.get("email", ""),
            csrf_token=_csrf_token(),
            saved=True,
        )
    except SupabaseDatabaseError as exc:
        error = (
            f"Supabase could not save this submission (HTTP {exc.status}): {exc}. "
            "Check that you ran the supplied SQL and enabled the table policies."
        )
        return render_template(
            "index.html",
            model_ready=MODEL_PATH.exists(),
            error=error,
            user_email=g.user.get("email", ""),
            csrf_token=_csrf_token(),
            form_values=form_values,
        ), 503
    except SupabaseUnavailableError as exc:
        return render_template(
            "index.html",
            model_ready=MODEL_PATH.exists(),
            error=str(exc),
            user_email=g.user.get("email", ""),
            csrf_token=_csrf_token(),
            form_values=form_values,
        ), 503
    except (TypeError, ValueError, RuntimeError) as exc:
        return render_template(
            "index.html",
            model_ready=MODEL_PATH.exists(),
            error=str(exc),
            user_email=g.user.get("email", ""),
            csrf_token=_csrf_token(),
            form_values=form_values,
        ), 400


if __name__ == "__main__":
    # Bind to loopback for local use; deployment servers bind via Gunicorn instead.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "7860")), debug=False)
