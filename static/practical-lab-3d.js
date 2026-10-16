(() => {
  const canvas = document.querySelector("#lab-scene-canvas");
  const slider = document.querySelector("#rheostat-slider");
  const status = document.querySelector("#lab-scene-status");
  const resetView = document.querySelector("#reset-lab-view");

  if (!(canvas instanceof HTMLCanvasElement) || !(slider instanceof HTMLInputElement)) return;

  let sceneController = null;
  const supplyVoltage = 3;
  const testResistance = 10;

  function updateReadings() {
    const rheostatResistance = Number(slider.value);
    const current = supplyVoltage / (testResistance + rheostatResistance);
    return {
      rheostatResistance,
      current,
      voltage: current * testResistance,
    };
  }

  function initializeScene(THREE) {
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#dcebe5");
    scene.fog = new THREE.Fog("#dcebe5", 24, 58);

    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 100);
    const cameraTarget = new THREE.Vector3(0, 1.35, 0);
    let yaw = 0.55;
    let pitch = 0.45;
    let distance = 13.5;

    const ambient = new THREE.HemisphereLight("#ffffff", "#718579", 2.2);
    scene.add(ambient);
    const keyLight = new THREE.DirectionalLight("#fff4dc", 3.1);
    keyLight.position.set(-5, 12, 8);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    keyLight.shadow.camera.left = -14;
    keyLight.shadow.camera.right = 14;
    keyLight.shadow.camera.top = 14;
    keyLight.shadow.camera.bottom = -14;
    scene.add(keyLight);

    const standardMaterial = (color, roughness = 0.58, metalness = 0) => new THREE.MeshStandardMaterial({
      color,
      roughness,
      metalness,
    });
    const makeBox = (width, height, depth, material, position) => {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
      mesh.position.set(...position);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      scene.add(mesh);
      return mesh;
    };

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(120, 120),
      standardMaterial("#e8efeb", 0.95),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.015;
    floor.receiveShadow = true;
    scene.add(floor);

    const benchTop = 0.86;
    makeBox(13, 0.24, 7.4, standardMaterial("#b78d61", 0.78), [0, benchTop, 0]);
    const benchEdge = makeBox(13.04, 0.09, 7.42, standardMaterial("#71523b", 0.72), [0, benchTop - 0.15, 0]);
    benchEdge.castShadow = false;
    for (const x of [-5.8, 5.8]) {
      for (const z of [-3.05, 3.05]) {
        makeBox(0.18, 0.64, 0.18, standardMaterial("#515e5b", 0.62), [x, 0.35, z]);
      }
    }
    for (const x of [-5.2, 5.2]) {
      makeBox(0.28, 0.035, 0.28, standardMaterial("#3f4947", 0.75), [x, 0.025, 3.05]);
    }

    function createDisplay(title, accent, initialValue) {
      const displayCanvas = document.createElement("canvas");
      displayCanvas.width = 512;
      displayCanvas.height = 192;
      const context = displayCanvas.getContext("2d");
      const texture = new THREE.CanvasTexture(displayCanvas);
      texture.colorSpace = THREE.SRGBColorSpace;

      function update(value) {
        context.fillStyle = "#102521";
        context.fillRect(0, 0, displayCanvas.width, displayCanvas.height);
        context.fillStyle = accent;
        context.fillRect(0, 0, 14, displayCanvas.height);
        context.fillStyle = "#a9c0b6";
        context.font = "600 25px sans-serif";
        context.textAlign = "left";
        context.fillText(title, 34, 47);
        context.fillStyle = "#c7ffd8";
        context.font = "700 60px monospace";
        context.textAlign = "right";
        context.fillText(value, 475, 137);
        texture.needsUpdate = true;
      }

      update(initialValue);
      return {
        material: new THREE.MeshBasicMaterial({ map: texture, toneMapped: false }),
        update,
      };
    }

    function createInstrument({ x, z, title, accent, initialValue, powerSupply = false }) {
      const width = powerSupply ? 2.35 : 2.05;
      const height = 1.12;
      const depth = 1.38;
      const display = createDisplay(title, accent, initialValue);
      const group = new THREE.Group();
      group.position.set(x, benchTop, z);
      scene.add(group);

      const body = new THREE.Mesh(
        new THREE.BoxGeometry(width, height, depth),
        standardMaterial(powerSupply ? "#d8ded9" : "#dfe5e1", 0.42, 0.12),
      );
      body.position.y = height / 2;
      body.castShadow = true;
      body.receiveShadow = true;
      group.add(body);

      const face = new THREE.Mesh(
        new THREE.PlaneGeometry(width * 0.76, 0.59),
        display.material,
      );
      face.position.set(0, height * 0.61, depth / 2 + 0.008);
      group.add(face);

      if (powerSupply) {
        for (const knobX of [-0.55, 0.55]) {
          const knob = new THREE.Mesh(
            new THREE.CylinderGeometry(0.14, 0.16, 0.13, 24),
            standardMaterial("#425650", 0.3, 0.28),
          );
          knob.position.set(knobX, height + 0.06, -0.08);
          knob.castShadow = true;
          group.add(knob);
          const indicator = makeBox(0.035, 0.012, 0.12, standardMaterial("#e3a85e", 0.4), [x + knobX, benchTop + height + 0.13, z - 0.08]);
          indicator.castShadow = false;
        }
      }

      const terminals = [];
      for (const [terminalX, color] of [[-0.62, "#c94a42"], [0.62, "#273536"]]) {
        const terminal = new THREE.Mesh(
          new THREE.CylinderGeometry(0.075, 0.075, 0.12, 20),
          standardMaterial(color, 0.28, 0.5),
        );
        terminal.rotation.x = Math.PI / 2;
        terminal.position.set(terminalX, 0.17, depth / 2 + 0.03);
        terminal.castShadow = true;
        group.add(terminal);
        terminals.push(new THREE.Vector3(x + terminalX, benchTop + 0.17, z + depth / 2 + 0.09));
      }
      return { group, terminals, width, depth, display };
    }

    const powerSupply = createInstrument({
      x: -4.15,
      z: 0.25,
      title: "DC POWER SUPPLY",
      accent: "#e8a653",
      initialValue: "3.00 V",
      powerSupply: true,
    });
    const ammeter = createInstrument({
      x: 4.05,
      z: 0.25,
      title: "AMMETER",
      accent: "#e05c4e",
      initialValue: "0.30 A",
    });
    const voltmeter = createInstrument({
      x: 1.2,
      z: -2.25,
      title: "VOLTMETER",
      accent: "#35a978",
      initialValue: "3.00 V",
    });

    const metalMaterial = standardMaterial("#9ca9a2", 0.3, 0.78);
    const ceramicMaterial = standardMaterial("#d5dfd6", 0.4, 0.06);
    makeBox(2.45, 0.13, 0.58, standardMaterial("#626e68", 0.55, 0.28), [-1.35, benchTop + 0.09, 0.25]);

    const rheostatCoil = new THREE.Mesh(
      new THREE.CylinderGeometry(0.23, 0.23, 1.9, 32),
      ceramicMaterial,
    );
    rheostatCoil.rotation.z = Math.PI / 2;
    rheostatCoil.position.set(-1.35, benchTop + 0.43, 0.25);
    rheostatCoil.castShadow = true;
    scene.add(rheostatCoil);

    const coilMaterial = standardMaterial("#b8773e", 0.32, 0.72);
    for (let index = 0; index < 17; index += 1) {
      const coil = new THREE.Mesh(new THREE.TorusGeometry(0.235, 0.035, 8, 18), coilMaterial);
      coil.rotation.y = Math.PI / 2;
      coil.position.set(-2.15 + index * 0.1, benchTop + 0.43, 0.25);
      coil.castShadow = true;
      scene.add(coil);
    }

    const sliderGroup = new THREE.Group();
    scene.add(sliderGroup);
    const sliderStem = new THREE.Mesh(
      new THREE.CylinderGeometry(0.045, 0.06, 0.47, 16),
      metalMaterial,
    );
    sliderStem.position.y = benchTop + 0.47;
    sliderStem.castShadow = true;
    sliderGroup.add(sliderStem);
    const sliderGrip = new THREE.Mesh(
      new THREE.SphereGeometry(0.11, 20, 14),
      standardMaterial("#e2a84c", 0.3, 0.35),
    );
    sliderGrip.position.y = benchTop + 0.72;
    sliderGrip.castShadow = true;
    sliderGroup.add(sliderGrip);

    makeBox(0.09, 0.09, 0.08, metalMaterial, [-2.25, benchTop + 0.14, 0.25]);
    makeBox(0.09, 0.09, 0.08, metalMaterial, [-0.45, benchTop + 0.14, 0.25]);

    const resistorBody = new THREE.Mesh(
      new THREE.CylinderGeometry(0.22, 0.22, 1.15, 32),
      standardMaterial("#eee4cb", 0.4, 0.02),
    );
    resistorBody.rotation.z = Math.PI / 2;
    resistorBody.position.set(1.2, benchTop + 0.36, 0.25);
    resistorBody.castShadow = true;
    scene.add(resistorBody);
    for (const [offset, color] of [[-0.34, "#9c503b"], [-0.08, "#d1a446"], [0.18, "#57463b"], [0.39, "#bd7653"]]) {
      const band = new THREE.Mesh(new THREE.TorusGeometry(0.224, 0.037, 8, 22), standardMaterial(color, 0.35));
      band.rotation.y = Math.PI / 2;
      band.position.set(1.2 + offset, benchTop + 0.36, 0.25);
      band.castShadow = true;
      scene.add(band);
    }
    for (const [x, length] of [[0.43, 0.38], [1.97, 0.38]]) {
      const lead = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, length, 12), metalMaterial);
      lead.rotation.z = Math.PI / 2;
      lead.position.set(x, benchTop + 0.36, 0.25);
      lead.castShadow = true;
      scene.add(lead);
    }

    function addWire(points, color, radius = 0.035) {
      const curve = new THREE.CatmullRomCurve3(points.map((point) => new THREE.Vector3(...point)));
      const wire = new THREE.Mesh(
        new THREE.TubeGeometry(curve, 64, radius, 10, false),
        standardMaterial(color, 0.31, 0.18),
      );
      wire.castShadow = true;
      scene.add(wire);
      return curve;
    }

    const wireY = benchTop + 0.12;
    const seriesPath = [
      [-3.0, wireY, 0.94],
      [-2.72, wireY, 0.65],
      [-2.45, wireY, 0.25],
      [-0.3, wireY, 0.25],
      [0.35, wireY, 0.25],
      [2.05, wireY, 0.25],
      [2.92, wireY, 0.25],
      [5.12, wireY, 0.25],
      [5.55, wireY, 0.8],
      [5.55, wireY, 2.9],
      [-5.55, wireY, 2.9],
      [-5.55, wireY, 0.75],
      [-5.28, wireY, 0.25],
    ];
    const currentCurve = new THREE.CatmullRomCurve3(seriesPath.map((point) => new THREE.Vector3(...point)));
    addWire(seriesPath.slice(0, 8), "#c84a42", 0.04);
    addWire(seriesPath.slice(7), "#263b3a", 0.04);
    addWire([[0.43, wireY + 0.015, 0.25], [0.1, wireY + 0.015, -0.1], [0.1, wireY + 0.015, -1.35], [0.58, wireY + 0.015, -1.35]], "#c84a42", 0.027);
    addWire([[1.97, wireY + 0.02, 0.25], [2.3, wireY + 0.02, -0.1], [2.3, wireY + 0.02, -1.35], [1.82, wireY + 0.02, -1.35]], "#263b3a", 0.027);

    const particles = [];
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const particleMaterial = new THREE.MeshStandardMaterial({
      color: "#f3d36c",
      emissive: "#936e1f",
      emissiveIntensity: 0.65,
      roughness: 0.25,
    });
    for (let index = 0; index < 7; index += 1) {
      const particle = new THREE.Mesh(new THREE.SphereGeometry(0.075, 12, 10), particleMaterial);
      particle.castShadow = true;
      scene.add(particle);
      particles.push(particle);
    }

    function setCamera(aspect = canvas.clientWidth / Math.max(canvas.clientHeight, 1)) {
      camera.aspect = aspect;
      camera.fov = aspect < 1.35 ? 44 : 36;
      if (aspect < 1.35) distance = Math.max(distance, 16.5);
      camera.position.set(
        cameraTarget.x + distance * Math.sin(yaw) * Math.cos(pitch),
        cameraTarget.y + distance * Math.sin(pitch),
        cameraTarget.z + distance * Math.cos(yaw) * Math.cos(pitch),
      );
      camera.lookAt(cameraTarget);
      camera.updateProjectionMatrix();
    }

    function resize() {
      const bounds = canvas.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return;
      renderer.setSize(bounds.width, bounds.height, false);
      setCamera(bounds.width / bounds.height);
    }

    let dragging = false;
    let previousPointer = null;
    canvas.addEventListener("pointerdown", (event) => {
      dragging = true;
      previousPointer = { x: event.clientX, y: event.clientY };
      canvas.setPointerCapture(event.pointerId);
      canvas.classList.add("is-dragging");
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!dragging || !previousPointer) return;
      yaw -= (event.clientX - previousPointer.x) * 0.006;
      pitch = THREE.MathUtils.clamp(pitch + (event.clientY - previousPointer.y) * 0.004, 0.18, 1.05);
      previousPointer = { x: event.clientX, y: event.clientY };
      setCamera();
    });
    const endDrag = () => {
      dragging = false;
      previousPointer = null;
      canvas.classList.remove("is-dragging");
    };
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);
    canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      distance = THREE.MathUtils.clamp(distance + event.deltaY * 0.012, 10.5, 23);
      setCamera();
    }, { passive: false });
    canvas.addEventListener("keydown", (event) => {
      if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "+", "-"].includes(event.key)) return;
      event.preventDefault();
      if (event.key === "ArrowLeft") yaw += 0.08;
      if (event.key === "ArrowRight") yaw -= 0.08;
      if (event.key === "ArrowUp") pitch = THREE.MathUtils.clamp(pitch + 0.06, 0.18, 1.05);
      if (event.key === "ArrowDown") pitch = THREE.MathUtils.clamp(pitch - 0.06, 0.18, 1.05);
      if (event.key === "+") distance = Math.max(10.5, distance - 0.8);
      if (event.key === "-") distance = Math.min(23, distance + 0.8);
      setCamera();
    });
    resetView?.addEventListener("click", () => {
      yaw = 0.55;
      pitch = 0.45;
      distance = canvas.clientWidth / Math.max(canvas.clientHeight, 1) < 1.35 ? 16.5 : 13.5;
      setCamera();
    });

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas.parentElement);
    window.addEventListener("resize", resize);
    resize();

    function update(readings) {
      powerSupply.display.update(`${supplyVoltage.toFixed(2)} V`);
      ammeter.display.update(`${readings.current.toFixed(2)} A`);
      voltmeter.display.update(`${readings.voltage.toFixed(2)} V`);
      sliderGroup.position.x = -2.15 + (readings.rheostatResistance / 25) * 1.6;
    }

    const clock = new THREE.Clock();
    function animate() {
      const elapsed = clock.getElapsedTime();
      particles.forEach((particle, index) => {
        const progress = reduceMotion ? index / particles.length : (elapsed * 0.11 + index / particles.length) % 1;
        particle.position.copy(currentCurve.getPointAt(progress));
      });
      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    }
    animate();
    return { update, resize };
  }

  slider.addEventListener("input", () => sceneController?.update(updateReadings()));
  updateReadings();

  import("https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js")
    .then((THREE) => {
      sceneController = initializeScene(THREE);
      sceneController.update(updateReadings());
      if (status) status.hidden = true;
    })
    .catch((error) => {
      if (status) status.textContent = "The 3D workbench could not load. The lesson readings and results table are still available.";
      console.error("Could not initialize the 3D physics workbench.", error);
    });
})();
