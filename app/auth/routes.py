"""Registration, login, logout and password reset."""

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.constants import ROLE_ADMIN, ROLE_DONOR, ROLE_RECIPIENT
from app.services import password_reset, users
from app.services.errors import ServiceError
from app.services.mailer import delivery_available, get_outbox, smtp_configured
from app.services.validation import (
    validate_email,
    validate_login,
    validate_password_reset,
    validate_registration,
)
from app.utils.ratelimit import rate_limit
from app.utils.security import is_safe_redirect_target

INVALID_LOGIN = "Invalid email or password."
DEMO_LOGIN_PASSWORD = "demo1234"


def _can_view_outbox():
    """Console mail links are for local development admins only, never the public."""
    config = current_app.config
    return (
        config.get("ALLOW_CONSOLE_MAIL")
        and not smtp_configured()
        and (current_app.debug or config.get("APP_ENV") == "testing")
        and current_user.is_authenticated
        and current_user.role == ROLE_ADMIN
    )


@bp.route("/login", methods=["GET", "POST"])
@rate_limit("login-ip", 20, 300)
@rate_limit("login-email", 5, 300, key="form:email")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    errors = {}
    if request.method == "POST":
        cleaned, errors = validate_login(request.form)
        if errors:
            flash(INVALID_LOGIN, "error")
        else:
            demo_state = None
            if current_app.config.get("ALLOW_DEMO_LOGIN"):
                user, demo_state = users.demo_login(
                    cleaned["email"],
                    cleaned["password"],
                    current_app.config.get("DEMO_LOGIN_PASSWORD")
                    or DEMO_LOGIN_PASSWORD,
                )
                state = "ok" if user else "invalid"
            else:
                user, state = users.authenticate(cleaned["email"], cleaned["password"])
            if state == "ok":
                login_user(user)
                session.permanent = True
                if current_app.config.get("ALLOW_DEMO_LOGIN"):
                    session["demo_email"] = user.email
                if demo_state != "demo":
                    users.record_login(user)
                target = request.args.get("next") or request.form.get("next")
                if is_safe_redirect_target(target):
                    return redirect(target)
                return redirect(url_for("dashboard.home"))
            if state == "suspended":
                flash(
                    "This account has been suspended. Please contact an administrator.",
                    "error",
                )
            else:
                flash(INVALID_LOGIN, "error")
    return (
        render_template(
            "auth/login.html",
            form=request.form,
            errors={},
            next_url=request.args.get("next", ""),
            demo_login=current_app.config.get("ALLOW_DEMO_LOGIN"),
            demo_password=current_app.config.get("DEMO_LOGIN_PASSWORD")
            or DEMO_LOGIN_PASSWORD,
        ),
        200,
    )


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been signed out.", "success")
    response = redirect(url_for("auth.login"))
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/register")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    return render_template("auth/register_choice.html")


def _register(role):
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    errors = {}
    if request.method == "POST":
        cleaned, errors = validate_registration(request.form, role)
        if not errors:
            if current_app.config.get("ALLOW_DEMO_LOGIN"):
                demo_password = (
                    current_app.config.get("DEMO_LOGIN_PASSWORD") or DEMO_LOGIN_PASSWORD
                )
                if cleaned.get("password") != demo_password:
                    errors["password"] = "Demo mode: use password %s." % demo_password
                    status = 400
                    return (
                        render_template(
                            "auth/register.html",
                            role=role,
                            form=request.form,
                            errors=errors,
                            demo_login=True,
                            demo_password=demo_password,
                        ),
                        status,
                    )
                user, _ = users.demo_login(
                    cleaned["email"], cleaned["password"], demo_password, role=role
                )
                login_user(user)
                session.permanent = True
                session["demo_email"] = user.email
                flash("Welcome to HemoLink! Demo account is ready.", "success")
                return redirect(url_for("dashboard.home"))
            try:
                user = users.register_user(cleaned, role)
            except ServiceError as error:
                errors[error.field or "form"] = error.message
            else:
                login_user(user)
                session.permanent = True
                users.record_login(user)
                flash("Welcome to HemoLink! Your account has been created.", "success")
                return redirect(url_for("dashboard.home"))
        status = 400
    else:
        status = 200
    return (
        render_template(
            "auth/register.html",
            role=role,
            form=request.form,
            errors=errors,
            demo_login=current_app.config.get("ALLOW_DEMO_LOGIN"),
            demo_password=current_app.config.get("DEMO_LOGIN_PASSWORD")
            or DEMO_LOGIN_PASSWORD,
        ),
        status,
    )


@bp.route("/register/donor", methods=["GET", "POST"])
@rate_limit("register", 10, 3600)
def register_donor():
    return _register(ROLE_DONOR)


@bp.route("/register/recipient", methods=["GET", "POST"])
@rate_limit("register", 10, 3600)
def register_recipient():
    return _register(ROLE_RECIPIENT)


@bp.route("/forgot-password", methods=["GET", "POST"])
@rate_limit("forgot", 5, 900)
def forgot_password():
    errors = {}
    available = delivery_available()
    if request.method == "POST":
        if not available:
            flash(
                "Password reset by email is not available on this deployment. "
                "Please contact an administrator.",
                "error",
            )
        else:
            email, error = validate_email(request.form.get("email"))
            if error:
                errors["email"] = error
            else:
                password_reset.request_reset(email)
                flash(
                    "If an account exists for that email, we have sent reset "
                    "instructions. The link expires soon and works once.",
                    "success",
                )
                return redirect(url_for("auth.login"))
    return render_template(
        "auth/forgot_password.html",
        form=request.form,
        errors=errors,
        available=available,
        dev_console=_can_view_outbox(),
    )


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@rate_limit("reset", 10, 900)
def reset_password(token):
    row = password_reset.get_valid_token(token)
    if row is None:
        return render_template("auth/reset_password.html", invalid=True, errors={}), 400
    errors = {}
    if request.method == "POST":
        cleaned, errors = validate_password_reset(request.form, row.user.email)
        if not errors:
            try:
                password_reset.reset_password(token, cleaned["password"])
            except ServiceError as error:
                errors["form"] = error.message
            else:
                flash("Your password has been changed. Please sign in.", "success")
                return redirect(url_for("auth.login"))
    return render_template(
        "auth/reset_password.html",
        invalid=False,
        errors=errors,
        token=token,
    ), (400 if errors else 200)


@bp.route("/dev/outbox")
def dev_outbox():
    """Development-only view of emails the console mail backend captured."""
    if not _can_view_outbox():
        abort(404)
    messages = list(reversed(get_outbox()))
    return render_template("auth/dev_outbox.html", messages=messages)
