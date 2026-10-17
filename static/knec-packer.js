/*
 * KNEC Practical Archive & Simulation Packer Engine (.knec)
 *
 * Browser-native archiving (fflate, ZIP-compliant) for the KNEC digital
 * assessment pipeline. Packs practical-exam payloads into a single
 * [IndexNumber]_[SubjectCode].knec archive:
 *
 *   ├── manifest.json        system metadata + payload inventory (SHA-256)
 *   ├── signature.sig        hex HMAC-SHA256 tag over manifest.json
 *   ├── data/readings.csv    raw experiment logs
 *   ├── data/lab_state.json  3D simulation / workbench parameters
 *   ├── data/report.pdf      final rendered candidate report
 *   └── media/…              setup_photo.jpg, process_proof.webm
 *
 * The HMAC key is issued per session by the server, so submissions can be
 * re-verified server side (school/knec.py).
 */
(() => {
  "use strict";

  const SUBJECTS = {
    "232": { name: "Physics", paper: "3" },
    "233": { name: "Chemistry", paper: "3" },
    "231": { name: "Biology", paper: "3" },
    "451": { name: "Computer Studies", paper: "2" },
  };

  const REQUIRED_MEDIA = ["media/setup_photo.jpg", "media/process_proof.webm"];
  const MAX_ARCHIVE_BYTES = 100 * 1024 * 1024;

  const toHex = (buffer) =>
    Array.from(new Uint8Array(buffer), (byte) => byte.toString(16).padStart(2, "0")).join("");

  const fromHex = (hex) => {
    const clean = String(hex || "").replace(/[^0-9a-f]/gi, "");
    if (clean.length % 2 !== 0) throw new Error("HMAC key is not valid hex.");
    const bytes = new Uint8Array(clean.length / 2);
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = parseInt(clean.substr(i * 2, 2), 16);
    return bytes;
  };

  const csvCell = (value) => {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };

  const buildReadingsCsv = (rows) => {
    const header = ["No.", ...Object.keys(rows[0] ?? {}), "recorded_at"];
    const lines = [header.map(csvCell).join(",")];
    rows.forEach((row, index) => {
      lines.push([String(index + 1), ...Object.values(row).map(csvCell), row.recorded_at ?? ""].join(","));
    });
    return lines.join("\r\n") + "\r\n";
  };

  /* Manifest builder — computes SHA-256 digests for the payload inventory. */
  const buildPayload = async ({ indexNumber, subjectCode, readingsRows, labState, report, media, generatedAt }) => {
    const readingsCsv = buildReadingsCsv(readingsRows);
    const labStateJson = JSON.stringify({ ...labState, generatedAt }, null, 2);
    const text = new TextEncoder();

    const inventory = [];
    const digest = async (name, bytes) => {
      inventory.push({ name, size: bytes.byteLength, sha256: toHex(await crypto.subtle.digest("SHA-256", bytes)) });
    };
    await digest("data/readings.csv", text.encode(readingsCsv));
    await digest("data/lab_state.json", text.encode(labStateJson));
    if (report?.file) await digest("data/report.pdf", report.bytes);
    for (const item of media) await digest(`media/${item.name}`, item.bytes);

    const manifest = {
      format: "KNEC-PRACTICAL-ARCHIVE",
      version: 1,
      generatedAt,
      candidate: {
        index_number: String(indexNumber),
        submitted_at: generatedAt,
        user_agent: navigator.userAgent,
      },
      subject: { code: subjectCode, name: SUBJECTS[subjectCode].name, paper: SUBJECTS[subjectCode].paper },
      payload: inventory,
      media_expected: REQUIRED_MEDIA,
      integrity: { algorithm: "SHA-256", signature: "HMAC-SHA256 over manifest.json" },
    };
    return { manifest, manifestBytes: text.encode(JSON.stringify(manifest, null, 2)), readingsCsv, labStateJson };
  };

  const hmacSign = async (bytes, keyHex) => {
    const key = await crypto.subtle.importKey(
      "raw",
      fromHex(keyHex),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    return toHex(await crypto.subtle.sign("HMAC", key, bytes));
  };

  const hmacVerify = async (bytes, keyHex, signatureHex) => {
    const key = await crypto.subtle.importKey(
      "raw",
      fromHex(keyHex),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["verify"]
    );
    const signature = fromHex(signatureHex);
    return signature.length > 0 && crypto.subtle.verify("HMAC", key, signature, bytes);
  };

  /**
   * Pack a submission archive.
   * @returns {Promise<{blob, filename, manifest, signature}>}
   */
  const pack = async ({
    indexNumber,
    subjectCode,
    readingsRows = [],
    labState = {},
    report = null,               // { file: File }
    media = [],                  // [{ name: "setup_photo.jpg", file: File }]
    hmacKeyHex,
  }) => {
    if (!/^\d{1,12}$/.test(String(indexNumber || "").trim())) {
      throw new Error("Enter a valid numeric candidate index number.");
    }
    if (!SUBJECTS[subjectCode]) {
      throw new Error(`Unsupported subject code ${subjectCode}.`);
    }
    if (!Array.isArray(readingsRows) || readingsRows.length === 0) {
      throw new Error("Record at least one reading before packing the archive.");
    }
    if (!report?.file || report.file.type !== "application/pdf") {
      throw new Error("Attach the final candidate report as a PDF.");
    }
    if (!window.fflate) throw new Error("The fflate compression engine failed to load.");

    const generatedAt = new Date().toISOString();
    const bytesOf = (file) =>
      file.arrayBuffer().then((buffer) => new Uint8Array(buffer));

    const reportBytes = await bytesOf(report.file);
    const mediaEntries = [];
    for (const item of media) {
      if (!item?.file) continue;
      mediaEntries.push({ name: item.name, bytes: await bytesOf(item.file) });
    }

    const { manifest, manifestBytes, readingsCsv, labStateJson } = await buildPayload({
      indexNumber: String(indexNumber).trim(),
      subjectCode,
      readingsRows,
      labState,
      report: { bytes: reportBytes },
      media: mediaEntries,
      generatedAt,
    });

    const signature = await hmacSign(manifestBytes, hmacKeyHex);

    const files = {
      "manifest.json": manifestBytes,
      "signature.sig": new TextEncoder().encode(signature),
      "data/readings.csv": new TextEncoder().encode(readingsCsv),
      "data/lab_state.json": new TextEncoder().encode(labStateJson),
      "data/report.pdf": reportBytes,
    };
    mediaEntries.forEach((entry) => { files[`media/${entry.name}`] = entry.bytes; });

    const zipped = fflate.zipSync(files, { level: 6 });
    if (zipped.byteLength > MAX_ARCHIVE_BYTES) {
      throw new Error("The packed archive exceeds the 100 MB limit.");
    }

    const filename = `${manifest.candidate.index_number}_${subjectCode}.knec`;
    return {
      blob: new Blob([zipped], { type: "application/octet-stream" }),
      filename,
      manifest,
      signature,
    };
  };

  /** Validate a previously packed .knec blob against the session key. */
  const validate = async (blob, hmacKeyHex) => {
    if (!window.fflate) throw new Error("The fflate compression engine failed to load.");
    const errors = [];
    const unzipped = fflate.unzipSync(new Uint8Array(await blob.arrayBuffer()));
    const names = Object.keys(unzipped);

    ["manifest.json", "signature.sig", "data/readings.csv", "data/lab_state.json", "data/report.pdf"].forEach(
      (entry) => {
        if (!names.includes(entry)) errors.push(`Missing required archive entries: ${entry}.`);
      }
    );
    if (errors.length) return { valid: false, errors, manifest: null };

    const manifestBytes = unzipped["manifest.json"];
    const signatureHex = new TextDecoder().decode(unzipped["signature.sig"]).trim();
    if (!(await hmacVerify(manifestBytes, hmacKeyHex, signatureHex))) {
      errors.push("Signature verification failed — the archive is not trustworthy.");
      return { valid: false, errors, manifest: null };
    }

    const manifest = JSON.parse(new TextDecoder().decode(manifestBytes));
    for (const entry of manifest.payload ?? []) {
      const bytes = unzipped[entry.name];
      if (!bytes) {
        errors.push(`Listed payload '${entry.name}' is not in the archive.`);
      } else if (entry.sha256 && toHex(await crypto.subtle.digest("SHA-256", bytes)) !== entry.sha256) {
        errors.push(`Payload '${entry.name}' SHA-256 digest does not match the manifest.`);
      }
    }
    return { valid: errors.length === 0, errors, manifest };
  };

  const download = (blob, filename) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  window.PeakKnecPacker = { SUBJECTS, pack, validate, download };
})();
