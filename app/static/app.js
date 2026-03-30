const state = {
  lesson: null,
  currentIndex: 0,
  hintsVisible: false,
  config: null,
  lastAnswer: "",
  showAccents: true,
  typingTimer: null,
  feedbackTypingTimer: null,
  contentAnimationTimers: [],
  panelAnimationTimer: null,
};

const el = {
  backendStatus: document.querySelector("#backend-status"),
  providerStatus: document.querySelector("#provider-status"),
  lessonCard: document.querySelector("#lesson-card"),
  lessonHeader: document.querySelector(".lesson-header"),
  setupPanel: document.querySelector("#setup-panel"),
  lessonForm: document.querySelector("#lesson-form"),
  lessonTitle: document.querySelector("#lesson-title"),
  progressBox: document.querySelector(".progress-box"),
  progressCurrent: document.querySelector("#progress-current"),
  progressTotal: document.querySelector("#progress-total"),
  emptyState: document.querySelector("#empty-state"),
  promptPanel: document.querySelector("#prompt-panel"),
  englishPrompt: document.querySelector("#english-prompt"),
  answerEntry: document.querySelector("#answer-entry"),
  answerForm: document.querySelector("#answer-entry"),
  answerInput: document.querySelector("#answer-input"),
  checkBtn: document.querySelector("#check-btn"),
  skipBtn: document.querySelector("#skip-btn"),
  feedbackCard: document.querySelector("#feedback-card"),
  finalPanel: document.querySelector("#final-panel"),
  finalTitle: document.querySelector("#final-title"),
  finalEnglishStory: document.querySelector("#final-english-story"),
  finalFrenchStory: document.querySelector("#final-french-story"),
  verdictText: document.querySelector("#verdict-text"),
  correctnessScore: document.querySelector("#correctness-score"),
  correctnessBar: document.querySelector("#correctness-bar"),
  learnerAnswer: document.querySelector("#learner-answer"),
  correctFrench: document.querySelector("#correct-french"),
  phraseExplainer: document.querySelector("#phrase-explainer"),
  phraseTitle: document.querySelector("#phrase-title"),
  phraseMeaning: document.querySelector("#phrase-meaning"),
  phraseNote: document.querySelector("#phrase-note"),
  addPhraseBtn: document.querySelector("#add-phrase-btn"),
  closePhraseBtn: document.querySelector("#close-phrase-btn"),
  notesList: document.querySelector("#notes-list"),
  vocabHints: document.querySelector("#vocab-hints"),
  toggleHintsBtn: document.querySelector("#toggle-hints-btn"),
  storySoFarList: document.querySelector("#story-so-far-list"),
  storySoFarCard: document.querySelector("#story-so-far-card"),
  savedVocabList: document.querySelector("#saved-vocab-list"),
  remindersList: document.querySelector("#reminders-list"),
  exportBtn: document.querySelector("#export-btn"),
  restartBtn: document.querySelector("#restart-btn"),
};

let selectedPhraseData = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

function currentSentence() {
  return state.lesson?.sentences?.[state.currentIndex] || null;
}

function clearPromptTyping() {
  if (state.typingTimer) {
    clearTimeout(state.typingTimer);
    state.typingTimer = null;
  }
}

function clearFeedbackTyping() {
  if (state.feedbackTypingTimer) {
    clearTimeout(state.feedbackTypingTimer);
    state.feedbackTypingTimer = null;
  }
}

function clearContentAnimations() {
  state.contentAnimationTimers.forEach((timer) => clearTimeout(timer));
  state.contentAnimationTimers = [];
}

function animatePanelIn(panel) {
  if (state.panelAnimationTimer) {
    clearTimeout(state.panelAnimationTimer);
    state.panelAnimationTimer = null;
  }
  panel.classList.remove("screen-slide-in-right");
  void panel.offsetWidth;
  panel.classList.add("screen-slide-in-right");
  state.panelAnimationTimer = setTimeout(() => {
    panel.classList.remove("screen-slide-in-right");
    state.panelAnimationTimer = null;
  }, 1100);
}

function launchCelebrationBurst() {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReducedMotion || typeof window.confetti !== "function") {
    return;
  }

  const defaults = {
    spread: 70,
    ticks: 220,
    gravity: 0.9,
    decay: 0.94,
    startVelocity: 42,
    colors: ["#d36241", "#e0a33a", "#2f7d59", "#d67852", "#b24a2d", "#d8893b"],
  };

  const fire = (particleRatio, options) => {
    window.confetti({
      ...defaults,
      ...options,
      particleCount: Math.floor(180 * particleRatio),
    });
  };

  fire(0.32, { origin: { x: 0, y: 0.72 }, angle: 58 });
  fire(0.32, { origin: { x: 1, y: 0.72 }, angle: 122 });
  setTimeout(() => fire(0.2, { origin: { x: 0, y: 0.68 }, angle: 64, spread: 82 }), 120);
  setTimeout(() => fire(0.2, { origin: { x: 1, y: 0.68 }, angle: 116, spread: 82 }), 120);
  setTimeout(() => fire(0.14, { origin: { x: 0.12, y: 0.28 }, angle: 72, spread: 60, startVelocity: 32 }), 240);
  setTimeout(() => fire(0.14, { origin: { x: 0.88, y: 0.28 }, angle: 108, spread: 60, startVelocity: 32 }), 240);
}

function hideLessonScreens() {
  el.setupPanel.classList.add("hidden");
  el.promptPanel.classList.add("hidden");
  el.feedbackCard.classList.add("hidden");
  el.finalPanel.classList.add("hidden");
}

function normalizeToken(token) {
  return token
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’']/g, "")
    .replace(/[^\p{L}\p{N}]/gu, "");
}

function tokenizeWithSpaces(text) {
  return text.split(/(\s+)/);
}

function stripAccents(text) {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function formatCorrectSentence(text) {
  return state.showAccents ? text : stripAccents(text);
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function splitEdgePunctuation(token) {
  const match = token.match(/^([^\p{L}\p{N}'’]*)([\p{L}\p{N}'’-]+)([^\p{L}\p{N}'’]*)$/u);
  if (!match) {
    return { leading: "", core: token, trailing: "" };
  }
  return {
    leading: match[1],
    core: match[2],
    trailing: match[3],
  };
}

function cleanPhraseText(text) {
  return text
    .trim()
    .replace(/^[^\p{L}\p{N}'’]+/u, "")
    .replace(/[^\p{L}\p{N}'’]+$/u, "");
}

function getKnownPhrasePatterns(current) {
  const hintPatterns = (current?.vocab_hints || [])
    .map((hint) => hint.french)
    .filter(Boolean);
  const builtInPatterns = [
    "près de",
    "à côté de",
    "loin de",
    "autour de",
    "en face de",
    "au lieu de",
    "à cause de",
    "grâce à",
    "en train de",
    "tout à fait",
    "il y a",
    "parce que",
    "afin de",
    "au bout de",
    "de temps en temps",
    "eau de mer",
    "sans poser",
  ];
  return [...new Set([...hintPatterns, ...builtInPatterns])].map((phrase) => ({
    lookup: phrase,
    tokens: phrase.split(/\s+/).map(normalizeToken).filter(Boolean),
  }));
}

function splitFrenchContraction(originalCore, displayCore) {
  const contractionMatch = originalCore.match(/^([A-Za-zÀ-ÿ]+)['’](.+)$/u);
  const displayMatch = displayCore.match(/^([A-Za-zÀ-ÿ]+)['’](.+)$/u);
  const supportedPrefixes = new Set(["j", "l", "d", "c", "m", "t", "s", "n", "qu"]);
  if (!contractionMatch) {
    return null;
  }
  const prefix = normalizeToken(contractionMatch[1]);
  if (!supportedPrefixes.has(prefix)) {
    return null;
  }
  return {
    prefixOriginal: `${contractionMatch[1]}'`,
    prefixDisplay: `${displayMatch ? displayMatch[1] : contractionMatch[1]}'`,
    stemOriginal: contractionMatch[2],
    stemDisplay: displayMatch ? displayMatch[2] : contractionMatch[2],
  };
}

function buildSentenceSegments(originalSentence, displaySentence) {
  const originalWords = originalSentence.split(/\s+/);
  const displayWords = displaySentence.split(/\s+/);
  const segments = [];

  originalWords.forEach((originalWord, wordIndex) => {
    const displayWord = displayWords[wordIndex] || originalWord;
    const originalParts = splitEdgePunctuation(originalWord);
    const displayParts = splitEdgePunctuation(displayWord);

    if (displayParts.leading) {
      segments.push({ type: "text", text: displayParts.leading });
    }

    const contraction = splitFrenchContraction(originalParts.core, displayParts.core);
    if (contraction) {
      segments.push({
        type: "token",
        role: "prefix",
        displayText: contraction.prefixDisplay,
        originalText: contraction.prefixOriginal,
        normalized: normalizeToken(contraction.prefixOriginal),
      });
      segments.push({
        type: "token",
        role: "word",
        displayText: contraction.stemDisplay,
        originalText: contraction.stemOriginal,
        normalized: normalizeToken(contraction.stemOriginal),
      });
    } else if (displayParts.core) {
      segments.push({
        type: "token",
        role: "word",
        displayText: displayParts.core,
        originalText: originalParts.core,
        normalized: normalizeToken(originalParts.core),
      });
    }

    if (displayParts.trailing) {
      segments.push({ type: "text", text: displayParts.trailing });
    }

    if (wordIndex < originalWords.length - 1) {
      segments.push({ type: "text", text: " " });
    }
  });

  return segments;
}

function buildCorrectSentenceMarkup(sentence) {
  const current = currentSentence();
  const displaySentence = formatCorrectSentence(sentence);
  const segments = buildSentenceSegments(sentence, displaySentence);
  const tokenSegmentIndexes = segments
    .map((segment, index) => ({ segment, index }))
    .filter(({ segment }) => segment.type === "token");
  const patterns = getKnownPhrasePatterns(current)
    .filter((pattern) => pattern.tokens.length > 1)
    .sort((a, b) => b.tokens.length - a.tokens.length);

  const phraseMatches = new Map();
  let tokenPointer = 0;
  while (tokenPointer < tokenSegmentIndexes.length) {
    let matchedPattern = null;
    for (const pattern of patterns) {
      let valid = true;
      for (let offset = 0; offset < pattern.tokens.length; offset += 1) {
        const tokenEntry = tokenSegmentIndexes[tokenPointer + offset];
        if (!tokenEntry) {
          valid = false;
          break;
        }
        const tokenSegment = tokenEntry.segment;
        const tokenTarget = pattern.tokens[offset];
        const contractionDeMatch = tokenSegment.role === "prefix" && tokenSegment.normalized === "d" && tokenTarget === "de";
        if (tokenSegment.normalized !== tokenTarget && !contractionDeMatch) {
          valid = false;
          break;
        }
      }
      if (valid) {
        matchedPattern = pattern;
        break;
      }
    }

    if (matchedPattern) {
      phraseMatches.set(tokenPointer, matchedPattern);
      tokenPointer += matchedPattern.tokens.length;
    } else {
      tokenPointer += 1;
    }
  }

  const output = [];
  let fullSegmentPointer = 0;
  let tokenIndex = 0;

  while (tokenIndex < tokenSegmentIndexes.length) {
    const { segment, index: fullIndex } = tokenSegmentIndexes[tokenIndex];

    while (fullSegmentPointer < fullIndex) {
      output.push(escapeHtml(segments[fullSegmentPointer].text));
      fullSegmentPointer += 1;
    }

    const matchedPattern = phraseMatches.get(tokenIndex);
    if (matchedPattern) {
      const lastTokenEntry = tokenSegmentIndexes[tokenIndex + matchedPattern.tokens.length - 1];
      const displayText = segments
        .slice(fullIndex, lastTokenEntry.index + 1)
        .map((item) => (item.type === "text" ? escapeHtml(item.text) : escapeHtml(item.displayText)))
        .join("");
      output.push(
        `<button class="inline-phrase-btn" type="button" data-phrase="${escapeHtml(matchedPattern.lookup)}">${displayText}</button>`,
      );
      fullSegmentPointer = lastTokenEntry.index + 1;
      tokenIndex += matchedPattern.tokens.length;
      continue;
    }

    if (segment.role === "prefix") {
      output.push(escapeHtml(segment.displayText));
    } else {
      const cleanedPhrase = cleanPhraseText(segment.originalText);
      output.push(
        `<button class="inline-phrase-btn" type="button" data-phrase="${escapeHtml(cleanedPhrase)}">${escapeHtml(segment.displayText)}</button>`,
      );
    }

    fullSegmentPointer = fullIndex + 1;
    tokenIndex += 1;
  }

  while (fullSegmentPointer < segments.length) {
    output.push(escapeHtml(segments[fullSegmentPointer].text));
    fullSegmentPointer += 1;
  }

  return output.join("");
}

function buildLearnerAnswerMarkup(answer, correctSentence) {
  const learnerParts = tokenizeWithSpaces(answer);
  const targetParts = tokenizeWithSpaces(correctSentence);

  const learnerWords = learnerParts
    .map((part, index) => ({ part, index, normalized: normalizeToken(part) }))
    .filter((item) => item.normalized);
  const targetWords = targetParts
    .map((part, index) => ({ part, index, normalized: normalizeToken(part) }))
    .filter((item) => item.normalized);

  const dp = Array.from({ length: learnerWords.length + 1 }, () =>
    Array(targetWords.length + 1).fill(0),
  );

  for (let i = 1; i <= learnerWords.length; i += 1) {
    for (let j = 1; j <= targetWords.length; j += 1) {
      if (learnerWords[i - 1].normalized === targetWords[j - 1].normalized) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  const matchedLearnerIndices = new Set();
  let i = learnerWords.length;
  let j = targetWords.length;
  while (i > 0 && j > 0) {
    if (learnerWords[i - 1].normalized === targetWords[j - 1].normalized) {
      matchedLearnerIndices.add(learnerWords[i - 1].index);
      i -= 1;
      j -= 1;
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      i -= 1;
    } else {
      j -= 1;
    }
  }

  return learnerParts
    .map((part, index) => {
      if (!part.trim()) {
        return part;
      }
      const normalized = normalizeToken(part);
      if (!normalized) {
        return `<span class="answer-word answer-word-neutral">${part}</span>`;
      }
      const cssClass = matchedLearnerIndices.has(index) ? "answer-word-correct" : "answer-word-wrong";
      return `<span class="answer-word ${cssClass}">${part}</span>`;
    })
    .join("");
}

function buildLearnerAnswerSegments(answer, correctSentence) {
  const markup = buildLearnerAnswerMarkup(answer, correctSentence);
  return markup
    .split(/(<span class="answer-word [^"]+">.*?<\/span>)/g)
    .filter(Boolean)
    .map((part) => {
      if (part.startsWith("<span")) {
        const match = part.match(/class="([^"]+)">([\s\S]*?)<\/span>/);
        return { type: "span", className: match[1], text: match[2] };
      }
      return { type: "text", text: part };
    });
}

function buildCorrectSentenceSegments(sentence) {
  const markup = buildCorrectSentenceMarkup(sentence);
  return markup
    .split(/(<button class="inline-phrase-btn" type="button" data-phrase="[^"]+">[\s\S]*?<\/button>)/g)
    .filter(Boolean)
    .map((part) => {
      if (part.startsWith("<button")) {
        const match = part.match(/data-phrase="([^"]+)">([\s\S]*?)<\/button>/);
        return {
          type: "button",
          phrase: match[1].replace(/&quot;/g, "\"").replace(/&#39;/g, "'").replace(/&amp;/g, "&"),
          text: match[2]
            .replace(/&quot;/g, "\"")
            .replace(/&#39;/g, "'")
            .replace(/&amp;/g, "&")
            .replace(/&lt;/g, "<")
            .replace(/&gt;/g, ">"),
        };
      }
      return {
        type: "text",
        text: part
          .replace(/&quot;/g, "\"")
          .replace(/&#39;/g, "'")
          .replace(/&amp;/g, "&")
          .replace(/&lt;/g, "<")
          .replace(/&gt;/g, ">"),
      };
    });
}

function buildConciseNotes(feedback) {
  const rawNotes = [...(feedback.mistakes || []), ...(feedback.tips || [])]
    .map((note) => note.trim())
    .filter(Boolean);
  const uniqueNotes = [];
  const seen = new Set();

  rawNotes.forEach((note) => {
    const key = note.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      uniqueNotes.push(note);
    }
  });

  const limit = feedback.is_correct ? 1 : 2;
  const concise = uniqueNotes.slice(0, limit);

  if (!concise.length) {
    return ["No major issues highlighted."];
  }

  return concise;
}

function isFeedbackVisible() {
  return !el.feedbackCard.classList.contains("hidden");
}

function isPromptVisible() {
  return !el.promptPanel.classList.contains("hidden");
}

function renderSetupView(message = "") {
  clearPromptTyping();
  clearFeedbackTyping();
  clearContentAnimations();
  state.lesson = null;
  state.currentIndex = 0;
  state.lastAnswer = "";
  el.lessonCard.classList.remove("hidden");
  el.lessonHeader.classList.remove("hidden");
  el.progressBox.classList.add("hidden");
  hideLessonScreens();
  el.setupPanel.classList.remove("hidden");
  el.emptyState.classList.toggle("hidden", !message);
  el.emptyState.innerHTML = `<p>${message || "Choose a difficulty, theme, and lesson mode to generate your first connected sequence."}</p>`;
  el.lessonTitle.textContent = "Choose your story.";
  el.progressCurrent.textContent = "0";
  el.progressTotal.textContent = "0";
  el.storySoFarCard.classList.add("hidden");
  scrollWindowToTop();
}

function focusAnswerInput() {
  requestAnimationFrame(() => {
    el.answerInput.focus();
    el.answerInput.setSelectionRange(el.answerInput.value.length, el.answerInput.value.length);
  });
}

function closePhraseExplainer() {
  el.phraseExplainer.classList.add("hidden");
  selectedPhraseData = null;
}

function scrollWindowToTop() {
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
}

function animatePromptText(text) {
  clearPromptTyping();

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReducedMotion) {
    el.englishPrompt.textContent = text;
    return;
  }

  const characters = Array.from(text);
  let index = 0;
  el.englishPrompt.textContent = "";

  const getTypingDelay = (currentChar, previousChar) => {
    if (!currentChar) {
      return 0;
    }

    if (/\s/.test(currentChar)) {
      return 10 + Math.random() * 12;
    }

    if (/[,.!?;:]/.test(currentChar)) {
      return 36 + Math.random() * 24;
    }

    if (/["'()]/.test(currentChar)) {
      return 12 + Math.random() * 14;
    }

    let delay = 8 + Math.random() * 10;
    if (previousChar && /[\s"'(]/.test(previousChar)) {
      delay += 5 + Math.random() * 6;
    }
    return delay;
  };

  const typeNext = () => {
    const nextChar = characters[index];
    const previousChar = index > 0 ? characters[index - 1] : "";
    index += 1;
    el.englishPrompt.textContent += nextChar;
    if (index < characters.length) {
      state.typingTimer = setTimeout(typeNext, getTypingDelay(characters[index], previousChar));
    } else {
      state.typingTimer = null;
    }
  };

  state.typingTimer = setTimeout(typeNext, 12);
}

function animateFeedbackLabel(text) {
  clearFeedbackTyping();

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReducedMotion) {
    el.verdictText.textContent = text;
    return 0;
  }

  const characters = Array.from(text);
  let index = 0;
  el.verdictText.textContent = "";

  let totalDelay = 0;
  for (let charIndex = 0; charIndex < characters.length - 1; charIndex += 1) {
    const previousChar = characters[charIndex];
    const nextChar = characters[charIndex + 1];
    let delay = 7 + Math.random() * 8;
    if (/\s/.test(nextChar)) {
      delay = 9 + Math.random() * 8;
    } else if (/[,.!?;:]/.test(nextChar)) {
      delay = 22 + Math.random() * 16;
    } else if (previousChar && /[\s"'(]/.test(previousChar)) {
      delay += 4 + Math.random() * 4;
    }
    totalDelay += delay;
  }

  const typeNext = () => {
    el.verdictText.textContent += characters[index];
    index += 1;
    if (index < characters.length) {
      const previousChar = characters[index - 1];
      const nextChar = characters[index];
      let delay = 7 + Math.random() * 8;
      if (/\s/.test(nextChar)) {
        delay = 9 + Math.random() * 8;
      } else if (/[,.!?;:]/.test(nextChar)) {
        delay = 22 + Math.random() * 16;
      } else if (previousChar && /[\s"'(]/.test(previousChar)) {
        delay += 4 + Math.random() * 4;
      }
      state.feedbackTypingTimer = setTimeout(typeNext, delay);
    } else {
      state.feedbackTypingTimer = null;
    }
  };

  state.feedbackTypingTimer = setTimeout(typeNext, 0);
  return totalDelay;
}

function animateInlineSegments(target, segments, startDelay = 0, baseDelay = 24) {
  target.innerHTML = "";
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (prefersReducedMotion) {
    segments.forEach((segment) => {
      if (segment.type === "text") {
        target.append(document.createTextNode(segment.text));
        return;
      }
      const node = document.createElement(segment.type === "button" ? "button" : "span");
      if (segment.type === "button") {
        node.type = "button";
        node.className = "inline-phrase-btn";
        node.dataset.phrase = segment.phrase;
      } else {
        node.className = segment.className;
      }
      node.textContent = segment.text;
      target.append(node);
    });
    return 0;
  }

  let delay = startDelay;
  segments.forEach((segment) => {
    const timer = setTimeout(() => {
      if (segment.type === "text") {
        target.append(document.createTextNode(segment.text));
        return;
      }
      const node = document.createElement(segment.type === "button" ? "button" : "span");
      if (segment.type === "button") {
        node.type = "button";
        node.className = "inline-phrase-btn";
        node.dataset.phrase = segment.phrase;
      } else {
        node.className = segment.className;
      }
      node.textContent = segment.text;
      target.append(node);
    }, delay);
    state.contentAnimationTimers.push(timer);
    delay += segment.type === "text" && /\s+/.test(segment.text) ? baseDelay * 0.4 : baseDelay;
  });
  return delay;
}

function animateNotesList(notes, startDelay = 0) {
  el.notesList.innerHTML = "";
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (prefersReducedMotion) {
    notes.forEach((note) => {
      const li = document.createElement("li");
      li.textContent = note;
      el.notesList.appendChild(li);
    });
    return 0;
  }

  let noteDelay = startDelay;
  notes.forEach((note) => {
    const li = document.createElement("li");
    el.notesList.appendChild(li);
    const chars = Array.from(note);
    let index = 0;

    const typeNext = () => {
      li.textContent += chars[index];
      index += 1;
      if (index < chars.length) {
        let delay = 7 + Math.random() * 6;
        if (/\s/.test(chars[index])) {
          delay = 4 + Math.random() * 3;
        } else if (/[,.!?;:]/.test(chars[index])) {
          delay = 16 + Math.random() * 10;
        }
        const timer = setTimeout(typeNext, delay);
        state.contentAnimationTimers.push(timer);
      }
    };

    const starter = setTimeout(typeNext, noteDelay);
    state.contentAnimationTimers.push(starter);
    noteDelay += note.length * 6 + 90;
  });
  return noteDelay;
}

function renderLesson() {
  clearContentAnimations();
  const sentence = currentSentence();
  const total = state.lesson?.sentences?.length || 0;
  el.progressCurrent.textContent = sentence ? String(state.currentIndex + 1) : "0";
  el.progressTotal.textContent = String(total);

  if (!sentence) {
    renderSetupView("Lesson complete. Adjust the settings above if you want a fresh story or dialogue.");
    return;
  }

  el.lessonCard.classList.remove("hidden");
  el.lessonHeader.classList.remove("hidden");
  el.progressBox.classList.remove("hidden");
  hideLessonScreens();
  el.emptyState.classList.add("hidden");
  el.promptPanel.classList.remove("hidden");
  el.verdictText.textContent = "Waiting for your answer";
  el.lessonTitle.textContent = state.lesson.title;
  animatePromptText(`"${sentence.english}"`);
  el.answerInput.value = "";
  closePhraseExplainer();
  state.hintsVisible = false;
  renderHints();
  renderStorySoFar();
  animatePanelIn(el.promptPanel);
  focusAnswerInput();
  scrollWindowToTop();
}

function renderHints() {
  const sentence = currentSentence();
  const hints = sentence?.vocab_hints || [];
  el.vocabHints.innerHTML = "";

  if (!hints.length) {
    el.toggleHintsBtn.textContent = "No vocab hints needed";
    el.toggleHintsBtn.disabled = true;
    el.vocabHints.classList.add("hidden");
    return;
  }

  el.toggleHintsBtn.disabled = false;
  el.toggleHintsBtn.textContent = state.hintsVisible ? "Hide vocab hints" : "Show vocab hints";

  hints.forEach((hint) => {
    const div = document.createElement("div");
    div.className = "vocab-hint";
    div.innerHTML = `<strong>${hint.english}</strong> -> ${hint.french}${hint.note ? `<div>${hint.note}</div>` : ""}`;
    el.vocabHints.appendChild(div);
  });

  el.vocabHints.classList.toggle("hidden", !state.hintsVisible);
}

function renderFeedback(feedback) {
  clearPromptTyping();
  clearFeedbackTyping();
  clearContentAnimations();
  el.lessonCard.classList.remove("hidden");
  el.lessonHeader.classList.add("hidden");
  el.storySoFarCard.classList.add("hidden");
  el.storySoFarList.innerHTML = "";
  hideLessonScreens();
  el.feedbackCard.classList.remove("hidden");
  animatePanelIn(el.feedbackCard);
  const verdictDuration = animateFeedbackLabel(feedback.verdict);
  el.correctnessScore.textContent = String(feedback.correctness_score);
  el.correctnessBar.classList.remove("score-bar-fill-animate");
  el.correctnessBar.style.width = "0%";
  void el.correctnessBar.offsetWidth;
  requestAnimationFrame(() => {
    el.correctnessBar.style.width = `${Math.max(0, Math.min(100, feedback.correctness_score))}%`;
    el.correctnessBar.classList.add("score-bar-fill-animate");
  });
  el.learnerAnswer.innerHTML = buildLearnerAnswerMarkup(state.lastAnswer || "No answer entered.", feedback.suggested_french);
  el.correctFrench.innerHTML = buildCorrectSentenceMarkup(feedback.suggested_french);
  closePhraseExplainer();

  const finalNotes = buildConciseNotes(feedback);
  const notes = [...finalNotes];
  if (feedback.reminders_triggered?.length) {
    notes.push(`Reminder added: ${feedback.reminders_triggered.join(", ")}`);
  }
  animateNotesList(notes, 0);

  scrollWindowToTop();
}

function renderFinalPanel() {
  if (!state.lesson) {
    renderSetupView();
    return;
  }

  clearPromptTyping();
  clearFeedbackTyping();
  clearContentAnimations();
  el.lessonCard.classList.remove("hidden");
  el.lessonHeader.classList.add("hidden");
  el.storySoFarCard.classList.add("hidden");
  el.storySoFarList.innerHTML = "";
  hideLessonScreens();
  el.finalPanel.classList.remove("hidden");
  el.emptyState.classList.add("hidden");
  el.finalTitle.textContent = state.lesson.title;
  el.finalEnglishStory.textContent = state.lesson.sentences.map((sentence) => sentence.english).join(" ");
  el.finalFrenchStory.textContent = state.lesson.sentences.map((sentence) => formatCorrectSentence(sentence.french)).join(" ");
  animatePanelIn(el.finalPanel);
  launchCelebrationBurst();
  scrollWindowToTop();
}

async function explainPhrase(phrase) {
  const sentence = currentSentence();
  if (!sentence) return;

  const data = await api("/api/explain-phrase", {
    method: "POST",
    body: JSON.stringify({
      english_sentence: sentence.english,
      french_sentence: sentence.french,
      selected_phrase: phrase,
      difficulty: state.lesson.difficulty,
      vocab_hints: sentence.vocab_hints || [],
    }),
  });

  selectedPhraseData = {
    english: data.english_meaning,
    french: phrase,
    note: data.save_note || data.usage_note || "",
    source_sentence: sentence.english,
  };

  el.phraseTitle.textContent = phrase;
  el.phraseMeaning.textContent = data.english_meaning;
  el.phraseNote.textContent = data.usage_note || data.save_note || "";
  el.phraseExplainer.classList.remove("hidden");
}

function renderSavedVocab(items) {
  el.savedVocabList.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty-vocab";
    empty.textContent = "No saved vocabulary yet. Save hints or useful phrases as you go.";
    el.savedVocabList.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const div = document.createElement("div");
    div.className = "saved-vocab-item";
    div.innerHTML = `
      <div><strong>${item.french}</strong> -> ${item.english}</div>
      ${item.note ? `<div>${item.note}</div>` : ""}
      ${item.source_sentence ? `<div><em>${item.source_sentence}</em></div>` : ""}
    `;
    el.savedVocabList.appendChild(div);
  });
}

function renderStorySoFar() {
  el.storySoFarList.innerHTML = "";
  if (!state.lesson) {
    el.storySoFarCard.classList.add("hidden");
    return;
  }

  const completedCount = state.currentIndex;
  if (completedCount === 0) {
    el.storySoFarCard.classList.add("hidden");
    return;
  }

  el.storySoFarCard.classList.remove("hidden");

  const previousSentences = state.lesson.sentences.slice(0, completedCount);
  const englishParagraph = previousSentences.map((sentence) => sentence.english).join(" ");

  const storyBlock = document.createElement("div");
  storyBlock.className = "story-so-far-block";
  storyBlock.innerHTML = `
    <div class="story-line-text">${englishParagraph}</div>
  `;

  el.storySoFarList.appendChild(storyBlock);
}

async function loadConfig() {
  try {
    const config = await api("/api/config");
    state.config = config;
    el.backendStatus.textContent = "Backend ready";
    el.providerStatus.textContent = config.openai_enabled ? "OpenAI mode enabled" : "Fallback demo mode";
  } catch (error) {
    el.backendStatus.textContent = "Backend not reachable";
    el.providerStatus.textContent = "Start the FastAPI server";
  }
}

async function loadVocab() {
  const data = await api("/api/vocab");
  renderSavedVocab(data.items);
}

function renderReminders(items) {
  el.remindersList.innerHTML = "";
  const repeated = items.filter((item) => item.count >= 2);

  if (!repeated.length) {
    const empty = document.createElement("div");
    empty.className = "empty-vocab";
    empty.textContent = "Repeated errors will start appearing here once the app spots a pattern more than once.";
    el.remindersList.appendChild(empty);
    return;
  }

  repeated.forEach((item) => {
    const div = document.createElement("div");
    div.className = "reminder-item";
    div.innerHTML = `
      <div>
        <strong>${item.label}</strong>
        <span class="reminder-count">${item.count}x</span>
      </div>
      <div>${item.explanation}</div>
      <div><em>Latest target:</em> ${item.last_target}</div>
      <div><em>Your latest answer:</em> ${item.last_answer}</div>
    `;
    el.remindersList.appendChild(div);
  });
}

async function loadReminders() {
  const data = await api("/api/reminders");
  renderReminders(data.items);
}

async function generateLesson(event) {
  event.preventDefault();
  const button = document.querySelector("#generate-btn");
  button.disabled = true;

  try {
    const lessonLength = document.querySelector("#lesson-length").value;
    const sentenceCountMap = {
      short: 5,
      medium: 8,
      long: 12,
    };
    const payload = {
      difficulty: document.querySelector("#difficulty").value,
      lesson_type: document.querySelector("#lesson-type").value,
      theme: document.querySelector("#theme").value.trim() || "mythological mystery",
      sentence_count: sentenceCountMap[lessonLength] || 8,
    };
    state.showAccents = document.querySelector("#show-accents").value === "show";
    const lesson = await api("/api/lesson", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.lesson = lesson;
    state.currentIndex = 0;
    state.lastAnswer = "";
    renderLesson();
  } catch (error) {
    alert(`Could not generate lesson: ${error.message}`);
  } finally {
    button.disabled = false;
  }
}

async function evaluateCurrentAnswer() {
  const sentence = currentSentence();
  if (!sentence) return;

  const learnerAnswer = el.answerInput.value.trim();
  if (!learnerAnswer) {
    alert("Enter a French answer first.");
    return;
  }

  el.checkBtn.disabled = true;
  try {
    state.lastAnswer = learnerAnswer;
    const feedback = await api("/api/evaluate", {
      method: "POST",
      body: JSON.stringify({
        english: sentence.english,
        target_french: sentence.french,
        learner_answer: learnerAnswer,
        difficulty: state.lesson.difficulty,
        context_note: sentence.context_note,
      }),
    });
    renderFeedback(feedback);
    await loadReminders();
  } catch (error) {
    alert(`Could not evaluate answer: ${error.message}`);
  } finally {
    el.checkBtn.disabled = false;
  }
}

function nextSentence() {
  if (!state.lesson) return;
  if (state.currentIndex < state.lesson.sentences.length - 1) {
    state.currentIndex += 1;
    renderLesson();
    return;
  }
  renderFinalPanel();
}

function revealAndSkip() {
  const sentence = currentSentence();
  if (!sentence) return;
  state.lastAnswer = "";
  renderFeedback({
    verdict: "Revealed target answer.",
    correctness_score: 0,
    naturalness_score: 0,
    suggested_french: sentence.french,
    more_common_french: sentence.french,
    tips: ["Read the target answer aloud once before moving on."],
    mistakes: [],
    encouraging_note: "Skipping quickly is fine when you want to keep the lesson flowing.",
  });
}

async function addSelectedPhraseToVocab() {
  if (!selectedPhraseData) return;
  await api("/api/vocab", {
    method: "POST",
    body: JSON.stringify(selectedPhraseData),
  });
  await loadVocab();
  closePhraseExplainer();
}

async function exportVocab() {
  const csv = await api("/api/vocab/export");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "french_story_trainer_anki.csv";
  link.click();
  URL.revokeObjectURL(url);
}

el.lessonForm.addEventListener("submit", generateLesson);
el.checkBtn.addEventListener("click", evaluateCurrentAnswer);
el.skipBtn.addEventListener("click", revealAndSkip);
el.correctFrench.addEventListener("click", async (event) => {
  const target = event.target.closest(".inline-phrase-btn");
  if (!target) return;
  await explainPhrase(target.dataset.phrase);
});
el.toggleHintsBtn.addEventListener("click", () => {
  state.hintsVisible = !state.hintsVisible;
  renderHints();
});
el.addPhraseBtn.addEventListener("click", addSelectedPhraseToVocab);
el.closePhraseBtn.addEventListener("click", closePhraseExplainer);
el.exportBtn.addEventListener("click", exportVocab);
el.restartBtn.addEventListener("click", () => renderSetupView());

function handleGlobalEnter(event) {
  if (
    event.key !== "Enter" ||
    event.shiftKey ||
    event.ctrlKey ||
    event.metaKey ||
    event.altKey ||
    event.isComposing
  ) {
    return;
  }

  const activeElement = document.activeElement;

  if (isPromptVisible() && activeElement === el.answerInput) {
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
    }
    evaluateCurrentAnswer();
    return;
  }

  if (isFeedbackVisible()) {
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
    }
    nextSentence();
  }
}

document.addEventListener("keydown", handleGlobalEnter, true);

loadConfig();
loadVocab();
loadReminders();
renderStorySoFar();
renderSetupView();
