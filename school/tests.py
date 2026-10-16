from io import BytesIO
import json
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import Client, override_settings
from django.urls import reverse
from unittest.mock import patch
from datetime import datetime
from django.utils import timezone

from . import whatsapp
from . import google_meet
from .models import (
    Exam,
    GameProgress,
    GameQuestion,
    GameTopic,
    Invoice,
    Payment,
    PracticalAttendance,
    ResourceMaterial,
    SchoolClass,
    SchoolStaffProfile,
    SubjectCatalog,
    SubjectDocket,
    SupportTicket,
    User,
)


class PortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User(
            email="student@example.com",
            first_name="Aisha",
            last_name="Njeri",
            role="student",
        )
        cls.user.set_password("student-pass")
        cls.user.save()

    def test_public_pages_render(self):
        for page in ("index", "library", "classes", "exams", "support", "contact", "create_account"):
            with self.subTest(page=page):
                self.assertEqual(self.client.get(reverse(page)).status_code, 200)

    def test_health_check_verifies_database_connectivity(self):
        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_protected_pages_redirect_to_login(self):
        for page in ("dashboard", "billing", "practical_exams", "practical_attendance"):
            with self.subTest(page=page):
                response = self.client.get(reverse(page))
                self.assertRedirects(response, reverse("login"))

    def test_student_can_open_physics_practical_lab(self):
        session = self.client.session
        session["user_id"] = self.user.pk
        session.save()

        response = self.client.get(reverse("practical_exams"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Investigating a resistor")
        self.assertContains(response, 'id="lab-scene-canvas"')
        self.assertContains(response, "Digital ammeter")
        self.assertContains(response, "Digital voltmeter")
        self.assertContains(response, "Record six pairs of readings")
        self.assertContains(response, "Direct WhatsApp group messaging is not configured.")

    def create_game_topic(self):
        docket = SubjectDocket.objects.create(
            title="Junior Secondary",
            slug=f"games-docket-{SubjectDocket.objects.count()}",
            grade_band="junior_secondary",
        )
        subject = SubjectCatalog.objects.create(
            name="Mathematics",
            code=f"GAMES-MATH-{SubjectCatalog.objects.count()}",
            grade_level="Grade 7",
            docket=docket,
            category="core",
        )
        return GameTopic.objects.create(subject=subject, title="Fractions")

    def test_game_progress_requires_correct_answers_and_unlocks_next_level(self):
        topic = self.create_game_topic()
        starter_first = GameQuestion.objects.create(
            topic=topic,
            difficulty=1,
            order=0,
            prompt="Which fraction is one half?",
            choices=["1/3", "1/4", "2/4", "3/4"],
            correct_choice=2,
        )
        starter_second = GameQuestion.objects.create(
            topic=topic,
            difficulty=1,
            order=1,
            prompt="What is 1/4 + 1/4?",
            choices=["1/2", "1/4", "1", "2/4"],
            correct_choice=0,
        )
        builder_question = GameQuestion.objects.create(
            topic=topic,
            difficulty=2,
            order=0,
            prompt="What is 2/3 + 1/6?",
            choices=["3/9", "5/6", "1/2", "1"],
            correct_choice=1,
        )
        session = self.client.session
        session["user_id"] = self.user.pk
        session.save()

        response = self.client.get(reverse("game_play", args=[topic.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Level 1 of 3")

        response = self.client.post(
            reverse("game_play", args=[topic.pk]),
            {"action": "answer", "question_id": starter_first.pk, "choice": "0"},
        )
        self.assertContains(response, "Not passed yet")
        progress = GameProgress.objects.get(user=self.user, topic=topic)
        self.assertEqual(progress.question_index, 0)
        self.assertEqual(progress.attempts, 1)

        response = self.client.post(
            reverse("game_play", args=[topic.pk]),
            {"action": "answer", "question_id": starter_first.pk, "choice": "2"},
        )
        self.assertRedirects(response, reverse("game_play", args=[topic.pk]))
        response = self.client.post(
            reverse("game_play", args=[topic.pk]),
            {"action": "answer", "question_id": starter_second.pk, "choice": "0"},
            follow=True,
        )
        self.assertContains(response, "Level 2 of 3")
        progress.refresh_from_db()
        self.assertEqual(progress.completed_level, 1)
        self.assertEqual(progress.unlocked_level, 2)
        self.assertEqual(progress.current_level, 2)

        response = self.client.post(
            reverse("game_play", args=[topic.pk]),
            {"action": "answer", "question_id": builder_question.pk, "choice": "1"},
            follow=True,
        )
        self.assertContains(response, "All available levels complete")
        progress.refresh_from_db()
        self.assertEqual(progress.completed_level, 2)

    def test_games_corner_handles_legacy_grade_labels(self):
        docket = SubjectDocket.objects.create(
            title="Legacy docket",
            slug="games-legacy-docket",
            grade_band="senior_secondary",
        )
        subject = SubjectCatalog.objects.create(
            name="Legacy subject",
            code="GAMES-LEGACY-F4",
            grade_level="f4",
            docket=docket,
        )
        session = self.client.session
        session["user_id"] = self.user.pk
        session.save()

        response = self.client.get(reverse("games"), {"grade": "f4", "subject": subject.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Legacy subject")

    def test_teacher_can_author_topics_and_levelled_questions(self):
        teacher = User.objects.create(
            email="games-teacher@example.com",
            first_name="John",
            last_name="Mwangi",
            role="teacher",
        )
        docket = SubjectDocket.objects.create(
            title="Junior Secondary",
            slug="games-author-docket",
            grade_band="junior_secondary",
        )
        subject = SubjectCatalog.objects.create(
            name="Science",
            code="GAMES-SCI-G7",
            grade_level="Grade 7",
            docket=docket,
            category="science",
        )
        session = self.client.session
        session["user_id"] = teacher.pk
        session.save()

        response = self.client.get(reverse("games_author"))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("games_author"),
            {"action": "create-topic", "subject": subject.pk, "title": "Matter", "description": "States of matter"},
        )
        topic = GameTopic.objects.get(title="Matter")
        self.assertEqual(topic.created_by, teacher)
        self.assertRedirects(response, f"{reverse('games_author')}?topic={topic.pk}")

        response = self.client.post(
            reverse("games_author"),
            {
                "action": "add-question",
                "topic": topic.pk,
                "difficulty": "2",
                "prompt": "Which state keeps its volume?",
                "option_a": "Solid",
                "option_b": "Gas",
                "option_c": "Plasma",
                "option_d": "None",
                "correct_choice": "0",
                "explanation": "Solids have a fixed volume.",
            },
        )
        self.assertRedirects(response, f"{reverse('games_author')}?topic={topic.pk}")
        question = GameQuestion.objects.get(topic=topic)
        self.assertEqual(question.difficulty, 2)
        self.assertEqual(question.choices[question.correct_choice], "Solid")

    def test_exams_page_includes_whatsapp_practical_invite(self):
        response = self.client.get(reverse("exams"))

        self.assertNotContains(response, "Send to WhatsApp group")

    @patch("school.views.whatsapp.is_configured", return_value=True)
    def test_configured_whatsapp_group_invite_button_posts_to_api(self, _is_configured):
        session = self.client.session
        session["user_id"] = self.user.pk
        session.save()

        response = self.client.get(reverse("practical_exams"))

        self.assertContains(response, "Send to WhatsApp group")
        self.assertContains(response, reverse("send_practical_whatsapp_invite"))

    @patch("school.views.whatsapp.send_group_message")
    def test_student_can_send_practical_invite_to_whatsapp_group(self, send_group_message):
        session = self.client.session
        session["user_id"] = self.user.pk
        session.save()

        response = self.client.post(reverse("send_practical_whatsapp_invite"), secure=True)

        self.assertRedirects(response, reverse("practical_exams"), fetch_redirect_response=False)
        send_group_message.assert_called_once()
        self.assertIn("https://testserver/practical-exams", send_group_message.call_args.args[0])

    def test_whatsapp_group_invite_requires_post_and_student_access(self):
        response = self.client.get(reverse("send_practical_whatsapp_invite"))
        self.assertEqual(response.status_code, 405)

        session = self.client.session
        session["user_id"] = self.user.pk
        session.save()
        response = self.client.post(reverse("send_practical_whatsapp_invite"))
        self.assertRedirects(response, reverse("practical_exams"), fetch_redirect_response=False)

    @patch.dict(
        "os.environ",
        {
            "WHATSAPP_API_VERSION": "v99.0",
            "WHATSAPP_PHONE_NUMBER_ID": "phone-id",
            "WHATSAPP_ACCESS_TOKEN": "test-token",
            "WHATSAPP_GROUP_ID": "group-id",
        },
    )
    @patch("school.whatsapp.json.load", return_value={"messages": [{"id": "wamid.test"}]})
    @patch("school.whatsapp.urllib.request.urlopen")
    def test_whatsapp_api_sends_message_to_configured_group(self, urlopen, _json_load):
        with urlopen.return_value as response:
            self.assertEqual(whatsapp.send_group_message("Practical invite"), "wamid.test")

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["recipient_type"], "group")
        self.assertEqual(payload["to"], "group-id")
        self.assertEqual(payload["text"]["body"], "Practical invite")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    @patch.dict("os.environ", {}, clear=True)
    def test_whatsapp_api_reports_missing_configuration(self):
        self.assertFalse(whatsapp.is_configured())
        with self.assertRaisesMessage(
            whatsapp.WhatsAppAPIError,
            "Direct WhatsApp group messaging is not configured.",
        ):
            whatsapp.send_group_message("Practical invite")

    @patch.dict("os.environ", {}, clear=True)
    def test_google_meet_reports_missing_configuration(self):
        self.assertFalse(google_meet.is_configured())
        with self.assertRaisesMessage(
            google_meet.GoogleMeetError,
            "Set GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_MEET_DELEGATE_EMAIL.",
        ):
            google_meet._configuration()

    def test_parent_cannot_open_student_practical_lab(self):
        parent = User(
            email="parent@example.com",
            first_name="Sam",
            last_name="Njeri",
            role="parent",
        )
        parent.set_password("parent-pass")
        parent.save()
        session = self.client.session
        session["user_id"] = parent.pk
        session.save()

        response = self.client.get(reverse("practical_exams"))

        self.assertRedirects(response, reverse("dashboard"))

    def test_teacher_can_save_and_review_practical_attendance(self):
        teacher = User.objects.create(
            email="teacher@example.com",
            first_name="John",
            last_name="Mwangi",
            role="teacher",
        )
        session = self.client.session
        session["user_id"] = teacher.pk
        session.save()

        response = self.client.get(reverse("practical_attendance"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attendance for Aisha Njeri")

        response = self.client.post(
            reverse("practical_attendance"),
            {
                "session_date": "2026-10-09",
                f"attendance_{self.user.pk}": "present",
            },
        )
        self.assertRedirects(
            response,
            f"{reverse('practical_attendance')}?date=2026-10-09",
            fetch_redirect_response=False,
        )
        attendance = PracticalAttendance.objects.get(student=self.user)
        self.assertEqual(attendance.status, "present")
        self.assertEqual(attendance.marked_by, teacher)

        response = self.client.get(reverse("practical_attendance"), {"date": "2026-10-09"})
        self.assertContains(response, "1</strong> present")
        self.assertContains(response, "2026-10-09")

    def test_practical_attendance_requires_staff_and_complete_valid_roster(self):
        session = self.client.session
        session["user_id"] = self.user.pk
        session.save()
        response = self.client.get(reverse("practical_attendance"))
        self.assertRedirects(response, reverse("dashboard"))

        teacher = User.objects.create(
            email="teacher@example.com",
            first_name="John",
            last_name="Mwangi",
            role="teacher",
        )
        session = self.client.session
        session["user_id"] = teacher.pk
        session.save()
        response = self.client.post(
            reverse("practical_attendance"),
            {"session_date": "2026-10-09"},
        )
        self.assertRedirects(
            response,
            f"{reverse('practical_attendance')}?date=2026-10-09",
            fetch_redirect_response=False,
        )
        self.assertEqual(PracticalAttendance.objects.count(), 0)

    def test_login_and_logout(self):
        response = self.client.post(
            reverse("login"),
            {"email": "student@example.com", "password": "student-pass"},
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.client.get(reverse("logout"))
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("login"))

    def test_admin_login_only_accepts_admin_accounts(self):
        response = self.client.get(reverse("admin_login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrator login")

        response = self.client.post(
            reverse("admin_login"),
            {"email": "student@example.com", "password": "student-pass"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")
        self.assertNotIn("user_id", self.client.session)

        admin = User.objects.create(
            email="admin@example.com",
            first_name="Miriam",
            last_name="Wanjiku",
            role="admin",
        )
        admin.set_password("admin-pass")
        admin.save()

        response = self.client.post(
            reverse("admin_login"),
            {"email": "admin@example.com", "password": "admin-pass"},
        )
        self.assertRedirects(response, reverse("school_admin"))
        self.assertEqual(self.client.session["user_id"], admin.pk)

    def test_invalid_login_shows_error_without_unauthorized_response(self):
        response = self.client.post(
            reverse("login"),
            {"email": "student@example.com", "password": "incorrect-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")
        self.assertNotIn("user_id", self.client.session)

    def test_student_can_create_account_and_is_signed_in(self):
        response = self.client.post(
            reverse("create_account"),
            {
                "first_name": "Kendi",
                "last_name": "Wanjiku",
                "email": "Kendi@example.com",
                "password": "new-student-pass",
                "confirm_password": "new-student-pass",
            },
        )

        account = User.objects.get(email="kendi@example.com")
        self.assertEqual(account.role, "student")
        self.assertTrue(account.check_password("new-student-pass"))
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_create_account_rejects_invalid_and_duplicate_submissions(self):
        cases = (
            {
                "first_name": "New",
                "last_name": "Student",
                "email": "new@example.com",
                "password": "short",
                "confirm_password": "short",
            },
            {
                "first_name": "New",
                "last_name": "Student",
                "email": "new@example.com",
                "password": "long-enough-pass",
                "confirm_password": "different-pass",
            },
            {
                "first_name": "Existing",
                "last_name": "Student",
                "email": "STUDENT@example.com",
                "password": "long-enough-pass",
                "confirm_password": "long-enough-pass",
            },
        )
        for data in cases:
            with self.subTest(email=data["email"], password=data["password"]):
                response = self.client.post(reverse("create_account"), data)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(User.objects.count(), 1)

    @override_settings(CSRF_TRUSTED_ORIGINS=["https://localhost:8000"])
    def test_create_account_accepts_csrf_from_forwarded_local_https_origin(self):
        client = Client(enforce_csrf_checks=True)
        form_response = client.get("https://localhost:8000/create-account")
        csrf_token = form_response.cookies["csrftoken"].value

        response = client.post(
            "https://localhost:8000/create-account",
            {
                "first_name": "Kendi",
                "last_name": "Wanjiku",
                "email": "kendi@example.com",
                "password": "new-student-pass",
                "confirm_password": "new-student-pass",
                "csrfmiddlewaretoken": csrf_token,
            },
            HTTP_ORIGIN="https://localhost:8000",
            HTTP_REFERER="https://localhost:8000/create-account",
        )

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_support_ticket_submission(self):
        response = self.client.post(
            reverse("support"),
            {
                "user_name": "Parent Example",
                "user_email": "parent@example.com",
                "subject": "School fees",
                "message": "Please help with my invoice.",
            },
        )
        self.assertRedirects(response, reverse("support"))
        self.assertEqual(SupportTicket.objects.count(), 1)

    def test_video_resources_render_zoom_controls(self):
        ResourceMaterial.objects.create(
            title="Fractions lesson",
            subject="Mathematics",
            grade_level="Grade 5",
            resource_type="Video",
            term="Term 1",
            academic_year="2026",
            file_url="https://media.example.org/fractions.mp4",
            uploaded_by="Teacher",
        )

        response = self.client.get(reverse("library"))

        self.assertContains(response, "Fractions lesson")
        self.assertContains(response, "data-video-player")
        self.assertContains(response, "data-zoom-in")
        self.assertContains(response, "data-zoom-out")
        self.assertContains(response, "data-zoom-reset")

    def test_uploaded_media_is_served_from_storage(self):
        with patch("school.views.default_storage.open", return_value=BytesIO(b"sample material")):
            response = self.client.get("/media/library/sample.pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"sample material")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_staff_room_restricts_access_and_uploads_library_material(self):
        response = self.client.get(reverse("staff_room"))
        self.assertRedirects(response, reverse("login"))

        self.client.post(
            reverse("login"),
            {"email": "student@example.com", "password": "student-pass"},
        )
        response = self.client.get(reverse("staff_room"))
        self.assertRedirects(response, reverse("login"))
        self.client.get(reverse("logout"))

        teacher = User(
            email="teacher@example.com",
            first_name="John",
            last_name="Mwangi",
            role="teacher",
        )
        teacher.set_password("teacher-pass")
        teacher.save()
        self.client.post(
            reverse("login"),
            {"email": "teacher@example.com", "password": "teacher-pass"},
        )
        self.assertEqual(self.client.get(reverse("staff_room")).status_code, 200)

        with patch("school.views.default_storage.save", return_value="library/lesson.pdf"):
            response = self.client.post(
                reverse("staff_room"),
                {
                    "title": "Fractions lesson",
                    "subject": "Mathematics",
                    "grade_level": "Grade 5",
                    "resource_type": "PDF",
                    "term": "Term 1",
                    "academic_year": "2026",
                    "material_file": SimpleUploadedFile("lesson.pdf", b"%PDF demo", content_type="application/pdf"),
                },
            )

        self.assertRedirects(response, reverse("staff_room"))
        material = ResourceMaterial.objects.get(title="Fractions lesson")
        self.assertEqual(material.file_url, "/media/library/lesson.pdf")
        self.assertEqual(material.uploaded_by, "John Mwangi")
        self.assertContains(self.client.get(reverse("library")), "Fractions lesson")

    def test_staff_room_accepts_leadership_profile_uploads(self):
        teacher = User.objects.create(
            email="teacher@example.com",
            first_name="John",
            last_name="Mwangi",
            role="teacher",
        )
        teacher.set_password("teacher-pass")
        teacher.save()
        session = self.client.session
        session["user_id"] = teacher.pk
        session.save()

        response = self.client.post(
            reverse("staff_room"),
            {
                "staff_role": "principal",
                "staff_full_name": "Grace Njeri",
                "staff_email": "grace.njeri@peakschools.ac.ke",
                "staff_phone": "+254712345678",
                "department": "School Leadership",
                "campus": "Main Campus",
                "staff_id": "PS-101",
            },
        )

        self.assertRedirects(response, reverse("staff_room"))
        profile = SchoolStaffProfile.objects.get(staff_id="PS-101")
        self.assertEqual(profile.role, "principal")
        self.assertEqual(profile.campus, "Main Campus")
        self.assertContains(self.client.get(reverse("staff_room")), "Grace Njeri")

    def test_school_admin_is_admin_only_and_manages_staff_structure(self):
        self.assertRedirects(self.client.get(reverse("school_admin")), reverse("login"))

        session = self.client.session
        session["user_id"] = self.user.pk
        session.save()
        self.assertRedirects(self.client.get(reverse("school_admin")), reverse("dashboard"))

        admin = User.objects.create(
            email="admin@example.com",
            first_name="Miriam",
            last_name="Wanjiku",
            role="admin",
        )
        session = self.client.session
        session["user_id"] = admin.pk
        session.save()

        response = self.client.get(reverse("school_admin"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "School administration")
        self.assertContains(response, "Principal")

        response = self.client.post(
            reverse("school_admin"),
            {
                "role": "principal",
                "full_name": "Grace Njeri",
                "email": "grace.njeri@peakschools.ac.ke",
                "phone": "+254712345678",
                "department": "School Leadership",
                "campus": "Main Campus",
                "staff_id": "PS-201",
            },
        )

        self.assertRedirects(response, reverse("school_admin"))
        self.assertContains(self.client.get(reverse("school_admin")), "Grace Njeri")

    def test_teacher_can_schedule_one_hour_google_meet_lesson(self):
        response = self.client.post(
            reverse("classes"),
            {"title": "Science", "subject": "Biology", "start_at": "2030-05-10T09:00"},
        )
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(SchoolClass.objects.count(), 0)

        teacher = User(
            email="teacher@example.com",
            first_name="John",
            last_name="Mwangi",
            role="teacher",
        )
        teacher.set_password("teacher-pass")
        teacher.save()
        self.client.post(
            reverse("login"),
            {"email": "teacher@example.com", "password": "teacher-pass"},
        )
        fake_meeting = {
            "join_url": "https://meet.google.com/abc-defg-hij",
            "space_name": "spaces/space-123",
        }
        with patch("school.views.google_meet.create_meeting", return_value=fake_meeting) as create_meeting:
            response = self.client.post(
                reverse("classes"),
                {"title": "Science", "subject": "Biology", "start_at": "2030-05-10T09:00"},
            )

        self.assertRedirects(response, reverse("classes"))
        create_meeting.assert_called_once_with()
        lesson = SchoolClass.objects.get(title="Science")
        self.assertEqual(lesson.end_time, "10:00 AM")
        self.assertEqual(lesson.lesson_date.isoformat(), "2030-05-10")
        self.assertEqual(lesson.google_meet_space_name, "spaces/space-123")

        with patch("school.views.google_meet.create_meeting") as create_again:
            response = self.client.post(reverse("class_go_live", args=[lesson.pk]))
        self.assertRedirects(response, reverse("classes"))
        create_again.assert_not_called()
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "Live")

    @patch("school.views.google_meet.create_meeting", side_effect=google_meet.GoogleMeetError("Google Meet is not configured."))
    def test_google_meet_schedule_failure_is_reported_without_creating_a_class(self, _create_meeting):
        teacher = User.objects.create(
            email="teacher@example.com",
            first_name="John",
            last_name="Mwangi",
            role="teacher",
        )
        session = self.client.session
        session["user_id"] = teacher.pk
        session.save()

        response = self.client.post(
            reverse("classes"),
            {"title": "Science", "subject": "Biology", "start_at": "2030-05-10T09:00"},
        )

        self.assertRedirects(response, reverse("classes"), fetch_redirect_response=False)
        self.assertEqual(SchoolClass.objects.count(), 0)
        response = self.client.get(reverse("classes"))
        self.assertContains(response, "Google Meet is not configured.")

    @patch("school.views.google_meet.is_configured", return_value=False)
    def test_staff_are_told_when_google_meet_is_not_configured(self, _is_configured):
        teacher = User.objects.create(
            email="teacher@example.com",
            first_name="John",
            last_name="Mwangi",
            role="teacher",
        )
        session = self.client.session
        session["user_id"] = teacher.pk
        session.save()

        response = self.client.get(reverse("classes"))

        self.assertContains(response, "Google Meet not configured")

    @patch("school.google_meet._configuration", return_value="access-token")
    @patch("school.google_meet.urllib.request.urlopen")
    @patch("school.google_meet.json.load", return_value={
        "name": "spaces/space-123",
        "meetingUri": "https://meet.google.com/abc-defg-hij",
    })
    def test_google_meet_api_creates_meeting_space(
        self, _json_load, urlopen, _configuration
    ):
        meeting = google_meet.create_meeting()

        self.assertEqual(
            meeting,
            {
                "join_url": "https://meet.google.com/abc-defg-hij",
                "space_name": "spaces/space-123",
            },
        )
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.full_url, "https://meet.googleapis.com/v2/spaces")
        self.assertEqual(payload, {})

    @patch.dict("os.environ", {}, clear=True)
    def test_google_meet_api_reports_missing_configuration(self):
        self.assertFalse(google_meet.is_configured())
        with self.assertRaisesMessage(
            google_meet.GoogleMeetError,
            "Set GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_MEET_DELEGATE_EMAIL.",
        ):
            google_meet._configuration()

    def test_invoice_payment_updates_status(self):
        invoice = Invoice.objects.create(
            student_name="Aisha Njeri",
            invoice_number="INV-TEST-1",
            term="Term 1",
            due_date="2026-10-15",
            total_amount=1000,
            amount_paid=0,
            status="Pending",
        )
        self.client.post(
            reverse("login"),
            {"email": "student@example.com", "password": "student-pass"},
        )
        response = self.client.post(
            reverse("pay_invoice", args=[invoice.pk]),
            {"amount": "1000", "method": "mpesa", "phone": "0712345678"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("mpesa_start"))
        # Daraja is not configured in tests, so a demo payment is recorded.
        response = self.client.get(reverse("mpesa_start"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("billing"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, 1000)
        self.assertEqual(invoice.status, "Paid")
        self.assertEqual(Payment.objects.filter(invoice=invoice).count(), 1)

    def test_exam_pdf_upload_requires_staff(self):
        pdf = SimpleUploadedFile("exam.pdf", b"%PDF-1.4 demo", content_type="application/pdf")
        response = self.client.post(reverse("exams"), {"title": "Midterm", "pdf_file": pdf})
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(Exam.objects.count(), 0)

        teacher = User(
            email="teacher@example.com",
            first_name="John",
            last_name="Mwangi",
            role="teacher",
        )
        teacher.set_password("teacher-pass")
        teacher.save()
        self.client.post(
            reverse("login"),
            {"email": "teacher@example.com", "password": "teacher-pass"},
        )
        pdf = SimpleUploadedFile("exam.pdf", b"%PDF-1.4 demo", content_type="application/pdf")
        response = self.client.post(
            reverse("exams"),
            {
                "title": "Midterm",
                "subject": "Mathematics",
                "grade_level": "Grade 7",
                "term": "Term 2",
                "academic_year": "2026",
                "pdf_file": pdf,
            },
        )
        self.assertRedirects(response, reverse("exams"))
        self.assertEqual(Exam.objects.count(), 1)