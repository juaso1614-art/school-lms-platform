(() => {
  const timerOutput = document.querySelector("#quiz-timer-count");
  const timerChip = document.querySelector("#quiz-timer");
  const timerBar = document.querySelector("#quiz-timer-bar");
  const streakOutput = document.querySelector("#quiz-streak-count");
  const bestStreakOutput = document.querySelector("#quiz-best-streak-count");
  const panel = document.querySelector(".game-question-panel");
  const questionTotalNode = document.querySelector("#quiz-question-total");
  if (!timerOutput || !streakOutput) return;

  const questionTotal = Number(questionTotalNode?.textContent ?? "0");
  if (!questionTotal) return;

  const streakKey = `peak-quiz-streak-${window.location.pathname}`;
  let streak = Number(window.sessionStorage.getItem(streakKey) ?? "0");
  let best = Number(window.sessionStorage.getItem(`${streakKey}-best`) ?? "0");
  streakOutput.value = String(streak);
  if (bestStreakOutput) bestStreakOutput.value = String(best);

  const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;
  const beep = (frequencies, gap = 0.12) => {
    if (!AudioContextConstructor) return;
    const context = beep.context ??= new AudioContextConstructor();
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

  const feedback = document.querySelector(".game-feedback");
  const justPassed = document.querySelector(".success-note");
  if (feedback?.classList.contains("error") || panel?.classList.contains("is-wrong-answer")) {
    streak = 0;
    window.sessionStorage.setItem(streakKey, "0");
    streakOutput.value = "0";
    beep([196, 165], 0.16);
  } else if (justPassed?.textContent.includes("Correct!") || panel?.classList.contains("is-correct-answer")) {
    streak += 1;
    best = Math.max(best, streak);
    window.sessionStorage.setItem(streakKey, String(streak));
    window.sessionStorage.setItem(`${streakKey}-best`, String(best));
    streakOutput.value = String(streak);
    if (bestStreakOutput) bestStreakOutput.value = String(best);
    beep([523.25, 659.25, 783.99]);
  } else {
    beep([440], 0.08);
  }

  const secondsLeft = { value: 30 };
  timerOutput.value = "30";
  const interval = window.setInterval(() => {
    secondsLeft.value -= 1;
    timerOutput.value = String(Math.max(secondsLeft.value, 0));
    if (timerBar) timerBar.style.transform = `scaleX(${Math.max(secondsLeft.value / 30, 0)})`;
    if (secondsLeft.value <= 5) timerChip?.classList.add("is-low");
    if (secondsLeft.value <= 0) {
      window.clearInterval(interval);
      timerChip?.classList.add("is-expired");
    }
  }, 1000);
})();
