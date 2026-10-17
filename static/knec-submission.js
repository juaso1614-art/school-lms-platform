/*
 * Page wiring for the KNEC .knec packer on the practical-exams page.
 * Collects the recorded readings table, live 3D workbench readings, the
 * candidate report PDF and captured media files, then packs, validates,
 * downloads and submits the .knec archive.
 */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const form = $("knec-form");
  if (!form) return;

  const statusEl = $("knec-status");
  const detailEl = $("knec-detail");
  const packButton = $("knec-pack");
  const submitButton = $("knec-submit");
  const downloadButton = $("knec-download");
  const indexInput = $("knec-index");
  const subjectInput = $("knec-subject");
  const reportInput = $("knec-report");
  const photoInput = $("knec-photo");
  const proofInput = $("knec-proof");

  let packed = null; // { blob, filename, manifest, signature }

  const hmacKey = (() => {
    const holder = $("knec-hmac-key");
    if (!holder) return "";
    const parsed = JSON.parse(holder.textContent);
    return Array.isArray(parsed) ? parsed[0] : parsed;
  })();

  const csrfToken = () =>
    document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] ?? "";

  const setStatus = (message, isError = false) => {
    statusEl.textContent = message;
    statusEl.classList.toggle("error", isError);
  };

  const showErrors = (errors) => {
    statusEl.textContent = errors[0] ?? "The archive could not be validated.";
    statusEl.classList.add("error");
    if (errors.length > 1) {
      detailEl.textContent = errors.slice(1).join(" ");
      detailEl.hidden = false;
    }
  };

  const readRows = () => {
    const rows = [];
    document.querySelectorAll("#readings-body tr:not(.empty-readings)").forEach((row) => {
      const cells = Array.from(row.cells, (cell) => cell.textContent.trim());
      if (cells.length >= 4) {
        rows.push({
          rheostatResistance: Number(cells[1]),
          voltage: Number(cells[2]),
          current: Number(cells[3]),
          vOverI: Number(cells[4]),
          recorded_at: new Date().toISOString(),
        });
      }
    });
    return rows;
  };

  const readLabState = () => ({
    workbench: "physics-resistor-circuit",
    supplyVoltage: 3.0,
    testResistance: 10,
    rheostatSlider: Number($("rheostat-slider")?.value ?? 0),
    voltmeter: Number($("voltage-reading")?.textContent ?? "0"),
    ammeter: Number($("current-reading")?.textContent ?? "0"),
    assemblyStatus: $("physics-assembly-status")?.textContent ?? "",
    viewResets: Number($("reset-lab-view")?.dataset.count ?? 0),
  });

  const collectFiles = () => {
    const media = [];
    if (photoInput.files[0]) media.push({ name: "setup_photo.jpg", file: photoInput.files[0] });
    if (proofInput.files[0]) media.push({ name: "process_proof.webm", file: proofInput.files[0] });
    return {
      report: reportInput.files[0] ? { file: reportInput.files[0] } : null,
      media,
    };
  };

  const resetPacked = () => {
    packed = null;
    downloadButton.hidden = true;
    submitButton.disabled = true;
  };

  packButton.addEventListener("click", async (event) => {
    event.preventDefault();
    detailEl.hidden = true;
    try {
      const { report, media } = collectFiles();
      packed = await window.PeakKnecPacker.pack({
        indexNumber: indexInput.value.trim(),
        subjectCode: subjectInput.value,
        readingsRows: readRows(),
        labState: readLabState(),
        report,
        media,
        hmacKeyHex: hmacKey,
      });
      setStatus(`Archive ${packed.filename} packed and verified (HMAC-SHA256 signature OK).`, false);
      downloadButton.hidden = false;
      submitButton.disabled = false;
      const mediaCount = packed.manifest.payload.filter((entry) => entry.name.startsWith("media/")).length;
      detailEl.hidden = false;
      detailEl.textContent =
        `manifest.json + signature.sig + ${packed.manifest.payload.length - mediaCount} data files` +
        (mediaCount ? ` + ${mediaCount} media files` : "") +
        ` · ${packed.blob.size.toLocaleString()} bytes compressed.`;
    } catch (error) {
      packed = null;
      setStatus(error.message, true);
      downloadButton.hidden = true;
      submitButton.disabled = true;
    }
  });

  downloadButton.addEventListener("click", (event) => {
    event.preventDefault();
    if (packed) window.PeakKnecPacker.download(packed.blob, packed.filename);
  });

  submitButton.addEventListener("click", async (event) => {
    event.preventDefault();
    if (!packed) return;
    submitButton.disabled = true;
    setStatus("Uploading and re-validating with the examination office…");
    try {
      const body = new FormData();
      body.append("archive", packed.blob, packed.filename);
      body.append("csrfmiddlewaretoken", csrfToken());
      const response = await fetch("/knec/submit", {
        method: "POST",
        body,
        credentials: "same-origin",
      });
      const result = await response.json();
      if (result.ok) {
        setStatus(`Submitted — the examination office verified ${result.filename}.`);
        detailEl.hidden = true;
      } else {
        showErrors(result.errors ?? ["The examination office rejected the archive."]);
      }
    } catch {
      setStatus("The archive could not reach the examination office. Try again.", true);
      submitButton.disabled = false;
    }
  });

  [indexInput, subjectInput, reportInput, photoInput, proofInput].forEach((input) =>
    input.addEventListener("change", resetPacked)
  );
  form.addEventListener("submit", (event) => event.preventDefault());
})();
