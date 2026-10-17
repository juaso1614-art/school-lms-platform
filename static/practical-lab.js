(() => {
  const canvas = document.querySelector("#circuit-canvas");
  const slider = document.querySelector("#rheostat-slider");

  if (!(canvas instanceof HTMLCanvasElement) || !(slider instanceof HTMLInputElement)) {
    return;
  }

  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }

  const voltageOutput = document.querySelector("#voltage-reading");
  const currentOutput = document.querySelector("#current-reading");
  const resistanceOutput = document.querySelector("#resistance-reading");
  const sliderOutput = document.querySelector("#slider-value");
  const recordButton = document.querySelector("#record-reading");
  const recordFeedback = document.querySelector("#record-feedback");
  const readingsBody = document.querySelector("#readings-body");
  const readingCount = document.querySelector("#reading-count");
  const submitButton = document.querySelector("#submit-practical");
  const answerForm = document.querySelector("#resistance-form");
  const answerInput = document.querySelector("#resistance-answer");
  const resultOutput = document.querySelector("#practical-result");
  const resetButton = document.querySelector("#reset-practical");
  const readings = [];
  const supplyVoltage = 3;
  const testResistance = 10;
  const practicalsNode = document.querySelector("#physics-practicals");
  const practicalChoice = document.querySelector("#physics-practical-choice");
  if (practicalsNode && practicalChoice) {
    const practicals = JSON.parse(practicalsNode.textContent || "[]");
    practicalChoice.addEventListener("change", () => {
      const practical = practicals[Number(practicalChoice.value)];
      if (!practical) return;
      document.querySelector("#physics-practical-title").textContent = practical.title;
      const stepList = document.querySelector("#physics-practical-steps");
      stepList.replaceChildren(...practical.steps.map((step) => {
        const item = document.createElement("li");
        item.textContent = step;
        return item;
      }));
    });
  }

  const circuitValues = () => {
    const rheostatResistance = Number(slider.value);
    const current = supplyVoltage / (testResistance + rheostatResistance);
    return {
      rheostatResistance,
      current,
      voltage: current * testResistance,
    };
  };

  function polygon(points, fill, stroke = null) {
    context.beginPath();
    context.moveTo(points[0][0], points[0][1]);
    for (const [x, y] of points.slice(1)) context.lineTo(x, y);
    context.closePath();
    context.fillStyle = fill;
    context.fill();
    if (stroke) {
      context.strokeStyle = stroke;
      context.lineWidth = 2;
      context.stroke();
    }
  }

  function line(points, color, width = 5) {
    context.beginPath();
    context.moveTo(points[0][0], points[0][1]);
    for (const [x, y] of points.slice(1)) context.lineTo(x, y);
    context.strokeStyle = color;
    context.lineWidth = width;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.stroke();
  }

  function device(x, y, width, height, label, subtitle, screenText = "") {
    const depth = 15;
    polygon([[x, y], [x + width, y], [x + width - depth, y - depth], [x - depth, y - depth]], "#e7eef0", "#a9b9bf");
    polygon([[x + width, y], [x + width, y + height], [x + width - depth, y + height - depth], [x + width - depth, y - depth]], "#9aabb2", "#7a8e97");
    context.fillStyle = "#f8fbfc";
    context.strokeStyle = "#a9b9bf";
    context.lineWidth = 2;
    context.beginPath();
    context.roundRect(x, y, width, height, 10);
    context.fill();
    context.stroke();
    context.fillStyle = "#142b3b";
    context.font = "700 17px Inter, sans-serif";
    context.textAlign = "center";
    context.fillText(label, x + width / 2, y + 29);
    if (subtitle) {
      context.fillStyle = "#627987";
      context.font = "600 12px Inter, sans-serif";
      context.fillText(subtitle, x + width / 2, y + 47);
    }
    if (screenText) {
      context.fillStyle = "#173a3b";
      context.fillRect(x + 20, y + 58, width - 40, 39);
      context.fillStyle = "#9df2bd";
      context.font = "700 22px ui-monospace, monospace";
      context.fillText(screenText, x + width / 2, y + 85);
    }
  }

  function drawMeter(x, y, label, value, unit, color) {
    const width = 190;
    const height = 132;
    device(x, y, width, height, label, "DIGITAL MULTIMETER", `${value.toFixed(2)} ${unit}`);
    for (const portX of [x + 65, x + 125]) {
      context.beginPath();
      context.arc(portX, y + height + 1, 8, 0, Math.PI * 2);
      context.fillStyle = color;
      context.fill();
      context.strokeStyle = "#fff";
      context.lineWidth = 2;
      context.stroke();
    }
  }

  function drawScene() {
    const { current, voltage, rheostatResistance } = circuitValues();
    const bounds = canvas.getBoundingClientRect();
    const scale = Math.min(bounds.width / 1000, 1);
    const pixelRatio = window.devicePixelRatio || 1;
    canvas.width = Math.round(1000 * scale * pixelRatio);
    canvas.height = Math.round(560 * scale * pixelRatio);
    context.setTransform(scale * pixelRatio, 0, 0, scale * pixelRatio, 0, 0);

    const background = context.createLinearGradient(0, 0, 1000, 560);
    background.addColorStop(0, "#f5fbfd");
    background.addColorStop(1, "#dbe9ed");
    context.fillStyle = background;
    context.fillRect(0, 0, 1000, 560);
    polygon([[0, 322], [1000, 277], [1000, 560], [0, 560]], "#cfb995");
    line([[0, 322], [1000, 277]], "#b29c77", 3);

    line([[157, 386], [239, 386], [270, 363]], "#c43d3d", 6);
    line([[388, 363], [456, 363], [482, 384]], "#c43d3d", 6);
    line([[640, 384], [738, 384], [838, 384]], "#c43d3d", 6);
    line([[898, 384], [930, 384], [930, 436], [157, 436]], "#244c69", 6);
    line([[469, 384], [480, 384], [480, 227], [591, 227]], "#a23ca7", 5);
    line([[651, 227], [665, 227], [665, 384], [640, 384]], "#244c69", 5);

    device(64, 341, 125, 101, "3.0 V", "DC SUPPLY");
    context.fillStyle = "#c43d3d";
    context.font = "700 20px Inter, sans-serif";
    context.textAlign = "center";
    context.fillText("+", 155, 386);
    context.fillStyle = "#244c69";
    context.fillText("−", 155, 436);

    device(252, 325, 151, 79, "RHEOSTAT", `${rheostatResistance} Ω`);
    line([[273, 383], [295, 383], [317 + (rheostatResistance / 25) * 78, 344]], "#f0a540", 4);
    polygon([[309 + (rheostatResistance / 25) * 78, 340], [321 + (rheostatResistance / 25) * 78, 345], [312 + (rheostatResistance / 25) * 78, 355]], "#d77a1d");

    device(469, 341, 171, 87, "10 Ω", "TEST RESISTOR");
    context.strokeStyle = "#c43d3d";
    context.lineWidth = 4;
    context.beginPath();
    context.moveTo(505, 386);
    for (let x = 505; x <= 595; x += 10) {
      context.lineTo(x + 5, 379);
      context.lineTo(x + 10, 393);
    }
    context.stroke();

    drawMeter(773, 250, "AMMETER", current, "A", "#c43d3d");
    drawMeter(526, 94, "VOLTMETER", voltage, "V", "#a23ca7");

    context.fillStyle = "#45616f";
    context.font = "600 13px Inter, sans-serif";
    context.textAlign = "left";
    context.fillText("Series circuit", 70, 510);
    context.fillText("V connected in parallel", 528, 76);
    context.fillText("Adjust rheostat to change current", 70, 536);
  }

  function updateCircuit() {
    const { current, voltage, rheostatResistance } = circuitValues();
    voltageOutput.value = voltage.toFixed(2);
    currentOutput.value = current.toFixed(2);
    resistanceOutput.value = String(rheostatResistance);
    sliderOutput.value = `${rheostatResistance} Ω`;
    recordButton.disabled = readings.some((reading) => reading.rheostatResistance === rheostatResistance);
    recordFeedback.textContent = recordButton.disabled
      ? "This setting is already in your table. Choose a different rheostat value."
      : "";
    drawScene();
  }

  function updateTable() {
    readingsBody.replaceChildren();
    if (readings.length === 0) {
      const row = readingsBody.insertRow();
      row.className = "empty-readings";
      const cell = row.insertCell();
      cell.colSpan = 5;
      cell.textContent = "Adjust the rheostat and record your first reading.";
    } else {
      readings.forEach((reading, index) => {
        const row = readingsBody.insertRow();
        const displayedVoltage = Number(reading.voltage.toFixed(2));
        const displayedCurrent = Number(reading.current.toFixed(2));
        [index + 1, reading.rheostatResistance, displayedVoltage.toFixed(2), displayedCurrent.toFixed(2), (displayedVoltage / displayedCurrent).toFixed(2)]
          .forEach((value) => {
            row.insertCell().textContent = String(value);
          });
      });
    }
    readingCount.textContent = `${readings.length} of 6 readings`;
    submitButton.disabled = readings.length !== 6;
  }

  slider.addEventListener("input", updateCircuit);
  recordButton.addEventListener("click", () => {
    if (readings.length >= 6) {
      recordFeedback.textContent = "All six readings are recorded. Check your result or reset the practical.";
      return;
    }
    if (readings.some((reading) => reading.rheostatResistance === Number(slider.value))) {
      recordFeedback.textContent = "Choose a different rheostat value before recording.";
      return;
    }
    readings.push(circuitValues());
    recordFeedback.textContent = "Reading recorded.";
    resultOutput.textContent = "";
    updateTable();
    updateCircuit();
  });

  answerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (readings.length !== 6) return;
    const estimate = Number(answerInput.value);
    if (!Number.isFinite(estimate) || estimate <= 0 || estimate > 100) {
      resultOutput.textContent = "Enter a resistance greater than 0 Ω and no more than 100 Ω.";
      resultOutput.className = "practical-result error";
      return;
    }
    const accurateReadings = readings.filter((reading) => Math.abs(reading.voltage / reading.current - testResistance) <= 0.5).length;
    if (Math.abs(estimate - testResistance) <= 0.5) {
      resultOutput.textContent = `Well done. Your estimate is close to ${testResistance} Ω. ${accurateReadings} of your recorded V/I values are consistent with the resistor.`;
      resultOutput.className = "practical-result success";
    } else {
      resultOutput.textContent = `Your estimate is not within 0.5 Ω of the expected ${testResistance} Ω. Compare the V/I column in your table and try again.`;
      resultOutput.className = "practical-result error";
    }
  });

  resetButton.addEventListener("click", () => {
    readings.length = 0;
    slider.value = "0";
    answerInput.value = "";
    resultOutput.textContent = "";
    resultOutput.className = "practical-result";
    recordFeedback.textContent = "";
    updateTable();
    updateCircuit();
  });

  window.addEventListener("resize", drawScene);
  updateTable();
  updateCircuit();
})();
