from django.core.management.base import BaseCommand

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

        subject_catalogue = [
            ("Lower Primary", "Grade 2", "English Language", "language", "ENG-G2"),
            ("Lower Primary", "Grade 2", "Kiswahili", "language", "KIS-G2"),
            ("Lower Primary", "Grade 2", "Mathematics", "core", "MAT-G2"),
            ("Lower Primary", "Grade 2", "Environmental Activities", "science", "ENV-G2"),
            ("Lower Primary", "Grade 2", "Creative Arts", "creative", "ART-G2"),
            ("Lower Primary", "Grade 3", "English Language", "language", "ENG-G3"),
            ("Lower Primary", "Grade 3", "Kiswahili", "language", "KIS-G3"),
            ("Lower Primary", "Grade 3", "Mathematics", "core", "MAT-G3"),
            ("Lower Primary", "Grade 3", "Science and Technology", "science", "ST-G3"),
            ("Lower Primary", "Grade 3", "Religious Education", "humanities", "RE-G3"),
            ("Upper Primary", "Grade 4", "English Language", "language", "ENG-G4"),
            ("Upper Primary", "Grade 4", "Kiswahili", "language", "KIS-G4"),
            ("Upper Primary", "Grade 4", "Mathematics", "core", "MAT-G4"),
            ("Upper Primary", "Grade 4", "Science", "science", "SCI-G4"),
            ("Upper Primary", "Grade 4", "Social Studies", "humanities", "SS-G4"),
            ("Upper Primary", "Grade 5", "English Language", "language", "ENG-G5"),
            ("Upper Primary", "Grade 5", "Kiswahili", "language", "KIS-G5"),
            ("Upper Primary", "Grade 5", "Mathematics", "core", "MAT-G5"),
            ("Upper Primary", "Grade 5", "Science", "science", "SCI-G5"),
            ("Upper Primary", "Grade 5", "Agriculture", "technical", "AGR-G5"),
            ("Upper Primary", "Grade 6", "English Language", "language", "ENG-G6"),
            ("Upper Primary", "Grade 6", "Kiswahili", "language", "KIS-G6"),
            ("Upper Primary", "Grade 6", "Mathematics", "core", "MAT-G6"),
            ("Upper Primary", "Grade 6", "Science", "science", "SCI-G6"),
            ("Upper Primary", "Grade 6", "Geography", "humanities", "GEO-G6"),
            ("Junior Secondary", "Grade 7", "English", "language", "ENG-G7"),
            ("Junior Secondary", "Grade 7", "Kiswahili", "language", "KIS-G7"),
            ("Junior Secondary", "Grade 7", "Mathematics", "core", "MAT-G7"),
            ("Junior Secondary", "Grade 7", "Integrated Science", "science", "INT-SCI-G7"),
            ("Junior Secondary", "Grade 7", "Pre-Technical Studies", "technical", "PTS-G7"),
            ("Junior Secondary", "Grade 8", "English", "language", "ENG-G8"),
            ("Junior Secondary", "Grade 8", "Kiswahili", "language", "KIS-G8"),
            ("Junior Secondary", "Grade 8", "Mathematics", "core", "MAT-G8"),
            ("Junior Secondary", "Grade 8", "Biology", "science", "BIO-G8"),
            ("Junior Secondary", "Grade 8", "History and Government", "humanities", "HIST-G8"),
            ("Junior Secondary", "Grade 9", "English", "language", "ENG-G9"),
            ("Junior Secondary", "Grade 9", "Kiswahili", "language", "KIS-G9"),
            ("Junior Secondary", "Grade 9", "Mathematics", "core", "MAT-G9"),
            ("Junior Secondary", "Grade 9", "Chemistry", "science", "CHEM-G9"),
            ("Junior Secondary", "Grade 9", "Business Studies", "technical", "BUS-G9"),
            ("Senior Secondary", "Grade 10", "English", "language", "ENG-G10"),
            ("Senior Secondary", "Grade 10", "Kiswahili", "language", "KIS-G10"),
            ("Senior Secondary", "Grade 10", "Mathematics", "core", "MAT-G10"),
            ("Senior Secondary", "Grade 10", "Biology", "science", "BIO-G10"),
            ("Senior Secondary", "Grade 10", "Physics", "science", "PHY-G10"),
            ("Senior Secondary", "Grade 10", "Geography", "humanities", "GEO-G10"),
            ("Senior Secondary", "Grade 11", "English", "language", "ENG-G11"),
            ("Senior Secondary", "Grade 11", "Kiswahili", "language", "KIS-G11"),
            ("Senior Secondary", "Grade 11", "Mathematics", "core", "MAT-G11"),
            ("Senior Secondary", "Grade 11", "Chemistry", "science", "CHEM-G11"),
            ("Senior Secondary", "Grade 11", "Economics", "humanities", "ECO-G11"),
            ("Senior Secondary", "Grade 12", "English", "language", "ENG-G12"),
            ("Senior Secondary", "Grade 12", "Kiswahili", "language", "KIS-G12"),
            ("Senior Secondary", "Grade 12", "Mathematics", "core", "MAT-G12"),
            ("Senior Secondary", "Grade 12", "Physics", "science", "PHY-G12"),
            ("Senior Secondary", "Grade 12", "Geography", "humanities", "GEO-G12"),
        ]
        for docket_title, grade_level, name, category, code in subject_catalogue:
            SubjectCatalog.objects.get_or_create(
                name=name,
                grade_level=grade_level,
                defaults={
                    "docket": docket_map[docket_title],
                    "category": category,
                    "code": code,
                    "description": f"{name} for {grade_level} within the {docket_title} docket.",
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