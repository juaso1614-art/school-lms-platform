from django.db import models


class ElectricalExercise(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    voltage = models.PositiveSmallIntegerField(default=230)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("title",)

    def __str__(self):
        return self.title


class CircuitAttempt(models.Model):
    STATUS_CHOICES = [
        ("not_tested", "Not tested"),
        ("deenergized", "De-energized"),
        ("operational", "Operational"),
        ("fault", "Fault detected"),
    ]

    user = models.ForeignKey("school.User", on_delete=models.CASCADE, related_name="electrical_attempts")
    exercise = models.ForeignKey(ElectricalExercise, on_delete=models.PROTECT, related_name="attempts")
    supply_on = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="not_tested")
    diagnostics = models.JSONField(default=list, blank=True)
    score = models.PositiveSmallIntegerField(default=0)
    passed = models.BooleanField(default=False)
    elapsed_seconds = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"{self.user.email}: {self.exercise.title}"


class CircuitComponent(models.Model):
    COMPONENT_CHOICES = [
        ("supply_ac", "AC supply"),
        ("mcb", "MCB"),
        ("switch_1way", "1-way switch"),
        ("lamp", "Lamp"),
    ]

    attempt = models.ForeignKey(CircuitAttempt, on_delete=models.CASCADE, related_name="components")
    client_id = models.CharField(max_length=40)
    component_type = models.CharField(max_length=24, choices=COMPONENT_CHOICES)
    x = models.PositiveSmallIntegerField(default=0)
    y = models.PositiveSmallIntegerField(default=0)
    rotation = models.PositiveSmallIntegerField(default=0)
    is_on = models.BooleanField(default=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("attempt", "client_id"), name="uniq_electrical_component_client_id"),
        ]

    def __str__(self):
        return f"{self.get_component_type_display()} in attempt {self.attempt_id}"


class CircuitConnection(models.Model):
    WIRE_CHOICES = [
        ("live", "Live"),
        ("neutral", "Neutral"),
        ("earth", "Earth"),
    ]

    attempt = models.ForeignKey(CircuitAttempt, on_delete=models.CASCADE, related_name="connections")
    source_component = models.ForeignKey(CircuitComponent, on_delete=models.CASCADE, related_name="outgoing_connections")
    source_terminal = models.CharField(max_length=20)
    destination_component = models.ForeignKey(CircuitComponent, on_delete=models.CASCADE, related_name="incoming_connections")
    destination_terminal = models.CharField(max_length=20)
    wire_type = models.CharField(max_length=12, choices=WIRE_CHOICES)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("attempt", "source_component", "source_terminal", "destination_component", "destination_terminal"),
                name="uniq_electrical_connection_endpoints",
            ),
        ]

    def __str__(self):
        return f"{self.source_component_id}:{self.source_terminal} to {self.destination_component_id}:{self.destination_terminal}"


class ElectricalProgress(models.Model):
    user = models.ForeignKey("school.User", on_delete=models.CASCADE, related_name="electrical_progress")
    exercise = models.ForeignKey(ElectricalExercise, on_delete=models.CASCADE, related_name="learner_progress")
    attempts = models.PositiveIntegerField(default=0)
    best_score = models.PositiveSmallIntegerField(default=0)
    best_time_seconds = models.PositiveIntegerField(blank=True, null=True)
    passed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(fields=("user", "exercise"), name="uniq_electrical_progress_user_exercise"),
        ]

    def __str__(self):
        return f"{self.user.email}: {self.exercise.title}"
