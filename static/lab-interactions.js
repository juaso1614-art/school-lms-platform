/* Shared helpers for the interactive 3D labs: drag-to-assemble parts and click-to-inspect. */
(() => {
  const DRAG_THRESHOLD_PX = 6;

  /**
   * Drag-and-drop (pointer based, touch friendly) assembly challenge.
   * Chips are dragged (or tapped) onto the drop zone in the required order.
   */
  function initAssembly({ partsHost, dropZone, statusEl, order, onPlace, onAllPlaced }) {
    if (!(partsHost instanceof HTMLElement) || !(dropZone instanceof HTMLElement)) return null;

    let isActive = false;
    let placedCount = 0;
    let dragState = null;

    const setStatus = (message) => {
      if (statusEl) statusEl.textContent = message;
    };

    const isOverDropZone = (event) => {
      const bounds = dropZone.getBoundingClientRect();
      return (
        event.clientX >= bounds.left &&
        event.clientX <= bounds.right &&
        event.clientY >= bounds.top &&
        event.clientY <= bounds.bottom
      );
    };

    const attemptPlace = (name) => {
      const expected = order[placedCount];
      if (name !== expected) {
        setStatus(`Not yet — place ${expected} first.`);
        return;
      }
      const chip = partsHost.querySelector(`[data-part="${CSS.escape(name)}"]`);
      chip?.remove();
      placedCount += 1;
      dropZone.classList.add("is-hovered");
      window.setTimeout(() => dropZone.classList.remove("is-hovered"), 350);
      onPlace?.(name);
      if (placedCount === order.length) {
        dropZone.classList.add("is-complete");
        setStatus("Setup assembled correctly. Dismantle it to try again.");
        onAllPlaced?.();
      } else {
        setStatus(`${placedCount} of ${order.length} parts placed. Next: ${order[placedCount]}.`);
      }
    };

    const buildChips = () => {
      partsHost.replaceChildren();
      order.slice().reverse().forEach((name) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "assembly-part";
        chip.dataset.part = name;
        chip.textContent = name;
        chip.addEventListener("pointerdown", (event) => {
          if (!isActive || placedCount >= order.length) return;
          event.preventDefault();
          dragState = {
            name,
            chip,
            startX: event.clientX,
            startY: event.clientY,
            moved: false,
            ghost: null,
            pointerId: event.pointerId,
          };
          chip.setPointerCapture?.(event.pointerId);
        });
        partsHost.appendChild(chip);
      });
    };

    const endDrag = (event) => {
      if (!dragState || event.pointerId !== dragState.pointerId) return;
      const state = dragState;
      dragState = null;
      state.chip.releasePointerCapture?.(event.pointerId);
      state.ghost?.remove();
      state.chip.classList.remove("is-dragging");
      dropZone.classList.remove("is-hovered");
      if (!state.moved) {
        attemptPlace(state.name);
        return;
      }
      if (isOverDropZone(event)) {
        attemptPlace(state.name);
      } else {
        setStatus(`Drop ${state.name} onto the assembly bench.`);
      }
    };

    document.addEventListener("pointermove", (event) => {
      if (!dragState || event.pointerId !== dragState.pointerId) return;
      const dx = event.clientX - dragState.startX;
      const dy = event.clientY - dragState.startY;
      if (!dragState.moved && dx * dx + dy * dy > DRAG_THRESHOLD_PX * DRAG_THRESHOLD_PX) {
        dragState.moved = true;
        dragState.ghost = document.createElement("div");
        dragState.ghost.className = "assembly-ghost";
        dragState.ghost.textContent = dragState.name;
        document.body.appendChild(dragState.ghost);
        dragState.chip.classList.add("is-dragging");
      }
      if (dragState.ghost) {
        dragState.ghost.style.left = `${event.clientX}px`;
        dragState.ghost.style.top = `${event.clientY}px`;
        dropZone.classList.toggle("is-hovered", isOverDropZone(event));
      }
    });
    document.addEventListener("pointerup", endDrag);
    document.addEventListener("pointercancel", endDrag);

    return {
      get active() {
        return isActive;
      },
      enter() {
        isActive = true;
        placedCount = 0;
        dropZone.classList.remove("is-complete", "is-hovered");
        dropZone.hidden = false;
        partsHost.hidden = false;
        buildChips();
        setStatus(`Setup dismantled. Drag or tap ${order[0]} to begin.`);
      },
      leave() {
        isActive = false;
        placedCount = 0;
        if (dragState) {
          dragState.ghost?.remove();
          dragState.chip.classList.remove("is-dragging");
          dragState = null;
        }
        partsHost.replaceChildren();
        partsHost.hidden = true;
        dropZone.classList.remove("is-complete", "is-hovered");
      },
      toggle() {
        if (isActive) {
          this.leave();
          return false;
        }
        this.enter();
        return true;
      },
    };
  }

  /**
   * Raycast inspector: clicking a 3D part highlights it with an emissive pulse
   * and shows its description in the info panel.
   */
  function initInspector({ THREE, canvas, camera, parts, infoPanel }) {
    if (!THREE) return null;
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let selected = null;

    const groupFor = (object) => {
      let node = object;
      while (node) {
        if (node.userData?.partName) return node;
        node = node.parent;
      }
      return null;
    };

    const highlight = (part, on) => {
      part.group.traverse((node) => {
        if (!node.isMesh || !node.material?.emissive) return;
        if (on) {
          node.userData.inspectorEmissive = node.material.emissive.clone();
          node.material.emissive = new THREE.Color("#22c55e");
          node.material.emissiveIntensity = 0.4;
        } else if (node.userData.inspectorEmissive) {
          node.material.emissive.copy(node.userData.inspectorEmissive);
          delete node.userData.inspectorEmissive;
        }
      });
    };

    const pick = (event) => {
      const bounds = canvas.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return null;
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const visibleParts = parts.filter((part) => part.group.visible).map((part) => part.group);
      const hits = raycaster.intersectObjects(visibleParts, true);
      if (!hits.length) return null;
      const group = groupFor(hits[0].object);
      if (!group) return null;
      return parts.find((part) => part.group === group) ?? null;
    };

    const inspect = (part) => {
      if (selected && selected !== part) highlight(selected, false);
      selected = part ?? null;
      canvas.classList.toggle("is-inspecting", Boolean(part));
      if (infoPanel) {
        infoPanel.replaceChildren();
        if (part) {
          const tag = document.createElement("span");
          tag.className = "lab-part-tag";
          tag.textContent = "Inspect";
          const label = document.createElement("span");
          const strong = document.createElement("strong");
          strong.textContent = part.name;
          label.append(strong);
          if (part.description) label.append(document.createTextNode(` — ${part.description}`));
          infoPanel.append(tag, label);
        }
      }
      return Boolean(part);
    };

    /* Called from the render loop so the selected part pulses. */
    const pulse = (elapsed) => {
      if (!selected) return;
      const intensity = 0.28 + 0.22 * Math.sin(elapsed * 4);
      selected.group.traverse((node) => {
        if (node.isMesh && node.material?.emissive && node.userData.inspectorEmissive) {
          node.material.emissiveIntensity = intensity;
        }
      });
    };

    return { pick, inspect, pulse, get selected() { return selected; } };
  }

  window.PeakLabInteractions = { initAssembly, initInspector };
})();
