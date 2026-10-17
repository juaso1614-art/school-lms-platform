(() => {
  const dataNode = document.querySelector("#game-activity-data");
  if (!dataNode) return;

  let cards = [];
  try {
    cards = JSON.parse(dataNode.textContent || "[]");
  } catch (error) {
    cards = [];
  }
  if (!cards.length) return;

  const scoreNode = document.querySelector("#activity-score");
  const donePanel = document.querySelector("#activity-done");
  const doneSummary = document.querySelector("#activity-done-summary");
  const doneScore = document.querySelector("#activity-done-score");
  const doneAttempts = document.querySelector("#activity-done-attempts");
  const track = document.querySelector("#activity-progress-track");
  const mode = document.querySelector(".flashcard-panel") ? "flashcards" : "matching";

  const sound = (frequencies, gap = 0.12) => {
    const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextConstructor) return;
    if (!sound.context) sound.context = new AudioContextConstructor();
    const context = sound.context;
    if (context.state === "suspended") void context.resume();
    let start = context.currentTime;
    frequencies.forEach((frequency) => {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0.14, start);
      gain.gain.exponentialRampToValueAtTime(0.001, start + gap);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(start);
      oscillator.stop(start + gap);
      start += gap;
    });
  };
  const happySound = () => sound([523.25, 659.25, 783.99]);
  const missSound = () => sound([196, 165], 0.16);

  function renderTrack(done, total) {
    if (!track) return;
    track.replaceChildren(...Array.from({ length: total }, (_, index) => {
      const step = document.createElement("span");
      if (index < done) step.className = "is-complete";
      else if (index === done) step.className = "is-current";
      step.textContent = String(index + 1);
      return step;
    }));
  }

  function finish(earned, attempts) {
    if (!donePanel) return;
    sound.context?.resume?.();
    happySound();
    doneScore.value = String(earned);
    doneAttempts.value = String(attempts);
    if (doneSummary) doneSummary.textContent = `You earned ${earned} points this round. Save them to your Games Corner score.`;
    if (scoreNode) scoreNode.textContent = `${Number(scoreNode.textContent.split(" ")[0]) + earned} pts`;
    donePanel.hidden = false;
    donePanel.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  if (mode === "flashcards") {
    let index = 0;
    const seen = new Set();
    const card = document.querySelector("#flashcard");
    const promptNode = document.querySelector("#flashcard-prompt");
    const answerNode = document.querySelector("#flashcard-answer");
    const explanationNode = document.querySelector("#flashcard-explanation");
    const countNode = document.querySelector("#flashcard-count");
    const prevButton = document.querySelector("#flashcard-prev");
    const nextButton = document.querySelector("#flashcard-next");
    let flipped = false;

    const show = () => {
      const cardData = cards[index];
      if (!cardData) return;
      flipped = false;
      card?.classList.remove("is-flipped");
      if (promptNode) promptNode.textContent = cardData.prompt;
      if (answerNode) answerNode.textContent = cardData.answer;
      if (explanationNode) explanationNode.textContent = cardData.explanation || "";
      if (countNode) countNode.textContent = `Card ${index + 1} of ${cards.length}`;
      renderTrack(seen.size, cards.length);
    };

    const flip = () => {
      flipped = !flipped;
      card?.classList.toggle("is-flipped", flipped);
      if (flipped) {
        seen.add(index);
        sound([660], 0.08);
        if (countNode) countNode.textContent = `Card ${index + 1} of ${cards.length}`;
        renderTrack(seen.size, cards.length);
        if (seen.size === cards.length && donePanel?.hidden) {
          finish(seen.size * 10, seen.size);
        }
      }
    };

    card?.addEventListener("click", flip);
    card?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        flip();
      }
    });
    prevButton?.addEventListener("click", () => {
      index = (index - 1 + cards.length) % cards.length;
      show();
    });
    nextButton?.addEventListener("click", () => {
      index = (index + 1) % cards.length;
      show();
    });
    show();
  } else {
    const promptList = document.querySelector("#matching-prompts");
    const answerList = document.querySelector("#matching-answers");
    const pairedNode = document.querySelector("#matching-paired");
    const missesNode = document.querySelector("#matching-misses");
    let selectedPrompt = null;
    let misses = 0;
    let paired = 0;
    let locked = false;

    const shuffled = cards.map((cardData, position) => ({ cardData, position }))
      .sort(() => Math.random() - 0.5);

    cards.forEach((cardData, position) => {
      const item = document.createElement("li");
      item.className = "matching-tile";
      item.tabIndex = 0;
      item.dataset.position = String(position);
      item.textContent = cardData.prompt;
      item.setAttribute("role", "button");
      item.setAttribute("aria-label", `Prompt ${position + 1}`);
      promptList?.appendChild(item);
    });
    shuffled.forEach(({ cardData, position }) => {
      const item = document.createElement("li");
      item.className = "matching-tile";
      item.tabIndex = 0;
      item.dataset.position = String(position);
      item.textContent = cardData.answer;
      item.setAttribute("role", "button");
      item.setAttribute("aria-label", `Answer option`);
      answerList?.appendChild(item);
    });

    renderTrack(0, cards.length);

    const choose = (event) => {
      const tile = event.target.closest(".matching-tile");
      if (!tile || locked || tile.classList.contains("is-paired")) return;
      event.preventDefault();

      const column = tile.closest(".matching-column");
      if (column?.id === "matching-prompts") {
        selectedPrompt?.classList.remove("is-selected");
        selectedPrompt = tile;
        tile.classList.add("is-selected");
        return;
      }
      if (!selectedPrompt) return;

      if (tile.dataset.position === selectedPrompt.dataset.position) {
        tile.classList.add("is-paired");
        selectedPrompt.classList.remove("is-selected");
        selectedPrompt.classList.add("is-paired");
        selectedPrompt = null;
        paired += 1;
        happySound();
        if (pairedNode) pairedNode.textContent = `${paired} of ${cards.length} matched`;
        renderTrack(paired, cards.length);
        if (paired === cards.length && donePanel?.hidden) {
          finish(Math.max(cards.length * 10 - misses * 2, 0), paired + misses);
        }
      } else {
        misses += 1;
        missSound();
        if (missesNode) missesNode.textContent = `${misses} misses`;
        tile.classList.add("is-wrong");
        selectedPrompt.classList.add("is-wrong");
        window.setTimeout(() => {
          tile.classList.remove("is-wrong");
          selectedPrompt?.classList.remove("is-wrong");
        }, 450);
      }
    };

    document.querySelector(".matching-panel")?.addEventListener("click", choose);
    document.querySelector(".matching-panel")?.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      if (event.target.classList?.contains("matching-tile")) choose(event);
    });
  }
})();
