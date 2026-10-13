import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import SuspiciousFileOperation
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.core.files.storage import default_storage
from django.db import connection
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods, require_POST

from . import google_meet, mpesa, paypal, stripe_card, whatsapp
from .forms import CreateAccountForm
from .models import (
    Exam,
    Invoice,
    Payment,
    PracticalAttendance,
    ResourceMaterial,
    SchoolClass,
    SupportTicket,
    User,
)


SUPPORT_PHONE = "0721954896"


def health_check(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


def index(request):
    return render(request, "index.html")


@require_http_methods(["GET", "POST"])
def login_view(request):
    login_role = request.GET.get("role", "").strip().lower()
    if request.path.rstrip("/").endswith("login/teacher"):
        login_role = "teacher"
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user and user.check_password(password):
            request.session.cycle_key()
            request.session["user_id"] = user.pk
            request.session["role"] = user.role
            return redirect("dashboard")
        messages.error(request, "Invalid email or password.")
        return render(request, "login.html", {"login_role": login_role})
    return render(request, "login.html", {"login_role": login_role})


@require_http_methods(["GET", "POST"])
def create_account(request):
    form = CreateAccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = User(
                    email=form.cleaned_data["email"],
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    role="student",
                )
                user.set_password(form.cleaned_data["password"])
                user.save()
        except IntegrityError:
            form.add_error("email", "An account already exists with this email.")
        else:
            request.session.cycle_key()
            request.session["user_id"] = user.pk
            request.session["role"] = user.role
            return redirect("dashboard")
    return render(request, "create_account.html", {"form": form})


def logout_view(request):
    request.session.flush()
    return redirect("index")


def _current_user(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return User.objects.filter(pk=user_id, is_active=True).first()


def dashboard(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    context = {
        "user": user,
        "classes": SchoolClass.objects.order_by("-id")[:3],
        "resources": ResourceMaterial.objects.order_by("-id")[:3],
        "invoices": Invoice.objects.order_by("-id"),
        "total_users": User.objects.count(),
        "total_classes": SchoolClass.objects.count(),
        "total_resources": ResourceMaterial.objects.count(),
        "total_invoices": Invoice.objects.count(),
    }
    return render(request, "dashboard.html", context)


@require_http_methods(["GET", "POST"])
def staff_room(request):
    user = _current_user(request)
    if not user or user.role not in ("teacher", "admin"):
        return redirect("login")

    if request.method == "POST":
        upload = request.FILES.get("material_file")
        allowed_extensions = {
            ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
            ".mp4", ".mp3", ".jpg", ".jpeg", ".png",
        }
        extension = "." + upload.name.rsplit(".", 1)[-1].lower() if upload and "." in upload.name else ""
        required_fields = ("title", "subject", "grade_level", "resource_type", "term", "academic_year")
        if not upload or extension not in allowed_extensions:
            messages.error(request, "Choose a supported PDF, Office, audio, video, or image file.")
            return redirect("staff_room")
        if any(not request.POST.get(field, "").strip() for field in required_fields):
            messages.error(request, "Complete all material details before uploading.")
            return redirect("staff_room")

        stored_path = default_storage.save(f"library/{upload.name}", upload)
        ResourceMaterial.objects.create(
            title=request.POST["title"].strip(),
            subject=request.POST["subject"].strip(),
            grade_level=request.POST["grade_level"].strip(),
            resource_type=request.POST["resource_type"].strip(),
            term=request.POST["term"].strip(),
            academic_year=request.POST["academic_year"].strip(),
            file_url=default_storage.url(stored_path),
            uploaded_by=f"{user.first_name} {user.last_name}".strip() or user.email,
        )
        messages.success(request, "Material uploaded to the digital library.")
        return redirect("staff_room")

    return render(
        request,
        "staff_room.html",
        {
            "user": user,
            "resources": ResourceMaterial.objects.order_by("-id")[:8],
            "total_resources": ResourceMaterial.objects.count(),
        },
    )


def library(request):
    user = _current_user(request)
    return render(
        request,
        "library.html",
        {
            "resources": ResourceMaterial.objects.order_by("-id"),
            "is_staff": bool(user and user.role in ("teacher", "admin")),
        },
    )


@require_http_methods(["GET", "HEAD"])
def serve_media(request, file_path):
    try:
        uploaded_file = default_storage.open(file_path, "rb")
    except (FileNotFoundError, SuspiciousFileOperation):
        raise Http404
    response = FileResponse(uploaded_file)
    response["X-Content-Type-Options"] = "nosniff"
    return response


def billing(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    invoices = Invoice.objects.all()
    if user.role in ("student", "parent"):
        invoices = invoices.filter(
            Q(student_name__icontains=user.first_name) | Q(student_name__icontains=user.last_name)
        )
        if not invoices.exists():
            invoices = Invoice.objects.all()
    mpesa_pending = bool(request.session.get("mpesa_checkout_id"))
    return render(request, "billing.html", {"user": user, "invoices": invoices, "mpesa_pending": mpesa_pending})


def _record_payment(invoice, amount, method, reference):
    Payment.objects.create(invoice=invoice, amount=amount, method=method, reference=reference)
    invoice.amount_paid += amount
    invoice.status = "Paid" if invoice.amount_paid >= invoice.total_amount else "Partially Paid"
    invoice.save(update_fields=["amount_paid", "status"])


def _validated_amount(request, invoice):
    try:
        amount = Decimal(request.POST.get("amount", "0")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    remaining = invoice.total_amount - invoice.amount_paid
    if amount <= 0 or amount > remaining:
        return None
    return amount


@require_POST
def pay_invoice(request, invoice_id):
    user = _current_user(request)
    if not user:
        return redirect("login")
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    amount = _validated_amount(request, invoice)
    if amount is None:
        messages.error(request, "Enter a valid payment amount up to the outstanding total.")
        return redirect("billing")
    method = request.POST.get("method", "mpesa")
    if method not in dict(Payment.METHOD_CHOICES):
        method = "mpesa"
    if method == "paypal":
        request.session["paypal_amount"] = str(amount)
        request.session["paypal_invoice_id"] = invoice.pk
        return redirect("paypal_start")
    if method in ("visa", "card"):
        request.session["card_amount"] = str(amount)
        request.session["card_invoice_id"] = invoice.pk
        request.session["card_method"] = method
        return redirect("card_start")
    if method == "mpesa":
        phone = mpesa.normalize_phone(request.POST.get("phone", ""))
        if not phone:
            messages.error(request, "Enter a valid M-Pesa phone number (e.g. 0712345678).")
            return redirect("billing")
        request.session["mpesa_amount"] = str(amount)
        request.session["mpesa_invoice_id"] = invoice.pk
        request.session["mpesa_phone"] = phone
        return redirect("mpesa_start")
    _record_payment(invoice, amount, method, f"PAY-{uuid.uuid4().hex[:10].upper()}")
    messages.success(request, f"Payment of KES {amount} recorded for {invoice.invoice_number}.")
    return redirect("billing")


@require_http_methods(["GET"])
def mpesa_start(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    invoice = get_object_or_404(Invoice, pk=request.session.get("mpesa_invoice_id"))
    amount = Decimal(request.session.get("mpesa_amount", "0"))
    phone = request.session.get("mpesa_phone", "")
    if amount <= 0 or not phone:
        messages.error(request, "No M-Pesa payment is in progress.")
        return redirect("billing")
    checkout_id, error = mpesa.stk_push(
        amount,
        phone,
        invoice.invoice_number,
        request.build_absolute_uri("/billing/mpesa/callback"),
    )
    if checkout_id is None and error is None:
        # Daraja not configured: record a local demo payment instead.
        _record_payment(invoice, amount, "mpesa", f"MP-DEMO-{uuid.uuid4().hex[:10].upper()}")
        for key in ("mpesa_amount", "mpesa_invoice_id", "mpesa_phone"):
            request.session.pop(key, None)
        messages.success(request, f"Demo M-Pesa payment of KES {amount} recorded for {invoice.invoice_number}.")
        return redirect("billing")
    if error:
        messages.error(request, f"M-Pesa request failed: {error}")
        return redirect("billing")
    request.session["mpesa_checkout_id"] = checkout_id
    messages.success(request, f"M-Pesa prompt sent to {phone}. Enter your PIN, then confirm below.")
    return redirect("billing")


@require_http_methods(["GET"])
def mpesa_status(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    invoice = get_object_or_404(Invoice, pk=request.session.get("mpesa_invoice_id"))
    amount = Decimal(request.session.get("mpesa_amount", "0"))
    checkout_id = request.session.get("mpesa_checkout_id", "")
    paid = checkout_id and mpesa.stk_query(checkout_id)
    for key in ("mpesa_amount", "mpesa_invoice_id", "mpesa_phone", "mpesa_checkout_id"):
        request.session.pop(key, None)
    if paid:
        _record_payment(invoice, amount, "mpesa", f"MP-{checkout_id}")
        messages.success(request, f"M-Pesa payment of KES {amount} confirmed for {invoice.invoice_number}.")
    else:
        messages.error(request, "M-Pesa payment not confirmed yet. Try again after entering your PIN.")
    return redirect("billing")


@require_http_methods(["GET"])
def mpesa_callback(request):
    # Placeholder endpoint for the Safaricom callback URL.
    return redirect("billing")


@require_http_methods(["GET"])
def paypal_start(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    invoice = get_object_or_404(Invoice, pk=request.session.get("paypal_invoice_id"))
    amount = Decimal(request.session.get("paypal_amount", "0"))
    if amount <= 0:
        messages.error(request, "No PayPal payment is in progress.")
        return redirect("billing")
    order_id, approve_url = paypal.create_order(
        amount,
        "USD",
        request.build_absolute_uri("/billing/paypal/return"),
        request.build_absolute_uri("/billing/paypal/cancel"),
        invoice.invoice_number,
    )
    if not approve_url:
        # PayPal not configured: record a local demo payment instead.
        _record_payment(invoice, amount, "paypal", f"PP-DEMO-{uuid.uuid4().hex[:10].upper()}")
        request.session.pop("paypal_amount", None)
        request.session.pop("paypal_invoice_id", None)
        messages.success(request, f"Demo PayPal payment of {amount} recorded for {invoice.invoice_number}.")
        return redirect("billing")
    request.session["paypal_order_id"] = order_id
    return redirect(approve_url)


@require_http_methods(["GET"])
def paypal_return(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    invoice = get_object_or_404(Invoice, pk=request.session.get("paypal_invoice_id"))
    amount = Decimal(request.session.get("paypal_amount", "0"))
    order_id = request.session.get("paypal_order_id", "") or request.GET.get("token", "")
    success, reference = paypal.capture_order(order_id)
    request.session.pop("paypal_amount", None)
    request.session.pop("paypal_invoice_id", None)
    request.session.pop("paypal_order_id", None)
    if success:
        _record_payment(invoice, amount, "paypal", f"PP-{reference}")
        messages.success(request, f"PayPal payment of {amount} captured for {invoice.invoice_number}.")
    else:
        messages.error(request, "PayPal payment could not be completed.")
    return redirect("billing")


@require_http_methods(["GET"])
def paypal_cancel(request):
    request.session.pop("paypal_amount", None)
    request.session.pop("paypal_invoice_id", None)
    request.session.pop("paypal_order_id", None)
    messages.error(request, "PayPal payment was cancelled.")
    return redirect("billing")


@require_http_methods(["GET"])
def card_start(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    invoice = get_object_or_404(Invoice, pk=request.session.get("card_invoice_id"))
    amount = Decimal(request.session.get("card_amount", "0"))
    method = request.session.get("card_method", "card")
    if amount <= 0:
        messages.error(request, "No card payment is in progress.")
        return redirect("billing")
    session_id, checkout_url = stripe_card.create_checkout_session(
        amount,
        "USD",
        request.build_absolute_uri("/billing/card/return"),
        request.build_absolute_uri("/billing/card/cancel"),
        invoice.invoice_number,
    )
    if not checkout_url:
        # Stripe not configured: record a local demo card payment instead.
        _record_payment(invoice, amount, method, stripe_card.demo_reference())
        for key in ("card_amount", "card_invoice_id", "card_method"):
            request.session.pop(key, None)
        messages.success(request, f"Demo card payment of {amount} recorded for {invoice.invoice_number}.")
        return redirect("billing")
    request.session["card_session_id"] = session_id
    return redirect(checkout_url)


@require_http_methods(["GET"])
def card_return(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    invoice = get_object_or_404(Invoice, pk=request.session.get("card_invoice_id"))
    amount = Decimal(request.session.get("card_amount", "0"))
    method = request.session.get("card_method", "card")
    session_id = request.session.get("card_session_id", "")
    paid, reference = stripe_card.retrieve_session(session_id)
    for key in ("card_amount", "card_invoice_id", "card_method", "card_session_id"):
        request.session.pop(key, None)
    if paid:
        _record_payment(invoice, amount, method, f"CARD-{reference}")
        messages.success(request, f"Card payment of {amount} completed for {invoice.invoice_number}.")
    else:
        messages.error(request, "Card payment could not be completed.")
    return redirect("billing")


@require_http_methods(["GET"])
def card_cancel(request):
    for key in ("card_amount", "card_invoice_id", "card_method", "card_session_id"):
        request.session.pop(key, None)
    messages.error(request, "Card payment was cancelled.")
    return redirect("billing")


@require_http_methods(["GET", "POST"])
def classes_page(request):
    user = _current_user(request)
    is_staff = bool(user and user.role in ("teacher", "admin"))
    if request.method == "POST":
        if not is_staff:
            return redirect("login")
        title = request.POST.get("title", "").strip()
        subject = request.POST.get("subject", "").strip()
        start_value = request.POST.get("start_at", "").strip()
        try:
            scheduled_start = datetime.fromisoformat(start_value)
            if scheduled_start.tzinfo is None:
                scheduled_start = timezone.make_aware(scheduled_start, timezone.get_current_timezone())
        except ValueError:
            scheduled_start = None

        if not title or not subject or not scheduled_start:
            messages.error(request, "Enter a lesson title, subject, date, and start time.")
            return redirect("classes")
        if scheduled_start <= timezone.now():
            messages.error(request, "Choose a future date and time for the lesson.")
            return redirect("classes")

        end_time = scheduled_start + timezone.timedelta(hours=1)
        pasted_url = request.POST.get("meeting_url", "").strip()
        if pasted_url:
            meeting_url = pasted_url
            space_name = ""
        else:
            try:
                meeting = google_meet.create_meeting()
            except google_meet.GoogleMeetError as error:
                messages.error(request, str(error))
                return redirect("classes")
            meeting_url = meeting["join_url"]
            space_name = meeting["space_name"]

        SchoolClass.objects.create(
            title=title,
            teacher_name=f"{user.first_name} {user.last_name}".strip() or user.email,
            subject=subject,
            lesson_date=scheduled_start.date(),
            start_time=scheduled_start.strftime("%I:%M %p"),
            end_time=end_time.strftime("%I:%M %p"),
            room_name="google-meet",
            meeting_url=meeting_url,
            google_meet_space_name=space_name,
            recurrence="One-off",
        )
        messages.success(request, "One-hour Google Meet lesson scheduled successfully.")
        return redirect("classes")

    return render(
        request,
        "classes.html",
        {
            "classes": SchoolClass.objects.order_by("id"),
            "is_staff": is_staff,
            "google_meet_configured": google_meet.is_configured(),
        },
    )


@require_POST
def class_go_live(request, class_id):
    user = _current_user(request)
    if not user or user.role not in ("teacher", "admin"):
        return redirect("login")
    school_class = get_object_or_404(SchoolClass, pk=class_id)
    if not school_class.meeting_url.startswith("https://meet.google.com/"):
        messages.error(request, "This lesson has no Google Meet link. Schedule a new Google Meet lesson.")
        return redirect("classes")
    school_class.status = "Live"
    school_class.save(update_fields=["status"])
    messages.success(request, f"{school_class.title} is now live on Google Meet.")
    return redirect("classes")


@require_http_methods(["GET", "POST"])
def exams_page(request):
    user = _current_user(request)
    is_staff = bool(user and user.role in ("teacher", "admin"))
    if request.method == "POST":
        if not is_staff:
            return redirect("login")
        upload = request.FILES.get("pdf_file")
        if not upload or not upload.name.lower().endswith(".pdf"):
            messages.error(request, "Please choose a PDF file to upload.")
            return redirect("exams")
        Exam.objects.create(
            title=request.POST.get("title", "").strip() or upload.name,
            subject=request.POST.get("subject", "").strip(),
            grade_level=request.POST.get("grade_level", "").strip(),
            term=request.POST.get("term", "").strip(),
            academic_year=request.POST.get("academic_year", "").strip(),
            pdf_file=upload,
            uploaded_by=f"{user.first_name} {user.last_name}".strip() or user.email,
        )
        messages.success(request, "Exam uploaded successfully.")
        return redirect("exams")
    return render(
        request,
        "exams.html",
        {
            "exams": Exam.objects.order_by("-id"),
            "is_staff": is_staff,
            "whatsapp_configured": whatsapp.is_configured(),
            "can_send_whatsapp": bool(user and user.role in ("student", "teacher", "admin")),
        },
    )


def practical_lab(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    if user.role not in ("student", "teacher", "admin"):
        return redirect("dashboard")
    return render(
        request,
        "practical_lab.html",
        {"user": user, "whatsapp_configured": whatsapp.is_configured()},
    )


@require_http_methods(["GET", "POST"])
def practical_attendance(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    if user.role not in ("teacher", "admin"):
        return redirect("dashboard")

    if request.method == "POST":
        session_date = parse_date(request.POST.get("session_date", ""))
        if not session_date:
            messages.error(request, "Choose a valid date for this practical session.")
            return redirect("practical_attendance")
        students = list(User.objects.filter(role="student", is_active=True).order_by("last_name", "first_name", "id"))
        submitted_ids = set(request.POST.keys()) - {"csrfmiddlewaretoken", "session_date"}
        expected_ids = {f"attendance_{student.pk}" for student in students}
        if submitted_ids != expected_ids:
            messages.error(request, "Attendance was not saved. Reload the register and mark every listed student.")
            return redirect(f"{request.path}?date={session_date.isoformat()}")

        statuses = {
            key.removeprefix("attendance_"): request.POST.get(key, "")
            for key in expected_ids
        }
        if any(status not in dict(PracticalAttendance.STATUS_CHOICES) for status in statuses.values()):
            messages.error(request, "Attendance was not saved. Choose Present or Absent for every student.")
            return redirect(f"{request.path}?date={session_date.isoformat()}")

        with transaction.atomic():
            for student in students:
                PracticalAttendance.objects.update_or_create(
                    student=student,
                    practical="Physics: investigating a resistor",
                    session_date=session_date,
                    defaults={
                        "status": statuses[str(student.pk)],
                        "marked_by": user,
                    },
                )
        messages.success(request, f"Attendance saved for {session_date:%d %B %Y}.")
        return redirect(f"{request.path}?date={session_date.isoformat()}")

    session_date = parse_date(request.GET.get("date", "")) or timezone.localdate()
    students = User.objects.filter(role="student", is_active=True).order_by("last_name", "first_name", "id")
    attendance_by_student = {
        record.student_id: record.status
        for record in PracticalAttendance.objects.filter(
            practical="Physics: investigating a resistor",
            session_date=session_date,
            student__in=students,
        )
    }
    rows = [
        {
            "student": student,
            "status": attendance_by_student.get(student.pk, ""),
        }
        for student in students
    ]
    return render(
        request,
        "practical_attendance.html",
        {
            "rows": rows,
            "session_date": session_date.isoformat(),
            "present_count": sum(row["status"] == "present" for row in rows),
            "absent_count": sum(row["status"] == "absent" for row in rows),
            "unmarked_count": sum(not row["status"] for row in rows),
        },
    )


@require_POST
def send_practical_whatsapp_invite(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    if user.role not in ("student", "teacher", "admin"):
        return redirect("dashboard")

    practical_url = request.build_absolute_uri("/practical-exams")
    message = (
        "Physics practical practice: investigate the current-voltage relationship "
        f"in the virtual lab: {practical_url}"
    )
    try:
        whatsapp.send_group_message(message)
    except whatsapp.WhatsAppAPIError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Practical invitation sent to the WhatsApp group.")
    return redirect("practical_exams")


@require_http_methods(["GET", "POST"])
def support_page(request):
    if request.method == "POST":
        SupportTicket.objects.create(
            user_name=request.POST.get("user_name", "").strip(),
            user_email=request.POST.get("user_email", "").strip(),
            subject=request.POST.get("subject", "").strip(),
            message=request.POST.get("message", "").strip(),
        )
        return redirect("support")
    return render(request, "support.html", {"support_phone": SUPPORT_PHONE})


def contact_page(request):
    return render(
        request,
        "support.html",
        {"support_phone": SUPPORT_PHONE, "contact_only": True},
    )