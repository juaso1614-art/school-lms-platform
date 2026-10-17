import json

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from school.views import _current_user

from .models import CircuitAttempt, CircuitComponent, CircuitConnection, ElectricalExercise, ElectricalProgress
from .simulator import COMPONENTS, CircuitPayloadError, simulate_lighting_circuit


ALLOWED_ROLES = ("student", "teacher", "admin")
ELECTRICAL_PRACTICALS = (
    {"title": "Identify circuit components", "description": "Explore the supply, protective device, switch, and lamp before building a lighting circuit.", "steps": ("Add one AC supply, one MCB, one 1-way switch, and one lamp.", "Select each component and inspect its terminals.", "Name the role of each component in the circuit.")},
    {"title": "Build a one-way lighting circuit", "description": "Connect the components to make a controlled lighting circuit and test the result.", "steps": ("Add the supply, MCB, switch, and lamp.", "Connect matching live, neutral, and earth terminals as shown by the simulator.", "Close the switch, turn on the supply, and run a circuit test.")},
    {"title": "Switch operation investigation", "description": "Observe how opening and closing the switch changes the simulated circuit state.", "steps": ("Build and test the one-way lighting circuit.", "Toggle the switch open and test the circuit.", "Close the switch and compare the diagnostic and lamp state.")},
    {"title": "Protective device check", "description": "Investigate the MCB's position and state in the simulated lighting circuit.", "steps": ("Build the circuit with the MCB between the supply and switched load.", "Test with the MCB off, then on.", "Explain how the protective device affects the circuit path.")},
    {"title": "Fault finding and commissioning", "description": "Use simulator diagnostics to identify a wiring or switching problem before commissioning.", "steps": ("Build the circuit and test it before energizing.", "Introduce an open switch or incorrect connection and inspect diagnostics.", "Correct the issue, retest, and confirm the expected lamp state.")},
)


def _active_user(request):
    user = _current_user(request)
    if not user or user.role not in ALLOWED_ROLES:
        return None
    return user


def lab_home(request):
    user = _active_user(request)
    if not user:
        return redirect("login")

    exercise = get_object_or_404(ElectricalExercise, slug="one-way-lighting", is_active=True)
    progress = ElectricalProgress.objects.filter(user=user, exercise=exercise).first()
    attempt = (
        CircuitAttempt.objects.filter(user=user, exercise=exercise)
        .prefetch_related("components", "connections")
        .first()
    )
    components = []
    connections = []
    if attempt:
        components = [
            {
                "id": component.client_id,
                "type": component.component_type,
                "x": component.x,
                "y": component.y,
                "rotation": component.rotation,
                "is_on": component.is_on,
                "is_closed": component.is_closed,
            }
            for component in attempt.components.all()
        ]
        connections = [
            {
                "from_component": wire.source_component.client_id,
                "from_terminal": wire.source_terminal,
                "to_component": wire.destination_component.client_id,
                "to_terminal": wire.destination_terminal,
                "wire_type": wire.wire_type,
            }
            for wire in attempt.connections.select_related("source_component", "destination_component")
        ]

    return render(
        request,
        "electrical_lab.html",
        {
            "exercise": exercise,
            "practicals": ELECTRICAL_PRACTICALS,
            "progress": progress,
            "attempt": attempt,
            "initial_result": {
                "status": attempt.status,
                "lamp_energized": attempt.status == "operational" and attempt.supply_on,
                "voltage": exercise.voltage if attempt.status == "operational" and attempt.supply_on else 0,
                "diagnostics": attempt.diagnostics,
            } if attempt else {},
            "component_specs": {
                component_type: {
                    "label": specification["label"],
                    "terminals": specification["terminals"],
                }
                for component_type, specification in COMPONENTS.items()
            },
            "initial_circuit": {
                "components": components,
                "connections": connections,
                "supply_on": attempt.supply_on if attempt else False,
            },
        },
    )


@require_POST
def simulate_circuit(request):
    user = _active_user(request)
    if not user:
        return JsonResponse({"error": "Sign in as a student or staff member to run this exercise."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Circuit data must be valid JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Circuit data must be an object."}, status=400)

    attempt_id = payload.pop("attempt_id", None)
    exercise = get_object_or_404(ElectricalExercise, slug="one-way-lighting", is_active=True)
    try:
        if attempt_id is not None:
            attempt = get_object_or_404(CircuitAttempt, pk=int(attempt_id), user=user, exercise=exercise)
            is_new_attempt = False
        else:
            attempt = None
            is_new_attempt = True
    except (TypeError, ValueError):
        return JsonResponse({"error": "Attempt identifier is invalid."}, status=400)

    try:
        result = simulate_lighting_circuit(payload)
    except CircuitPayloadError as error:
        return JsonResponse({"error": str(error)}, status=400)

    with transaction.atomic():
        if is_new_attempt:
            attempt = CircuitAttempt.objects.create(user=user, exercise=exercise)
        attempt.components.all().delete()
        components_by_client_id = {}
        for component_data in result["components"]:
            component = CircuitComponent.objects.create(
                attempt=attempt,
                client_id=component_data["id"],
                component_type=component_data["type"],
                x=component_data["x"],
                y=component_data["y"],
                rotation=component_data["rotation"],
                is_on=component_data["is_on"],
                is_closed=component_data["is_closed"],
            )
            components_by_client_id[component.client_id] = component
        for wire_data in result["connections"]:
            CircuitConnection.objects.create(
                attempt=attempt,
                source_component=components_by_client_id[wire_data["from_component"]],
                source_terminal=wire_data["from_terminal"],
                destination_component=components_by_client_id[wire_data["to_component"]],
                destination_terminal=wire_data["to_terminal"],
                wire_type=wire_data["wire_type"],
            )

        attempt.supply_on = result["supply_on"]
        attempt.status = result["status"]
        attempt.diagnostics = result["diagnostics"]
        attempt.score = result["score"]
        attempt.passed = result["passed"]
        attempt.elapsed_seconds = max(int((timezone.now() - attempt.started_at).total_seconds()), 0)
        if attempt.passed and attempt.completed_at is None:
            attempt.completed_at = timezone.now()
        attempt.save()

        progress, _ = ElectricalProgress.objects.get_or_create(user=user, exercise=exercise)
        if is_new_attempt:
            progress.attempts += 1
        progress.best_score = max(progress.best_score, attempt.score)
        progress.passed = progress.passed or attempt.passed
        if attempt.passed and (
            progress.best_time_seconds is None or attempt.elapsed_seconds < progress.best_time_seconds
        ):
            progress.best_time_seconds = attempt.elapsed_seconds
        progress.save()

    result.update({"attempt_id": attempt.pk, "elapsed_seconds": attempt.elapsed_seconds})
    return JsonResponse(result)
