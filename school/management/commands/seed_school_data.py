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

SUBJECT_TOPIC_EXTENSIONS = {
    "Agriculture": (("Crop rotation and planting systems", "crop rotation, spacing, and seasonal planning", "plan a simple crop rotation using different crop groups"), ("Irrigation and crop protection", "irrigation scheduling, pest identification, and integrated controls", "compare irrigation choices and select a safe crop-protection response")),
    "Arabic": (("Arabic vocabulary and pronouns", "nouns, pronouns, and vocabulary for people and places", "match words to their referents and build short sentences"), ("Arabic reading and dialogue", "short texts, question forms, and conversational responses", "read a short dialogue and answer with a complete sentence")),
    "Aviation": (("Aircraft components and control surfaces", "ailerons, elevators, rudders, and their effects on movement", "match a control surface to the movement it helps produce"), ("Aviation weather and flight planning", "wind, visibility, weather reports, and safe planning", "interpret a simple weather observation before a model-flight plan")),
    "Biology": (("Ecology and ecosystem relationships", "food chains, populations, habitats, and energy transfer", "trace how a change in one population can affect a food chain"), ("Human body systems and health", "organs, transport, nutrition, and system coordination", "connect a body system to its role in maintaining health")),
    "Building Construction": (("Construction measurement and drawings", "dimensions, scale, symbols, and plan views", "read a scaled drawing and identify a required measurement"), ("Structures, materials, and site safety", "loads, material selection, hazards, and protective measures", "choose a suitable material and identify a safe work procedure")),
    "Business Studies": (("Markets, customers, and enterprise", "customer needs, products, pricing, and ethical selling", "match a customer need to a product and a fair price"), ("Business costs and simple records", "start-up costs, sales, expenses, and basic cash records", "calculate a simple balance from recorded sales and expenses")),
    "CRE": (("Biblical stories and interpretation", "characters, context, message, and textual evidence", "use a detail from a Bible story to explain its message"), ("Christian worship and community service", "worship, compassion, reconciliation, and service", "select a responsible community action linked to a Christian value")),
    "Chemistry": (("Atomic structure and the periodic table", "elements, protons, electrons, groups, and periods", "use an element's position to identify a basic property"), ("Chemical reactions and acids", "reactants, products, indicators, and safe observations", "classify a simulated indicator result and represent a simple reaction")),
    "Community Service Learning": (("Community needs assessment", "stakeholders, observation, respectful questions, and priorities", "sort observations to identify a clearly evidenced community need"), ("Service action and reflection", "action plans, roles, participation, and evaluation", "set a measurable goal and reflect on evidence after a service activity")),
    "Computer Studies": (("Algorithms and programming logic", "sequence, selection, repetition, and debugging", "trace an algorithm and locate a step that causes an incorrect result"), ("Data representation and computer networks", "binary data, devices, connections, and responsible access", "identify how a device sends information across a simple network")),
    "Core Mathematics": (("Functions and algebraic models", "variables, expressions, equations, and input-output relationships", "represent a changing quantity with a simple function"), ("Geometry, statistics, and probability", "shape properties, data summaries, and chance", "choose a suitable representation for a data set or geometric relationship")),
    "Creative Activities": (("Colour, shape, and pattern", "primary colours, repeated shapes, contrast, and arrangement", "create and describe a repeating pattern with a clear rule"), ("Making, movement, and creative expression", "materials, rhythm, movement, and reflective choices", "plan a short creative sequence and explain one design choice")),
    "Creative Arts": (("Visual elements and composition", "line, shape, colour, space, balance, and emphasis", "revise a composition to make its focal point clearer"), ("Art materials and creative interpretation", "media choice, technique, audience, and interpretation", "select a medium and justify how it supports an intended message")),
    "Electricity": (("Circuit symbols and series circuits", "circuit paths, symbols, switches, and component connections", "trace a low-voltage series circuit from its diagram"), ("Electrical measurement and protection", "current, voltage, isolation, fuses, and safe procedures", "choose a safe meter connection for a supervised circuit check")),
    "English": (("Grammar, sentence structure, and vocabulary", "parts of speech, clauses, punctuation, and meaning in context", "edit a paragraph for clear sentence structure and word choice"), ("Composition and oral communication", "purpose, audience, paragraphing, listening, and revision", "plan and revise a short message for a stated audience")),
    "English Activities": (("Letter sounds and word building", "phonemes, letter patterns, syllables, and familiar words", "segment a familiar word and match its sounds to letters"), ("Listening, speaking, and early reading", "listening for details, sequencing, and oral sentences", "retell a short event in order using a complete sentence")),
    "Environmental Activities": (("Water sources and conservation", "water uses, clean sources, safe storage, and conservation", "identify a way to reduce water waste at home or school"), ("Habitats, waste, and local action", "living things, habitats, sorting waste, and community care", "classify a local waste item and suggest an appropriate action")),
    "Essential Mathematics": (("Measurement, money, and budgeting", "units, prices, totals, change, and simple budgets", "compare costs and prepare a balanced small budget"), ("Data, chance, and practical numeracy", "tables, graphs, frequency, and everyday chance", "read a data display and support a conclusion with values")),
    "Fasihi ya Kiswahili": (("Ushairi na matumizi ya lugha", "mshororo, vina, tamathali za usemi, na ujumbe", "tumia mfano wa lugha kueleza ujumbe wa shairi"), ("Riwaya, tamthilia, na wahusika", "wahusika, mandhari, migogoro, na dhamira", "linganisha kitendo cha mhusika na dhamira ya kazi")),
    "Fine Arts": (("Line, form, and perspective", "contour, proportion, viewpoint, and spatial depth", "use a viewpoint and proportions to plan a drawing"), ("Tone, colour, and art interpretation", "light source, value, colour relationships, and meaning", "explain how tone or colour changes the reading of an artwork")),
    "French": (("French vocabulary and everyday situations", "common nouns, articles, greetings, and useful expressions", "choose an expression that fits a familiar situation"), ("French verbs and sentence construction", "subject pronouns, present-tense verbs, and word order", "build a short sentence with a suitable subject and verb")),
    "General Science": (("Energy forms and transformations", "energy stores, transfer, conservation, and observable change", "trace an energy transfer in a familiar device"), ("Materials and fair investigations", "material properties, variables, measurements, and evidence", "plan a fair comparison of two materials and record observations")),
    "Geography": (("Map scale, direction, and location", "grid references, compass direction, symbols, and scale", "use a map key and scale to describe a route"), ("Weather, climate, and landform processes", "weather elements, rainfall, relief, and surface processes", "interpret observations to explain a local weather or landform pattern")),
    "German": (("German vocabulary and everyday situations", "common nouns, articles, greetings, and useful expressions", "choose a phrase that fits a familiar situation"), ("German verbs and sentence construction", "pronouns, present-tense verbs, and basic word order", "build a simple sentence with an appropriate verb form")),
    "HRE": (("Hindu stories, teachings, and interpretation", "context, dharma, ahimsa, and lessons from Hindu traditions", "use a story or teaching to explain a respectful choice"), ("Hindu worship, festivals, and community", "worship practices, festivals, belonging, and responsibility", "connect a festival or practice to its community meaning")),
    "History and Citizenship": (("Chronology and historical sources", "timelines, primary sources, perspective, and corroboration", "compare two accounts and identify a supported claim"), ("Rights, duties, and public participation", "rights, responsibilities, leadership, and civic processes", "choose a constructive way to address a community issue")),
    "Home Science": (("Balanced nutrition and meal planning", "food groups, nutrients, portions, and dietary needs", "plan a balanced meal using locally available foods"), ("Food hygiene, textiles, and household resources", "clean handling, storage, fibres, care labels, and waste reduction", "choose a safe storage or care method for a household item")),
    "ICT": (("Digital documents and information management", "files, folders, productivity tools, and accurate data handling", "organize a set of files and select a suitable digital tool"), ("Online safety, privacy, and communication", "personal data, secure access, respectful communication, and risks", "identify a risk in a digital scenario and choose a safer response")),
    "IRE": (("Qur'anic guidance and Islamic teachings", "context, compassion, honesty, and interpretation of guidance", "connect a teaching to a fair everyday decision"), ("Worship, conduct, and community responsibility", "worship, respect, service, and care for others", "choose a responsible action for a community situation")),
    "Indigenous Language": (("Oral expression and everyday vocabulary", "listening, pronunciation, vocabulary, and turn-taking", "use a familiar expression appropriately in a short dialogue"), ("Stories, sayings, and language context", "oral narrative, proverbs, meaning, and respectful context", "explain the meaning of a saying using an example")),
    "Indigenous Languages": (("Oral literature and storytelling", "narrative sequence, performance, audience, and language heritage", "retell a story and identify how its sequence supports meaning"), ("Proverbs, vocabulary, and cultural context", "figurative meaning, local vocabulary, and context", "interpret a proverb and describe a context where it applies")),
    "Integrated Science": (("Variables, measurement, and fair testing", "independent and dependent variables, controls, and repeat readings", "identify what to change and measure in a fair test"), ("Ecosystems, materials, and evidence", "organism relationships, material properties, and supported claims", "use observations to explain a change in a simple ecosystem")),
    "Kiswahili": (("Sarufi na ujenzi wa sentensi", "aina za maneno, nyakati, upatanisho, na mpangilio wa sentensi", "rekebisha sentensi ili iwe na upatanisho sahihi"), ("Ufahamu, msamiati, na mawasiliano", "maana ya maneno, hoja kuu, kusikiliza, na majibu", "jibu swali la ufahamu kwa kutumia ushahidi wa kifungu")),
    "Kiswahili Lugha": (("Ngeli na upatanisho wa kisarufi", "ngeli za nomino, vivumishi, vitenzi, na upatanisho", "chagua upatanisho unaolingana na nomino katika sentensi"), ("Uandishi na ufahamu wa Kiswahili", "muundo wa insha, msamiati, hoja, na ushahidi", "boresha aya kwa kutumia msamiati na mpangilio unaofaa")),
    "Literature in English": (("Poetry, imagery, and voice", "speaker, imagery, sound, form, and interpretation", "support an interpretation of a poem with a quotation"), ("Prose, drama, and character", "character, setting, conflict, dialogue, and theme", "explain how a character's choice develops a theme")),
    "Mandarin": (("Mandarin pronunciation and tones", "pinyin, tone contrasts, syllables, and listening", "distinguish tones in a familiar word pair"), ("Mandarin characters and sentence patterns", "basic characters, word order, question forms, and greetings", "build a short sentence using a familiar pattern")),
    "Marine and Fisheries Technology": (("Aquatic habitats and water quality", "salinity, oxygen, habitats, and organism needs", "interpret a water-quality observation for an aquatic habitat"), ("Fish handling and sustainable fisheries", "hygiene, preservation, stock management, and conservation", "select a safe fish-handling or sustainable harvesting practice")),
    "Mathematics": (("Fractions, multiplication, and measurement", "number facts, equal groups, fractions, and standard units", "solve a practical problem and show each calculation"), ("Geometry, patterns, and data", "shape properties, sequences, tables, and simple graphs", "identify a pattern rule or summarize data in a suitable display")),
    "Media Technology": (("Audio, image, and video production", "framing, sound capture, editing sequence, and file formats", "plan a short media product using appropriate production steps"), ("Audience, sources, and media ethics", "audience, attribution, representation, and consent", "review a media message for sourcing and audience suitability")),
    "Metalwork": (("Metal properties and marking out", "measurement, ferrous and non-ferrous metals, and layout", "select and mark a material for a supervised model"), ("Tools, joints, and workshop safety", "tool selection, joining methods, inspection, and protective practice", "identify an appropriate joint and its safety checks")),
    "Music and Dance": (("Rhythm, notation, and ensemble", "pulse, note duration, dynamics, and coordinated performance", "perform a short rhythm while keeping a steady pulse"), ("Pitch, movement, and cultural context", "pitch patterns, movement, expression, and context", "compare two movement or musical patterns and describe their differences")),
    "Physical Education": (("Fitness components and safe training", "endurance, strength, flexibility, warm-up, and recovery", "match an exercise to a fitness component and a safe warm-up"), ("Movement skills and healthy participation", "coordination, balance, teamwork, rules, and inclusion", "apply a movement skill while following rules and including others")),
    "Physics": (("Motion, forces, and energy", "speed, force, work, energy transfer, and measurement", "interpret simple motion data and explain a force effect"), ("Current, potential difference, and resistance", "circuit symbols, meter connections, Ohm's law, and safety", "use readings from a supervised circuit to relate voltage and current")),
    "Power Mechanics": (("Engines and energy transfer", "engine components, input energy, motion, and transmission", "trace the path of motion through a simple mechanical system"), ("Inspection, maintenance, and workshop safety", "routine checks, tools, hazards, and maintenance records", "select a safe inspection step for a stated mechanical symptom")),
    "Pre-Technical Studies": (("Technical drawing and design briefs", "orthographic views, dimensions, constraints, and communication", "interpret a brief and draw a dimensioned solution"), ("Materials, prototypes, and evaluation", "properties, joining, testing, and iterative improvement", "test a prototype against a stated design requirement")),
    "Science and Technology": (("Living things and material properties", "organism needs, material properties, observation, and comparison", "classify observations and select a material for a simple purpose"), ("Simple systems and design solutions", "inputs, processes, outputs, responsible design, and testing", "test a simple solution and improve it using recorded evidence")),
    "Social Studies": (("Maps, location, and community resources", "map symbols, direction, local resources, and settlement", "use a map to locate a community resource and describe access"), ("Culture, citizenship, and shared responsibility", "community diversity, rights, duties, and cooperation", "propose a respectful response to a shared community concern")),
    "Sports and Recreation": (("Game skills, rules, and tactics", "skill execution, rules, positioning, and fair play", "choose a tactic that follows the rules of a familiar game"), ("Fitness, recreation, and inclusion", "fitness, leisure, adaptation, teamwork, and safety", "adapt a recreational activity to support safe participation")),
    "Theatre and Film": (("Script, character, and dramatic structure", "scene sequence, motivation, dialogue, and conflict", "revise a scene so a character's motivation is clear"), ("Storyboards, camera, and production roles", "shot sequence, framing, sound, roles, and production safety", "order storyboard frames to communicate a coherent short scene")),
    "Woodwork": (("Timber properties and marking out", "grain, measurement, defects, layout, and material choice", "mark a measured piece while accounting for the grain"), ("Joints, finishing, and workshop safety", "joint purpose, surface preparation, finishing, and tool care", "choose a suitable joint and list its supervised safety checks")),
}

LEGACY_GAME_TOPIC_TITLES = (
    "Number patterns and problem solving",
    "Reading and communication skills",
    "Investigation and scientific evidence",
    "People, place, and evidence",
    "Elements and creative practice",
    "Tools, design, and safe practice",
)


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
    curricula = (curriculum, *SUBJECT_TOPIC_EXTENSIONS[subject.name])
    title = f"{subject.grade_level} {subject.name} Topical Study Guide"
    focus_list = ", ".join(item[0] for item in curricula)
    description = f"CBE study guide for {subject.grade_level} {subject.name}, covering {focus_list}."
    content_outline = "\n".join(
        f"Topic {index}: {focus}\nKey concept: {concept.capitalize()}.\nGuided activity: Learners {practice}."
        for index, (focus, concept, practice) in enumerate(curricula, start=1)
    )
    exercises = "\n".join(
        f"Topic {index}: explain {concept}; {practice}; record evidence and write a supported conclusion."
        for index, (_, concept, practice) in enumerate(curricula, start=1)
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

            for subject_name, grade_level, title, description, levels in CBE_GAME_CONTENT:
                subject = SubjectCatalog.objects.filter(
                    name=subject_name,
                    grade_level=grade_level,
                    is_active=True,
                ).first()
                if not subject:
                    continue
                upsert_game_topic(subject, title, description, levels)

            active_subjects = list(SubjectCatalog.objects.filter(is_active=True).select_related("docket"))
            subjects_by_category = {}
            for subject in active_subjects:
                subjects_by_category.setdefault(subject.category, {})[subject.name] = SUBJECT_CURRICULUM_CONTENT[
                    subject.name
                ]

            for subject in active_subjects:
                peers = [
                    peer_curriculum
                    for peer_name, peer_curriculum in subjects_by_category[subject.category].items()
                    if peer_name != subject.name
                ]
                curricula = (SUBJECT_CURRICULUM_CONTENT[subject.name], *SUBJECT_TOPIC_EXTENSIONS[subject.name])
                for curriculum in curricula:
                    title = f"{subject.name}: {curriculum[0]}"
                    description = (
                        f"{subject.grade_level} {subject.name}. Focus: {curriculum[0]}. "
                        f"Key idea: {curriculum[1]}."
                    )
                    upsert_game_topic(
                        subject,
                        title,
                        description,
                        generated_subject_levels(subject, curriculum, peers),
                    )

            for subject in active_subjects:
                for legacy_title in LEGACY_GAME_TOPIC_TITLES:
                    topic = GameTopic.objects.filter(
                        subject=subject,
                        title=f"{subject.name}: {legacy_title}",
                        created_by__isnull=True,
                        is_active=True,
                    ).first()
                    if topic:
                        topic.is_active = False
                        topic.save(update_fields=("is_active",))
                        topic.questions.update(is_active=False)

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