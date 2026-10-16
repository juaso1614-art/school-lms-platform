(() => {
  const board = document.querySelector("#circuit-board");
  if (!(board instanceof SVGSVGElement)) return;

  const wiresGroup = document.querySelector("#circuit-wires");
  const componentsGroup = document.querySelector("#circuit-components");
  const componentSpecs = JSON.parse(document.querySelector("#component-specs").textContent);
  const initialCircuit = JSON.parse(document.querySelector("#initial-circuit").textContent);
  const diagnostics = document.querySelector("#electrical-diagnostics");
  const attemptIdNode = document.querySelector("#electrical-attempt-id");
  const csrfToken = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("csrftoken="))?.split("=")[1] || "";
  const terminalPositions = {
    supply_ac: { L: [54, 25], N: [54, 48], PE: [54, 71] },
    mcb: { LINE_L: [-52, 31], LOAD_L: [52, 31] },
    switch_1way: { COM: [-52, 31], L1: [52, 20], L2: [52, 48] },
    lamp: { L: [-52, 31], N: [52, 20], PE: [52, 48] },
  };
  const wireColors = { live: "#c3483e", neutral: "#395a83", earth: "#27835b" };
  const components = initialCircuit.components || [];
  const connections = initialCircuit.connections || [];
  let attemptId = attemptIdNode?.value || "";
  let supplyOn = initialCircuit.supply_on === true;
  let selectedComponentId = null;
  let pendingTerminal = null;
  let dragging = null;
  let lastSimulation = null;
  let generatedId = 0;

  const element = (name, attributes = {}, text = "") => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text) node.textContent = text;
    return node;
  };

  function getComponent(clientId) {
    return components.find((component) => component.id === clientId);
  }

  function terminalWorldPosition(component, terminalName) {
    const [localX, localY] = terminalPositions[component.type][terminalName];
    const angle = component.rotation * Math.PI / 180;
    return {
      x: component.x + localX * Math.cos(angle) - localY * Math.sin(angle),
      y: component.y + localX * Math.sin(angle) + localY * Math.cos(angle),
    };
  }

  function makeWirePath(connection) {
    const source = getComponent(connection.from_component);
    const destination = getComponent(connection.to_component);
    if (!source || !destination) return null;
    const start = terminalWorldPosition(source, connection.from_terminal);
    const end = terminalWorldPosition(destination, connection.to_terminal);
    const middleX = (start.x + end.x) / 2;
    return `M ${start.x} ${start.y} H ${middleX} V ${end.y} H ${end.x}`;
  }

  function componentShape(component) {
    const group = element("g", {
      class: `circuit-component${component.id === selectedComponentId ? " is-selected" : ""}${lastSimulation?.lamp_energized && component.type === "lamp" ? " is-energized" : ""}`,
      transform: `translate(${component.x} ${component.y}) rotate(${component.rotation})`,
      "data-component-id": component.id,
      tabindex: 0,
    });
    const shell = element("rect", { x: -48, y: 0, width: 96, height: 96, rx: 8, class: "component-shell" });
    group.append(shell);

    if (component.type === "supply_ac") {
      group.append(element("circle", { cx: 0, cy: 30, r: 17, class: "component-symbol" }));
      group.append(element("path", { d: "M -10 30 C -6 19 0 41 5 30 S 14 20 16 30", class: "component-mark" }));
      group.append(element("text", { x: 0, y: 66, class: "component-label" }, "230V AC"));
    } else if (component.type === "mcb") {
      group.append(element("rect", { x: -25, y: 17, width: 50, height: 30, rx: 4, class: "component-symbol" }));
      group.append(element("path", { d: "M -13 39 L 9 24", class: "component-mark" }));
      group.append(element("text", { x: 0, y: 66, class: "component-label" }, component.is_on ? "MCB · ON" : "MCB · OFF"));
    } else if (component.type === "switch_1way") {
      group.append(element("circle", { cx: -18, cy: 32, r: 4, class: "component-mark" }));
      group.append(element("circle", { cx: 18, cy: 32, r: 4, class: "component-mark" }));
      group.append(element("path", { d: component.is_closed ? "M -18 32 H 18" : "M -18 32 L 12 15", class: "component-mark" }));
      group.append(element("text", { x: 0, y: 66, class: "component-label" }, component.is_closed ? "SWITCH · CLOSED" : "SWITCH · OPEN"));
    } else {
      group.append(element("circle", { cx: 0, cy: 32, r: 20, class: "lamp-glass" }));
      group.append(element("path", { d: "M -10 22 L 10 42 M 10 22 L -10 42", class: "component-mark" }));
      group.append(element("text", { x: 0, y: 66, class: "component-label" }, "LAMP"));
    }

    for (const [terminalName, [terminalX, terminalY]] of Object.entries(terminalPositions[component.type])) {
      const terminalType = componentSpecs[component.type].terminals[terminalName];
      const terminal = element("circle", {
        cx: terminalX,
        cy: terminalY,
        r: 7,
        class: `circuit-terminal terminal-${terminalType}${pendingTerminal?.component_id === component.id && pendingTerminal.terminal === terminalName ? " is-pending" : ""}`,
        "data-component-id": component.id,
        "data-terminal": terminalName,
        "data-wire-type": terminalType,
      });
      const title = element("title", {}, terminalName);
      terminal.append(title);
      group.append(terminal);
      group.append(element("text", {
        x: terminalX,
        y: terminalY + (terminalY < 32 ? -11 : 18),
        class: "terminal-label",
      }, terminalName));
    }
    return group;
  }

  function renderBoard() {
    wiresGroup.replaceChildren();
    connections.forEach((connection) => {
      const path = makeWirePath(connection);
      if (!path) return;
      wiresGroup.append(element("path", {
        d: path,
        class: `circuit-wire wire-${connection.wire_type}`,
        "data-connection-id": connection.id,
      }));
    });
    componentsGroup.replaceChildren(...components.map(componentShape));
    document.querySelector("#wire-count").textContent = String(connections.length);
    document.querySelector("#electrical-state").textContent = lastSimulation?.status === "operational"
      ? "Circuit operational"
      : supplyOn ? "Supply ON · test required" : "De-energized";
    document.querySelector("#power-toggle").textContent = supplyOn ? "Supply ON" : "Supply OFF";
    document.querySelector("#power-toggle").setAttribute("aria-pressed", String(supplyOn));
    document.querySelector("#lamp-indicator").classList.toggle("is-lit", lastSimulation?.lamp_energized === true);
    document.querySelector("#lamp-state").textContent = lastSimulation?.lamp_energized ? "Lamp on" : "Lamp off";
    document.querySelector("#voltage-reading").textContent = `${lastSimulation?.voltage || 0} V`;
    updateInspector();
  }

  function updateInspector() {
    const selected = getComponent(selectedComponentId);
    const name = document.querySelector("#selected-component-name");
    const detail = document.querySelector("#selected-component-detail");
    const deleteButton = document.querySelector("#delete-component");
    const rotateButton = document.querySelector("#rotate-component");
    const toggleButton = document.querySelector("#toggle-device");
    if (!selected) {
      name.textContent = "None";
      detail.textContent = "Select a component on the board to inspect it.";
      deleteButton.disabled = true;
      rotateButton.disabled = true;
      toggleButton.disabled = true;
      return;
    }
    name.textContent = componentSpecs[selected.type].label;
    detail.textContent = Object.keys(componentSpecs[selected.type].terminals).join(" · ");
    deleteButton.disabled = false;
    rotateButton.disabled = false;
    toggleButton.disabled = !["mcb", "switch_1way"].includes(selected.type);
    toggleButton.textContent = selected.type === "switch_1way"
      ? selected.is_closed ? "Open switch" : "Close switch"
      : selected.is_on ? "Turn MCB off" : "Turn MCB on";
  }

  function showDiagnostics(items) {
    diagnostics.replaceChildren();
    if (!items?.length) {
      diagnostics.append(element("p", {}, "No simulation results yet. Select Test circuit to inspect your wiring."));
      return;
    }
    const list = element("ul", { class: "electrical-diagnostic-list" });
    items.forEach((item) => list.append(element("li", {}, item)));
    diagnostics.append(list);
  }

  function addComponent(type) {
    if (components.filter((component) => component.type === type).length >= 1) {
      showDiagnostics([`This Phase 1 exercise uses one ${componentSpecs[type].label.toLowerCase()}.`]);
      return;
    }
    const defaults = { supply_ac: [110, 170], mcb: [310, 170], switch_1way: [515, 170], lamp: [715, 170] };
    const [x, y] = defaults[type] || [150 + (generatedId % 4) * 150, 280];
    generatedId += 1;
    components.push({
      id: `component-${Date.now()}-${generatedId}`,
      type,
      x,
      y,
      rotation: 0,
      is_on: true,
      is_closed: false,
    });
    selectedComponentId = components.at(-1).id;
    lastSimulation = null;
    renderBoard();
  }

  function terminalClicked(target) {
    const endpoint = {
      component_id: target.dataset.componentId,
      terminal: target.dataset.terminal,
      wire_type: target.dataset.wireType,
    };
    if (!pendingTerminal) {
      pendingTerminal = endpoint;
      document.querySelector("#board-hint").textContent = `Now select a ${endpoint.wire_type} terminal to finish the wire.`;
      renderBoard();
      return;
    }
    if (pendingTerminal.component_id === endpoint.component_id && pendingTerminal.terminal === endpoint.terminal) {
      pendingTerminal = null;
      renderBoard();
      return;
    }
    if (pendingTerminal.wire_type !== endpoint.wire_type) {
      showDiagnostics([`That wire joins ${pendingTerminal.wire_type} to ${endpoint.wire_type}. Check the terminal labels and try again.`]);
      return;
    }
    const duplicate = connections.some((connection) => (
      (connection.from_component === pendingTerminal.component_id && connection.from_terminal === pendingTerminal.terminal)
      || (connection.to_component === pendingTerminal.component_id && connection.to_terminal === pendingTerminal.terminal)
      || (connection.from_component === endpoint.component_id && connection.from_terminal === endpoint.terminal)
      || (connection.to_component === endpoint.component_id && connection.to_terminal === endpoint.terminal)
    ));
    if (duplicate) {
      showDiagnostics(["A terminal can only hold one wire. Remove or move the existing connection first."]);
      pendingTerminal = null;
      renderBoard();
      return;
    }
    connections.push({
      id: `wire-${Date.now()}-${connections.length}`,
      from_component: pendingTerminal.component_id,
      from_terminal: pendingTerminal.terminal,
      to_component: endpoint.component_id,
      to_terminal: endpoint.terminal,
      wire_type: endpoint.wire_type,
    });
    pendingTerminal = null;
    lastSimulation = null;
    document.querySelector("#board-hint").textContent = "Wire connected. Continue wiring, then run Test circuit.";
    renderBoard();
  }

  function svgPoint(event) {
    const point = board.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(board.getScreenCTM().inverse());
  }

  board.addEventListener("pointerdown", (event) => {
    const terminal = event.target.closest(".circuit-terminal");
    if (terminal) {
      event.stopPropagation();
      terminalClicked(terminal);
      return;
    }
    const group = event.target.closest(".circuit-component");
    if (!group) {
      selectedComponentId = null;
      pendingTerminal = null;
      renderBoard();
      return;
    }
    const component = getComponent(group.dataset.componentId);
    selectedComponentId = component.id;
    const point = svgPoint(event);
    dragging = { id: component.id, x: point.x - component.x, y: point.y - component.y };
    board.setPointerCapture(event.pointerId);
    componentsGroup.querySelectorAll(".circuit-component").forEach((item) => item.classList.remove("is-selected"));
    group.classList.add("is-selected");
    updateInspector();
  });

  board.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const component = getComponent(dragging.id);
    const point = svgPoint(event);
    component.x = Math.max(55, Math.min(845, Math.round(point.x - dragging.x)));
    component.y = Math.max(45, Math.min(455, Math.round(point.y - dragging.y)));
    lastSimulation = null;
    renderBoard();
  });

  board.addEventListener("pointerup", () => { dragging = null; });
  board.addEventListener("pointercancel", () => { dragging = null; });
  board.addEventListener("keydown", (event) => {
    if (!selectedComponentId || !["Delete", "Backspace"].includes(event.key)) return;
    event.preventDefault();
    removeSelectedComponent();
  });

  function removeSelectedComponent() {
    if (!selectedComponentId) return;
    const removedId = selectedComponentId;
    const removedConnections = connections.filter((connection) => (
      connection.from_component === removedId || connection.to_component === removedId
    ));
    removedConnections.forEach((connection) => connections.splice(connections.indexOf(connection), 1));
    components.splice(components.findIndex((component) => component.id === removedId), 1);
    selectedComponentId = null;
    pendingTerminal = null;
    lastSimulation = null;
    renderBoard();
  }

  document.querySelectorAll("[data-add-component]").forEach((button) => {
    button.addEventListener("click", () => addComponent(button.dataset.addComponent));
  });
  document.querySelector("#rotate-component").addEventListener("click", () => {
    const component = getComponent(selectedComponentId);
    if (!component) return;
    component.rotation = (component.rotation + 90) % 360;
    lastSimulation = null;
    renderBoard();
  });
  document.querySelector("#delete-component").addEventListener("click", removeSelectedComponent);
  document.querySelector("#toggle-device").addEventListener("click", () => {
    const component = getComponent(selectedComponentId);
    if (!component) return;
    if (component.type === "switch_1way") component.is_closed = !component.is_closed;
    if (component.type === "mcb") component.is_on = !component.is_on;
    lastSimulation = null;
    renderBoard();
  });
  document.querySelector("#power-toggle").addEventListener("click", () => {
    supplyOn = !supplyOn;
    lastSimulation = null;
    renderBoard();
  });
  document.querySelector("#reset-circuit").addEventListener("click", () => {
    components.splice(0);
    connections.splice(0);
    attemptId = "";
    supplyOn = false;
    selectedComponentId = null;
    pendingTerminal = null;
    lastSimulation = null;
    showDiagnostics([]);
    renderBoard();
  });
  document.querySelector("#test-circuit").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = "Testing...";
    try {
      const response = await fetch("/electrical-lab/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ attempt_id: attemptId || null, supply_on: supplyOn, components, connections }),
      });
      const result = await response.json();
      if (!response.ok) {
        showDiagnostics([result.error || "Circuit test could not be completed."]);
        return;
      }
      attemptId = String(result.attempt_id);
      lastSimulation = result;
      showDiagnostics(result.diagnostics);
      document.querySelector("#board-hint").textContent = result.passed
        ? "Passed. Your circuit is operational."
        : "Review the diagnostic and inspect the named terminals.";
      renderBoard();
    } catch (error) {
      showDiagnostics(["Could not contact the simulator. Check your connection and try again."]);
      console.error("Electrical simulation request failed.", error);
    } finally {
      button.disabled = false;
      button.textContent = "Test circuit";
    }
  });

  if (attemptId) {
    const existingAttempt = document.querySelector("#initial-attempt-result");
    if (existingAttempt?.textContent) {
      try {
        lastSimulation = JSON.parse(existingAttempt.textContent);
        showDiagnostics(lastSimulation.diagnostics);
      } catch {
        lastSimulation = null;
      }
    }
  }
  if (!lastSimulation) showDiagnostics([]);
  renderBoard();
})();
