from django.core.management import call_command
from django.test import TestCase

from .models import GameQuestion, GameTopic, SubjectBook, SubjectCatalog, SubjectDocket


class CurriculumSeedTests(TestCase):
    def test_seed_populates_complete_active_cbe_catalog_idempotently(self):
        docket = SubjectDocket.objects.create(
            title="Upper Primary",
            slug="upper-primary-test",
            grade_band="upper_primary",
        )
        legacy_subject = SubjectCatalog.objects.create(
            name="Legacy Biology",
            code="LEGACY-G4",
            grade_level="Grade 4",
            docket=docket,
            category="science",
        )

        call_command("seed_school_data")

        expected_counts = {
            "Grade 2": 9,
            "Grade 3": 9,
            "Grade 4": 15,
            "Grade 5": 15,
            "Grade 6": 15,
            "Grade 7": 16,
            "Grade 8": 16,
            "Grade 9": 16,
            "Grade 10": 39,
            "Grade 11": 39,
            "Grade 12": 39,
        }
        for grade_level, expected_count in expected_counts.items():
            with self.subTest(grade_level=grade_level):
                self.assertEqual(
                    SubjectCatalog.objects.filter(grade_level=grade_level, is_active=True).count(),
                    expected_count,
                )

        self.assertFalse(SubjectCatalog.objects.get(pk=legacy_subject.pk).is_active)
        core_mathematics = SubjectCatalog.objects.get(name="Core Mathematics", grade_level="Grade 10")
        self.assertEqual(core_mathematics.pathways, ["stem"])
        essential_mathematics = SubjectCatalog.objects.get(name="Essential Mathematics", grade_level="Grade 10")
        self.assertEqual(essential_mathematics.pathways, ["social_sciences", "arts_sports_science"])
        shared_english = SubjectCatalog.objects.get(name="English", grade_level="Grade 10")
        self.assertTrue(shared_english.is_core)
        self.assertEqual(len(shared_english.pathways), 3)

        call_command("seed_school_data")
        self.assertEqual(SubjectCatalog.objects.filter(is_active=True).count(), sum(expected_counts.values()))
        active_subjects = SubjectCatalog.objects.filter(is_active=True)
        self.assertEqual(GameTopic.objects.filter(is_active=True).count(), active_subjects.count())
        self.assertEqual(GameQuestion.objects.filter(is_active=True).count(), active_subjects.count() * 6)
        self.assertEqual(
            GameTopic.objects.filter(is_active=True, subject__is_active=True)
            .values("subject_id")
            .distinct()
            .count(),
            active_subjects.count(),
        )
        guides = SubjectBook.objects.filter(title__endswith="Topical Study Guide")
        self.assertEqual(guides.count(), active_subjects.count())
        for subject in active_subjects:
            with self.subTest(guide_subject=subject.name, grade=subject.grade_level):
                guide = guides.get(subject=subject)
                self.assertIn(subject.name, guide.title)
                self.assertIn(subject.grade_level, guide.title)
                self.assertIn(subject.name, guide.description)
                self.assertTrue(guide.content_outline)
                self.assertTrue(guide.exercises)

        agriculture = active_subjects.get(name="Agriculture", grade_level="Grade 7")
        literature = active_subjects.get(name="Literature in English", grade_level="Grade 10")
        self.assertIn("crop production", guides.get(subject=agriculture).content_outline.lower())
        self.assertIn("poetry", guides.get(subject=literature).content_outline.lower())
        for topic in GameTopic.objects.filter(is_active=True):
            with self.subTest(topic=topic.title):
                self.assertEqual(topic.questions.filter(is_active=True, difficulty=1).count(), 2)
                self.assertEqual(topic.questions.filter(is_active=True, difficulty=2).count(), 2)
                self.assertEqual(topic.questions.filter(is_active=True, difficulty=3).count(), 2)
