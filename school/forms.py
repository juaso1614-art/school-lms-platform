from django import forms

from .models import GameQuestion, GameTopic, SchoolStaffProfile, SubjectCatalog, User


class CreateAccountForm(forms.Form):
    first_name = forms.CharField(max_length=100, strip=True)
    last_name = forms.CharField(max_length=100, strip=True)
    email = forms.EmailField(max_length=254)
    password = forms.CharField(
        min_length=8,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="Confirm password",
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already exists with this email.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data


class SchoolStaffProfileForm(forms.ModelForm):
    class Meta:
        model = SchoolStaffProfile
        fields = (
            "role",
            "full_name",
            "email",
            "phone",
            "department",
            "campus",
            "staff_id",
        )


class GameTopicForm(forms.ModelForm):
    class Meta:
        model = GameTopic
        fields = ("subject", "title", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = SubjectCatalog.objects.filter(is_active=True).select_related("docket")


class GameQuestionForm(forms.Form):
    topic = forms.ModelChoiceField(queryset=GameTopic.objects.none())
    difficulty = forms.TypedChoiceField(choices=GameQuestion.DIFFICULTY_CHOICES, coerce=int)
    prompt = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=1200)
    option_a = forms.CharField(max_length=240, label="Option A")
    option_b = forms.CharField(max_length=240, label="Option B")
    option_c = forms.CharField(max_length=240, label="Option C")
    option_d = forms.CharField(max_length=240, label="Option D")
    correct_choice = forms.TypedChoiceField(
        choices=((0, "A"), (1, "B"), (2, "C"), (3, "D")),
        coerce=int,
        label="Correct answer",
    )
    explanation = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, topics=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topic"].queryset = topics if topics is not None else GameTopic.objects.filter(is_active=True)

    def save(self):
        topic = self.cleaned_data["topic"]
        difficulty = self.cleaned_data["difficulty"]
        return GameQuestion.objects.create(
            topic=topic,
            difficulty=difficulty,
            order=topic.questions.filter(difficulty=difficulty).count(),
            prompt=self.cleaned_data["prompt"],
            choices=[
                self.cleaned_data["option_a"],
                self.cleaned_data["option_b"],
                self.cleaned_data["option_c"],
                self.cleaned_data["option_d"],
            ],
            correct_choice=self.cleaned_data["correct_choice"],
            explanation=self.cleaned_data["explanation"],
        )
