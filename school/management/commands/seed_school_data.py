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


SUBJECT_CURRICULUM_CONTENT = {
    "Agriculture": ("Soil health and crop production", "soil texture, organic matter, and nutrient cycling", "compare soil samples and plan a crop-bed improvement"),
    "Arabic": ("Everyday greetings and sentence building", "Arabic greetings, common vocabulary, and sentence order", "read a short greeting and build a simple dialogue"),
    "Aviation": ("Principles of flight and aviation safety", "lift, drag, thrust, and safe pre-flight checks", "identify how control surfaces affect a supervised model flight"),
    "Biology": ("Cells and life processes", "cell structures, photosynthesis, and organism systems", "connect an observed structure to its function"),
    "Building Construction": ("Building materials and structural drawings", "material properties, scale drawings, and site safety", "interpret a simple plan and select a suitable building material"),
    "Business Studies": ("Enterprise and basic business records", "customer needs, costs, revenue, and simple records", "prepare a small enterprise budget and record a transaction"),
    "CRE": ("Christian values and responsible stewardship", "Christian teachings, service, and care for creation", "interpret a parable and relate its message to a community choice"),
    "Chemistry": ("Matter, mixtures, and separation", "particle properties, solubility, and separation methods", "select a safe method for separating a stated mixture"),
    "Community Service Learning": ("Community needs and service planning", "listening, needs assessment, shared responsibility, and reflection", "plan a small service action with a clear goal and review"),
    "Computer Studies": ("Algorithms and computer systems", "input, processing, output, storage, and stepwise algorithms", "write and test an algorithm for a familiar task"),
    "Core Mathematics": ("Algebraic reasoning and functions", "variables, equivalent expressions, and relationships", "represent a real situation with an equation and check its solution"),
    "Creative Activities": ("Pattern, colour, and creative expression", "shape, colour, rhythm, and purposeful arrangement", "make and explain a repeating pattern"),
    "Creative Arts": ("Composition and visual communication", "line, shape, colour, balance, and intended meaning", "plan a composition and revise it against a design goal"),
    "Electricity": ("Electrical circuits and installation safety", "series paths, circuit symbols, conductors, and isolation", "trace a supervised low-voltage circuit using a circuit diagram"),
    "English": ("Reading comprehension and clear writing", "main ideas, evidence, vocabulary in context, and sentence structure", "support an inference with evidence from a passage"),
    "English Activities": ("Listening, phonics, and early reading", "letter sounds, familiar words, listening, and oral expression", "match a spoken word to its sound pattern and use it in a sentence"),
    "Environmental Activities": ("Water, soil, and local environmental care", "local resources, waste, habitats, and conservation", "observe one local environmental issue and propose a practical action"),
    "Essential Mathematics": ("Numeracy and mathematics in daily life", "number operations, measurement, money, and data", "solve a practical budgeting or measurement problem and show the working"),
    "Fasihi ya Kiswahili": ("Uchambuzi wa fasihi ya Kiswahili", "dhamira, wahusika, mandhari, na matumizi ya lugha", "tumia ushahidi kutoka kwenye kifungu kueleza dhamira"),
    "Fine Arts": ("Drawing, tone, and visual composition", "line, form, value, perspective, and visual emphasis", "use a light source to plan tones in a still-life drawing"),
    "French": ("Salutations and simple French sentences", "greetings, articles, common verbs, and basic word order", "introduce yourself and ask a simple question in French"),
    "General Science": ("Energy, materials, and scientific investigation", "forms of energy, material properties, and fair testing", "plan a simple comparison and record measurable observations"),
    "Geography": ("Map skills, weather, and landforms", "map symbols, scale, direction, rainfall, and relief", "use a map and observations to explain a local landscape pattern"),
    "German": ("German greetings and sentence structure", "greetings, noun articles, common verbs, and word order", "introduce yourself and form a simple German sentence"),
    "HRE": ("Hindu teachings and values in daily life", "dharma, respect, responsibility, and Hindu traditions", "relate a teaching or story to a respectful everyday decision"),
    "History and Citizenship": ("Historical sources and responsible citizenship", "primary sources, chronology, rights, duties, and public participation", "compare a source with another account and justify a civic action"),
    "Home Science": ("Nutrition, food safety, and household resources", "balanced meals, hygiene, food storage, and resource use", "plan a balanced meal and explain safe preparation choices"),
    "ICT": ("Digital information, productivity, and online safety", "files, data, digital communication, privacy, and security", "organize information and identify a safe response to an online risk"),
    "IRE": ("Islamic values, worship, and community responsibility", "Qur'anic guidance, compassion, honesty, and responsible conduct", "apply an Islamic value to a practical community situation"),
    "Indigenous Language": ("Oral language and community vocabulary", "listening, pronunciation, local vocabulary, and respectful conversation", "record and use a familiar expression in a short dialogue"),
    "Indigenous Languages": ("Oral literature and language heritage", "oral narratives, proverbs, vocabulary, and cultural context", "interpret a proverb or story and explain its context"),
    "Integrated Science": ("Scientific investigations and living systems", "variables, observations, ecosystems, and evidence-based explanations", "plan a fair investigation and support a conclusion with observations"),
    "Kiswahili": ("Ufahamu na mawasiliano ya Kiswahili", "msamiati, sarufi, ufahamu, na ujenzi wa sentensi", "soma kifungu kifupi na uunge mkono jibu kwa ushahidi"),
    "Kiswahili Lugha": ("Sarufi na matumizi ya Kiswahili", "aina za maneno, ngeli, upatanisho, na uandishi", "rekebisha sentensi kwa kutumia upatanisho sahihi wa kisarufi"),
    "Literature in English": ("Poetry, prose, and dramatic methods", "voice, imagery, character, setting, and theme", "support an interpretation of a text with a relevant quotation"),
    "Mandarin": ("Mandarin tones and everyday expressions", "tone, pinyin, greetings, and simple sentence patterns", "listen for tone differences and use a greeting in context"),
    "Marine and Fisheries Technology": ("Aquatic ecosystems and sustainable fisheries", "water quality, aquatic habitats, fish handling, and conservation", "interpret a water-quality observation and suggest a sustainable practice"),
    "Mathematics": ("Number, ratio, and problem solving", "place value, fractions, ratio, and checking calculations", "model a real problem with calculations and explain the answer"),
    "Media Technology": ("Media production and responsible communication", "audience, framing, sound, editing, and source attribution", "plan a short media message and identify its intended audience"),
    "Metalwork": ("Metal properties, tools, and safe joining", "measurement, material choice, marking out, and joining methods", "choose a suitable joining method for a supervised model task"),
    "Music and Dance": ("Rhythm, pitch, and movement patterns", "steady beat, pitch, dynamics, and coordinated movement", "perform and compare a short rhythm or movement sequence"),
    "Physical Education": ("Fitness, movement, and healthy participation", "warm-up, coordination, fitness components, and recovery", "plan a safe warm-up and identify the fitness skill it develops"),
    "Physics": ("Forces, energy, and electrical measurements", "motion, energy transfer, current, potential difference, and resistance", "take readings in a supervised circuit and explain a relationship"),
    "Power Mechanics": ("Mechanical systems and engine maintenance", "motion transfer, components, routine inspection, and workshop safety", "trace how a mechanical system transfers motion"),
    "Pre-Technical Studies": ("Design process, materials, and technical drawing", "design briefs, measurement, material properties, and evaluation", "make a dimensioned plan and evaluate a model against its brief"),
    "Science and Technology": ("Materials, living things, and design solutions", "observation, material properties, simple systems, and responsible design", "test a simple design and record evidence before improving it"),
    "Social Studies": ("Maps, communities, and shared responsibilities", "location, community resources, culture, and civic participation", "use a map or local evidence to explain a community issue"),
    "Sports and Recreation": ("Game skills, rules, and inclusive participation", "movement skills, fair play, teamwork, and adaptation", "apply a game skill while following rules and including teammates"),
    "Theatre and Film": ("Story, performance, and visual storytelling", "script, character, staging, storyboard, and audience", "plan a short scene with a clear sequence and performance roles"),
    "Woodwork": ("Timber, measurement, and safe construction", "wood grain, marking out, joints, finishing, and tool safety", "plan and measure a small supervised timber model"),
}


def upsert_game_topic(subject, title, description, levels):
    topic, _ = GameTopic.objects.update_or_create(
        subject=subject,
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
    return topic


def generated_subject_levels(subject, curriculum, peers):
    focus, concept, practice = curriculum

    def evidence(item):
        return f"Observations about {item[1]} recorded while learners {item[2]}"

    def application(item):
        return f"Use {item[1]} to {item[2]} in {item[0]}"

    def conclusion(item):
        return f"{item[0]} can be explained using {item[1]} and evidence from the task"

    questions = (
        (f"Which topical focus belongs to {subject.name}?", focus, [item[0] for item in peers], f"{focus} is the selected CBE focus for {subject.name}."),
        (f"Which key idea supports learning about {focus}?", concept, [item[1] for item in peers], f"{concept.capitalize()} is central to {focus}."),
        (f"Which activity gives practice with {focus}?", practice, [item[2] for item in peers], f"Learners can {practice} to explore {focus}."),
        (f"What evidence should be recorded during {focus}?", evidence(curriculum), [evidence(item) for item in peers], f"Record observations about {concept} while completing the practical task."),
        (f"Which scenario applies {subject.name} learning about {focus}?", application(curriculum), [application(item) for item in peers], f"Apply {concept} through a task connected to {focus}."),
        (f"Which conclusion connects {focus} with its key idea?", conclusion(curriculum), [conclusion(item) for item in peers], f"A sound conclusion links {focus} to {concept} and the evidence collected."),
    )

    levels = []
    for difficulty in range(1, 4):
        level_questions = []
        for order in range(2):
            prompt, answer, distractors, explanation = questions[(difficulty - 1) * 2 + order]
            distractors = list(dict.fromkeys(choice for choice in distractors if choice != answer))[:3]
            while len(distractors) < 3:
                distractors.append(f"An unrelated idea from another {subject.category} topic")
            correct_choice = (difficulty + order) % 4
            choices = distractors
            choices.insert(correct_choice, answer)
            level_questions.append((prompt, choices, correct_choice, explanation))
        levels.append(tuple(level_questions))
    return tuple(levels)


def upsert_subject_guide(subject, curriculum, created_by):
    focus, concept, practice = curriculum
    title = f"{subject.grade_level} {subject.name} Topical Study Guide"
    description = f"CBE study guide for {subject.grade_level} {subject.name}, focused on {focus}."
    content_outline = (
        f"Topic: {focus}\n"
        f"Key concept: {concept.capitalize()}.\n"
        f"Guided learning activity: Learners {practice}.\n"
        "Review: explain the idea, practise the skill, and use evidence to check understanding."
    )
    exercises = (
        f"1. Explain {concept} in your own words.\n"
        f"2. Complete this task: {practice}.\n"
        f"3. Record one observation or example connected to {focus}.\n"
        "4. Write a short conclusion using evidence from your work."
    )
    SubjectBook.objects.update_or_create(
        subject=subject,
        title=title,
        defaults={
            "grade_level": subject.grade_level,
            "author_name": "Peak CBE Learning Team",
            "docket": subject.docket,
            "description": description,
            "content_outline": content_outline,
            "exercises": exercises,
            "diagrams": "",
            "file_url": "",
            "created_by": created_by,
            "is_teacher_uploaded": False,
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

            active_subjects = list(SubjectCatalog.objects.filter(is_active=True).select_related("docket"))
            subjects_by_category = {}
            for subject in active_subjects:
                subjects_by_category.setdefault(subject.category, {})[subject.name] = SUBJECT_CURRICULUM_CONTENT[
                    subject.name
                ]

            for subject in active_subjects:
                if subject.pk in authored_subjects:
                    continue
                curriculum = SUBJECT_CURRICULUM_CONTENT[subject.name]
                peers = [
                    peer_curriculum
                    for peer_name, peer_curriculum in subjects_by_category[subject.category].items()
                    if peer_name != subject.name
                ]
                title = f"{subject.name}: {curriculum[0]}"
                description = f"{subject.grade_level} {subject.name}. Focus: {curriculum[0]}. Key idea: {curriculum[1]}."
                topic = GameTopic.objects.filter(
                    subject=subject,
                    created_by__isnull=True,
                ).order_by("id").first()
                if topic:
                    topic.title = title
                    topic.description = description
                    topic.is_active = True
                    topic.save(update_fields=("title", "description", "is_active"))
                else:
                    topic = GameTopic.objects.create(
                        subject=subject,
                        title=title,
                        description=description,
                    )
                for difficulty, questions in enumerate(
                    generated_subject_levels(subject, curriculum, peers),
                    start=1,
                ):
                    for order, (prompt, choices, correct_choice, explanation) in enumerate(questions):
                        GameQuestion.objects.update_or_create(
                            topic=topic,
                            difficulty=difficulty,
                            order=order,
                            defaults={
                                "prompt": prompt,
                                "choices": choices,
                                "correct_choice": correct_choice,
                                "explanation": explanation,
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

        cbe_author = User.objects.filter(role="admin", is_active=True).first()
        for subject in SubjectCatalog.objects.filter(is_active=True).select_related("docket"):
            upsert_subject_guide(
                subject,
                SUBJECT_CURRICULUM_CONTENT[subject.name],
                cbe_author,
            )

        self.stdout.write(self.style.SUCCESS("Peak Group of Schools demo data is ready."))