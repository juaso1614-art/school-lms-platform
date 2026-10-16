(() => {
  const canvas = document.querySelector("#subject-scene");
  const labData = document.querySelector("#lab-data");
  if (!(canvas instanceof HTMLCanvasElement) || !labData) return;

  const lab = JSON.parse(labData.textContent || "{}");
  const status = document.querySelector("#scene-status");
  const feedback = document.querySelector("#lab-feedback");
  const observations = document.querySelector("#observation-list");
  const emptyMessage = document.querySelector("#observation-empty");
  const caption = document.querySelector("#scene-caption");
  let sceneController = null;
  let audioContext = null;

  function addObservation(text) {
    const item = document.createElement("li");
    item.textContent = text;
    observations?.prepend(item);
    if (emptyMessage) emptyMessage.hidden = true;
    if (feedback) feedback.textContent = text;
  }

  document.querySelector("#clear-observations")?.addEventListener("click", () => {
    observations?.replaceChildren();
    if (emptyMessage) emptyMessage.hidden = false;
    if (feedback) feedback.textContent = "Your observations were cleared.";
  });

  function initializeScene(THREE) {
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const background = "#dce9e3";
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(background);
    scene.fog = new THREE.Fog(background, 20, 48);

    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    const target = new THREE.Vector3(0, 1.25, 0);
    let yaw = 0.58;
    let pitch = 0.42;
    let distance = 12.4;

    scene.add(new THREE.HemisphereLight("#ffffff", "#768d7c", 2.1));
    const keyLight = new THREE.DirectionalLight("#fff4dd", 3);
    keyLight.position.set(-5, 12, 8);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    keyLight.shadow.camera.left = -12;
    keyLight.shadow.camera.right = 12;
    keyLight.shadow.camera.top = 12;
    keyLight.shadow.camera.bottom = -12;
    scene.add(keyLight);

    const material = (color, roughness = 0.56, metalness = 0) => new THREE.MeshStandardMaterial({
      color,
      roughness,
      metalness,
    });
    const addMesh = (geometry, mat, position, parent = scene) => {
      const mesh = new THREE.Mesh(geometry, mat);
      mesh.position.set(...position);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      parent.add(mesh);
      return mesh;
    };
    const box = (width, height, depth, mat, position, parent = scene) =>
      addMesh(new THREE.BoxGeometry(width, height, depth), mat, position, parent);
    const cylinder = (radiusTop, radiusBottom, height, mat, position, parent = scene, segments = 24) =>
      addMesh(new THREE.CylinderGeometry(radiusTop, radiusBottom, height, segments), mat, position, parent);
    const sphere = (radius, mat, position, parent = scene, segments = 24) =>
      addMesh(new THREE.SphereGeometry(radius, segments, Math.max(12, segments / 2)), mat, position, parent);
    const line = (points, color, radius = 0.035) => {
      const curve = new THREE.CatmullRomCurve3(points.map(([x, y, z]) => new THREE.Vector3(x, y, z)));
      return addMesh(new THREE.TubeGeometry(curve, 32, radius, 8, false), material(color, 0.3, 0.12), [0, 0, 0]);
    };
    const glass = new THREE.MeshPhysicalMaterial({
      color: "#cce7e4",
      roughness: 0.12,
      metalness: 0.05,
      transmission: 0.35,
      transparent: true,
      opacity: 0.52,
    });
    const metal = material("#aebdb7", 0.28, 0.72);
    const dark = material("#253a38", 0.4, 0.28);
    const white = material("#edf1eb", 0.38, 0.08);
    const wood = material("#b68760", 0.65);
    const accent = material("#33865b", 0.42, 0.06);
    const tabletop = 0.9;

    const floor = addMesh(new THREE.PlaneGeometry(100, 100), material("#e5ede8", 0.92), [0, -0.015, 0]);
    floor.rotation.x = -Math.PI / 2;
    box(13, 0.2, 7, wood, [0, tabletop, 0]);
    box(13.04, 0.08, 7.04, material("#70523c"), [0, tabletop - 0.14, 0]);
    for (const x of [-5.9, 5.9]) {
      for (const z of [-3, 3]) box(0.17, 0.7, 0.17, dark, [x, 0.36, z]);
    }

    const equipment = [];
    let terrainMaterial = null;
    let specimenMaterial = null;
    let specimenMesh = null;
    let solutionMaterial = null;
    const addEquipment = (name, x, z, build) => {
      const group = new THREE.Group();
      group.position.set(x, tabletop + 0.12, z);
      scene.add(group);
      build(group);
      equipment.push({ name, group });
      return group;
    };

    const screen = (group, title, subtitle, w = 1.7, h = 1.05) => {
      box(w + 0.18, h + 0.15, 0.12, dark, [0, h / 2 + 0.36, 0], group);
      const panel = box(w, h, 0.015, material("#b9edcd", 0.28), [0, h / 2 + 0.36, 0.072], group);
      const textureCanvas = document.createElement("canvas");
      textureCanvas.width = 512;
      textureCanvas.height = 320;
      const context = textureCanvas.getContext("2d");
      let texture = null;
      if (context) {
        context.fillStyle = "#102d29";
        context.fillRect(0, 0, 512, 320);
        context.fillStyle = "#8de7ad";
        context.font = "700 38px sans-serif";
        context.fillText(title.slice(0, 18), 22, 100);
        context.fillStyle = "#d9eee1";
        context.font = "500 24px sans-serif";
        context.fillText(subtitle.slice(0, 26), 22, 151);
        texture = new THREE.CanvasTexture(textureCanvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        panel.material = new THREE.MeshBasicMaterial({ map: texture, toneMapped: false });
      }
      box(0.2, 0.34, 0.24, metal, [0, 0.12, 0], group);
      box(1.18, 0.11, 0.58, dark, [0, 0, 0.05], group);
    };
    const addGlobe = (group) => {
      cylinder(0.52, 0.62, 0.14, dark, [0, 0.12, 0], group);
      cylinder(0.055, 0.055, 0.95, metal, [0, 0.63, 0], group);
      const globe = sphere(0.56, material("#4e9cb0", 0.36), [0, 1.17, 0], group, 32);
      globe.material = new THREE.MeshStandardMaterial({
        color: "#5daab1",
        roughness: 0.65,
        metalness: 0,
        wireframe: false,
      });
      const land = sphere(0.565, material("#75a66e", 0.8), [0, 1.17, 0], group, 14);
      land.scale.set(1.002, 1, 0.52);
    };
    const addTerrain = (group) => {
      const segments = 32;
      const geometry = new THREE.PlaneGeometry(3.5, 2.55, segments, segments);
      const positions = geometry.attributes.position;
      for (let index = 0; index < positions.count; index += 1) {
        const x = positions.getX(index);
        const y = positions.getY(index);
        const hill = Math.exp(-((x + 0.55) ** 2 + (y - 0.15) ** 2) * 1.35);
        const ridge = Math.exp(-((x - 0.75) ** 2) * 1.4) * 0.2;
        positions.setZ(index, hill * 0.5 + ridge + 0.06 * Math.sin(x * 3) * Math.cos(y * 2));
      }
      geometry.computeVertexNormals();
      terrainMaterial = new THREE.MeshStandardMaterial({
        color: "#76a979",
        roughness: 0.9,
        wireframe: false,
        flatShading: true,
      });
      const surface = addMesh(geometry, terrainMaterial, [-0.3, 0.24, 0], group);
      surface.rotation.x = -Math.PI / 2;
      box(3.8, 0.18, 2.85, wood, [-0.3, 0.05, 0], group);
      for (let index = 1; index <= 4; index += 1) {
        const contour = new THREE.Mesh(
          new THREE.TorusGeometry(0.2 + index * 0.21, 0.012, 5, 48),
          material("#e7d99b", 0.85),
        );
        contour.rotation.x = Math.PI / 2;
        contour.scale.set(1.8, 0.72, 1);
        contour.position.set(-0.85, 0.37 + (4 - index) * 0.018, 0);
        group.add(contour);
      }
    };
    const addMicroscope = (group) => {
      box(1.4, 0.12, 0.85, dark, [0, 0.14, 0], group);
      const base = box(0.72, 0.1, 0.55, metal, [0, 0.25, 0], group);
      base.rotation.z = -0.08;
      const arm = new THREE.TorusGeometry(0.52, 0.09, 10, 32, Math.PI * 0.84);
      const curvedArm = addMesh(arm, white, [0, 0.78, -0.04], group);
      curvedArm.rotation.z = Math.PI * 0.54;
      box(0.96, 0.09, 0.82, material("#31544c"), [0, 0.52, 0], group);
      specimenMaterial = material("#bb6da0", 0.36, 0.02);
      specimenMesh = box(0.42, 0.025, 0.31, specimenMaterial, [0.08, 0.59, 0], group);
      cylinder(0.1, 0.12, 0.55, metal, [0.28, 1.2, 0], group);
      const objective = cylinder(0.085, 0.12, 0.37, material("#dce6e1", 0.22, 0.58), [0.28, 0.91, 0], group);
      objective.rotation.z = -0.35;
      cylinder(0.11, 0.16, 0.22, dark, [0.19, 1.51, 0], group);
      const eyepiece = cylinder(0.08, 0.09, 0.45, material("#6b8291", 0.22, 0.42), [-0.03, 1.69, 0], group);
      eyepiece.rotation.z = -0.26;
      for (const z of [-0.13, 0.13]) cylinder(0.16, 0.16, 0.08, accent, [-0.28, 0.62, z], group);
    };
    const addBeaker = (group, x, z, color) => {
      cylinder(0.32, 0.36, 0.82, glass, [x, 0.48, z], group);
      cylinder(0.29, 0.29, 0.28, material(color, 0.2), [x, 0.25, z], group);
      cylinder(0.345, 0.345, 0.035, material("#bad1cb", 0.16, 0.08), [x, 0.9, z], group);
    };

    if (lab.scene === "terrain") {
      addEquipment("topographic model", -0.4, 0, addTerrain);
      addEquipment("globe", -4.0, -1.1, addGlobe);
      addEquipment("weather station", 3.2, -0.7, (group) => {
        box(0.8, 0.82, 0.58, white, [0, 0.45, 0], group);
        box(0.62, 0.31, 0.035, material("#183c36"), [0, 0.55, 0.31], group);
        for (let index = 0; index < 5; index += 1) {
          box(0.05, 0.04, 0.035, material("#75dda1"), [-0.22 + index * 0.11, 0.55, 0.34], group);
        }
        cylinder(0.035, 0.035, 0.64, metal, [0.47, 0.73, 0], group);
        for (let index = 0; index < 3; index += 1) {
          const cup = sphere(0.13, material("#e2f0e8", 0.2, 0.1), [0.47 + Math.cos(index * 2.1) * 0.17, 1.05 + Math.sin(index * 2.1) * 0.17, 0], group);
          cup.scale.set(1, 0.55, 0.65);
        }
        line([[0.47, 0.48, 0], [0.47, 0.35, 0.18], [0.47, 0.26, 0.24]], "#b54f43", 0.025);
      });
      addEquipment("rain gauge & field compass", 4.35, 1.5, (group) => {
        cylinder(0.16, 0.24, 0.85, glass, [-0.32, 0.48, 0], group);
        cylinder(0.18, 0.18, 0.05, material("#5296a1"), [-0.32, 0.12, 0], group);
        cylinder(0.29, 0.29, 0.12, dark, [0.35, 0.12, 0], group);
        cylinder(0.22, 0.22, 0.045, white, [0.35, 0.21, 0], group);
        const needle = box(0.025, 0.018, 0.32, material("#c64237"), [0.35, 0.25, 0], group);
        needle.rotation.y = 0.42;
      });
    } else if (lab.scene === "language") {
      addEquipment("listening console", -3.35, -0.45, (group) => screen(group, "LISTEN", "Language studio"));
      addEquipment("studio microphone", 0, -0.35, (group) => {
        cylinder(0.07, 0.08, 0.66, metal, [0, 0.35, 0], group);
        cylinder(0.07, 0.07, 0.46, dark, [0, 0.91, 0], group);
        const head = sphere(0.23, material("#394e50", 0.32, 0.5), [0, 1.2, 0], group);
        head.scale.set(0.8, 1.05, 0.72);
        cylinder(0.24, 0.2, 0.22, material("#829394", 0.3, 0.42), [0, 1.36, 0], group);
        cylinder(0.44, 0.52, 0.08, dark, [0, 0.06, 0], group);
        line([[0.2, 1.2, 0], [0.38, 1.04, 0], [0.38, 0.8, 0]], "#cc664d", 0.025);
      });
      addEquipment("studio headphones", 3.15, -0.35, (group) => {
        const arch = addMesh(new THREE.TorusGeometry(0.55, 0.075, 10, 36, Math.PI), dark, [0, 0.82, 0], group);
        arch.rotation.z = Math.PI;
        for (const x of [-0.52, 0.52]) {
          box(0.22, 0.44, 0.22, material("#456f61"), [x, 0.4, 0], group);
          box(0.13, 0.32, 0.15, dark, [x, 0.4, 0.12], group);
        }
      });
      addEquipment("vocabulary cards", 0.1, 1.55, (group) => {
        for (let index = 0; index < 3; index += 1) {
          const card = box(1.2, 0.06, 0.78, material(["#f2d79f", "#c3e1cb", "#bed9ec"][index]), [-0.72 + index * 0.72, 0.1 + index * 0.025, 0], group);
          card.rotation.y = (index - 1) * 0.13;
          const lineMark = box(0.72, 0.012, 0.025, material("#657870"), [-0.72 + index * 0.72, 0.14 + index * 0.025, 0], group);
          lineMark.rotation.y = (index - 1) * 0.13;
        }
      });
    } else if (lab.scene === "computer") {
      addEquipment("computer workstation", -2.2, -0.35, (group) => screen(group, "DIGITAL LAB", "Binary systems", 2.0, 1.22));
      const workstation = equipment.find((item) => item.name === "computer workstation")?.group;
      if (workstation) {
        for (let row = 0; row < 3; row += 1) {
          for (let column = 0; column < 10; column += 1) {
            box(0.13, 0.035, 0.12, material("#c3d0ca", 0.42), [-0.62 + column * 0.14, 0.075, 0.33 + row * 0.14], workstation);
          }
        }
        sphere(0.12, material("#384d4b", 0.32, 0.3), [0.93, 0.1, 0.35], workstation);
      }
      addEquipment("binary logic board", 2.05, -0.35, (group) => {
        box(2.0, 0.11, 1.38, material("#2c5348"), [0, 0.12, 0], group);
        for (let index = 0; index < 8; index += 1) {
          const switchBody = box(0.17, 0.12, 0.46, material("#253a38", 0.4, 0.28), [-0.78 + index * 0.22, 0.24, 0], group);
          switchBody.userData.switchIndex = index;
          box(0.07, 0.05, 0.18, material("#a3d4ae"), [-0.78 + index * 0.22, 0.33, 0], group);
        }
        const chip = box(0.62, 0.2, 0.5, material("#445d68", 0.35, 0.46), [0.94, 0.25, 0], group);
        chip.rotation.y = 0.1;
      });
      addEquipment("network switch & test meter", 0.15, 1.7, (group) => {
        box(1.65, 0.3, 0.68, dark, [0, 0.2, 0], group);
        for (let index = 0; index < 6; index += 1) {
          box(0.14, 0.09, 0.04, metal, [-0.55 + index * 0.22, 0.2, 0.36], group);
          sphere(0.04, material("#48c17d"), [-0.56 + index * 0.22, 0.38, 0.3], group, 12);
        }
        box(0.43, 0.6, 0.12, material("#dce5df"), [1.15, 0.36, 0.15], group);
        box(0.31, 0.19, 0.02, material("#143c35"), [1.15, 0.48, 0.22], group);
      });
    } else if (lab.scene === "music") {
      addEquipment("digital piano", -0.25, 0.1, (group) => {
        box(4.6, 0.28, 0.95, dark, [0, 0.22, 0], group);
        for (let index = 0; index < 14; index += 1) {
          box(0.31, 0.08, 0.66, white, [-2.02 + index * 0.31, 0.4, 0.04], group);
        }
        for (let index = 0; index < 10; index += 1) {
          if ([2, 6, 9].includes(index % 7)) continue;
          box(0.19, 0.1, 0.38, dark, [-1.87 + index * 0.31, 0.47, -0.08], group);
        }
        box(1.28, 0.58, 0.13, material("#426f5a"), [0, 0.68, -0.42], group);
        box(1.12, 0.34, 0.018, material("#193d32"), [0, 0.69, -0.34], group);
      });
      addEquipment("drum pads & metronome", 3.25, -0.65, (group) => {
        for (let index = 0; index < 4; index += 1) {
          const pad = cylinder(0.36, 0.36, 0.16, material(["#cf705f", "#56a480", "#6c88bb", "#e2b45b"][index]), [-0.5 + (index % 2) * 1.0, 0.24, -0.35 + Math.floor(index / 2) * 0.8], group);
          pad.rotation.x = Math.PI / 2;
        }
        box(0.48, 0.75, 0.36, material("#ded8c8"), [0.55, 0.5, 1.2], group);
        const pendulum = box(0.035, 0.5, 0.04, material("#b48b4f"), [0.55, 0.76, 1.41], group);
        pendulum.rotation.z = 0.2;
        sphere(0.09, material("#b48b4f"), [0.65, 0.56, 1.43], group);
      });
      addEquipment("mixing console & headphones", -4.1, -0.6, (group) => {
        box(1.4, 0.18, 1.2, dark, [0, 0.16, 0], group);
        for (let index = 0; index < 5; index += 1) {
          box(0.13, 0.28, 0.13, material("#91b69f"), [-0.5 + index * 0.25, 0.35, -0.15], group);
          cylinder(0.07, 0.07, 0.08, material("#d6b368"), [-0.5 + index * 0.25, 0.31, 0.36], group);
        }
        line([[-0.35, 0.08, -0.35], [-0.7, 0.6, -0.6], [-0.35, 0.9, -0.6], [0.35, 0.9, -0.6], [0.7, 0.6, -0.6], [0.35, 0.08, -0.35]], "#6b8d80", 0.07);
      });
    } else if (lab.scene === "biology") {
      addEquipment("compound microscope", -2.15, -0.3, addMicroscope);
      addEquipment("specimen slides & cell models", 1.6, -0.3, (group) => {
        for (let index = 0; index < 3; index += 1) {
          box(1.1, 0.04, 0.42, material(["#f0dce9", "#deebca", "#d3e1f2"][index], 0.25), [-0.65 + index * 0.67, 0.12 + index * 0.03, 0], group);
          box(0.38, 0.015, 0.23, material(["#bb6da0", "#75a86f", "#7b91cc"][index]), [-0.65 + index * 0.67, 0.15 + index * 0.03, 0], group);
        }
        const cell = sphere(0.48, material("#8ebc85", 0.46), [0.05, 0.58, 0.8], group);
        cell.scale.set(1.25, 0.68, 0.8);
        sphere(0.18, material("#9b73b8"), [0.12, 0.61, 0.88], group);
        for (let index = 0; index < 4; index += 1) {
          sphere(0.07, material("#e8c46b"), [-0.24 + index * 0.15, 0.65, 0.96], group, 14);
        }
      });
      addEquipment("digital imaging display", 4.2, -0.55, (group) => screen(group, "SPECIMEN", "Digital view", 1.4, 0.95));
    } else if (lab.scene === "chemistry") {
      addEquipment("glassware & solutions", -2.5, -0.35, (group) => {
        addBeaker(group, -0.75, 0, "#dfc75e");
        addBeaker(group, 0, 0.15, "#75b9d3");
        addBeaker(group, 0.75, 0, "#c97caf");
        cylinder(0.12, 0.13, 0.86, glass, [0, 1.0, -0.8], group);
        cylinder(0.08, 0.08, 0.26, material("#df6e57"), [0, 0.68, -0.8], group);
      });
      addEquipment("burette & retort stand", 0.35, -0.35, (group) => {
        box(1.25, 0.12, 0.5, dark, [0, 0.1, 0], group);
        cylinder(0.055, 0.055, 2.1, metal, [0, 1.18, 0], group);
        cylinder(0.11, 0.11, 1.55, glass, [0.26, 1.46, 0], group);
        cylinder(0.095, 0.095, 0.45, material("#6b9ad0"), [0.26, 0.92, 0], group);
        box(0.68, 0.08, 0.08, metal, [0.22, 1.24, 0], group);
        sphere(0.09, material("#c64a42"), [0.26, 0.64, 0], group);
        cylinder(0.025, 0.025, 0.3, glass, [0.26, 0.47, 0], group);
      });
      addEquipment("pH meter & indicator station", 3.4, 1.15, (group) => {
        box(0.95, 0.75, 0.48, white, [0, 0.42, 0], group);
        box(0.7, 0.27, 0.04, material("#143c35"), [0, 0.55, 0.25], group);
        box(0.4, 0.13, 0.04, material("#a8e4bc"), [0, 0.56, 0.28], group);
        line([[-0.35, 0.77, 0.15], [-0.5, 1.0, 0.15], [-0.5, 1.25, 0.15]], "#344b4c", 0.025);
        cylinder(0.13, 0.16, 0.38, glass, [0.68, 0.24, 0], group);
        const sample = cylinder(0.12, 0.12, 0.15, material("#8eba75"), [0.68, 0.15, 0], group);
        solutionMaterial = sample.material;
        for (let index = 0; index < 3; index += 1) {
          cylinder(0.1, 0.11, 0.34, glass, [-0.8 + index * 0.24, 0.22, 0.38], group);
          cylinder(0.095, 0.095, 0.12, material(["#e0674d", "#e2bb53", "#8f72bb"][index]), [-0.8 + index * 0.24, 0.12, 0.38], group);
          cylinder(0.11, 0.11, 0.06, material("#677975", 0.36), [-0.8 + index * 0.24, 0.42, 0.38], group);
        }
      });
      addEquipment("fume hood", -4.5, 1.5, (group) => {
        box(1.65, 1.55, 0.8, material("#dce6df", 0.4, 0.08), [0, 0.8, 0], group);
        box(1.35, 0.62, 0.035, material("#8eb7b0", 0.2, 0.04), [0, 1.03, 0.42], group);
        box(1.4, 0.12, 0.82, dark, [0, 0.12, 0], group);
      });
    }

    const resetCamera = () => {
      const aspect = canvas.clientWidth / Math.max(canvas.clientHeight, 1);
      camera.aspect = aspect;
      camera.fov = aspect < 1.35 ? 46 : 38;
      camera.position.set(
        target.x + distance * Math.sin(yaw) * Math.cos(pitch),
        target.y + distance * Math.sin(pitch),
        target.z + distance * Math.cos(yaw) * Math.cos(pitch),
      );
      camera.lookAt(target);
      camera.updateProjectionMatrix();
    };
    const render = () => renderer.render(scene, camera);
    const resize = () => {
      if (!canvas.clientWidth || !canvas.clientHeight) return;
      renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
      resetCamera();
      render();
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas.parentElement);
    window.addEventListener("resize", resize);

    let dragging = false;
    let previous = null;
    canvas.addEventListener("pointerdown", (event) => {
      dragging = true;
      previous = { x: event.clientX, y: event.clientY };
      canvas.setPointerCapture(event.pointerId);
      canvas.classList.add("is-dragging");
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!dragging || !previous) return;
      yaw -= (event.clientX - previous.x) * 0.006;
      pitch = THREE.MathUtils.clamp(pitch + (event.clientY - previous.y) * 0.004, 0.16, 1.04);
      previous = { x: event.clientX, y: event.clientY };
      resetCamera();
      render();
    });
    const stopDragging = () => {
      dragging = false;
      previous = null;
      canvas.classList.remove("is-dragging");
    };
    canvas.addEventListener("pointerup", stopDragging);
    canvas.addEventListener("pointercancel", stopDragging);
    canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      distance = THREE.MathUtils.clamp(distance + event.deltaY * 0.008, 8.5, 19);
      resetCamera();
      render();
    }, { passive: false });
    canvas.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") yaw += 0.08;
      else if (event.key === "ArrowRight") yaw -= 0.08;
      else if (event.key === "ArrowUp") pitch = THREE.MathUtils.clamp(pitch + 0.06, 0.16, 1.04);
      else if (event.key === "ArrowDown") pitch = THREE.MathUtils.clamp(pitch - 0.06, 0.16, 1.04);
      else if (event.key === "+" || event.key === "=") distance = Math.max(8.5, distance - 0.8);
      else if (event.key === "-") distance = Math.min(19, distance + 0.8);
      else return;
      event.preventDefault();
      resetCamera();
      render();
    });
    document.querySelector("#reset-studio")?.addEventListener("click", () => {
      yaw = 0.58;
      pitch = 0.42;
      distance = canvas.clientWidth / Math.max(canvas.clientHeight, 1) < 1.35 ? 15.5 : 12.4;
      resetCamera();
      render();
    });
    resize();

    return {
      render,
      setRainfall(value) {
        if (terrainMaterial) {
          terrainMaterial.color.setHSL(0.31 - Number(value) / 1000, 0.34, 0.49 - Number(value) / 600);
        }
        render();
      },
      setMagnification(value) {
        if (specimenMesh) specimenMesh.scale.set(1 + Number(value) / 180, 1, 1 + Number(value) / 180);
        render();
      },
      setSpecimen(value) {
        if (!specimenMaterial) return;
        specimenMaterial.color.set(value === "onion" ? "#cf86b1" : value === "cheek" ? "#e6a48e" : "#75ae78");
        render();
      },
      setSolution(color, ph) {
        solutionMaterial?.color.set(color);
        if (caption) caption.textContent = `Simulated solution · approximate pH ${ph}`;
        render();
      },
      setBinary(bits) {
        const board = equipment.find((item) => item.name === "binary logic board")?.group;
        if (!board) return;
        board.children.forEach((child) => {
          if (child.userData.switchIndex !== undefined) {
            child.material.color.set(bits[child.userData.switchIndex] === "1" ? "#4dcb80" : "#253a38");
          }
        });
        render();
      },
      resetCamera() {
        yaw = 0.58;
        pitch = 0.42;
        distance = 12.4;
        resetCamera();
        render();
      },
    };
  }

  const rainfall = document.querySelector("#rainfall");
  rainfall?.addEventListener("input", () => {
    const value = Number(rainfall.value);
    const output = document.querySelector("#rainfall-value");
    if (output) output.textContent = `${value} mm`;
    sceneController?.setRainfall(value);
  });
  document.querySelector("#run-geography")?.addEventListener("click", () => {
    const value = Number(rainfall?.value ?? 40);
    const runoff = value < 30 ? "low" : value < 70 ? "moderate" : "high";
    addObservation(`${value} mm simulated rainfall: ${runoff} surface runoff in this terrain model. Compare the contour spacing with the slope.`);
  });

  const speechRate = document.querySelector("#speech-rate");
  speechRate?.addEventListener("input", () => {
    const output = document.querySelector("#speech-rate-value");
    if (output) output.textContent = `${Number(speechRate.value).toFixed(1)}×`;
  });
  document.querySelector("#play-phrase")?.addEventListener("click", () => {
    const phrase = document.querySelector("#phrase-choice")?.value;
    if (!phrase) return;
    if (!("speechSynthesis" in window)) {
      if (feedback) feedback.textContent = "Speech playback is not supported by this browser. You can still read the selected phrase.";
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(phrase);
    utterance.rate = Number(speechRate?.value ?? 1);
    utterance.onerror = () => {
      if (feedback) feedback.textContent = "Speech playback could not start. Check your browser audio settings and try again.";
    };
    window.speechSynthesis.speak(utterance);
    addObservation(`Listening practice · “${phrase}” at ${utterance.rate.toFixed(1)}× pace.`);
  });

  document.querySelector("#convert-binary")?.addEventListener("click", () => {
    const switches = Array.from(document.querySelectorAll(".binary-switches input"));
    const bits = switches.map((input) => input.checked ? "1" : "0").join("");
    const decimal = Number.parseInt(bits, 2);
    const result = document.querySelector("#binary-result");
    if (result) result.textContent = `Binary ${bits} = Decimal ${decimal}`;
    sceneController?.setBinary(bits);
    addObservation(`Binary systems · ${bits}₂ = ${decimal}₁₀.`);
  });

  const tempo = document.querySelector("#tempo");
  tempo?.addEventListener("input", () => {
    const output = document.querySelector("#tempo-value");
    if (output) output.textContent = `${tempo.value} BPM`;
  });
  function playTone(frequency, duration = 0.42) {
    const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextConstructor) return false;
    audioContext ??= new AudioContextConstructor();
    if (audioContext.state === "suspended") void audioContext.resume();
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0.18, audioContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + duration);
    oscillator.connect(gain);
    gain.connect(audioContext.destination);
    oscillator.start();
    oscillator.stop(audioContext.currentTime + duration);
    return true;
  }
  document.querySelectorAll(".piano-keys button").forEach((key) => {
    key.addEventListener("click", () => {
      const note = key.dataset.note ?? "C";
      const frequencies = { C: 261.63, D: 293.66, E: 329.63, F: 349.23, G: 392, A: 440, B: 493.88 };
      if (playTone(frequencies[note])) addObservation(`Sound study · note ${note}4 (${frequencies[note]} Hz).`);
      else if (feedback) feedback.textContent = "Audio playback is not supported by this browser.";
    });
  });
  document.querySelector("#play-pulse")?.addEventListener("click", () => {
    const beatsPerMinute = Number(tempo?.value ?? 90);
    const duration = 60 / beatsPerMinute;
    if (playTone(880, Math.min(duration * 0.3, 0.35))) {
      addObservation(`Rhythm study · one metronome beat at ${beatsPerMinute} BPM (${duration.toFixed(2)} seconds per beat).`);
    } else if (feedback) {
      feedback.textContent = "Audio playback is not supported by this browser.";
    }
  });

  const magnification = document.querySelector("#magnification");
  magnification?.addEventListener("input", () => {
    const value = Number(magnification.value);
    const output = document.querySelector("#magnification-value");
    if (output) output.textContent = `${value}×`;
    sceneController?.setMagnification(value);
  });
  const specimen = document.querySelector("#specimen");
  specimen?.addEventListener("change", () => sceneController?.setSpecimen(specimen.value));
  document.querySelector("#focus-specimen")?.addEventListener("click", () => {
    const specimenNames = { onion: "onion epidermis", cheek: "cheek smear", leaf: "leaf section" };
    const name = specimenNames[specimen?.value ?? "onion"];
    const value = Number(magnification?.value ?? 100);
    addObservation(`Microscope focus · ${name} at ${value}× magnification. Identify visible structures and record their relative size.`);
  });

  const solutions = {
    lemon: { name: "citrus solution", ph: 2.5 },
    vinegar: { name: "vinegar solution", ph: 3 },
    water: { name: "distilled water", ph: 7 },
    bicarbonate: { name: "bicarbonate solution", ph: 8.3 },
    soap: { name: "soap solution", ph: 10 },
  };
  document.querySelector("#test-solution")?.addEventListener("click", () => {
    const solutionKey = document.querySelector("#solution")?.value ?? "water";
    const indicator = document.querySelector("#indicator")?.value ?? "universal";
    const solution = solutions[solutionKey];
    const color = solution.ph < 4 ? "#e45f48" : solution.ph < 6 ? "#e7a348" : solution.ph <= 7.5 ? "#7ab574" : solution.ph < 9 ? "#4da9bd" : "#7761ad";
    sceneController?.setSolution(color, solution.ph);
    const colorText = indicator === "litmus"
      ? solution.ph < 7 ? "red" : "blue"
      : indicator === "phenolphthalein"
        ? solution.ph >= 8.2 ? "pink" : "colourless"
        : solution.ph < 4 ? "red-orange" : solution.ph < 6 ? "yellow" : solution.ph <= 7.5 ? "green" : solution.ph < 9 ? "blue-green" : "violet";
    addObservation(`Indicator test · ${solution.name} is approximately pH ${solution.ph}; ${indicator} shows ${colorText}. Values are simulated for revision.`);
  });

  import("https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js")
    .then((THREE) => {
      sceneController = initializeScene(THREE);
      if (lab.scene === "geography") sceneController.setRainfall(Number(rainfall?.value ?? 40));
      if (lab.scene === "biology") {
        sceneController.setMagnification(Number(magnification?.value ?? 100));
        sceneController.setSpecimen(specimen?.value ?? "onion");
      }
      if (lab.scene === "computer") {
        const bits = Array.from(document.querySelectorAll(".binary-switches input"))
          .map((input) => input.checked ? "1" : "0")
          .join("");
        sceneController.setBinary(bits);
      }
      if (status) status.hidden = true;
    })
    .catch((error) => {
      if (status) status.textContent = "The 3D studio could not load. Check your connection; the guided activity controls remain available.";
      console.error("Could not initialize the subject 3D lab.", error);
    });
})();
