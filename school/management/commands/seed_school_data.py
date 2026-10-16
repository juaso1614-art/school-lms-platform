from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from school.models import (
    GameQuestion,
    GameTopic,
    Invoice,
    ResourceMaterial,
    SchoolClass,
    SubjectBook,
    SubjectCatalog,
    SubjectDocket,
    User,
)


CBE_GAME_CONTENT = (
    (
        "Mathematics",
        "Grade 2",
        "Place value and addition",
        "Build number sense with tens, ones, and everyday addition.",
        (
            (
                ("How many tens are in 46?", ("4", "6", "40", "46"), 0, "The digit 4 is in the tens place, so it represents four tens."),
                ("What is 23 + 14?", ("27", "37", "36", "47"), 1, "Add tens and ones: 20 + 10 + 3 + 4 = 37."),
            ),
            (
                ("Which number is made from 5 tens and 8 ones?", ("58", "85", "13", "508"), 0, "Five tens make 50; eight ones make 8; together they make 58."),
                ("A learner has 35 beads and gets 27 more. How many beads are there now?", ("52", "62", "612", "72"), 1, "35 + 27 = 62."),
            ),
            (
                ("Which equation shows 64 split into tens and ones?", ("6 + 4", "60 + 4", "64 + 10", "6 + 40"), 1, "64 is six tens and four ones, which is 60 + 4."),
                ("A class has 48 pencils. It receives 26 more, then shares all the pencils equally among 2 groups. How many pencils are in each group?", ("32", "37", "74", "24"), 0, "48 + 26 = 74, and 74 shared equally between 2 groups is 37."),
            ),
        ),
    ),
    (
        "Science and Technology",
        "Grade 4",
        "Plants and their parts",
        "Explore how roots, stems, leaves, and flowers support plant growth.",
        (
            (
                ("Which plant part usually absorbs water from the soil?", ("Flower", "Root", "Leaf", "Fruit"), 1, "Roots absorb water and mineral salts from the soil."),
                ("Which part of a plant mainly makes food using sunlight?", ("Leaf", "Root", "Seed", "Bark"), 0, "Leaves use sunlight, water, and carbon dioxide to make food."),
            ),
            (
                ("What is one main job of a plant stem?", ("Absorb soil only", "Support the plant and carry water", "Make seeds only", "Take in light underground"), 1, "The stem supports the plant and transports water and food."),
                ("Which plant part can develop into a fruit after fertilisation?", ("Root", "Flower", "Stem", "Leaf"), 1, "The flower contains reproductive parts and can develop into fruit after fertilisation."),
            ),
            (
                ("A plant kept in darkness becomes weak. Which process is most directly affected?", ("Photosynthesis", "Germination only", "Water absorption", "Pollination"), 0, "Without light, photosynthesis cannot make enough food for healthy growth."),
                ("A learner covers a leaf with a clear plastic bag and later sees water droplets inside. What does this show?", ("Roots make rain", "Leaves release water vapour", "Flowers absorb water", "Stems produce soil"), 1, "Water vapour leaves the leaf through tiny openings and condenses on the bag."),
            ),
        ),
    ),
    (
        "Integrated Science",
        "Grade 7",
        "Mixtures and separation",
        "Choose suitable methods for separating mixtures in the home and laboratory.",
        (
            (
                ("Which method separates stones from dry sand using a mesh?", ("Sieving", "Evaporation", "Distillation", "Decanting"), 0, "A sieve lets fine sand pass through while larger stones remain."),
                ("How can clean water be separated from muddy water after the mud settles?", ("Filtration", "Magnetism", "Melting", "Freezing"), 0, "Filtration traps insoluble mud while water passes through the filter."),
            ),
            (
                ("Which method can recover salt from a salt solution?", ("Evaporation", "Sieving", "Magnetic separation", "Sorting by hand"), 0, "Evaporating the water leaves the dissolved salt behind."),
                ("A mixture contains iron filings and sulphur powder. What is the simplest way to remove the iron?", ("Use a magnet", "Add water and sieve", "Evaporate it", "Use a filter paper"), 0, "Iron is magnetic, while sulphur is not attracted to a magnet."),
            ),
            (
                ("Which method is best for obtaining pure water from salty water?", ("Distillation", "Sieving", "Hand sorting", "Filtration only"), 0, "Distillation evaporates water and condenses the vapour, leaving salt behind."),
                ("A learner wants to separate cooking oil from water. Which method is most suitable?", ("Separating funnel", "Evaporation to dryness", "Magnetism", "Chromatography"), 0, "Oil and water form separate layers, which can be drained using a separating funnel."),
            ),
        ),
    ),
    (
        "Biology",
        "Grade 10",
        "Cell structure and function",
        "Connect cell structures to the functions that keep organisms alive.",
        (
            (
                ("Which cell structure controls most cell activities?", ("Nucleus", "Cell wall", "Vacuole", "Cytoplasm"), 0, "The nucleus contains genetic material and controls cell activities."),
                ("Which structure is the site of aerobic respiration in a typical eukaryotic cell?", ("Mitochondrion", "Ribosome", "Chloroplast", "Cell membrane"), 0, "Mitochondria release usable energy through aerobic respiration."),
            ),
            (
                ("Which structure controls what enters and leaves the cell?", ("Cell membrane", "Nucleus", "Ribosome", "Chromosome"), 0, "The cell membrane is selectively permeable and regulates movement of substances."),
                ("Why do palisade cells contain many chloroplasts?", ("To absorb light for photosynthesis", "To store genetic information", "To control osmosis", "To make the cell rigid"), 0, "Chloroplasts contain chlorophyll, which captures light energy for photosynthesis."),
            ),
            (
                ("A cell specialised to absorb water from soil has a long extension. What is the main advantage?", ("It increases surface area for absorption", "It stores more chromosomes", "It prevents respiration", "It reduces contact with soil"), 0, "The root hair extension increases surface area, improving water and mineral uptake."),
                ("Which feature distinguishes a typical prokaryotic cell from a eukaryotic cell?", ("It has no membrane-bound nucleus", "It has a cell membrane", "It contains cytoplasm", "It carries genetic material"), 0, "Prokaryotic genetic material is not enclosed in a membrane-bound nucleus."),
            ),
        ),
    ),
)


CBE_CATEGORY_GAME_CONTENT = {
    "core": (
        "Number patterns and problem solving",
        "Practise number sense, calculation, and reasoning with everyday problems.",
        (
            (
                ("In 572, what is the value of the digit 7?", ("7", "70", "700", "572"), 1, "The 7 is in the tens place, so its value is 70."),
                ("What is 36 + 28?", ("54", "64", "74", "68"), 1, "36 + 28 = 64."),
            ),
            (
                ("What is 3/4 of 20?", ("5", "10", "15", "18"), 2, "20 divided into 4 equal parts gives 5; 3 parts give 15."),
                ("Four notebooks cost 35 shillings each. What is the total cost?", ("105", "120", "140", "160"), 2, "4 × 35 = 140 shillings."),
            ),
            (
                ("A learner reads 18 pages each day for 5 days. How many pages are read?", ("23", "72", "90", "95"), 2, "18 × 5 = 90 pages."),
                ("A 150 litre tank is 3/5 full. How much water is in it?", ("50 L", "60 L", "90 L", "120 L"), 2, "150 × 3/5 = 90 litres."),
            ),
        ),
    ),
    "language": (
        "Reading and communication skills",
        "Build vocabulary, sentence awareness, and meaning from context.",
        (
            (
                ("Which punctuation mark normally ends a direct question?", ("Full stop", "Comma", "Question mark", "Apostrophe"), 2, "A direct question normally ends with a question mark."),
                ("Which word is the action word in 'The farmer waters seedlings'?", ("farmer", "waters", "seedlings", "the"), 1, "'Waters' tells what the farmer does; it is the verb."),
            ),
            (
                ("In 'The path was narrow, so we walked in single file', what does 'narrow' mean?", ("Not wide", "Very long", "Slippery", "Crowded"), 0, "The clue 'single file' shows that the path was not wide."),
                ("Which sentence uses a joining word to show contrast?", ("We planted beans and maize.", "We planted beans, but the soil was dry.", "We planted beans yesterday.", "We planted beans near the fence."), 1, "'But' joins ideas that contrast."),
            ),
            (
                ("A passage says, 'Although the sky was cloudy, the match continued.' What does 'although' signal?", ("A contrast", "A list", "A cause only", "A question"), 0, "'Although' introduces an idea that contrasts with the main clause."),
                ("Which is the clearest summary of a paragraph about saving water at school?", ("It mentions a tap.", "Learners can reduce waste by closing taps and reporting leaks.", "Water is wet.", "The paragraph has four sentences."), 1, "A good summary captures the main idea and key actions without minor details."),
            ),
        ),
    ),
    "science": (
        "Investigation and scientific evidence",
        "Practise careful observation, fair testing, and interpreting evidence.",
        (
            (
                ("Which action is a safe way to identify an unknown classroom material?", ("Taste it", "Smell it closely", "Observe it without touching or tasting", "Mix it with another material"), 2, "Use safe observation and follow the teacher's instructions; never taste unknown materials."),
                ("What should you use to measure the temperature of water?", ("Thermometer", "Ruler", "Balance", "Stopwatch"), 0, "A thermometer measures temperature."),
            ),
            (
                ("A learner tests how light affects seedling growth. Which factor should be kept the same for a fair comparison?", ("Amount of water", "Light exposure", "Measured growth", "Final conclusion"), 0, "Keep other conditions, such as water, the same while changing light exposure."),
                ("Why should measurements include units?", ("To show what quantity and scale were measured", "To make results longer", "To replace observations", "To guarantee a result"), 0, "Units make measurements interpretable and comparable."),
            ),
            (
                ("A learner repeats a measurement and gets similar results. What does this most strongly support?", ("Greater reliability", "A guaranteed hypothesis", "A larger sample", "A different variable"), 0, "Consistent repeated measurements make results more reliable."),
                ("A result differs greatly from the other trials. What is the best next step?", ("Hide it", "Check the method and repeat the trial", "Change every variable", "Choose the expected result"), 1, "Check for a measurement or procedure issue and repeat carefully; do not discard data without reason."),
            ),
        ),
    ),
    "humanities": (
        "People, place, and evidence",
        "Use maps, sources, and reasoned evidence to understand people and places.",
        (
            (
                ("What does a map key help a reader understand?", ("The meaning of map symbols", "The age of the map", "The weather tomorrow", "The distance to every place"), 0, "A key or legend explains the symbols used on a map."),
                ("On a standard map, which direction is usually at the top?", ("South", "East", "North", "West"), 2, "Most maps are oriented with north at the top unless a compass rose says otherwise."),
            ),
            (
                ("Which source is usually a primary source for studying a past event?", ("A diary written by a person who witnessed it", "A recent textbook summary", "An unsigned online summary", "A fictional story set later"), 0, "A contemporary diary is a first-hand record from the period."),
                ("Why compare two accounts of the same event?", ("To consider perspective and corroborate evidence", "To make both accounts identical", "To avoid checking dates", "To select the longer account"), 0, "Comparing accounts can reveal perspective and help check claims against evidence."),
            ),
            (
                ("A claim says a market grew because a new road opened. Which evidence would best help test the claim?", ("Records of market activity before and after the road opened", "The colour of the road signs", "A person's unrelated opinion", "A map with no dates"), 0, "Comparable records before and after the change provide relevant evidence."),
                ("A source was created long after the event it describes. What should a researcher do?", ("Check its author, evidence, and other sources", "Assume every detail is exact", "Ignore all earlier records", "Treat opinion as measurement"), 0, "Evaluate authorship and corroborate later accounts with other available evidence."),
            ),
        ),
    ),
    "creative": (
        "Elements and creative practice",
        "Explore pattern, rhythm, planning, and reflection in creative work.",
        (
            (
                ("Which pair of colours makes orange when mixed as paint?", ("Red and yellow", "Blue and green", "Black and white", "Blue and yellow"), 0, "Red and yellow combine to make orange in basic pigment mixing."),
                ("In music, what is a steady repeated pulse called?", ("Beat", "Shade", "Texture", "Frame"), 0, "A beat is the regular pulse that supports rhythm."),
            ),
            (
                ("Why might an artist repeat a shape or colour in a composition?", ("To create pattern and visual unity", "To remove all contrast", "To hide the subject", "To make every part identical"), 0, "Repetition can create pattern and help connect parts of a composition."),
                ("What is a useful first step before rehearsing a short performance?", ("Agree on roles and a simple plan", "Skip the script", "Perform without listening", "Change every movement at once"), 0, "A shared plan helps performers coordinate roles and practice purposefully."),
            ),
            (
                ("After reviewing a draft performance, one section is unclear. What is the best response?", ("Revise that section and rehearse it again", "Ignore all feedback", "Remove the whole performance", "Stop checking the work"), 0, "Focused revision and another rehearsal help test whether the change improves clarity."),
                ("How can a learner judge whether a design communicates its intended idea?", ("Compare it with the goal and seek audience feedback", "Count only the materials", "Avoid showing anyone", "Change it without a reason"), 0, "Evaluate creative work against its purpose and use feedback to guide improvements."),
            ),
        ),
    ),
    "technical": (
        "Tools, design, and safe practice",
        "Practise safe tool choices, measurement, and step-by-step problem solving.",
        (
            (
                ("What should you do before using an unfamiliar tool?", ("Check instructions and safety guidance", "Use it as quickly as possible", "Remove its guard", "Ask a friend to guess"), 0, "Understand the instructions and safety guidance before use, with supervision where required."),
                ("Which tool is best for measuring the length of a short board?", ("Ruler or tape measure", "Thermometer", "Compass", "Measuring jug"), 0, "A ruler or tape measure is designed to measure length."),
            ),
            (
                ("A design does not fit its intended space. What should be checked first?", ("The recorded dimensions", "The paint colour", "The project title", "The storage label"), 0, "Check the dimensions against the available space before changing the design."),
                ("Why is personal protective equipment used for a practical task?", ("To reduce exposure to identified hazards", "To replace safe procedures", "To make every tool harmless", "To avoid reading instructions"), 0, "Appropriate protective equipment helps reduce specific risks but does not replace safe practice."),
            ),
            (
                ("A prototype fails during a supervised test. What is the best next step?", ("Record what happened, identify a cause, and revise one feature", "Hide the result", "Change every part without recording it", "Repeat the same test without inspection"), 0, "Recorded evidence helps identify a cause and evaluate a focused design change."),
                ("How can a learner compare two material samples fairly?", ("Test them under the same conditions and record observations", "Use a different test for each", "Choose the preferred result first", "Skip measurements"), 0, "Consistent conditions make comparisons more meaningful."),
            ),
        ),
    ),
}


def upsert_game_topic(subject, title, description, levels):
    topic, _ = GameTopic.objects.update_or_create(
        subject=subject,
        title=title,
        defaults={"description": description, "is_active": True},
    )
    for difficulty, questions in enumerate(levels, start=1):
        for order, (prompt, choices, correct_choice, explanation) in enumerate(questions):
            GameQuestion.objects.update_or_create(
                topic=topic,
                difficulty=difficulty,
                order=order,
                defaults={
                    "prompt": prompt,
                    "choices": list(choices),
                    "correct_choice": correct_choice,
                    "explanation": explanation,
                    "is_active": True,
                },
            )


class Command(BaseCommand):
    help = "Create the CBE subject catalog, topical games, demo users, and sample portal data."

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

            authored_subjects = set()
            for subject_name, grade_level, title, description, levels in CBE_GAME_CONTENT:
                subject = SubjectCatalog.objects.filter(
                    name=subject_name,
                    grade_level=grade_level,
                    is_active=True,
                ).first()
                if not subject:
                    continue
                upsert_game_topic(subject, title, description, levels)
                authored_subjects.add(subject.pk)

            for subject in SubjectCatalog.objects.filter(is_active=True):
                if subject.pk in authored_subjects:
                    continue
                title, description, levels = CBE_CATEGORY_GAME_CONTENT[subject.category]
                upsert_game_topic(
                    subject,
                    f"{subject.name}: {title}",
                    f"{subject.grade_level} {subject.name}. {description}",
                    levels,
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