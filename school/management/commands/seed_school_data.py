from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from school.models import (
    Invoice,
    ResourceMaterial,
    SchoolClass,
    SubjectBook,
    SubjectCatalog,
    SubjectDocket,
    User,
)


class Command(BaseCommand):
    help = "Create the Peak Group of Schools demo users and sample portal data."

    def handle(self, *args, **options):
        dockets = [
            ("Lower Primary", "lower_primary", "Foundational literacy, numeracy, and life skills for Grades 2-3.", 1),
            ("Upper Primary", "upper_primary", "Core learning and subject mastery for Grades 4-6.", 2),
            ("Junior Secondary", "junior_secondary", "Middle-school enrichment and curriculum transitions for Grades 7-9.", 3),
            ("Senior Secondary", "senior_secondary", "Exam-focused academic pathways and rigorous subject specialization for Grades 10-12.", 4),
        ]
        docket_map = {}
        for title, slug, description, order in dockets:
            docket, _ = SubjectDocket.objects.get_or_create(
                slug=slug,
                defaults={"title": title, "description": description, "grade_band": slug, "display_order": order},
            )
            docket_map[title] = docket

        lower_primary_subjects = {
            "language": ("English Activities", "Indigenous Languages", "Kiswahili"),
            "core": ("Mathematics",),
            "science": ("Environmental Activities",),
            "creative": ("Creative Activities",),
            "humanities": ("CRE", "HRE", "IRE"),
        }
        upper_primary_subjects = {
            "technical": ("Agriculture",),
            "language": ("Arabic", "English", "French", "German", "Indigenous Language", "Kiswahili", "Mandarin"),
            "creative": ("Creative Arts",),
            "humanities": ("CRE", "HRE", "IRE", "Social Studies"),
            "core": ("Mathematics",),
            "science": ("Science and Technology",),
        }
        junior_secondary_subjects = {
            "technical": ("Agriculture", "Pre-Technical Studies"),
            "language": ("Arabic", "English", "French", "German", "Indigenous Language", "Kiswahili", "Mandarin"),
            "creative": ("Creative Arts",),
            "humanities": ("CRE", "HRE", "IRE", "Social Studies"),
            "core": ("Mathematics",),
            "science": ("Integrated Science",),
        }
        senior_secondary_subjects = {
            "Applied Sciences": ("technical", ("Agriculture", "Computer Studies", "Home Science", "ICT")),
            "Arts & Sports": ("creative", ("Fine Arts", "Music and Dance", "Physical Education", "Sports and Recreation", "Theatre and Film")),
            "Foreign Languages": ("language", ("Arabic", "French", "German", "Mandarin")),
            "Humanities": ("humanities", ("Business Studies", "Community Service Learning", "Geography", "History and Citizenship")),
            "Languages": ("language", ("English", "Fasihi ya Kiswahili", "Indigenous Languages", "Kiswahili Lugha", "Literature in English")),
            "Pure Sciences": ("science", ("Biology", "Chemistry", "Core Mathematics", "Essential Mathematics", "General Science", "Physics")),
            "Religious Education": ("humanities", ("CRE", "HRE", "IRE")),
            "Technical Studies": ("technical", ("Aviation", "Building Construction", "Electricity", "Marine and Fisheries Technology", "Media Technology", "Metalwork", "Power Mechanics", "Woodwork")),
        }
        senior_pathway_by_category = {
            "Applied Sciences": ["stem"],
            "Arts & Sports": ["arts_sports_science"],
            "Foreign Languages": ["social_sciences"],
            "Humanities": ["social_sciences"],
            "Languages": ["social_sciences"],
            "Pure Sciences": ["stem"],
            "Religious Education": ["social_sciences"],
            "Technical Studies": ["stem"],
        }
        shared_senior_subjects = {"Community Service Learning", "English", "Kiswahili Lugha"}
        all_pathways = [value for value, _ in SubjectCatalog.PATHWAY_CHOICES]
        grade_dockets = {
            2: "Lower Primary",
            3: "Lower Primary",
            4: "Upper Primary",
            5: "Upper Primary",
            6: "Upper Primary",
            7: "Junior Secondary",
            8: "Junior Secondary",
            9: "Junior Secondary",
            10: "Senior Secondary",
            11: "Senior Secondary",
            12: "Senior Secondary",
        }

        with transaction.atomic():
            SubjectCatalog.objects.filter(grade_level__in=[f"Grade {grade}" for grade in grade_dockets]).update(is_active=False)
            for grade, docket_title in grade_dockets.items():
                grade_level = f"Grade {grade}"
                if grade in (2, 3):
                    subject_groups = [
                        (category, name, [], False)
                        for category, names in lower_primary_subjects.items()
                        for name in names
                    ]
                elif 4 <= grade <= 6:
                    subject_groups = [
                        (category, name, [], False)
                        for category, names in upper_primary_subjects.items()
                        for name in names
                    ]
                elif 7 <= grade <= 9:
                    subject_groups = [
                        (category, name, [], False)
                        for category, names in junior_secondary_subjects.items()
                        for name in names
                    ]
                else:
                    subject_groups = []
                    for curriculum_group, (category, names) in senior_secondary_subjects.items():
                        for name in names:
                            pathways = senior_pathway_by_category[curriculum_group]
                            is_core = name in shared_senior_subjects
                            if is_core:
                                pathways = all_pathways
                            elif name == "Essential Mathematics":
                                pathways = ["social_sciences", "arts_sports_science"]
                            subject_groups.append((category, name, pathways, is_core))

                for category, name, pathways, is_core in subject_groups:
                    code = f"G{grade}-{slugify(name).upper()}"
                    SubjectCatalog.objects.update_or_create(
                        name=name,
                        grade_level=grade_level,
                        defaults={
                            "code": code,
                            "docket": docket_map[docket_title],
                            "category": category,
                            "description": f"KICD CBE {grade_level} curriculum subject.",
                            "pathways": pathways,
                            "is_core": is_core,
                            "is_active": True,
                        },
                    )

        demo_users = [
            ("admin@school.com", "admin123", "Mary", "King", "admin", "0721000000"),
            ("teacher@school.com", "teacher123", "John", "Mwangi", "teacher", "0711223344"),
            ("student@school.com", "student123", "Aisha", "Njeri", "student", "0700112233"),
            ("parent@school.com", "parent123", "Sam", "Njeri", "parent", "0712345678"),
        ]
        for email, password, first_name, last_name, role, phone in demo_users:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": role,
                    "phone": phone,
                },
            )
            if created:
                user.set_password(password)
                user.save(update_fields=["password_hash"])

        resources = [
            ("Grade 7 Mathematics Revision Guide", "Mathematics", "Grade 7", "PDF", "Term 2", "2026", "Admin"),
            ("Biology Past Paper 2025", "Biology", "Form 4", "Past Paper", "Term 3", "2025", "Teacher"),
            ("English Comprehension Workbook", "English", "Grade 6", "Workbook", "Term 1", "2026", "Teacher"),
        ]
        for title, subject, grade, kind, term, year, uploader in resources:
            ResourceMaterial.objects.get_or_create(
                title=title,
                defaults={
                    "subject": subject,
                    "grade_level": grade,
                    "resource_type": kind,
                    "term": term,
                    "academic_year": year,
                    "file_url": "/static/sample.pdf",
                    "uploaded_by": uploader,
                },
            )

        classes = [
            ("Science Practical Lab", "John Mwangi", "Biology", "09:00 AM", "10:00 AM", "biology-lab-01", "https://meet.jit.si/biology-lab-01", "Live", "Weekly"),
            ("Algebra Mastery", "Jane Otieno", "Mathematics", "11:00 AM", "12:00 PM", "maths-room-02", "https://meet.jit.si/maths-room-02", "Scheduled", "Weekly"),
        ]
        for title, teacher, subject, start, end, room, url, status, recurrence in classes:
            SchoolClass.objects.get_or_create(
                title=title,
                defaults={
                    "teacher_name": teacher,
                    "subject": subject,
                    "start_time": start,
                    "end_time": end,
                    "room_name": room,
                    "meeting_url": url,
                    "status": status,
                    "recurrence": recurrence,
                },
            )

        invoices = [
            ("INV-2026-001", "Term 1", "2026-10-15", 18000, 6000, "Partially Paid"),
            ("INV-2026-002", "Term 2", "2026-11-18", 18000, 0, "Pending"),
        ]
        for number, term, due_date, total, paid, status in invoices:
            Invoice.objects.get_or_create(
                invoice_number=number,
                defaults={
                    "student_name": "Aisha Njeri",
                    "term": term,
                    "due_date": due_date,
                    "total_amount": total,
                    "amount_paid": paid,
                    "status": status,
                },
            )

        authored_books = [
            ("Kiswahili Revision Companion", "Kiswahili", "Grade 7", "Peter Njuguna", "Lower Primary"),
            ("Geography Essentials", "Geography", "Grade 10", "Peter Njuguna", "Senior Secondary"),
            ("English Practice Book", "English", "Grade 8", "Jane Akinyi", "Junior Secondary"),
            ("Mathematics Mastery Workbook", "Mathematics", "Grade 9", "Mary Wanjiku", "Junior Secondary"),
            ("Physics Revision Guide", "Physics", "Grade 12", "Daniel Otieno", "Senior Secondary"),
        ]
        for title, subject_name, grade_level, author_name, docket_title in authored_books:
            subject = SubjectCatalog.objects.filter(name__iexact=subject_name, grade_level=grade_level).first()
            if subject:
                SubjectBook.objects.get_or_create(
                    title=title,
                    defaults={
                        "subject": subject,
                        "grade_level": grade_level,
                        "author_name": author_name,
                        "docket": subject.docket,
                        "description": f"Detailed topic notes, guided exercises, and diagrams for {subject_name} in {grade_level}.",
                        "content_outline": "Lesson objectives\nWorked examples\nRevision prompts\nExam-style questions",
                        "exercises": "Practice tasks, timed quizzes, and chapter recap questions.",
                        "diagrams": "Annotated charts, labelled figures, process maps, and concept visuals.",
                        "file_url": "/library",
                        "is_teacher_uploaded": True,
                        "created_by": User.objects.filter(role__in=["teacher", "admin"]).first(),
                    },
                )

        self.stdout.write(self.style.SUCCESS("Peak Group of Schools demo data is ready."))