import re


COMPONENTS = {
    "supply_ac": {
        "label": "AC supply",
        "terminals": {"L": "live", "N": "neutral", "PE": "earth"},
    },
    "mcb": {
        "label": "MCB",
        "terminals": {"LINE_L": "live", "LOAD_L": "live"},
    },
    "switch_1way": {
        "label": "1-way switch",
        "terminals": {"COM": "live", "L1": "live", "L2": "live"},
    },
    "lamp": {
        "label": "Lamp",
        "terminals": {"L": "live", "N": "neutral", "PE": "earth"},
    },
}

REQUIRED_COMPONENTS = ("supply_ac", "mcb", "switch_1way", "lamp")
MAX_COMPONENTS = 8
MAX_CONNECTIONS = 20


class CircuitPayloadError(ValueError):
    pass


def _validated_payload(payload):
    if not isinstance(payload, dict):
        raise CircuitPayloadError("Circuit data must be an object.")
    components = payload.get("components")
    connections = payload.get("connections")
    supply_on = payload.get("supply_on", False)
    if not isinstance(components, list) or not isinstance(connections, list):
        raise CircuitPayloadError("Circuit data must include component and connection lists.")
    if len(components) > MAX_COMPONENTS or len(connections) > MAX_CONNECTIONS:
        raise CircuitPayloadError("This exercise has reached its component or wire limit.")
    if not isinstance(supply_on, bool):
        raise CircuitPayloadError("Supply state must be on or off.")

    component_map = {}
    normalized_components = []
    for component in components:
        if not isinstance(component, dict):
            raise CircuitPayloadError("A component entry is invalid.")
        client_id = component.get("id")
        component_type = component.get("type")
        if not isinstance(client_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", client_id):
            raise CircuitPayloadError("A component has an invalid identifier.")
        if client_id in component_map:
            raise CircuitPayloadError("Component identifiers must be unique.")
        if not isinstance(component_type, str) or component_type not in COMPONENTS:
            raise CircuitPayloadError("This exercise only supports AC supply, MCB, 1-way switch, and lamp components.")
        try:
            x = int(component.get("x", 0))
            y = int(component.get("y", 0))
            rotation = int(component.get("rotation", 0)) % 360
        except (TypeError, ValueError):
            raise CircuitPayloadError("Component position and rotation must be numbers.") from None
        if not 0 <= x <= 1000 or not 0 <= y <= 600:
            raise CircuitPayloadError("A component must stay inside the work area.")
        if rotation not in (0, 90, 180, 270):
            raise CircuitPayloadError("Components can rotate in 90-degree steps.")
        normalized = {
            "id": client_id,
            "type": component_type,
            "x": x,
            "y": y,
            "rotation": rotation,
            "is_on": component.get("is_on", True) is True,
            "is_closed": component.get("is_closed", False) is True,
        }
        component_map[client_id] = normalized
        normalized_components.append(normalized)

    normalized_connections = []
    for connection in connections:
        if not isinstance(connection, dict):
            raise CircuitPayloadError("A wire entry is invalid.")
        source_id = connection.get("from_component")
        destination_id = connection.get("to_component")
        source_terminal = connection.get("from_terminal")
        destination_terminal = connection.get("to_terminal")
        wire_type = connection.get("wire_type")
        if (
            not isinstance(source_id, str)
            or not isinstance(destination_id, str)
            or source_id not in component_map
            or destination_id not in component_map
            or source_id == destination_id
            or not isinstance(source_terminal, str)
            or not isinstance(destination_terminal, str)
        ):
            raise CircuitPayloadError("Every wire must connect terminals on two different placed components.")
        source_schema = COMPONENTS[component_map[source_id]["type"]]["terminals"]
        destination_schema = COMPONENTS[component_map[destination_id]["type"]]["terminals"]
        if source_terminal not in source_schema or destination_terminal not in destination_schema:
            raise CircuitPayloadError("A wire refers to a terminal that does not exist on that component.")
        if wire_type not in ("live", "neutral", "earth"):
            raise CircuitPayloadError("Choose Live, Neutral, or Earth for each wire.")
        normalized_connections.append({
            "from_component": source_id,
            "from_terminal": source_terminal,
            "to_component": destination_id,
            "to_terminal": destination_terminal,
            "wire_type": wire_type,
        })

    return normalized_components, normalized_connections, component_map, supply_on


def _has_path(adjacency, start, finish):
    if start not in adjacency or finish not in adjacency:
        return False
    pending = [start]
    visited = {start}
    while pending:
        node = pending.pop()
        if node == finish:
            return True
        for neighbor in adjacency.get(node, ()):
            if neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return False


def simulate_lighting_circuit(payload):
    components, connections, component_map, supply_on = _validated_payload(payload)
    diagnostics = []
    blocking_fault = False
    by_type = {}
    for component in components:
        by_type.setdefault(component["type"], []).append(component)
    for component_type in REQUIRED_COMPONENTS:
        found = len(by_type.get(component_type, ()))
        if found == 0:
            diagnostics.append(f"{COMPONENTS[component_type]['label']} missing.")
            blocking_fault = True
        elif found > 1:
            diagnostics.append(f"Use one {COMPONENTS[component_type]['label'].lower()} in this exercise.")
            blocking_fault = True

    used_terminals = set()
    connection_keys = set()
    valid_wires = []
    short_circuit = False
    for wire in connections:
        source_key = (wire["from_component"], wire["from_terminal"])
        destination_key = (wire["to_component"], wire["to_terminal"])
        unordered_key = tuple(sorted((source_key, destination_key)))
        if unordered_key in connection_keys:
            diagnostics.append("Duplicate wire detected. Remove the extra connection.")
            blocking_fault = True
            continue
        connection_keys.add(unordered_key)
        source_domain = COMPONENTS[component_map[source_key[0]]["type"]]["terminals"][source_key[1]]
        destination_domain = COMPONENTS[component_map[destination_key[0]]["type"]]["terminals"][destination_key[1]]
        if source_domain != destination_domain:
            if {source_domain, destination_domain} == {"live", "neutral"}:
                diagnostics.append("Short circuit detected: live is connected directly to neutral.")
                short_circuit = True
            elif {source_domain, destination_domain} == {"live", "earth"}:
                diagnostics.append("Short circuit detected: live is connected directly to earth.")
                short_circuit = True
            else:
                diagnostics.append("Incorrect neutral and earth connection. Match each wire to its terminal type.")
            blocking_fault = True
            continue
        if wire["wire_type"] != source_domain:
            diagnostics.append(f"Incorrect {wire['wire_type']} wire on a {source_domain} terminal.")
            blocking_fault = True
            continue
        if source_key in used_terminals or destination_key in used_terminals:
            diagnostics.append("A terminal has more than one wire. Check for a loose or crossed connection.")
            blocking_fault = True
            continue
        used_terminals.update((source_key, destination_key))
        valid_wires.append((source_key, destination_key, source_domain))

    terminal_graph = {domain: {} for domain in ("live", "neutral", "earth")}
    for source, destination, domain in valid_wires:
        graph = terminal_graph[domain]
        graph.setdefault(source, set()).add(destination)
        graph.setdefault(destination, set()).add(source)

    mcb = by_type.get("mcb", [None])[0]
    if mcb and mcb["is_on"]:
        graph = terminal_graph["live"]
        line = (mcb["id"], "LINE_L")
        load = (mcb["id"], "LOAD_L")
        graph.setdefault(line, set()).add(load)
        graph.setdefault(load, set()).add(line)
    switch = by_type.get("switch_1way", [None])[0]
    if switch and switch["is_closed"]:
        graph = terminal_graph["live"]
        common = (switch["id"], "COM")
        switched = (switch["id"], "L1")
        graph.setdefault(common, set()).add(switched)
        graph.setdefault(switched, set()).add(common)

    supply = by_type.get("supply_ac", [None])[0]
    lamp = by_type.get("lamp", [None])[0]
    topology_ready = False
    if supply and lamp:
        live_ready = _has_path(terminal_graph["live"], (supply["id"], "L"), (lamp["id"], "L"))
        neutral_ready = _has_path(terminal_graph["neutral"], (supply["id"], "N"), (lamp["id"], "N"))
        earth_ready = _has_path(terminal_graph["earth"], (supply["id"], "PE"), (lamp["id"], "PE"))
        topology_ready = live_ready and neutral_ready and earth_ready and not short_circuit and not blocking_fault
        if not live_ready:
            if mcb and not mcb["is_on"]:
                diagnostics.append("MCB is OFF. Switch it on after checking the circuit.")
            elif switch and not switch["is_closed"]:
                diagnostics.append("Switch is open. Close it to complete the live path.")
            else:
                diagnostics.append("Open circuit detected on the live path from supply to lamp.")
        if not neutral_ready:
            diagnostics.append("Neutral missing: connect supply N to lamp N.")
        if not earth_ready:
            diagnostics.append("Earth connection missing: connect supply PE to lamp PE.")

    if short_circuit:
        status = "fault"
        passed = False
        score = 0
        lamp_energized = False
    elif not supply_on:
        status = "deenergized"
        passed = False
        score = 0
        lamp_energized = False
        if topology_ready:
            diagnostics.append("Circuit checks passed. Turn the supply ON to test operation.")
        else:
            diagnostics.append("Supply is OFF. Complete the wiring checks before energizing the circuit.")
    elif topology_ready:
        status = "operational"
        passed = True
        score = 100
        lamp_energized = True
        diagnostics.append("Circuit operational. The lamp is receiving live, neutral, and earth connections.")
    else:
        status = "fault"
        passed = False
        score = 0
        lamp_energized = False

    return {
        "components": components,
        "connections": connections,
        "supply_on": supply_on,
        "status": status,
        "passed": passed,
        "score": score,
        "lamp_energized": lamp_energized,
        "voltage": 230 if lamp_energized else 0,
        "diagnostics": diagnostics,
    }
