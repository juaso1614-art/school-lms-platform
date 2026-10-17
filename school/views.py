import secrets
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import SuspiciousFileOperation
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.core.files.storage import default_storage
from django.db import connection
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods, require_POST

from . import jitsi, knec, mpesa, paypal, stripe_card, whatsapp
from .forms import CreateAccountForm, GameQuestionForm, GameTopicForm, SchoolStaffProfileForm
from .models import (
    Exam,
    GameProgress,
    GameQuestion,
    KnecSubmission,
    GameTopic,
    Invoice,
    LoginHistory,
    Payment,
    PracticalAttendance,
    ResourceMaterial,
    SchoolClass,
    SchoolStaffProfile,
    SubjectBook,
    SubjectCatalog,
    SubjectDocket,
    TeacherSubjectAssignment,
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
    admin_login = request.path.rstrip("/").endswith("admin-login")
    login_role = "admin" if admin_login else request.GET.get("role", "").strip().lower()
    if request.path.rstrip("/").endswith("login/teacher"):
        login_role = "teacher"
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        authenticated = bool(
            user
            and user.check_password(password)
            and (not admin_login or user.role == "admin")
        )
        LoginHistory.objects.create(
            user=user,
            email=email,
            ip_address=request.META.get("REMOTE_ADDR") or None,
            successful=authenticated,
        )
        if authenticated:
            request.session.cycle_key()
            request.session["user_id"] = user.pk
            request.session["role"] = user.role
            return redirect("school_admin" if admin_login else "dashboard")
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


def games_corner(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    if user.role not in ("student", "teacher", "admin"):
        return redirect("dashboard")

    grade_levels = list(
        SubjectCatalog.objects.filter(is_active=True)
        .values_list("grade_level", flat=True)
        .distinct()
    )

    def grade_sort_key(grade):
        try:
            return (0, int(grade.split()[-1]))
        except (AttributeError, ValueError):
            return (1, grade.casefold())

    grade_levels.sort(key=grade_sort_key)
    requested_grade = request.GET.get("grade", "")
    selected_grade = requested_grade if requested_grade in grade_levels else (grade_levels[0] if grade_levels else "")
    subjects = SubjectCatalog.objects.filter(is_active=True, grade_level=selected_grade).select_related("docket")
    try:
        selected_subject_id = int(request.GET.get("subject", ""))
    except ValueError:
        selected_subject_id = None
    selected_subject = subjects.filter(pk=selected_subject_id).first() if selected_subject_id else None
    topics = []
    progress_by_topic = {}
    if selected_subject:
        topics = list(
            GameTopic.objects.filter(subject=selected_subject, is_active=True)
            .annotate(
                level_one_questions=Count("questions", filter=Q(questions__is_active=True, questions__difficulty=1)),
                level_two_questions=Count("questions", filter=Q(questions__is_active=True, questions__difficulty=2)),
                level_three_questions=Count("questions", filter=Q(questions__is_active=True, questions__difficulty=3)),
                total_questions=Count("questions", filter=Q(questions__is_active=True)),
            )
            .order_by("title")
        )
        progress_by_topic = {
            progress.topic_id: progress
            for progress in GameProgress.objects.filter(user=user, topic__in=topics)
        }
        for topic in topics:
            topic.progress = progress_by_topic.get(topic.pk)

    return render(
        request,
        "games.html",
        {
            "grade_levels": grade_levels,
            "selected_grade": selected_grade,
            "subjects": subjects,
            "selected_subject": selected_subject,
            "topics": topics,
            "progress_by_topic": progress_by_topic,
            "is_staff": user.role in ("teacher", "admin"),
        },
    )


@require_http_methods(["GET", "POST"])
def games_author(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    if user.role not in ("teacher", "admin"):
        return redirect("dashboard")

    topics = GameTopic.objects.filter(is_active=True, subject__is_active=True).select_related("subject")
    topic_form = GameTopicForm()
    question_form = GameQuestionForm(topics=topics)
    if request.method == "POST" and request.POST.get("action") == "create-topic":
        topic_form = GameTopicForm(request.POST)
        if topic_form.is_valid():
            topic = topic_form.save(commit=False)
            topic.created_by = user
            topic.save()
            messages.success(request, "Game topic created. Add its questions by level.")
            return redirect(f"{reverse('games_author')}?topic={topic.pk}")
    elif request.method == "POST" and request.POST.get("action") == "add-question":
        question_form = GameQuestionForm(request.POST, topics=topics)
        if question_form.is_valid():
            question = question_form.save()
            messages.success(request, f"Question added to Level {question.difficulty}.")
            return redirect(f"{reverse('games_author')}?topic={question.topic_id}")

    try:
        selected_topic_id = int(request.GET.get("topic", ""))
    except ValueError:
        selected_topic_id = None
    selected_topic = topics.filter(pk=selected_topic_id).first() if selected_topic_id else None
    topic_questions = list(selected_topic.questions.filter(is_active=True)) if selected_topic else []
    return render(
        request,
        "games_author.html",
        {
            "topic_form": topic_form,
            "question_form": question_form,
            "topics": topics,
            "selected_topic": selected_topic,
            "topic_questions": topic_questions,
        },
    )


ACTIVITY_MODES = ("flashcards", "matching")


@require_http_methods(["GET", "POST"])
def game_play(request, topic_id):
    user = _current_user(request)
    if not user:
        return redirect("login")
    if user.role not in ("student", "teacher", "admin"):
        return redirect("dashboard")

    topic = get_object_or_404(GameTopic, pk=topic_id, is_active=True, subject__is_active=True)
    progress, _ = GameProgress.objects.get_or_create(user=user, topic=topic)
    topic.total_questions = topic.questions.filter(is_active=True).count()

    mode = request.GET.get("mode", "") or request.POST.get("mode", "")
    if mode in ACTIVITY_MODES:
        return _game_activity(request, topic, progress, mode)

    questions = list(
        topic.questions.filter(is_active=True, difficulty=progress.current_level).order_by("order", "id")
    )
    feedback = ""
    feedback_type = ""
    selected_choice = None

    if request.method == "POST" and request.POST.get("action") == "restart":
        progress.current_level = 1
        progress.unlocked_level = 1
        progress.completed_level = 0
        progress.question_index = 0
        progress.score = 0
        progress.attempts = 0
        progress.save()
        return redirect("game_play", topic_id=topic.pk)

    state = "playing"
    question = None
    if not questions:
        state = "not_ready"
    elif progress.question_index >= len(questions):
        state = "complete"
    else:
        question = questions[progress.question_index]

    if request.method == "POST" and state == "playing" and question:
        try:
            submitted_question_id = int(request.POST.get("question_id", ""))
            selected_choice = int(request.POST.get("choice", ""))
        except ValueError:
            submitted_question_id = -1
            selected_choice = -1

        if submitted_question_id != question.pk or not 0 <= selected_choice < len(question.choices):
            feedback = "Choose one of the answers for the current question."
            feedback_type = "error"
        else:
            progress.attempts += 1
            if selected_choice != question.correct_choice:
                progress.save(update_fields=("attempts", "updated_at"))
                feedback = "Not passed yet. Try another answer to continue."
                feedback_type = "error"
            else:
                progress.score += progress.current_level * 10
                progress.question_index += 1
                progress.save(update_fields=("score", "question_index", "attempts", "updated_at"))
                if progress.question_index >= len(questions):
                    progress.completed_level = max(progress.completed_level, progress.current_level)
                    next_level = progress.current_level + 1
                    has_next_level = topic.questions.filter(is_active=True, difficulty=next_level).exists()
                    if has_next_level:
                        progress.current_level = next_level
                        progress.unlocked_level = max(progress.unlocked_level, next_level)
                        progress.question_index = 0
                        feedback = f"Level {progress.completed_level} passed. Level {next_level} unlocked."
                        feedback_type = "success"
                    else:
                        feedback = "Topic complete. You passed every available level."
                        feedback_type = "success"
                    progress.save()
                else:
                    messages.success(request, f"Correct! +{progress.current_level * 10} points.")
                    return redirect("game_play", topic_id=topic.pk)
                if feedback_type == "success":
                    messages.success(request, feedback)
                    return redirect("game_play", topic_id=topic.pk)

    return render(
        request,
        "game_play.html",
        {
            "topic": topic,
            "progress": progress,
            "state": state,
            "question": question,
            "question_number": progress.question_index + 1,
            "question_total": len(questions),
            "feedback": feedback,
            "feedback_type": feedback_type,
            "selected_choice": selected_choice,
            "choice_labels": ("A", "B", "C", "D"),
        },
    )


def _game_activity(request, topic, progress, mode):
    """Flashcard and matching game modes built from the topic's questions."""
    if request.method == "POST" and request.POST.get("action") == "activity-complete":
        try:
            earned = int(request.POST.get("score", "0"))
            spent = int(request.POST.get("attempts", "1"))
        except ValueError:
            earned, spent = 0, 1
        question_count = topic.questions.filter(is_active=True).count()
        progress.score += max(0, min(earned, question_count * 10))
        progress.attempts += max(1, min(spent, 500))
        progress.save(update_fields=("score", "attempts", "updated_at"))
        label = "Flashcard deck" if mode == "flashcards" else "Matching game"
        messages.success(request, f"{label} complete — {min(max(earned, 0), question_count * 10)} points added to your score.")
        return redirect(f"{reverse('games')}?grade={topic.subject.grade_level}&subject={topic.subject_id}")

    questions = list(
        topic.questions.filter(is_active=True).order_by("difficulty", "order", "id")
    )
    if not questions:
        messages.info(request, "Questions are still being prepared for this game.")
        return redirect(f"{reverse('games')}?grade={topic.subject.grade_level}&subject={topic.subject_id}")

    cards = []
    for question in questions:
        answer = question.choices[question.correct_choice] if 0 <= question.correct_choice < len(question.choices) else ""
        cards.append({
            "prompt": question.prompt,
            "answer": answer,
            "explanation": question.explanation,
        })

    return render(
        request,
        "game_activity.html",
        {
            "topic": topic,
            "progress": progress,
            "mode": mode,
            "mode_title": "Flashcards" if mode == "flashcards" else "Matching",
            "cards": cards,
        },
    )


@require_http_methods(["GET", "POST"])
def school_admin(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    if user.role != "admin":
        return redirect("dashboard")

    form = SchoolStaffProfileForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "School staff profile added.")
        return redirect("school_admin")

    role_groups = [
        {
            "value": role,
            "label": label,
            "staff": SchoolStaffProfile.objects.filter(role=role),
        }
        for role, label in SchoolStaffProfile.ROLE_CHOICES
    ]
    return render(
        request,
        "school_admin.html",
        {
            "form": form,
            "role_groups": role_groups,
            "total_staff_profiles": SchoolStaffProfile.objects.count(),
            "login_history": LoginHistory.objects.select_related("user")[:20],
        },
    )


@require_http_methods(["GET", "POST"])
def staff_room(request):
    user = _current_user(request)
    if not user or user.role not in ("teacher", "admin"):
        return redirect("login")

    if request.method == "POST":
        staff_form_fields = (
            "staff_role",
            "staff_full_name",
            "staff_email",
            "staff_phone",
            "department",
            "campus",
            "staff_id",
        )
        if any(field in request.POST for field in staff_form_fields):
            required_fields = {"staff_role", "staff_full_name", "staff_email", "staff_id"}
            missing = [field for field in sorted(required_fields) if not request.POST.get(field, "").strip()]
            if missing:
                messages.error(request, "Complete the required staff details before saving the profile.")
                return redirect("staff_room")

            profile = SchoolStaffProfile.objects.filter(staff_id=request.POST["staff_id"].strip()).first()
            if profile:
                messages.error(request, "A staff profile with this staff ID already exists.")
                return redirect("staff_room")

            SchoolStaffProfile.objects.create(
                full_name=request.POST["staff_full_name"].strip(),
                email=request.POST["staff_email"].strip(),
                phone=request.POST.get("staff_phone", "").strip(),
                role=request.POST["staff_role"].strip(),
                department=request.POST.get("department", "").strip(),
                campus=request.POST.get("campus", "").strip(),
                staff_id=request.POST["staff_id"].strip(),
            )
            messages.success(request, "School leadership profile saved successfully.")
            return redirect("staff_room")

        revision_fields = {
            "book_title",
            "book_subject",
            "book_grade",
            "book_author",
            "book_docket",
            "book_summary",
            "book_outline",
            "book_exercises",
            "book_diagrams",
        }
        if any(field in request.POST for field in revision_fields):
            required_book_fields = {"book_title", "book_subject", "book_grade", "book_author"}
            missing = [field for field in sorted(required_book_fields) if not request.POST.get(field, "").strip()]
            if missing:
                messages.error(request, "Complete the required revision book details before submitting.")
                return redirect("staff_room")

            docket_map = {
                "Lower Primary": "lower_primary",
                "Upper Primary": "upper_primary",
                "Junior Secondary": "junior_secondary",
                "Senior Secondary": "senior_secondary",
            }
            grade_level = request.POST["book_grade"].strip()
            docket_slug = docket_map.get(request.POST["book_docket"].strip(), "lower_primary")
            docket, _ = SubjectDocket.objects.get_or_create(
                slug=docket_slug,
                defaults={
                    "title": request.POST["book_docket"].strip() or "Lower Primary",
                    "description": "CBE academic docket",
                    "grade_band": docket_slug,
                    "display_order": {"lower_primary": 1, "upper_primary": 2, "junior_secondary": 3, "senior_secondary": 4}.get(docket_slug, 1),
                },
            )
            subject, _ = SubjectCatalog.objects.get_or_create(
                name=request.POST["book_subject"].strip(),
                grade_level=grade_level,
                defaults={
                    "code": f"{request.POST['book_subject'].strip()[:3].upper()}-{grade_level.replace(' ', '')}",
                    "docket": docket,
                    "description": "Teacher curated subject plan",
                },
            )
            if subject.docket_id != docket.id:
                subject.docket = docket
                subject.save(update_fields=["docket"])

            book = SubjectBook.objects.create(
                title=request.POST["book_title"].strip(),
                subject=subject,
                grade_level=grade_level,
                author_name=request.POST["book_author"].strip(),
                docket=docket,
                description=request.POST.get("book_summary", "").strip(),
                content_outline=request.POST.get("book_outline", "").strip(),
                exercises=request.POST.get("book_exercises", "").strip(),
                diagrams=request.POST.get("book_diagrams", "").strip(),
                created_by=user,
                is_teacher_uploaded=True,
            )
            TeacherSubjectAssignment.objects.get_or_create(
                teacher=user,
                subject=subject,
                defaults={"role": "Subject Teacher"},
            )
            ResourceMaterial.objects.create(
                title=book.title,
                subject=book.subject.name,
                grade_level=book.grade_level,
                resource_type="Revision Book",
                term="Term 1",
                academic_year=str(datetime.now().year),
                file_url=book.file_url or "/library",
                uploaded_by=f"{user.first_name} {user.last_name}".strip() or user.email,
                author_name=book.author_name,
                content_summary=book.description,
                is_revision_material=True,
            )
            messages.success(request, "Revision material and subject book saved successfully.")
            return redirect("staff_room")

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
            is_revision_material=True,
        )
        messages.success(request, "Material uploaded to the digital library.")
        return redirect("staff_room")

    return render(
        request,
        "staff_room.html",
        {
            "user": user,
            "resources": ResourceMaterial.objects.order_by("-id")[:8],
            "staff_profiles": SchoolStaffProfile.objects.order_by("-id")[:8],
            "subject_books": SubjectBook.objects.order_by("-id")[:8],
            "subject_dockets": SubjectDocket.objects.order_by("display_order").prefetch_related("subjects"),
            "total_resources": ResourceMaterial.objects.count(),
            "total_staff_profiles": SchoolStaffProfile.objects.count(),
            "total_subject_books": SubjectBook.objects.count(),
        },
    )


def library(request):
    user = _current_user(request)
    return render(
        request,
        "library.html",
        {
            "resources": ResourceMaterial.objects.order_by("-id"),
            "subject_dockets": SubjectDocket.objects.order_by("display_order").prefetch_related("subjects"),
            "subject_books": SubjectBook.objects.order_by("-created_at"),
            "teacher_assignments": TeacherSubjectAssignment.objects.select_related("teacher", "subject").order_by("subject__docket__display_order", "subject__grade_level", "subject__name"),
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
            meeting = jitsi.create_meeting(title=title)
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
        messages.success(request, "One-hour Jitsi Meet lesson scheduled successfully.")
        return redirect("classes")

    return render(
        request,
        "classes.html",
        {
            "classes": SchoolClass.objects.order_by("id"),
            "is_staff": is_staff,
        },
    )


@require_POST
def class_go_live(request, class_id):
    user = _current_user(request)
    if not user or user.role not in ("teacher", "admin"):
        return redirect("login")
    school_class = get_object_or_404(SchoolClass, pk=class_id)
    if not school_class.meeting_url.startswith("https://meet.jit.si/"):
        messages.error(request, "This lesson has no Jitsi Meet link. Schedule a new Jitsi lesson.")
        return redirect("classes")
    school_class.status = "Live"
    school_class.save(update_fields=["status"])
    messages.success(request, f"{school_class.title} is now live on Jitsi Meet.")
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


def _knec_session_key(request):
    """Per-session HMAC key the .knec packer signs manifests with."""
    key = request.session.get("knec_hmac_key")
    if not key:
        key = secrets.token_hex(32)
        request.session["knec_hmac_key"] = key
    return key


@require_http_methods(["POST"])
def knec_submit(request):
    """Receive a packed .knec archive, validate it and store valid ones."""
    user = _current_user(request)
    if not user:
        return JsonResponse({"ok": False, "errors": ["Please log in before submitting."]}, status=401)
    if user.role not in ("student", "teacher", "admin"):
        return JsonResponse({"ok": False, "errors": ["Your account cannot submit practical archives."]}, status=403)
    upload = request.FILES.get("archive")
    if not upload:
        return JsonResponse({"ok": False, "errors": ["Attach the packed .knec archive."]}, status=400)
    manifest, errors = knec.validate_archive(
        upload.read(), upload.name, _knec_session_key(request)
    )
    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)
    submission = KnecSubmission.objects.create(
        subject_code=manifest["subject"]["code"],
        index_number=str(manifest["candidate"]["index_number"]),
        paper=manifest["subject"]["paper"],
        archive=upload,
        manifest=manifest,
        uploaded_by=f"{user.first_name} {user.last_name}".strip() or user.email,
    )
    return JsonResponse(
        {"ok": True, "submission_id": submission.pk, "manifest": manifest, "filename": upload.name}
    )


def practical_lab(request):
    user = _current_user(request)
    if not user:
        return redirect("login")
    if user.role not in ("student", "teacher", "admin"):
        return redirect("dashboard")
    practicals = (
        {"title": "Estimate resistance", "steps": ("Adjust the rheostat to obtain different current values.", "Read the voltmeter and ammeter for each setting.", "Record six pairs of readings and estimate resistance using V / I.")},
        {"title": "Verify Ohm's law", "steps": ("Record six voltage and current pairs as the rheostat changes.", "Compare how voltage changes as current changes.", "State whether the observations support a proportional relationship.")},
        {"title": "Compare V / I values", "steps": ("Record the six readings across the rheostat range.", "Calculate V / I for each row in the results table.", "Compare the ratios and explain what they indicate about resistance.")},
        {"title": "Investigate current and voltage", "steps": ("Start at low rheostat resistance and record a reading.", "Increase rheostat resistance in steps and record six pairs.", "Describe the trend between circuit current and the resistor voltage.")},
        {"title": "Repeatability of readings", "steps": ("Choose a rheostat setting and record the meter readings.", "Repeat the same setting twice and compare the values.", "Use six readings to discuss consistency and likely measurement variation.")},
    )
    return render(
        request,
        "practical_lab.html",
        {
            "user": user,
            "whatsapp_configured": whatsapp.is_configured(),
            "practicals": practicals,
            "knec_hmac_key": _knec_session_key(request),
        },
    )


PRACTICAL_LABS = (
    {
        "slug": "geography",
        "name": "Geography Field Lab",
        "icon": "🌍",
        "room": "Earth & environment studio",
        "description": "Explore landforms, contour lines, weather patterns, and field observations with an interactive terrain table.",
        "activity": "Investigate how rainfall and elevation shape a landscape. Adjust the rainfall and rotate the terrain to compare runoff and contour patterns.",
        "learning_outcome": "Explain how slope and rainfall affect surface runoff using observations from the model.",
        "lesson_steps": (
            "Set simulated rainfall to 20 mm and observe the terrain and contour lines.",
            "Repeat at 60 mm and 90 mm; note how the runoff estimate changes.",
            "Rotate the model and identify the steeper and gentler slopes.",
            "Compare your observations and state where erosion risk is greatest.",
        ),
        "equipment": ("3D terrain model", "Contour map table", "Weather station", "Field compass", "Rain gauge"),
        "scene": "terrain",
        "practicals": (
            {"title": "Rainfall and runoff", "activity": "Compare simulated runoff at three rainfall levels and relate the change to the terrain slope.", "lesson_steps": ("Set rainfall to 20 mm and note the runoff estimate.", "Repeat at 60 mm and 90 mm, then compare the results."), "learning_outcome": "Explain how rainfall intensity and slope affect surface runoff."},
            {"title": "Reading contour patterns", "activity": "Use the terrain model and contour lines to identify steep and gentle areas.", "lesson_steps": ("Rotate the terrain and locate the closest contour lines.", "Compare them with widely spaced contours and identify the steeper slope."), "learning_outcome": "Interpret contour spacing as evidence of changing gradient."},
            {"title": "Erosion risk survey", "activity": "Investigate which parts of the model are most at risk of erosion during heavy rain.", "lesson_steps": ("Set rainfall to 90 mm and inspect the high and low ground.", "Identify a likely runoff path and explain where soil loss may be greatest."), "learning_outcome": "Use terrain and rainfall observations to identify erosion risk."},
            {"title": "Field-site selection", "activity": "Choose a suitable site for a school path while avoiding steep slopes and concentrated runoff.", "lesson_steps": ("Rotate the terrain to compare the ridge, slope, and lower ground.", "Select a route and support it with contour and rainfall observations."), "learning_outcome": "Justify a land-use choice using physical geography evidence."},
            {"title": "Weather station observation", "activity": "Conduct a short virtual field observation and relate the rainfall reading to the landscape.", "lesson_steps": ("Set two different rainfall values and observe the terrain response.", "Record how the weather condition could affect movement across the site."), "learning_outcome": "Connect a weather observation to likely effects on a local environment."},
        ),
    },
    {
        "slug": "languages",
        "name": "Language & Communication Studio",
        "icon": "💬",
        "room": "Multilingual listening studio",
        "description": "Practice listening, pronunciation, vocabulary, and sentence-building at an interactive language-learning station.",
        "activity": "Choose a practice phrase and use the studio controls to explore speech pace and clear pronunciation. The app does not capture or upload microphone recordings.",
        "learning_outcome": "Use listening, repetition, and sentence clues to communicate a short greeting clearly.",
        "lesson_steps": (
            "Choose a phrase and listen once at the normal pace.",
            "Replay it slowly and identify the greeting and the question.",
            "Say the phrase aloud, then repeat it at the normal pace.",
            "Compare the versions and note one sound or word that was difficult.",
        ),
        "equipment": ("Studio microphone", "Listening headphones", "Audio recorder", "Phrase cards", "Waveform display"),
        "scene": "language",
        "practicals": (
            {"title": "Greeting and response", "activity": "Listen to a greeting and prepare a clear, appropriate spoken response.", "lesson_steps": ("Choose a phrase and listen at normal pace.", "Replay it slowly, then say the greeting and response aloud."), "learning_outcome": "Recognize and use a short greeting in the selected language."},
            {"title": "Listening for key words", "activity": "Identify the important words in a short greeting or question.", "lesson_steps": ("Listen once without repeating the phrase.", "Replay it and identify the greeting, question, and time reference."), "learning_outcome": "Extract key meaning from a short spoken phrase."},
            {"title": "Speech pace practice", "activity": "Compare how speech pace affects clarity and understanding.", "lesson_steps": ("Listen to the phrase at 0.6× pace and note one sound.", "Increase the pace gradually and repeat it clearly at normal speed."), "learning_outcome": "Adjust speaking pace while preserving clear pronunciation."},
            {"title": "Language comparison", "activity": "Compare how the studio phrase expresses a greeting in different languages.", "lesson_steps": ("Listen to the English phrase and note its meaning.", "Choose Kiswahili or French and compare the greeting and question."), "learning_outcome": "Identify shared meaning across greetings in different languages."},
            {"title": "Pronunciation and fluency", "activity": "Practice a complete phrase with steady pace and clear pronunciation.", "lesson_steps": ("Listen to the phrase once at normal pace.", "Repeat it slowly, then again at normal pace with clear word endings."), "learning_outcome": "Deliver a short phrase with improved fluency and intelligibility."},
        ),
    },
    {
        "slug": "computer",
        "name": "Computer Science Lab",
        "icon": "🖥️",
        "room": "Digital systems workshop",
        "description": "Explore computer hardware, binary numbers, and digital logic at a fully equipped virtual workstation.",
        "activity": "Set the eight binary switches, convert the resulting byte to decimal, and inspect the workstation components.",
        "learning_outcome": "Convert an 8-bit binary number into a decimal value by adding place values.",
        "lesson_steps": (
            "Set the switches to 00000101 and write down the bit positions that are on.",
            "Use the board to read the decimal value and compare it with your own sum.",
            "Try 00001010 and 00001111; record each binary and decimal pair.",
            "Explain how the place values 8, 4, 2, and 1 contribute to the final value.",
        ),
        "equipment": ("3D workstation", "Monitor & keyboard", "Binary logic board", "Network switch", "Digital multimeter"),
        "scene": "computer",
        "practicals": (
            {"title": "Binary to decimal", "activity": "Convert an 8-bit binary input to decimal and check the displayed result.", "lesson_steps": ("Set the switches to 00000101 and add the active place values.", "Try 00001010 and compare your sum with the board."), "learning_outcome": "Convert an 8-bit binary number into its decimal value."},
            {"title": "Place-value investigation", "activity": "Investigate how each switch position contributes to the value of a byte.", "lesson_steps": ("Turn on one switch at a time, starting with bit 0.", "Record the decimal change for bit 1, bit 2, and bit 3."), "learning_outcome": "Explain the powers-of-two place values in a binary number."},
            {"title": "Binary pattern comparison", "activity": "Compare binary patterns and explain how changing one bit affects the total.", "lesson_steps": ("Enter 00001111 and record its decimal value.", "Turn off the 1, 2, and 4 place-value switches one at a time."), "learning_outcome": "Relate a change in binary digits to a change in decimal value."},
            {"title": "Build a target number", "activity": "Construct a binary byte that represents a chosen decimal target.", "lesson_steps": ("Choose a target from 12 to 30 and identify its powers of two.", "Set the matching switches and verify the displayed decimal result."), "learning_outcome": "Represent a decimal value using an 8-bit binary pattern."},
            {"title": "Byte capacity", "activity": "Explore the range of values represented by an unsigned 8-bit byte.", "lesson_steps": ("Set all switches off and record the minimum value.", "Set all switches on and explain how the maximum is formed."), "learning_outcome": "Determine the minimum and maximum unsigned values of a byte."},
        ),
    },
    {
        "slug": "music",
        "name": "Music & Sound Lab",
        "icon": "🎼",
        "room": "Acoustics & performance studio",
        "description": "Discover pitch, rhythm, and timbre with virtual instruments, a mixing desk, and acoustic visualizations.",
        "activity": "Play notes on the virtual keyboard and compare their pitch. Use the tempo control to hear how pulse changes rhythm.",
        "learning_outcome": "Describe how pitch and tempo change what a short musical pattern sounds like.",
        "lesson_steps": (
            "Play C, E, and G one at a time and order them from lowest to highest pitch.",
            "Set the metronome to 60 BPM and play one beat; repeat at 120 BPM.",
            "Clap four steady beats at each tempo and compare the spacing.",
            "Record which setting produced the faster pulse and how you know.",
        ),
        "equipment": ("Digital piano", "Drum pads", "Studio headphones", "Mixing console", "Metronome"),
        "scene": "music",
        "practicals": (
            {"title": "Pitch ordering", "activity": "Compare keyboard notes and arrange them from lowest to highest pitch.", "lesson_steps": ("Play C, E, and G one at a time.", "Order the notes by pitch and describe the difference you hear."), "learning_outcome": "Describe how pitch changes across selected musical notes."},
            {"title": "Tempo and pulse", "activity": "Investigate how tempo changes the spacing of a steady musical pulse.", "lesson_steps": ("Play one beat at 60 BPM and tap four steady beats.", "Repeat at 120 BPM and compare the time between beats."), "learning_outcome": "Explain the relationship between BPM and pulse speed."},
            {"title": "Major-triad listening", "activity": "Listen to the notes C, E, and G as a simple major-triad pattern.", "lesson_steps": ("Play C, E, and G in order, keeping each note even.", "Repeat the pattern and identify which note sounds highest."), "learning_outcome": "Recognize a simple ordered pitch pattern by listening."},
            {"title": "Rhythm accuracy", "activity": "Keep a steady four-beat rhythm against two different metronome settings.", "lesson_steps": ("Set 80 BPM and tap four beats with the metronome.", "Set 120 BPM and repeat without speeding up between clicks."), "learning_outcome": "Maintain a consistent pulse at different tempos."},
            {"title": "Tempo performance", "activity": "Perform the same short note pattern at a slow and a fast tempo.", "lesson_steps": ("Play C, D, E, and G at 60 BPM.", "Repeat at 120 BPM and describe how the character changes."), "learning_outcome": "Connect tempo changes with the perceived character of music."},
        ),
    },
    {
        "slug": "biology",
        "name": "Biology & Life Sciences Lab",
        "icon": "🧬",
        "room": "Microscopy & life sciences suite",
        "description": "Investigate cell structures and magnification on a modern virtual microscope with prepared specimen slides.",
        "activity": "Select a specimen, change magnification, and identify visible structures. The virtual microscope is for learning, not diagnosis.",
        "learning_outcome": "Compare how magnification changes the apparent size and field of view of a specimen.",
        "lesson_steps": (
            "Select the onion epidermis specimen and focus at 40×.",
            "Increase magnification to 100×, then 200×; observe the scale change.",
            "Switch to the leaf section and look for the stomata shown in the model.",
            "Record one structure observed and explain why the field of view changes.",
        ),
        "equipment": ("Compound microscope", "Prepared specimen slides", "Cell models", "Digital imaging screen", "Slide cabinet"),
        "scene": "biology",
        "practicals": (
            {"title": "Magnification and field of view", "activity": "Observe how magnification changes specimen size and the visible field.", "lesson_steps": ("Focus the onion specimen at 40× and note the visible area.", "Increase to 100× and 200×, then compare the field of view."), "learning_outcome": "Explain the trade-off between magnification and field of view."},
            {"title": "Plant and animal cells", "activity": "Compare prepared plant and animal cell specimens using the virtual microscope.", "lesson_steps": ("Focus the onion epidermis and note its visible cell boundaries.", "Switch to the cheek smear and record one difference in appearance."), "learning_outcome": "Compare visible features of plant and animal cells."},
            {"title": "Leaf stomata survey", "activity": "Inspect a leaf section and locate the stomata shown in the specimen model.", "lesson_steps": ("Select the leaf section at 100× magnification.", "Increase magnification and locate the stomata in the field of view."), "learning_outcome": "Identify stomata and relate them to leaf structure."},
            {"title": "Specimen comparison", "activity": "Compare two specimens at the same magnification for a fair observation.", "lesson_steps": ("Observe onion epidermis at 100× and record a feature.", "Observe cheek cells at 100× and compare the visible structures."), "learning_outcome": "Make a fair comparison by controlling magnification."},
            {"title": "Microscope focusing", "activity": "Practice moving from a broad view to a more detailed view of a specimen.", "lesson_steps": ("Start with the onion specimen at 40× and bring it into focus.", "Increase magnification in stages and describe the added detail."), "learning_outcome": "Use magnification systematically to examine a specimen."},
        ),
    },
    {
        "slug": "chemistry",
        "name": "Chemistry & Materials Lab",
        "icon": "⚗️",
        "room": "Virtual wet chemistry suite",
        "description": "Explore indicators and the pH scale using interactive glassware and simulated, classroom-safe solutions.",
        "activity": "Select a solution and add indicator to observe its approximate pH and colour change. All experiments are virtual.",
        "learning_outcome": "Classify simulated solutions as acidic, neutral, or alkaline from indicator evidence.",
        "lesson_steps": (
            "Select a solution and universal indicator in the simulator.",
            "Add the indicator and record the displayed approximate pH and colour.",
            "Repeat with distilled water and bicarbonate solution.",
            "Group the results as acidic, neutral, or alkaline and compare the evidence.",
        ),
        "equipment": ("Volumetric glassware", "Burette & retort stand", "Indicator bottles", "Digital pH meter", "Fume hood"),
        "scene": "chemistry",
        "practicals": (
            {"title": "Classify solutions by pH", "activity": "Use a selected indicator to classify virtual solutions as acidic, neutral, or alkaline.", "lesson_steps": ("Test distilled water with universal indicator and note its colour.", "Compare citrus, bicarbonate, and soap solutions with the same indicator."), "learning_outcome": "Classify simulated solutions using indicator evidence."},
            {"title": "Indicator comparison", "activity": "Compare how different indicators display the same simulated solution.", "lesson_steps": ("Choose vinegar and test it with universal indicator.", "Repeat with litmus and phenolphthalein; compare the displayed changes."), "learning_outcome": "Describe how indicators provide evidence about a solution."},
            {"title": "Acidity ranking", "activity": "Rank the available simulated solutions by their approximate acidity.", "lesson_steps": ("Test citrus, vinegar, and distilled water using universal indicator.", "Order the results by approximate pH and justify the ranking."), "learning_outcome": "Use approximate pH evidence to compare acidity."},
            {"title": "Neutrality investigation", "activity": "Use the pH scale to identify a neutral reference among the simulated solutions.", "lesson_steps": ("Test distilled water with universal indicator.", "Compare its result with vinegar and bicarbonate solution."), "learning_outcome": "Identify neutral conditions and distinguish them from acidic or alkaline ones."},
            {"title": "Indicator selection", "activity": "Choose an indicator suited to distinguishing the available acidic and alkaline samples.", "lesson_steps": ("Compare the indicator choices using vinegar and soap solution.", "Select the clearest indicator for the comparison and explain why."), "learning_outcome": "Select an indicator and support the choice with observed results."},
        ),
    },
    {
        "slug": "agriculture",
        "name": "Agriculture & Food Systems Lab",
        "icon": "🌱",
        "room": "Crop science & soil studio",
        "description": "Investigate crop growth, soil water retention, and irrigation through a guided virtual field trial.",
        "activity": "Compare maize, beans, and kale across sandy, loamy, and clay soils. Adjust irrigation and observe how water retention affects simulated crop growth.",
        "learning_outcome": "Use trial results to explain how crop water demand and soil texture affect simulated growth.",
        "lesson_steps": (
            "Choose maize, loam soil, and 25 mm irrigation; run the field trial and record the result.",
            "Keep the crop and soil the same; change irrigation to 50 mm and then 75 mm.",
            "Choose sandy soil and repeat at the irrigation amount that gave the best first result.",
            "Compare water retained and growth estimates; identify which factor changed each result.",
        ),
        "equipment": ("Virtual crop beds", "Soil texture samples", "Drip irrigation lines", "Rain gauge", "Crop growth monitor"),
        "scene": "agriculture",
        "practicals": (
            {"title": "Irrigation and crop growth", "activity": "Compare how irrigation amount affects a selected crop growing in loam soil.", "lesson_steps": ("Run the chosen crop at 25 mm irrigation.", "Repeat at 50 mm and 75 mm, keeping crop and soil unchanged."), "learning_outcome": "Use a controlled comparison to relate irrigation to simulated growth."},
            {"title": "Soil water retention", "activity": "Compare water retention across sandy, loamy, and clay soils.", "lesson_steps": ("Run the same crop at 50 mm in sandy soil.", "Repeat in loam and clay, keeping all other conditions constant."), "learning_outcome": "Explain how soil texture influences water availability."},
            {"title": "Crop water needs", "activity": "Compare simulated water needs for maize, beans, and kale under the same conditions.", "lesson_steps": ("Run each crop in loam soil with 50 mm irrigation.", "Compare the growth estimates and identify which crop responds best."), "learning_outcome": "Compare crop responses while holding soil and irrigation constant."},
            {"title": "Fair field trial", "activity": "Design a fair virtual trial by changing one growing condition at a time.", "lesson_steps": ("Choose maize in loam soil and run at 25 mm irrigation.", "Change only irrigation to 50 mm, then only soil to sandy."), "learning_outcome": "Explain why changing one variable at a time supports a fair test."},
            {"title": "Irrigation planning", "activity": "Find a suitable irrigation level for the selected crop and soil combination.", "lesson_steps": ("Run the trial at 25 mm, 50 mm, and 75 mm per week.", "Choose the best result and justify it using the simulated growth and retention."), "learning_outcome": "Use trial evidence to recommend an irrigation plan."},
        ),
    },
)


def practical_labs(request, slug=None):
    user = _current_user(request)
    if not user:
        return redirect("login")
    if user.role not in ("student", "teacher", "admin"):
        return redirect("dashboard")

    if slug is None:
        return render(request, "practical_labs.html", {"user": user, "labs": PRACTICAL_LABS})

    lab = next((item for item in PRACTICAL_LABS if item["slug"] == slug), None)
    if lab is None:
        raise Http404
    return render(request, "subject_lab.html", {"user": user, "lab": lab})


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