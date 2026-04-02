const state = {
  language: "french",
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
  correctnessAnimationFrame: null,
  nextTransitionInProgress: false,
  storyFlightCleanupTimer: null,
  storyFlightFinishTimer: null,
  lessonPollTimer: null,
  lessonPollInFlight: false,
  checkingEllipsisTimer: null,
  generatingEllipsisTimer: null,
  generatingCopyTimer: null,
  generatingWaveTimer: null,
  devVersion: null,
  devReloadTimer: null,
  lastCheckingTipIndex: -1,
  checkingTipsLessonId: null,
  usedCheckingTipIndexes: {},
  checkingTipQueueByDifficulty: {},
};

const el = {
  lessonCard: document.querySelector("#lesson-card"),
  lessonHeader: document.querySelector(".lesson-header"),
  setupPanel: document.querySelector("#setup-panel"),
  lessonForm: document.querySelector("#lesson-form"),
  lessonTitle: document.querySelector("#lesson-title"),
  heroCopy: document.querySelector("#hero-copy"),
  languageSwitch: document.querySelector("#language-switch"),
  languageFrenchBtn: document.querySelector("#language-french-btn"),
  languageSpanishBtn: document.querySelector("#language-spanish-btn"),
  progressBox: document.querySelector(".progress-box"),
  progressCurrent: document.querySelector("#progress-current"),
  progressTotal: document.querySelector("#progress-total"),
  emptyState: document.querySelector("#empty-state"),
  generatingPanel: document.querySelector("#generating-panel"),
  generatingCopy: document.querySelector("#generating-copy"),
  generatingEllipsis: document.querySelector("#generating-ellipsis"),
  promptPanel: document.querySelector("#prompt-panel"),
  contextNote: document.querySelector("#context-note"),
  englishPrompt: document.querySelector("#english-prompt"),
  hintShortcutCopy: document.querySelector("#hint-shortcut-copy"),
  answerEntry: document.querySelector("#answer-entry"),
  answerForm: document.querySelector("#answer-entry"),
  answerInput: document.querySelector("#answer-input"),
  checkBtn: document.querySelector("#check-btn"),
  skipBtn: document.querySelector("#skip-btn"),
  checkingPanel: document.querySelector("#checking-panel"),
  checkingCopy: document.querySelector(".checking-copy"),
  checkingEllipsis: document.querySelector("#checking-ellipsis"),
  feedbackCard: document.querySelector("#feedback-card"),
  finalPanel: document.querySelector("#final-panel"),
  finalTitle: document.querySelector("#final-title"),
  finalEnglishStory: document.querySelector("#final-english-story"),
  finalFrenchStory: document.querySelector("#final-french-story"),
  verdictText: document.querySelector("#verdict-text"),
  correctnessScore: document.querySelector("#correctness-score"),
  correctnessBar: document.querySelector("#correctness-bar"),
  feedbackQuestionLabel: document.querySelector("#feedback-question-label"),
  feedbackQuestionText: document.querySelector("#feedback-question-text"),
  yourAnswerLabel: document.querySelector("#your-answer-label"),
  learnerAnswer: document.querySelector("#learner-answer"),
  correctSentenceLabel: document.querySelector("#correct-sentence-label"),
  correctFrench: document.querySelector("#correct-french"),
  phraseExplainer: document.querySelector("#phrase-explainer"),
  phraseTitle: document.querySelector("#phrase-title"),
  phraseMeaning: document.querySelector("#phrase-meaning"),
  phraseNote: document.querySelector("#phrase-note"),
  addPhraseBtn: document.querySelector("#add-phrase-btn"),
  closePhraseBtn: document.querySelector("#close-phrase-btn"),
  feedbackNotesLabel: document.querySelector("#feedback-notes-label"),
  notesList: document.querySelector("#notes-list"),
  vocabHints: document.querySelector("#vocab-hints"),
  toggleHintsBtn: document.querySelector("#toggle-hints-btn"),
  storySoFarList: document.querySelector("#story-so-far-list"),
  storySoFarCard: document.querySelector("#story-so-far-card"),
  savedVocabList: document.querySelector("#saved-vocab-list"),
  remindersList: document.querySelector("#reminders-list"),
  exportBtn: document.querySelector("#export-btn"),
  restartBtn: document.querySelector("#restart-btn"),
  appMasthead: document.querySelector("#app-masthead"),
  sidebarHomeBtn: document.querySelector("#sidebar-home-btn"),
  sidebarLessonTitle: document.querySelector("#sidebar-lesson-title"),
  sidebarTheme: document.querySelector("#sidebar-theme"),
  sidebarLanguage: document.querySelector("#sidebar-language"),
  sidebarDifficulty: document.querySelector("#sidebar-difficulty"),
  sidebarProgress: document.querySelector("#sidebar-progress"),
  sidebarVocabCount: document.querySelector("#sidebar-vocab-count"),
  sidebarReminderCount: document.querySelector("#sidebar-reminder-count"),
};

let selectedPhraseData = null;

const CHECKING_TIPS_BY_LEVEL = {
  A1: [
    "Helpful tip: \"J'ai\" means \"I have\" and is one of the most common starter phrases.",
    "Helpful tip: French usually needs an article, like \"un\", \"une\", or \"le\", where English may be looser.",
    "Helpful tip: \"Je suis\" means \"I am,\" but use \"j'ai\" for age: \"j'ai vingt ans\".",
    "Helpful tip: Common survival phrase: \"Je voudrais...\" means \"I would like...\".",
    "Helpful tip: Many basic adjectives come after the noun, like \"un livre interessant\".",
    "Helpful tip: \"Il y a\" means \"there is\" or \"there are\" and shows up everywhere.",
    "Helpful tip: \"C'est\" is one of the easiest ways to say \"it is\" or \"this is\".",
    "Helpful tip: \"Je m'appelle...\" means \"My name is...\" and is worth memorizing early.",
    "Helpful tip: French often uses \"est-ce que\" to make a simple question.",
    "Helpful tip: \"Merci beaucoup\" is stronger than just \"merci\" and sounds very natural.",
    "Helpful tip: \"Voici\" means \"here is\" and \"voila\" means \"there is\" or \"there you go\".",
    "Helpful tip: \"Je ne comprends pas\" is a very useful phrase when you are stuck.",
    "Helpful tip: Days and months in French do not usually take capital letters.",
    "Helpful tip: \"Il est\" is used for time, like \"il est deux heures\".",
    "Helpful tip: \"Dans\" often means \"in\" or \"inside\", while \"a\" can mean \"to\" or \"at\".",
    "Helpful tip: French often keeps subject pronouns explicit: \"je\", \"tu\", \"il\", \"elle\".",
    "Helpful tip: \"J'aime\" means \"I like\" or \"I love\", depending on context.",
    "Helpful tip: \"Un\" and \"une\" are not interchangeable, so noun gender matters from the start.",
    "Helpful tip: \"Comment ca va ?\" is a common way to ask how someone is doing.",
    "Helpful tip: \"Je voudrais\" usually sounds more polite than \"je veux\" in requests.",
  ],
  A2: [
    "Helpful tip: After \"aimer\", \"vouloir\", and \"pouvoir\", French often uses an infinitive: \"je veux partir\".",
    "Helpful tip: \"Chez\" often means \"at the home or place of\", as in \"chez moi\" or \"chez le medecin\".",
    "Helpful tip: Use \"aller + infinitive\" for the near future, like \"je vais partir\".",
    "Helpful tip: \"Parce que\" introduces a reason, while \"pour\" is often followed by a noun or infinitive.",
    "Helpful tip: Useful phrase: \"On y va ?\" means \"Shall we go?\" or \"Are we going?\".",
    "Helpful tip: In negation, French usually wraps the verb: \"je ne sais pas\".",
    "Helpful tip: \"Il faut\" is an easy structure for saying what is necessary.",
    "Helpful tip: \"Depuis\" is often used for something that started in the past and is still true now.",
    "Helpful tip: \"Toujours\" means \"always\", while \"encore\" can mean \"still\" or \"again\".",
    "Helpful tip: \"Rien\" means \"nothing\" and often appears with negation: \"je ne vois rien\".",
    "Helpful tip: \"Personne\" can mean \"nobody\" in negative sentences: \"il n'y a personne\".",
    "Helpful tip: \"Quelqu'un\" means \"someone\" and is extremely common in everyday French.",
    "Helpful tip: \"Tout le monde\" means \"everyone\" and behaves like a singular idea.",
    "Helpful tip: \"Avant de\" is followed by an infinitive, like \"avant de partir\".",
    "Helpful tip: \"Apres avoir\" or \"apres etre\" often helps connect two actions naturally.",
    "Helpful tip: \"En train de\" is useful when you want to stress that something is happening right now.",
    "Helpful tip: \"Je viens de...\" means \"I have just...\" and is common in conversation.",
    "Helpful tip: \"Connaître\" is for being familiar with people or places; \"savoir\" is for facts and skills.",
    "Helpful tip: \"Mieux\" means \"better\" as an adverb, while \"meilleur\" is an adjective.",
    "Helpful tip: French often uses reflexive verbs for daily routine: \"je me leve\", \"je me couche\".",
  ],
  B1: [
    "Helpful tip: \"Depuis\" means \"since\" or \"for\" with actions still continuing, as in \"j'habite ici depuis deux ans\".",
    "Helpful tip: \"En train de\" highlights an action in progress: \"je suis en train de lire\".",
    "Helpful tip: \"Il faut\" is a very common way to say \"it is necessary\" or \"you have to\".",
    "Helpful tip: \"Y\" often replaces \"there\" or \"to it\", as in \"j'y vais\".",
    "Helpful tip: \"Plus... plus...\" builds comparisons like \"plus je lis, plus je comprends\".",
    "Helpful tip: Useful connector: \"du coup\" often means \"so\" or \"as a result\" in everyday French.",
    "Helpful tip: \"Alors que\" helps you contrast two ideas inside one sentence.",
    "Helpful tip: \"Pendant que\" means \"while\" and is useful for linked actions.",
    "Helpful tip: \"Venir de\" and \"aller\" help French narration move more naturally through time.",
    "Helpful tip: B1 French often sounds better when you connect clauses instead of stacking short sentences.",
    "Helpful tip: \"On\" is extremely common in spoken French and often replaces \"nous\".",
    "Helpful tip: \"Finir par\" means \"to end up doing\" and is useful for narration.",
    "Helpful tip: \"Se rendre compte\" means \"to realize\" and is worth learning as a chunk.",
    "Helpful tip: \"Avoir l'air\" means \"to seem\" or \"to look\".",
    "Helpful tip: \"Faillir\" is rarer, but \"j'ai failli\" means \"I almost...\".",
    "Helpful tip: \"Par rapport a\" is common in speech, but sometimes a simpler connector sounds cleaner.",
    "Helpful tip: \"D'abord\", \"ensuite\", and \"finalement\" help structure a sequence clearly.",
    "Helpful tip: B1 answers improve a lot when the tense choice stays stable across the sentence.",
    "Helpful tip: \"Ce qui\" and \"ce que\" are useful when English would say \"what\".",
    "Helpful tip: \"En fait\" can mean \"actually\" or \"in fact\", depending on context.",
  ],
  B2: [
    "Helpful tip: The subjunctive often appears after expressions like \"il faut que\" or \"bien que\".",
    "Helpful tip: \"Dont\" can replace \"de + noun\", as in \"le livre dont je parle\".",
    "Helpful tip: \"Avoir beau\" means doing something even though it does not help: \"j'ai beau essayer...\".",
    "Helpful tip: French often prefers a clean relative clause over repeating the noun too many times.",
    "Helpful tip: Useful connector: \"pourtant\" means \"however\" or \"and yet\".",
    "Helpful tip: Stronger B2 phrasing often relies on connectors like \"ainsi\", \"tandis que\", or \"alors que\".",
    "Helpful tip: At B2, the difference between acceptable French and natural French is often connector choice.",
    "Helpful tip: \"Or\" is a compact formal connector meaning something like \"now\" or \"yet\" in argumentation.",
    "Helpful tip: \"Autant\" and \"d'autant plus que\" help build more nuanced comparisons.",
    "Helpful tip: \"Ce dont\" and \"ce a quoi\" are useful when the clause has no explicit noun head.",
    "Helpful tip: \"Bien que\" takes the subjunctive and often sounds more polished than a simpler contrast.",
    "Helpful tip: \"A peine... que\" is a compact way to express immediate sequence.",
    "Helpful tip: B2 French benefits from varying sentence openings instead of always starting with the subject.",
    "Helpful tip: \"Il s'agit de\" is very common in explanations and formal descriptions.",
    "Helpful tip: \"Mettre en place\" means \"to set up\" or \"to put in place\" and appears often in formal French.",
    "Helpful tip: \"Meme si\" usually takes the indicative, unlike some nearby structures.",
    "Helpful tip: \"Quoique\" and \"bien que\" are similar, but register and rhythm can differ.",
    "Helpful tip: A strong B2 sentence often compresses ideas instead of translating every English word separately.",
    "Helpful tip: Watch article choices after abstract verbs; French often wants one where English does not.",
    "Helpful tip: Relative pronouns are a major fluency marker at B2, especially \"dont\" and \"lequel\" forms.",
  ],
  C1: [
    "Helpful tip: At C1, register matters: ask whether the sentence sounds neutral, formal, literary, or conversational.",
    "Helpful tip: Small connector choices reshape nuance: \"or\", \"pourtant\", \"toutefois\", \"d'ailleurs\".",
    "Helpful tip: Watch pronominal verbs closely, especially when meaning shifts, as in \"se rendre compte\".",
    "Helpful tip: French often sounds more elegant when repetition is replaced with pronouns or tighter clause structure.",
    "Helpful tip: \"Mettre en valeur\" means \"to highlight\" and is common in analytical or formal writing.",
    "Helpful tip: At higher levels, idiomatic precision matters more than literal word-for-word alignment.",
    "Helpful tip: C1 French often improves through restraint: fewer heavy calques, tighter syntax, sharper nuance.",
    "Helpful tip: \"D'autant que\" can justify a statement with a stronger follow-up reason.",
    "Helpful tip: \"Force est de constater\" is formal and should be used sparingly, but it is worth recognizing.",
    "Helpful tip: Advanced French often prefers nominal structures where English prefers verbs.",
    "Helpful tip: A C1 sentence should sound intentional in rhythm as well as correct in grammar.",
    "Helpful tip: \"Quitte a\" signals a tradeoff or accepted consequence and adds nuance efficiently.",
    "Helpful tip: \"Pour peu que\" is an advanced conditional trigger that takes the subjunctive.",
    "Helpful tip: \"Il n'en demeure pas moins que\" is formal but useful for concession in argumentation.",
    "Helpful tip: At C1, you should notice when a phrase is grammatical but too flat for the intended register.",
    "Helpful tip: Advanced fluency often comes from pruning unnecessary pronouns, articles, and literal repetitions.",
    "Helpful tip: \"N'avoir de cesse de\" is literary, but recognizing such structures helps with high-level input.",
    "Helpful tip: \"Du reste\" and \"au demeurant\" are high-register connectors with a distinct written tone.",
    "Helpful tip: A polished C1 answer often reorganizes the sentence instead of preserving English information order.",
    "Helpful tip: Nuance pairs matter at this level: \"quoique\" vs \"bien que\", \"encore\" vs \"toujours\", \"voire\" vs \"meme\".",
  ],
};

const CHECKING_TIPS_BY_LEVEL_SPANISH = {
  A1: [
    "Helpful tip: \"Tengo\" means \"I have\" and is one of the most useful starters.",
    "Helpful tip: Spanish often needs an article like \"un\", \"una\", \"el\", or \"la\".",
    "Helpful tip: \"Soy\" and \"estoy\" are different, so watch which kind of \"to be\" you need.",
    "Helpful tip: Common useful phrase: \"Quiero...\" means \"I want...\".",
    "Helpful tip: Basic adjectives often come after the noun in Spanish.",
    "Helpful tip: \"Hay\" means \"there is\" or \"there are\".",
    "Helpful tip: \"Me llamo...\" means \"My name is...\" and is worth knowing early.",
    "Helpful tip: Watch noun gender from the start: \"un\" and \"una\" matter.",
    "Helpful tip: \"Voy a...\" is a very common way to say the near future.",
    "Helpful tip: Short words like \"de\", \"a\", and \"en\" can change the whole sentence."
  ],
  A2: [
    "Helpful tip: After \"querer\", \"poder\", and \"ir a\", Spanish often uses an infinitive.",
    "Helpful tip: Watch common contractions like \"al\" and \"del\".",
    "Helpful tip: \"Porque\" gives a reason, while \"para\" often points to purpose.",
    "Helpful tip: \"Entrar en\" is often better than leaving out the preposition.",
    "Helpful tip: \"Acabar de\" helps you say you have just done something.",
    "Helpful tip: \"Hay que\" is a useful way to say what is necessary.",
    "Helpful tip: Reflexive verbs are common in daily routine, like \"me levanto\".",
    "Helpful tip: Keep one clear main idea per sentence before adding detail."
  ],
  B1: [
    "Helpful tip: Keep an eye on tense consistency across the sentence.",
    "Helpful tip: Connect ideas naturally instead of stacking short literal translations.",
    "Helpful tip: Useful connectors include \"mientras\", \"aunque\", and \"entonces\".",
    "Helpful tip: B1 Spanish improves a lot when articles and prepositions are precise.",
    "Helpful tip: Good intermediate Spanish often sounds simpler than a literal English calque."
  ],
  B2: [
    "Helpful tip: At B2, natural connector choice matters almost as much as grammar.",
    "Helpful tip: Stronger Spanish often comes from tighter phrasing, not more words.",
    "Helpful tip: Check whether the register sounds neutral, formal, or conversational.",
    "Helpful tip: Good B2 answers often reorganize the sentence rather than translate word by word."
  ],
  C1: [
    "Helpful tip: At C1, nuance and register matter as much as correctness.",
    "Helpful tip: Look for a sharper idiomatic phrasing rather than a literal one.",
    "Helpful tip: Advanced Spanish often improves through cleaner clause structure.",
    "Helpful tip: Ask whether the sentence sounds genuinely native, not just grammatical."
  ],
};

const GENERATING_STORY_LINES = [
  "Gathering a fresh little world, one sentence at a time.",
  "Letting the pages rustle until the story finds its shape.",
  "Coaxing a few curious characters into the same scene.",
  "Threading the setting, the mood, and the French together.",
  "Adding just enough mischief, wonder, and momentum.",
  "Tucking the next twist neatly between the pages.",
];

const LANGUAGE_COPY = {
  french: {
    name: "French",
    hero: "Generate a connected story or dialogue, then translate each English sentence into French with feedback on what you wrote.",
  },
  spanish: {
    name: "Spanish",
    hero: "Generate a connected story or dialogue, then translate each English sentence into Spanish with feedback on what you wrote.",
  },
};

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

if (el.vocabHints && el.vocabHints.parentElement !== document.body) {
  document.body.appendChild(el.vocabHints);
}

async function apiMaybe(path, options = {}) {
  try {
    return await api(path, options);
  } catch (error) {
    return null;
  }
}

function setInlineStatus(element, message = "", loading = false) {
  element.textContent = message;
  element.classList.toggle("hidden", !message);
  element.classList.toggle("inline-status-loading", Boolean(message) && loading);
}

async function watchForDevReload() {
  const payload = await apiMaybe("/api/dev/version");
  if (payload?.version) {
    if (state.devVersion && payload.version !== state.devVersion) {
      window.location.reload();
      return;
    }
    state.devVersion = payload.version;
  }

  state.devReloadTimer = window.setTimeout(watchForDevReload, 1200);
}

function clearLessonPolling() {
  if (state.lessonPollTimer) {
    clearTimeout(state.lessonPollTimer);
    state.lessonPollTimer = null;
  }
  state.lessonPollInFlight = false;
}

function clearCheckingEllipsis() {
  if (state.checkingEllipsisTimer) {
    clearTimeout(state.checkingEllipsisTimer);
    state.checkingEllipsisTimer = null;
  }
  if (el.checkingEllipsis) {
    el.checkingEllipsis.textContent = "";
  }
}

function clearGeneratingScreenAnimation() {
  if (state.generatingEllipsisTimer) {
    clearTimeout(state.generatingEllipsisTimer);
    state.generatingEllipsisTimer = null;
  }
  if (state.generatingCopyTimer) {
    clearTimeout(state.generatingCopyTimer);
    state.generatingCopyTimer = null;
  }
  if (state.generatingWaveTimer) {
    clearTimeout(state.generatingWaveTimer);
    state.generatingWaveTimer = null;
  }
  if (el.generatingEllipsis) {
    el.generatingEllipsis.textContent = "";
  }
  if (el.generatingCopy) {
    el.generatingCopy.classList.remove("wave-active");
  }
}

function startCheckingEllipsisLoop() {
  clearCheckingEllipsis();
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReducedMotion) {
    el.checkingEllipsis.textContent = "...";
    return;
  }

  const frames = ["", ".", "..", "..."];
  let index = 0;

  const tick = () => {
    el.checkingEllipsis.textContent = frames[index];
    index = (index + 1) % frames.length;
    const delay = index === 0 ? 520 : 220;
    state.checkingEllipsisTimer = setTimeout(tick, delay);
  };

  tick();
}

function startGeneratingScreenAnimation() {
  clearGeneratingScreenAnimation();
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const lines = [...GENERATING_STORY_LINES];
  let lineIndex = 0;

  if (el.generatingCopy) {
    setGeneratingCopyLine(lines[0], prefersReducedMotion);
  }

  if (el.generatingEllipsis) {
    if (prefersReducedMotion) {
      el.generatingEllipsis.textContent = "...";
    } else {
      const frames = ["", ".", "..", "..."];
      let index = 0;
      const tickEllipsis = () => {
        el.generatingEllipsis.textContent = frames[index];
        index = (index + 1) % frames.length;
        const delay = index === 0 ? 540 : 220;
        state.generatingEllipsisTimer = setTimeout(tickEllipsis, delay);
      };
      tickEllipsis();
    }
  }

  if (lines.length <= 1) {
    return;
  }

  const rotateCopy = () => {
    lineIndex = (lineIndex + 1) % lines.length;
    if (el.generatingCopy) {
      setGeneratingCopyLine(lines[lineIndex], prefersReducedMotion);
    }
    state.generatingCopyTimer = setTimeout(rotateCopy, prefersReducedMotion ? 2800 : 2200);
  };

  state.generatingCopyTimer = setTimeout(rotateCopy, prefersReducedMotion ? 2800 : 2200);
}

function setGeneratingCopyLine(text, prefersReducedMotion = false) {
  if (!el.generatingCopy) {
    return;
  }

  if (prefersReducedMotion) {
    el.generatingCopy.textContent = text;
    return;
  }

  const fragment = document.createDocumentFragment();
  [...text].forEach((char, index) => {
    const span = document.createElement("span");
    span.className = "wave-char";
    span.style.setProperty("--wave-index", String(index));
    span.textContent = char === " " ? "\u00A0" : char;
    fragment.appendChild(span);
  });

  el.generatingCopy.replaceChildren(fragment);
  startGeneratingCopyWaveLoop();
}

function startGeneratingCopyWaveLoop() {
  if (!el.generatingCopy) {
    return;
  }

  if (state.generatingWaveTimer) {
    clearTimeout(state.generatingWaveTimer);
    state.generatingWaveTimer = null;
  }

  const chars = Array.from(el.generatingCopy.querySelectorAll(".wave-char"));
  if (!chars.length) {
    return;
  }

  const delayStep = 12;
  const shiverDuration = 120;
  const totalDuration = chars.length * delayStep + shiverDuration + 320;

  chars.forEach((char, index) => {
    char.style.setProperty("--wave-delay", `${index * delayStep}ms`);
  });

  const runWave = () => {
    if (!el.generatingCopy) {
      return;
    }
    el.generatingCopy.classList.remove("wave-active");
    void el.generatingCopy.offsetWidth;
    el.generatingCopy.classList.add("wave-active");
    state.generatingWaveTimer = setTimeout(runWave, totalDuration);
  };

  runWave();
}

function mergeLessonUpdate(lesson) {
  if (!state.lesson || state.lesson.lesson_id !== lesson.lesson_id) {
    state.lesson = lesson;
    ensureCheckingTipHistory(lesson.lesson_id);
    return;
  }

  state.lesson = {
    ...state.lesson,
    ...lesson,
    sentences: lesson.sentences || state.lesson.sentences,
  };
}

function lessonNeedsPolling() {
  return Boolean(state.lesson && state.lesson.status === "generating" && !state.lesson.is_complete);
}

async function pollLessonStatus() {
  if (!lessonNeedsPolling() || state.lessonPollInFlight) {
    return;
  }

  state.lessonPollTimer = null;
  state.lessonPollInFlight = true;
  try {
    const updatedLesson = await api(`/api/lesson/${state.lesson.lesson_id}`);
    const hadSentence = Boolean(currentSentence());
    mergeLessonUpdate(updatedLesson);

    if (updatedLesson.status === "failed") {
      clearLessonPolling();
      renderSetupView();
      alert(updatedLesson.error_message || "The rest of the lesson could not be generated.");
      return;
    }

    if (lessonNeedsPolling()) {
      state.lessonPollTimer = setTimeout(pollLessonStatus, 1400);
    } else {
      clearLessonPolling();
    }

    if (!hadSentence && currentSentence() && (isPromptVisible() || isGeneratingStoryVisible())) {
      renderLesson();
      return;
    }

  } catch (error) {
    state.lessonPollTimer = setTimeout(pollLessonStatus, 2200);
  } finally {
    state.lessonPollInFlight = false;
  }
}

function ensureLessonPolling() {
  if (!lessonNeedsPolling()) {
    clearLessonPolling();
    return;
  }
  if (state.lessonPollTimer || state.lessonPollInFlight) {
    return;
  }
  state.lessonPollTimer = setTimeout(pollLessonStatus, 900);
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

function clearStoryFlight() {
  if (state.storyFlightCleanupTimer) {
    clearTimeout(state.storyFlightCleanupTimer);
    state.storyFlightCleanupTimer = null;
  }
  if (state.storyFlightFinishTimer) {
    clearTimeout(state.storyFlightFinishTimer);
    state.storyFlightFinishTimer = null;
  }
  document.querySelectorAll(".story-flight-clone").forEach((node) => node.remove());
  document.querySelectorAll(".story-sentence-pending, .story-sentence-landed").forEach((node) => {
    node.classList.remove("story-sentence-pending", "story-sentence-landed");
  });
  state.nextTransitionInProgress = false;
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
  clearCheckingEllipsis();
  clearGeneratingScreenAnimation();
  el.setupPanel.classList.add("hidden");
  el.generatingPanel.classList.add("hidden");
  el.promptPanel.classList.add("hidden");
  el.checkingPanel.classList.add("hidden");
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

function normalizeFrenchText(text) {
  return (text || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[â€™']/g, "")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
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

function pickSingleFrenchSentence(text) {
  const trimmed = (text || "").trim();
  if (!trimmed) {
    return "";
  }
  const slashSplit = trimmed.split(/\s\/\s/).map((part) => part.trim()).filter(Boolean);
  if (slashSplit.length > 1) {
    return slashSplit[0];
  }
  return trimmed;
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
      if (!cleanedPhrase) {
        output.push(escapeHtml(segment.displayText));
      } else {
        output.push(
          `<button class="inline-phrase-btn" type="button" data-phrase="${escapeHtml(cleanedPhrase)}">${escapeHtml(segment.displayText)}</button>`,
        );
      }
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

function getMatchedLearnerIndexes(answer, targetSentence) {
  const learnerParts = tokenizeWithSpaces(answer);
  const targetParts = tokenizeWithSpaces(targetSentence);

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

  const matchedLearnerIndexes = new Set();
  let i = learnerWords.length;
  let j = targetWords.length;
  while (i > 0 && j > 0) {
    if (learnerWords[i - 1].normalized === targetWords[j - 1].normalized) {
      matchedLearnerIndexes.add(learnerWords[i - 1].index);
      i -= 1;
      j -= 1;
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      i -= 1;
    } else {
      j -= 1;
    }
  }

  return matchedLearnerIndexes;
}

function promoteAcceptableDifferenceLabels(answer, targetSentence, learnerTokenLabels = [], isCorrect = false) {
  const cleanedLabels = Array.isArray(learnerTokenLabels) ? [...learnerTokenLabels] : [];
  const learnerParts = tokenizeWithSpaces(answer);
  const learnerWordCount = learnerParts.filter((part) => normalizeToken(part)).length;
  if (!isCorrect || cleanedLabels.length !== learnerWordCount) {
    return cleanedLabels;
  }
  if (normalizeFrenchText(answer) === normalizeFrenchText(targetSentence)) {
    return cleanedLabels.map(() => "correct");
  }

  const matchedLearnerIndexes = getMatchedLearnerIndexes(answer, targetSentence);
  let labelIndex = 0;
  learnerParts.forEach((part, partIndex) => {
    const normalized = normalizeToken(part);
    if (!normalized) {
      return;
    }
    if (!matchedLearnerIndexes.has(partIndex) && cleanedLabels[labelIndex] === "correct") {
      cleanedLabels[labelIndex] = "acceptable";
    }
    labelIndex += 1;
  });
  return cleanedLabels;
}

function buildLearnerAnswerMarkup(answer, correctSentence, learnerTokenLabels = []) {
  const learnerParts = tokenizeWithSpaces(answer);
  const cleanedLabels = Array.isArray(learnerTokenLabels) ? learnerTokenLabels : [];
  const learnerWordCount = learnerParts.filter((part) => normalizeToken(part)).length;

  if (cleanedLabels.length === learnerWordCount) {
    let labelIndex = 0;
    return learnerParts
      .map((part) => {
        if (!part.trim()) {
          return part;
        }
        const normalized = normalizeToken(part);
        if (!normalized) {
          return `<span class="answer-word answer-word-neutral">${part}</span>`;
        }
        const label = cleanedLabels[labelIndex] || "wrong";
        labelIndex += 1;
        const cssClass = label === "correct"
          ? "answer-word-correct"
          : label === "acceptable"
            ? "answer-word-acceptable"
            : "answer-word-wrong";
        return `<span class="answer-word ${cssClass}">${part}</span>`;
      })
      .join("");
  }

  const matchedLearnerIndices = getMatchedLearnerIndexes(answer, correctSentence);

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

function formatLearnerAnswerDisplay(answer) {
  const trimmed = (answer || "").trim();
  if (!trimmed) {
    return "No answer entered.";
  }

  let formatted = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  if (!/[.!?…]$/.test(formatted)) {
    formatted += ".";
  }
  return formatted;
}

function formatCorrectSentenceDisplay(answer) {
  const trimmed = (answer || "").trim();
  if (!trimmed) {
    return "";
  }

  let formatted = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  if (!/[.!?â€¦]$/.test(formatted)) {
    formatted += ".";
  }
  return formatted;
}

function getDisplayedCorrectSentence(feedback) {
  const current = currentSentence();
  const acceptedLearner = pickSingleFrenchSentence(feedback.accepted_learner_sentence);
  const suggested = pickSingleFrenchSentence(feedback.suggested_sentence);
  const moreCommon = pickSingleFrenchSentence(feedback.more_common_sentence);
  const fallbackTarget = pickSingleFrenchSentence(current?.french || "");
  if (acceptedLearner) {
    return acceptedLearner;
  }
  if (!suggested && !moreCommon) {
    return fallbackTarget;
  }
  if (!moreCommon) {
    return suggested || fallbackTarget;
  }
  if (!suggested) {
    return moreCommon || fallbackTarget;
  }
  if (normalizeFrenchText(moreCommon) === normalizeFrenchText(suggested)) {
    return suggested || fallbackTarget;
  }
  const hints = current?.vocab_hints || [];
  const breaksHintAlignment = hints.some((hint) => {
    const hinted = normalizeFrenchText(hint.french);
    if (!hinted) {
      return false;
    }
    return normalizeFrenchText(suggested).includes(hinted) && !normalizeFrenchText(moreCommon).includes(hinted);
  });
  if (breaksHintAlignment) {
    return suggested || fallbackTarget;
  }
  return moreCommon || suggested || fallbackTarget;
}

function buildNoteDedupKey(note) {
  const wrongWordMatch = note.match(/^['"]([^'"]+)['"] is the wrong word; use ['"]([^'"]+)['"]\.$/i);
  if (wrongWordMatch) {
    return `replacement:${normalizeFrenchText(wrongWordMatch[1])}->${normalizeFrenchText(wrongWordMatch[2])}`;
  }

  const correctNounMatch = note.match(/^Use the correct (?:noun|word|verb|phrase) ['"]([^'"]+)['"] not ['"]([^'"]+)['"]\.$/i);
  if (correctNounMatch) {
    return `replacement:${normalizeFrenchText(correctNounMatch[2])}->${normalizeFrenchText(correctNounMatch[1])}`;
  }

  const preferWithMatch = note.match(/^Prefer ['"]([^'"]+)['"](?: or ['"]([^'"]+)['"])? with ['"]([^'"]+)['"]\.$/i);
  if (preferWithMatch) {
    return `preferred-with:${normalizeFrenchText(preferWithMatch[3])}`;
  }

  const useNotMatch = note.match(/^Use ['"]([^'"]+)['"],? not ['"]([^'"]+)['"]\.$/i);
  if (useNotMatch) {
    return `replacement:${normalizeFrenchText(useNotMatch[2])}->${normalizeFrenchText(useNotMatch[1])}`;
  }

  const misspellingMatch = note.match(
    /^([^".]+?) is a misspelling; correct [^.]* is ([^."']+(?:\s+[^."']+)*)\.$/i,
  );
  if (misspellingMatch) {
    return `replacement:${normalizeFrenchText(misspellingMatch[1])}->${normalizeFrenchText(misspellingMatch[2])}`;
  }

  const renderedAsMatch = note.match(
    /^([^".]+?) should be rendered as ([^."']+(?:\s+[^."']+)*) in french\.$/i,
  );
  if (renderedAsMatch) {
    return `replacement:${normalizeFrenchText(renderedAsMatch[1])}->${normalizeFrenchText(renderedAsMatch[2])}`;
  }

  const spellingPairMatch = note.match(
    /(?:name spelled incorrectly|spelled incorrectly|proper form)[^"'a-zA-ZÀ-ÿ]*['"]([^'"]+)['"][^"'a-zA-ZÀ-ÿ]+['"]([^'"]+)['"]/i,
  );
  if (spellingPairMatch) {
    const left = normalizeFrenchText(spellingPairMatch[1]);
    const right = normalizeFrenchText(spellingPairMatch[2]);
    if (left && right && left === right) {
      return `orthography:${left}`;
    }
  }

  const articleAgreementMatch = note.match(
    /wrote ['"]([^'"]+)['"] instead of ['"]([^'"]+)['"]/i,
  );
  if (articleAgreementMatch) {
    const correctedPhrase = normalizeFrenchText(articleAgreementMatch[2]);
    const correctedTokens = correctedPhrase.split(/\s+/).filter(Boolean);
    const noun = correctedTokens[correctedTokens.length - 1] || correctedPhrase;
    return `gender-article:${noun}`;
  }

  const genderArticleMatch = note.match(
    /"(l[ea]|un|une)\s+([^"]+)"[^.]*\b([^"\s]+)\b is (masculine|feminine)\b/i,
  );
  if (genderArticleMatch) {
    return `gender-article:${normalizeFrenchText(genderArticleMatch[3])}:${genderArticleMatch[4].toLowerCase()}`;
  }

  const rememberGenderMatch = note.match(
    /remember the gender of nouns:[^.]*['"]([^'"]+)['"] is (masculine|feminine)[^.]*['"]([^'"]+)['"]/i,
  );
  if (rememberGenderMatch) {
    return `gender-article:${normalizeFrenchText(rememberGenderMatch[1])}:${rememberGenderMatch[2].toLowerCase()}`;
  }

  const nounGenderMatch = note.match(
    /\b([^"\s]+)\b is (masculine|feminine)\b[^.]*\b(use|requires?)\b[^"]*"([^"]+)"/i,
  );
  if (nounGenderMatch) {
    return `gender-article:${normalizeFrenchText(nounGenderMatch[1])}:${nounGenderMatch[2].toLowerCase()}`;
  }

  const normalized = normalizeFrenchText(note)
    .replace(/\b(verb form|conjugate|conjugation|correctly|needs|ending|troisieme personne du singulier|third person singular)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const quoted = [...note.matchAll(/"([^"]+)"/g)]
    .map((match) => normalizeFrenchText(match[1]))
    .filter(Boolean);
  if (quoted.length >= 2) {
    return `quotes:${quoted.join("|")}`;
  }
  if (quoted.length === 1) {
    return `quote:${quoted[0]}:${normalized}`;
  }
  return normalized;
}

function sentenceCase(text) {
  if (!text) {
    return "";
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function ensureSentencePunctuation(text) {
  if (!text) {
    return "";
  }
  return /[.!?]$/.test(text) ? text : `${text}.`;
}

function normalizeQuotationMarks(text) {
  return (text || "")
    .replace(/(?:«|Â«)\s*/g, "\"")
    .replace(/\s*(?:»|Â»)/g, "\"");
}

function resetCheckingTipHistory(lessonId = null) {
  state.checkingTipsLessonId = lessonId;
  state.usedCheckingTipIndexes = {};
  state.checkingTipQueueByDifficulty = {};
  state.lastCheckingTipIndex = -1;
}

function ensureCheckingTipHistory(lessonId) {
  if (!lessonId) {
    if (state.checkingTipsLessonId !== null) {
      resetCheckingTipHistory(null);
    }
    return;
  }
  if (state.checkingTipsLessonId !== lessonId) {
    resetCheckingTipHistory(lessonId);
  }
}

function shuffleIndexes(length) {
  const indexes = Array.from({ length }, (_, index) => index);
  for (let i = indexes.length - 1; i > 0; i -= 1) {
    const swapIndex = Math.floor(Math.random() * (i + 1));
    [indexes[i], indexes[swapIndex]] = [indexes[swapIndex], indexes[i]];
  }
  return indexes;
}

function ensureCheckingTipQueue(difficulty) {
  const languageKey = currentLanguage();
  const queueKey = `${languageKey}:${difficulty}`;
  const tipBank = currentLanguage() === "spanish" ? CHECKING_TIPS_BY_LEVEL_SPANISH : CHECKING_TIPS_BY_LEVEL;
  const tips = tipBank[difficulty] || [];
  const existingQueue = state.checkingTipQueueByDifficulty[queueKey] || [];
  if (existingQueue.length) {
    return existingQueue;
  }

  if (!tips.length) {
    state.checkingTipQueueByDifficulty[queueKey] = [];
    return [];
  }

  let queue = shuffleIndexes(tips.length);
  if (tips.length > 1 && queue[0] === state.lastCheckingTipIndex) {
    queue.push(queue.shift());
  }
  state.checkingTipQueueByDifficulty[queueKey] = queue;
  return queue;
}

function pickNextCheckingTip(difficulty) {
  const languageKey = currentLanguage();
  const queueKey = `${languageKey}:${difficulty}`;
  const tipBank = currentLanguage() === "spanish" ? CHECKING_TIPS_BY_LEVEL_SPANISH : CHECKING_TIPS_BY_LEVEL;
  const tips = tipBank[difficulty] || tipBank.A2;
  if (!tips.length) {
    return "Helpful tip: Watch the article, verb, and word order before you submit.";
  }

  const queue = ensureCheckingTipQueue(difficulty);
  const nextIndex = queue.shift();
  state.checkingTipQueueByDifficulty[queueKey] = queue;
  state.usedCheckingTipIndexes[queueKey] = [
    ...(state.usedCheckingTipIndexes[queueKey] || []),
    nextIndex,
  ].slice(-tips.length);
  state.lastCheckingTipIndex = nextIndex;
  return tips[nextIndex];
}

function currentLessonId() {
  return state.lesson?.lesson_id || null;
}

function currentLanguage() {
  return state.lesson?.language || state.language || "french";
}

function updateLanguageToggle() {
  const activeLanguage = currentLanguage();
  el.languageFrenchBtn?.classList.toggle("active", activeLanguage === "french");
  el.languageSpanishBtn?.classList.toggle("active", activeLanguage === "spanish");
  document.title = activeLanguage === "spanish" ? "Spanish Story Trainer" : "French Story Trainer";
}

function setLanguage(language) {
  const nextLanguage = language === "spanish" ? "spanish" : "french";
  const wasSetupVisible = isSetupVisible();
  const previousLanguage = state.language;
  if (nextLanguage === previousLanguage) {
    updateLanguageToggle();
    return;
  }
  state.language = nextLanguage;
  updateLanguageToggle();
  if (wasSetupVisible) {
    const heroCopyText = LANGUAGE_COPY[currentLanguage()]?.hero || LANGUAGE_COPY.french.hero;
    reserveTextBlockHeight(el.heroCopy, heroCopyText);
    el.lessonTitle.textContent = "Choose your story.";
    animatePlainText(
      el.heroCopy,
      heroCopyText,
      0,
      0.42,
    );
    updateSidebarMeta();
    loadVocab();
    loadReminders();
    return;
  }
  renderSetupView();
  loadVocab();
  loadReminders();
}

function currentDifficulty() {
  return state.lesson?.difficulty || document.querySelector("#difficulty")?.value || "A2";
}

function getCheckingTipForCurrentLesson() {
  ensureCheckingTipHistory(currentLessonId());
  return pickNextCheckingTip(currentDifficulty());
}

function buildConciseVerdict(feedback) {
  const rawVerdict = normalizeQuotationMarks((feedback.verdict || "").trim());
  const score = Number(feedback.correctness_score) || 0;

  if (feedback.is_correct && score >= 96) {
    return "Correct.";
  }
  if (feedback.is_correct && score >= 85) {
    return "Mostly correct.";
  }
  if (score >= 70) {
    return "Close.";
  }
  if (score >= 45) {
    return "Partly right.";
  }

  const compact = rawVerdict
    .replace(/^this is exactly the kind of repeatable pattern the reminder list is meant to catch\.?$/i, "Watch this pattern.")
    .replace(/^probably correct, but the wording could be smoother\.?$/i, "Probably correct.")
    .replace(/^you are close on the main meaning\.?$/i, "Close.")
    .replace(/^close, but an important grammar word is missing\.?$/i, "Missing a small grammar word.")
    .replace(/^not quite right yet\.?$/i, "Not quite right.")
    .replace(/^revealed target answer\.?$/i, "Answer revealed.")
    .replace(/^nice work\.[\s\S]*$/i, "Correct.")
    .replace(/^mostly correct\.[\s\S]*$/i, "Mostly correct.")
    .replace(/\s+/g, " ")
    .trim();

  if (!compact) {
    return score >= 50 ? "Close." : "Not quite right.";
  }

  return ensureSentencePunctuation(sentenceCase(compact));
}

function buildVerdictDisplay(feedback) {
  const verdict = buildConciseVerdict(feedback);
  const normalized = verdict.toLowerCase();

  if (normalized === "answer revealed.") {
    return `👀 ${verdict}`;
  }
  if (feedback.is_correct && Number(feedback.correctness_score) >= 96) {
    return `✅ ${verdict}`;
  }
  if (feedback.is_correct) {
    return `🟡 ${verdict}`;
  }
  if (Number(feedback.correctness_score) >= 45) {
    return `🟠 ${verdict}`;
  }
  return `❌ ${verdict}`;
}

function shortenFeedbackNote(note) {
  const shortened = normalizeQuotationMarks(note)
    .replace(/^Word choice:\s*/i, "")
    .replace(/^Verb form:\s*/i, "")
    .replace(/^Conjugate [^:]+:\s*/i, "")
    .replace(/^You used\s*/i, "")
    .replace(/\s*which is correct; consider\s*/i, " Consider ")
    .replace(/\s*depending on the object\.?$/i, "")
    .replace(/\s+/g, " ")
    .trim();

  return ensureSentencePunctuation(sentenceCase(shortened));
}

function compressFeedbackNote(note) {
  let compact = shortenFeedbackNote(note);

  compact = compact
    .replace(
      /^['"]([^'"]+)['"] is the wrong word; use ['"]([^'"]+)['"]\.$/i,
      'Use "$2", not "$1".',
    )
    .replace(
      /^Use the correct (?:noun|word|verb|phrase) ['"]([^'"]+)['"] not ['"]([^'"]+)['"]\.$/i,
      'Use "$1", not "$2".',
    )
    .replace(
      /^Prefer ['"]([^'"]+)['"](?: or ['"]([^'"]+)['"])? with ['"]([^'"]+)['"]\.$/i,
      (_, first, second) => second ? `Prefer "${first}" or "${second}".` : `Prefer "${first}".`,
    )
    .replace(
      /^([^".]+?) is a misspelling; correct [^.]* is ([^."']+(?:\s+[^."']+)*)\.$/i,
      'Use "$2", not "$1".',
    )
    .replace(
      /^([^".]+?) should be rendered as ([^."']+(?:\s+[^."']+)*) in french\.$/i,
      'Use "$2" here.',
    )
    .replace(
      /^Wrong article-gender agreement: wrote ['"]([^'"]+)['"] instead of ['"]([^'"]+)['"]\.$/i,
      'Use "$2" here.',
    )
    .replace(
      /^Remember the gender of nouns:\s*['"]([^'"]+)['"] is (masculine|feminine), so use ['"]([^'"]+)['"][^.]*['"]([^'"]+)['"]\.$/i,
      (_, noun, gender, article) => `Use "${article} ${noun}" here: "${noun}" is ${gender}.`,
    )
    .replace(
      /^Learner wrote ['"]([^'"]+)['"] but ['"]?([^'".]+)['"]? is (masculine|feminine), so it requires ['"]([^'"]+)['"]\.$/i,
      (_, _written, noun, gender, article) => `Use "${article} ${noun}" here: "${noun}" is ${gender}.`,
    )
    .replace(
      /^Use the (masculine|feminine) definite article ['"]([^'"]+)['"] before ['"]?([^'".]+)['"]? because ['"]?([^'".]+)['"]? is a \1 noun: ['"]([^'"]+)['"]\.$/i,
      (_, gender, article, noun) => `Use "${article} ${noun}" here: "${noun}" is ${gender}.`,
    )
    .replace(
      /^Use the (masculine|feminine) indefinite article ['"]([^'"]+)['"] before ['"]?([^'".]+)['"]? because ['"]?([^'".]+)['"]? is a \1 noun: ['"]([^'"]+)['"]\.$/i,
      (_, gender, article, noun) => `Use "${article} ${noun}" here: "${noun}" is ${gender}.`,
    )
    .replace(
      /^Wrote "([^"]+)" instead of "([^"]+)" \(needs [^)]+\)\.$/i,
      'Use "$2" here.',
    )
    .replace(
      /^Conjugate ([^ ]+) correctly: .*?"([^"]+)"\.$/i,
      'Use "$2" here.',
    )
    .replace(
      /^Use[d]? "([^"]+)" which is correct; consider "([^"]+)"(?: as [^.]+)?\.$/i,
      'More natural: "$2".',
    )
    .replace(
      /^"([^"]+)" is grammatically correct but sounds unusual[^;]*; prefer "([^"]+)"(?: or "([^"]+)")?.*$/i,
      (_, _first, better, alt) => alt ? `Better fit: "${better}" or "${alt}".` : `Better fit: "${better}".`,
    )
    .replace(
      /^Missing ([^.]+)\.$/i,
      'Add $1.',
    )
    .replace(/^Remember the gender of nouns:\s*/i, "")
    .replace(
      /^Incorrect article[^:]*:\s*/i,
      "",
    )
    .replace(
      /^Incorrect preposition[^:]*:\s*/i,
      "",
    )
    .replace(
      /^Incorrect tense[^:]*:\s*/i,
      "",
    )
    .replace(
      /^Word order[^:]*:\s*/i,
      "",
    )
    .replace(
      /^Agreement[^:]*:\s*/i,
      "",
    )
    .replace(/\bthird person singular\b/gi, "il/elle form")
    .replace(/\bthird person plural\b/gi, "ils/elles form")
    .replace(/\bfirst person singular\b/gi, "je form")
    .replace(/\bfirst person plural\b/gi, "nous form")
    .replace(/\bsecond person singular\b/gi, "tu form")
    .replace(/\bsecond person plural\b/gi, "vous form")
    .replace(/\buse the suggested answer as a model, then try the next sentence quickly\.?$/i, "Check the model answer.")
    .replace(/\bcompare your answer with the suggested version carefully\.?$/i, "Compare with the model answer.")
    .replace(/\bfrench often needs a small linking word here:?/i, "Add the small linking word.")
    .replace(/\bthe meaning or structure differs noticeably from the target sentence\.?$/i, "Meaning or structure is off.")
    .replace(/\bcheck the core verb and the small grammar words\.?$/i, "Check the verb and grammar words.")
    .replace(/\s+/g, " ")
    .trim();

  if (/^None affecting meaning or grammar/i.test(compact)) {
    return "";
  }

  compact = ensureSentencePunctuation(sentenceCase(compact));

  if (compact.length > 95) {
    const shorter = compact
      .replace(/: "[^"]+"\.$/, ".")
      .replace(/: "[^"]+" or "[^"]+"\.$/, ".")
      .replace(/\s+/g, " ")
      .trim();
    return ensureSentencePunctuation(sentenceCase(shorter));
  }

  return compact;
}

function buildLearnerAnswerSegments(answer, correctSentence, learnerTokenLabels = []) {
  const markup = buildLearnerAnswerMarkup(answer, correctSentence, learnerTokenLabels);
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
    .map((note) => normalizeQuotationMarks(note.trim()))
    .map((note) => compressFeedbackNote(note))
    .filter(Boolean);
  const uniqueNotes = [];
  const seen = new Set();

  rawNotes.forEach((note) => {
    const key = buildNoteDedupKey(note);
    if (!seen.has(key)) {
      seen.add(key);
      uniqueNotes.push(note);
    }
  });

  const limit = feedback.is_correct ? 1 : 3;
  const concise = uniqueNotes.slice(0, limit);

  if (!concise.length) {
    return feedback.is_correct ? ["No major issues!"] : ["Check the model answer."];
  }

  return concise;
}

function animateCorrectnessMeter(score) {
  const target = Math.max(0, Math.min(100, Number(score) || 0));
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (state.correctnessAnimationFrame) {
    cancelAnimationFrame(state.correctnessAnimationFrame);
    state.correctnessAnimationFrame = null;
  }
  el.correctnessBar.classList.remove("score-bar-fill-animate");
  void el.correctnessBar.offsetWidth;
  el.correctnessBar.style.width = "0%";
  el.correctnessScore.textContent = "0";

  if (prefersReducedMotion) {
    el.correctnessBar.style.width = `${target}%`;
    el.correctnessScore.textContent = String(Math.round(target));
    return;
  }

  const start = performance.now();
  const duration = 920;

  const tick = (now) => {
    const progress = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = target * eased;
    el.correctnessBar.style.width = `${current}%`;
    el.correctnessScore.textContent = String(Math.round(current));
    if (progress < 1) {
      state.correctnessAnimationFrame = requestAnimationFrame(tick);
      return;
    }
    el.correctnessBar.style.width = `${target}%`;
    el.correctnessScore.textContent = String(Math.round(target));
    state.correctnessAnimationFrame = null;
  };

  state.correctnessAnimationFrame = requestAnimationFrame(tick);
}

function isFeedbackVisible() {
  return !el.feedbackCard.classList.contains("hidden");
}

function isFinalVisible() {
  return !el.finalPanel.classList.contains("hidden");
}

function isPromptVisible() {
  return !el.promptPanel.classList.contains("hidden");
}

function isSetupVisible() {
  return !el.setupPanel.classList.contains("hidden");
}

function isGeneratingStoryVisible() {
  return !el.generatingPanel.classList.contains("hidden");
}

function renderSetupView(message = "") {
  const heroCopyText = LANGUAGE_COPY[currentLanguage()]?.hero || LANGUAGE_COPY.french.hero;
  document.body.classList.add("landing-bauhaus-colors");
  clearPromptTyping();
  clearFeedbackTyping();
  clearContentAnimations();
  clearStoryFlight();
  clearLessonPolling();
  state.lesson = null;
  state.currentIndex = 0;
  state.lastAnswer = "";
  resetCheckingTipHistory(null);
  el.lessonCard.classList.remove("hidden");
  el.lessonCard.classList.remove("lesson-card-checking");
  el.lessonHeader.classList.remove("hidden");
  el.languageSwitch?.classList.remove("hidden");
  el.progressBox.classList.add("hidden");
  hideLessonScreens();
  el.setupPanel.classList.remove("hidden");
  el.emptyState.classList.toggle("hidden", !message);
  el.emptyState.innerHTML = `<p>${message || "Choose a difficulty, theme, and lesson mode to generate your first connected sequence."}</p>`;
  reserveTextBlockHeight(el.heroCopy, heroCopyText);
  animatePlainText(el.lessonTitle, "Choose your story.");
  animatePlainText(
    el.heroCopy,
    heroCopyText,
    80,
    0.42,
  );
  animateSetupFields();
  el.progressCurrent.textContent = "0";
  el.progressTotal.textContent = "0";
  el.storySoFarCard.classList.add("hidden");
  updateSidebarMeta();
  scrollWindowToTop();
}

function renderGeneratingStoryScreen() {
  clearPromptTyping();
  clearFeedbackTyping();
  clearContentAnimations();
  clearStoryFlight();
  el.lessonCard.classList.remove("hidden");
  el.lessonCard.classList.add("lesson-card-checking");
  el.lessonHeader.classList.add("hidden");
  el.languageSwitch?.classList.add("hidden");
  el.storySoFarCard.classList.add("hidden");
  el.storySoFarList.innerHTML = "";
  hideLessonScreens();
  el.emptyState.classList.add("hidden");
  el.generatingPanel.classList.remove("hidden");
  startGeneratingScreenAnimation();
  animatePanelIn(el.generatingPanel);
  scrollWindowToTop();
}

function animateSetupFields() {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fields = Array.from(el.lessonForm.querySelectorAll(".form-field"));
  const button = el.lessonForm.querySelector("#generate-btn");

  fields.forEach((node, index) => {
    node.classList.remove("setup-field-enter");
    node.style.animationDelay = "";
    if (prefersReducedMotion) {
      return;
    }
    void node.offsetWidth;
    node.style.animationDelay = `${220 + index * 55}ms`;
    node.classList.add("setup-field-enter");
  });

  if (!button) {
    return;
  }
  button.classList.remove("setup-button-enter");
  button.style.animationDelay = "";
  if (prefersReducedMotion) {
    button.style.opacity = "1";
    button.style.transform = "none";
    return;
  }
  void button.offsetWidth;
  button.style.animationDelay = `${240 + fields.length * 55}ms`;
  button.classList.add("setup-button-enter");
}

function focusAnswerInput() {
  requestAnimationFrame(() => {
    if (el.answerInput.disabled) {
      return;
    }
    el.answerInput.focus();
    el.answerInput.setSelectionRange(el.answerInput.value.length, el.answerInput.value.length);
  });
}

function closeVocabHintsBubble() {
  el.vocabHints.classList.add("hidden");
  el.vocabHints.style.visibility = "";
  el.vocabHints.style.left = "";
  el.vocabHints.style.top = "";
}

function closePhraseExplainer() {
  el.phraseExplainer.classList.add("hidden");
  el.phraseExplainer.style.visibility = "";
  el.phraseExplainer.style.left = "";
  el.phraseExplainer.style.top = "";
  selectedPhraseData = null;
}

function positionFloatingBubble(anchorElement, bubbleElement) {
  if (!anchorElement || !bubbleElement) {
    return;
  }

  const margin = 16;
  const gap = 22;
  const anchorRect = anchorElement.getBoundingClientRect();
  const bubbleRect = bubbleElement.getBoundingClientRect();
  const bubbleWidth = bubbleRect.width;
  const bubbleHeight = bubbleRect.height;

  let left = anchorRect.left + (anchorRect.width - bubbleWidth) / 2;
  left = Math.max(margin, Math.min(left, window.innerWidth - bubbleWidth - margin));

  let top = anchorRect.bottom + gap;
  if (top + bubbleHeight > window.innerHeight - margin) {
    top = Math.max(margin, anchorRect.top - bubbleHeight - gap);
  }

  bubbleElement.style.left = `${left}px`;
  bubbleElement.style.top = `${top}px`;
}

function positionPhraseExplainer(anchorElement) {
  el.phraseExplainer.style.position = "fixed";
  positionFloatingBubble(anchorElement, el.phraseExplainer);
}

function positionVocabHintsBubble(anchorElement) {
  if (!anchorElement || !el.vocabHints) {
    return;
  }

  const margin = 16;
  const gap = 14;
  const anchorRect = anchorElement.getBoundingClientRect();
  const bubbleRect = el.vocabHints.getBoundingClientRect();
  const bubbleWidth = bubbleRect.width;
  const bubbleHeight = bubbleRect.height;

    let left = anchorRect.left - bubbleWidth;
    left = Math.max(margin, Math.min(left, window.innerWidth - bubbleWidth - margin));

    let top = anchorRect.bottom + gap;
    if (top + bubbleHeight > window.innerHeight - margin) {
      top = Math.max(margin, anchorRect.top - bubbleHeight - gap);
    }

    el.vocabHints.style.position = "fixed";
    el.vocabHints.style.left = `${left}px`;
    el.vocabHints.style.top = `${top}px`;
  }

function scrollWindowToTop() {
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
}

function buildPlainTextSegments(text) {
  return text.split(/(\s+)/).filter(Boolean).map((part) => ({
    type: "text",
    text: part,
  }));
}

function animatePromptText(text) {
  clearPromptTyping();
  animateInlineSegments(el.englishPrompt, buildPlainTextSegments(text), 12, 30);
}

function animateFeedbackLabel(text) {
  clearFeedbackTyping();
  return animateInlineSegments(el.verdictText, buildPlainTextSegments(text), 0, 30);
}

function getNaturalAnimationDelay(nextChunk, previousChunk = "", baseDelay = 18) {
  let delay = baseDelay * 0.56 + Math.random() * (baseDelay * 0.44);

  if (!nextChunk) {
    return delay;
  }

  if (/\s+/.test(nextChunk)) {
    return 2 + Math.random() * 4.5;
  }

  if (/^[,.!?;:]+$/.test(nextChunk)) {
    return baseDelay * 1.35 + Math.random() * (baseDelay * 1.0);
  }

  if (previousChunk && /[\s"'(]/.test(previousChunk)) {
    delay += 2 + Math.random() * 4.5;
  }

  if (Math.random() < 0.12) {
    delay += baseDelay * (0.4 + Math.random() * 1.0);
  }

  return delay;
}

function animatePlainText(target, text, startDelay = 0, speedMultiplier = 1) {
  return animateInlineSegments(
    target,
    buildPlainTextSegments(text),
    startDelay,
    Math.max(8, 30 * speedMultiplier),
  );
}

function reserveTextBlockHeight(target, text) {
  const previousText = target.textContent;
  const previousMinHeight = target.style.minHeight;
  target.textContent = text;
  target.style.minHeight = `${target.scrollHeight}px`;
  target.textContent = previousText;
  if (previousText) {
    target.style.minHeight = previousMinHeight;
  }
}

function reserveAnimatedMarkupHeight(target, html) {
  const width = target.getBoundingClientRect().width || target.parentElement?.getBoundingClientRect().width || 0;
  const probe = target.cloneNode(false);
  probe.innerHTML = html;
  probe.style.position = "absolute";
  probe.style.visibility = "hidden";
  probe.style.pointerEvents = "none";
  probe.style.height = "auto";
  probe.style.minHeight = "0";
  probe.style.left = "-9999px";
  probe.style.top = "0";
  probe.style.width = `${Math.max(width, 1)}px`;
  probe.style.whiteSpace = "normal";
  target.parentElement?.appendChild(probe);
  target.style.minHeight = `${probe.scrollHeight}px`;
  probe.remove();
}

function animateFastNaturalText(target, text, startDelay = 0) {
  return animateInlineSegments(target, buildPlainTextSegments(text), startDelay, 16);
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
  segments.forEach((segment, index) => {
    const previousSegment = segments[index - 1];
    const previousText = previousSegment?.type === "text" ? previousSegment.text : previousSegment?.text || "";
    const currentText = segment.type === "text" ? segment.text : segment.text || "";

    let containerNode = null;
    if (segment.type === "button" || segment.type === "span") {
      const node = document.createElement(segment.type === "button" ? "button" : "span");
      if (segment.type === "button") {
        node.type = "button";
        node.className = "inline-phrase-btn";
        node.dataset.phrase = segment.phrase;
      } else {
        node.className = segment.className;
      }
      const starter = setTimeout(() => {
        target.append(node);
      }, delay);
      state.contentAnimationTimers.push(starter);
      containerNode = node;
    }

    const characters = Array.from(currentText);
    characters.forEach((character, charIndex) => {
      const timer = setTimeout(() => {
        if (segment.type === "text") {
          target.append(document.createTextNode(character));
          return;
        }
        containerNode.textContent += character;
      }, delay);
      state.contentAnimationTimers.push(timer);
      const prevChunk =
        charIndex > 0
          ? characters[charIndex - 1]
          : previousText
            ? previousText.slice(-1)
            : "";
      delay += getNaturalAnimationDelay(character, prevChunk, baseDelay);
    });
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

    const starter = setTimeout(() => {
      el.notesList.appendChild(li);
      animateInlineSegments(li, buildPlainTextSegments(note), 0, 30);
    }, noteDelay);
    state.contentAnimationTimers.push(starter);
    noteDelay += note.split(/\s+/).filter(Boolean).length * 30 + 120;
  });
  return noteDelay;
}

function renderLesson(preserveStoryFlight = false) {
  document.body.classList.remove("landing-bauhaus-colors");
  clearContentAnimations();
  if (!preserveStoryFlight) {
    clearStoryFlight();
  }
  const sentence = currentSentence();
  const total = state.lesson?.requested_sentence_count || state.lesson?.sentences?.length || 0;
  el.progressCurrent.textContent = state.lesson ? String(Math.min(state.currentIndex + 1, total || 0)) : "0";
  el.progressTotal.textContent = String(total);
  updateSidebarMeta();

    if (!sentence) {
      if (state.lesson && !state.lesson.is_complete) {
        el.lessonCard.classList.remove("hidden");
        el.lessonHeader.classList.remove("hidden");
        el.progressBox.classList.remove("hidden");
      hideLessonScreens();
      el.emptyState.classList.add("hidden");
      el.promptPanel.classList.remove("hidden");
      el.promptPanel.classList.add("prompt-panel-waiting");
      el.lessonTitle.textContent = state.lesson.title;
      el.contextNote.textContent = "Preparing the next sentence...";
      el.englishPrompt.textContent = "The next part of your story is still being written.";
      el.answerInput.value = "";
      el.answerInput.disabled = true;
      el.checkBtn.disabled = true;
      el.skipBtn.disabled = true;
        el.toggleHintsBtn.disabled = true;
        el.vocabHints.innerHTML = "";
        el.vocabHints.classList.add("hidden");
        renderStorySoFar();
        ensureLessonPolling();
        animatePanelIn(el.promptPanel);
        scrollWindowToTop();
        return;
      }
    renderSetupView("Lesson complete. Adjust the settings above if you want a fresh story or dialogue.");
    return;
  }

  el.lessonCard.classList.remove("hidden");
  el.lessonCard.classList.remove("lesson-card-checking");
  el.lessonHeader.classList.remove("hidden");
  el.languageSwitch?.classList.add("hidden");
  el.progressBox.classList.remove("hidden");
  hideLessonScreens();
  el.emptyState.classList.add("hidden");
  el.promptPanel.classList.remove("hidden");
  el.promptPanel.classList.remove("prompt-panel-waiting");
  el.verdictText.textContent = "Waiting for your answer";
  el.lessonTitle.textContent = state.lesson.title;
  el.contextNote.textContent = "Translate the following sentence...";
  animatePromptText(`"${sentence.english}"`);
  el.answerInput.value = "";
  el.answerInput.disabled = false;
  el.checkBtn.disabled = false;
  el.skipBtn.disabled = false;
  closeVocabHintsBubble();
  closePhraseExplainer();
  state.hintsVisible = false;
  renderHints();
  renderStorySoFar();
  ensureLessonPolling();
  animatePanelIn(el.promptPanel);
  focusAnswerInput();
  scrollWindowToTop();
}

function renderHints() {
  const sentence = currentSentence();
  const hints = sentence?.vocab_hints || [];
  el.vocabHints.innerHTML = "";

  if (!hints.length) {
    el.hintShortcutCopy.classList.add("hidden");
    el.toggleHintsBtn.textContent = "No vocab hints needed";
    el.toggleHintsBtn.disabled = true;
    closeVocabHintsBubble();
    return;
  }

  el.hintShortcutCopy.classList.remove("hidden");
  el.toggleHintsBtn.disabled = false;
  el.toggleHintsBtn.textContent = state.hintsVisible ? "Hide vocab hints" : "Show vocab hints";

  hints.forEach((hint) => {
    const div = document.createElement("div");
    div.className = "vocab-hint";
    const frenchDisplay = hint.display_french || hint.french;
    div.innerHTML = `
      <div class="vocab-hint-row">
        <div><strong>${frenchDisplay}</strong> -> ${hint.english}</div>
        <button class="ghost-btn vocab-hint-save-btn" type="button">Add</button>
      </div>
    `;
    const saveBtn = div.querySelector(".vocab-hint-save-btn");
    saveBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await addHintToVocab(hint);
      saveBtn.textContent = "Added";
      saveBtn.disabled = true;
    });
    el.vocabHints.appendChild(div);
  });

  if (!state.hintsVisible) {
    closeVocabHintsBubble();
    return;
  }

  el.vocabHints.classList.remove("hidden");
  el.vocabHints.style.visibility = "hidden";
  requestAnimationFrame(() => {
    positionVocabHintsBubble(el.toggleHintsBtn);
    el.vocabHints.style.visibility = "visible";
  });
}

async function addHintToVocab(hint) {
  const sentence = currentSentence();
  if (!sentence) {
    return;
  }

  await api("/api/vocab", {
    method: "POST",
    body: JSON.stringify({
      english: hint.english,
      french: hint.display_french || hint.french,
      note: "",
      source_sentence: sentence.english,
    }),
  });
  await loadVocab();
}

function renderFeedback(feedback) {
  document.body.classList.remove("landing-bauhaus-colors");
  clearPromptTyping();
  clearFeedbackTyping();
  clearContentAnimations();
  clearStoryFlight();
  el.lessonCard.classList.remove("hidden");
  el.lessonCard.classList.remove("lesson-card-checking");
  el.lessonHeader.classList.add("hidden");
  el.storySoFarCard.classList.add("hidden");
  el.storySoFarList.innerHTML = "";
    hideLessonScreens();
    el.feedbackCard.classList.remove("hidden");
    updateSidebarMeta();
    animatePanelIn(el.feedbackCard);
    const verdictDuration = animateFeedbackLabel(buildVerdictDisplay(feedback));
  animateCorrectnessMeter(feedback.correctness_score);
  el.feedbackQuestionLabel.textContent = "Question sentence";
  el.yourAnswerLabel.textContent = "Your answer";
  el.correctSentenceLabel.textContent = "Correct sentence";
  el.feedbackNotesLabel.textContent = "Feedback notes";
  const questionSentenceStartDelay = verdictDuration + 40;
  const yourAnswerStartDelay = verdictDuration + 90;
  const feedbackSentence = state.lesson?.sentences?.[state.currentIndex] || currentSentence();
  const questionSentenceDisplay = `"${feedbackSentence?.english || ""}"`;
  const learnerAnswerDisplay = formatLearnerAnswerDisplay(state.lastAnswer);
  const displayedCorrectSentence = formatCorrectSentenceDisplay(
    getDisplayedCorrectSentence(feedback) || feedbackSentence?.french || state.lesson?.sentences?.[state.currentIndex]?.french || "",
  );
  const canonicalTargetSentence = formatCorrectSentenceDisplay(
    pickSingleFrenchSentence(feedback.suggested_sentence) || feedbackSentence?.french || displayedCorrectSentence,
  );
  const learnerTokenLabels = promoteAcceptableDifferenceLabels(
    learnerAnswerDisplay,
    canonicalTargetSentence,
      feedback.learner_token_labels || [],
      Boolean(feedback.is_correct),
    );
  const learnerAnswerMarkup = buildLearnerAnswerMarkup(
    learnerAnswerDisplay,
    canonicalTargetSentence,
    learnerTokenLabels,
  );
  const correctSentenceMarkup = buildCorrectSentenceMarkup(displayedCorrectSentence);
  el.feedbackQuestionText.textContent = "";
  el.learnerAnswer.innerHTML = "";
  el.correctFrench.innerHTML = "";
  reserveTextBlockHeight(el.feedbackQuestionText, questionSentenceDisplay);
  reserveAnimatedMarkupHeight(el.learnerAnswer, learnerAnswerMarkup);
  reserveAnimatedMarkupHeight(el.correctFrench, correctSentenceMarkup);
  const questionSentenceEndDelay = animatePlainText(
    el.feedbackQuestionText,
      questionSentenceDisplay,
      questionSentenceStartDelay,
    );
  const yourAnswerEndDelay = animateInlineSegments(
    el.learnerAnswer,
    buildLearnerAnswerSegments(learnerAnswerDisplay, canonicalTargetSentence, learnerTokenLabels),
    Math.max(yourAnswerStartDelay + 120, questionSentenceEndDelay + 40),
    28,
  );
  const correctSentenceStartDelay = yourAnswerEndDelay + 70;
  const correctSentenceEndDelay = animateInlineSegments(
    el.correctFrench,
    buildCorrectSentenceSegments(displayedCorrectSentence),
    correctSentenceStartDelay + 120,
    30,
  );
  closePhraseExplainer();

  const finalNotes = buildConciseNotes(feedback);
  const notes = [...finalNotes];
  if (feedback.reminders_triggered?.length) {
    notes.push(`Reminder added: ${feedback.reminders_triggered.join(", ")}`);
  }
  const notesStartDelay = Math.max(correctSentenceEndDelay + 80, correctSentenceStartDelay + 240);
  animateNotesList(notes, notesStartDelay + 140);

  scrollWindowToTop();
}

function renderFinalPanel() {
  if (!state.lesson) {
    renderSetupView();
    return;
  }

  document.body.classList.remove("landing-bauhaus-colors");
  clearPromptTyping();
  clearFeedbackTyping();
  clearContentAnimations();
  clearStoryFlight();
  el.lessonCard.classList.remove("hidden");
  el.lessonCard.classList.remove("lesson-card-checking");
  el.lessonHeader.classList.add("hidden");
  el.storySoFarCard.classList.add("hidden");
  el.storySoFarList.innerHTML = "";
  hideLessonScreens();
  el.finalPanel.classList.remove("hidden");
  updateSidebarMeta();
  el.emptyState.classList.add("hidden");
  el.finalTitle.textContent = state.lesson.title;
  const finalEnglishText = state.lesson.sentences.map((sentence) => sentence.english).join(" ");
  const finalFrenchText = state.lesson.sentences.map((sentence) => formatCorrectSentence(sentence.french)).join(" ");
  reserveTextBlockHeight(el.finalEnglishStory, finalEnglishText);
  reserveTextBlockHeight(el.finalFrenchStory, finalFrenchText);
  animateFastNaturalText(el.finalEnglishStory, finalEnglishText, 20);
  animateFastNaturalText(el.finalFrenchStory, finalFrenchText, 70);
  animatePanelIn(el.finalPanel);
  launchCelebrationBurst();
  scrollWindowToTop();
}

function renderCheckingScreen() {
  document.body.classList.remove("landing-bauhaus-colors");
  clearPromptTyping();
  clearFeedbackTyping();
  clearContentAnimations();
  clearStoryFlight();
  el.lessonCard.classList.remove("hidden");
  el.lessonCard.classList.add("lesson-card-checking");
  el.lessonHeader.classList.add("hidden");
  el.storySoFarCard.classList.add("hidden");
  el.storySoFarList.innerHTML = "";
  hideLessonScreens();
  if (el.checkingCopy) {
    el.checkingCopy.textContent = getCheckingTipForCurrentLesson();
  }
  el.checkingPanel.classList.remove("hidden");
  updateSidebarMeta();
  startCheckingEllipsisLoop();
  animatePanelIn(el.checkingPanel);
  scrollWindowToTop();
}

function toggleVocabHints() {
  if (!el.toggleHintsBtn || el.toggleHintsBtn.disabled) {
    return;
  }
  state.hintsVisible = !state.hintsVisible;
  renderHints();
}

async function explainPhrase(phrase, anchorElement) {
  const sentence = currentSentence();
  if (!sentence) return;

  const data = await api("/api/explain-phrase", {
    method: "POST",
    body: JSON.stringify({
      english_sentence: sentence.english,
      language: currentLanguage(),
      target_sentence: sentence.french,
      selected_text: phrase,
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

  el.phraseTitle.textContent = data.selected_text || phrase;
  el.phraseMeaning.textContent = data.english_meaning;
  el.phraseNote.textContent = data.usage_note || data.save_note || "";
  el.phraseExplainer.classList.remove("hidden");
  el.phraseExplainer.style.visibility = "hidden";
  requestAnimationFrame(() => {
    positionPhraseExplainer(anchorElement);
    el.phraseExplainer.style.visibility = "visible";
  });
}

function renderSavedVocab(items) {
  el.savedVocabList.innerHTML = "";
  if (el.sidebarVocabCount) {
    el.sidebarVocabCount.textContent = `${items.length} item${items.length === 1 ? "" : "s"}`;
  }
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
      <div class="saved-vocab-row">
        <strong class="saved-vocab-french">${item.french}</strong>
        <span class="saved-vocab-english">${item.english}</span>
      </div>
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
  const storyBlock = document.createElement("div");
  storyBlock.className = "story-so-far-block story-line-text";

  previousSentences.forEach((sentence, index) => {
    const span = document.createElement("span");
    span.className = "story-sentence";
    span.dataset.step = String(sentence.step);
    span.textContent = formatCorrectSentence(sentence.french);
    storyBlock.appendChild(span);
    if (index < previousSentences.length - 1) {
      storyBlock.appendChild(document.createTextNode(" "));
    }
  });

  el.storySoFarList.appendChild(storyBlock);
}

async function loadConfig() {
  try {
    const config = await api("/api/config");
    state.config = config;
  } catch (error) {
    state.config = null;
  }
}

async function loadVocab() {
  const data = await api(`/api/vocab?language=${encodeURIComponent(currentLanguage())}`);
  renderSavedVocab(data.items);
}

function renderReminders(items) {
  el.remindersList.innerHTML = "";
  const repeated = items.filter((item) => item.count >= 2);
  if (el.sidebarReminderCount) {
    el.sidebarReminderCount.textContent = `${repeated.length} item${repeated.length === 1 ? "" : "s"}`;
  }

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
      <div class="reminder-row">
        <strong class="reminder-item-title">${item.label}</strong>
        <span class="reminder-count">${item.count}x</span>
      </div>
      <p class="reminder-item-explanation">${item.explanation}</p>
    `;
    el.remindersList.appendChild(div);
  });
}

async function loadReminders() {
  const data = await api(`/api/reminders?language=${encodeURIComponent(currentLanguage())}`);
  renderReminders(data.items);
}

function updateSidebarMeta() {
  const lesson = state.lesson;
  const requestedCount = lesson?.requested_sentence_count || lesson?.sentences?.length || 0;
  const progressValue = lesson ? Math.min(state.currentIndex + 1, requestedCount || 0) : 0;

  if (el.sidebarLessonTitle) {
    el.sidebarLessonTitle.textContent = lesson?.title || "Choose your story";
  }
  if (el.sidebarTheme) {
    el.sidebarTheme.textContent =
      lesson?.theme ||
      document.querySelector("#theme")?.value?.trim() ||
      "Greek myth";
  }
  if (el.sidebarLanguage) {
    el.sidebarLanguage.textContent = currentLanguage() === "spanish" ? "Spanish" : "French";
  }
  if (el.sidebarDifficulty) {
    el.sidebarDifficulty.textContent =
      lesson?.difficulty ||
      document.querySelector("#difficulty")?.value ||
      "A1";
  }
  if (el.sidebarProgress) {
    el.sidebarProgress.textContent = `${progressValue} / ${requestedCount || 0}`;
  }
}

async function generateLesson(event) {
  event.preventDefault();
  const button = document.querySelector("#generate-btn");
  button.disabled = true;
  button.textContent = "Generating lesson...";
  button.classList.add("button-loading");
  renderGeneratingStoryScreen();

  try {
    const lessonLength = document.querySelector("#lesson-length").value;
    const sentenceCountMap = {
      short: 5,
      medium: 8,
      long: 12,
    };
    const payload = {
      language: currentLanguage(),
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
    resetCheckingTipHistory(lesson.lesson_id);
    state.currentIndex = 0;
    state.lastAnswer = "";
    ensureLessonPolling();
    if (currentSentence()) {
      renderLesson();
    } else {
      renderGeneratingStoryScreen();
    }
  } catch (error) {
    renderSetupView();
    alert(`Could not generate lesson: ${error.message}`);
  } finally {
    button.disabled = false;
    button.innerHTML = '<span class="generate-btn-label">Generate lesson!</span><span class="generate-btn-hint">Press <kbd>Enter</kbd> to continue.</span>';
    button.classList.remove("button-loading");
    button.style.opacity = "";
    button.style.transform = "";
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
  el.checkBtn.textContent = "Checking...";
  renderCheckingScreen();
  try {
    state.lastAnswer = learnerAnswer;
    const feedback = await api("/api/evaluate", {
      method: "POST",
      body: JSON.stringify({
        language: currentLanguage(),
        english: sentence.english,
        target_sentence: sentence.french,
        learner_answer: learnerAnswer,
        difficulty: state.lesson.difficulty,
        context_note: sentence.context_note,
        vocab_hints: sentence.vocab_hints || [],
      }),
    });
    renderFeedback(feedback);
    await loadReminders();
  } catch (error) {
    alert(`Could not evaluate answer: ${error.message}`);
    renderLesson();
  } finally {
    el.checkBtn.disabled = false;
    el.checkBtn.textContent = "Check answer";
  }
}

function animateCurrentSentenceIntoStory() {
  const sentence = currentSentence();
  if (!sentence) {
    renderLesson();
    return;
  }

  const sourceRect = el.correctFrench.getBoundingClientRect();
  state.nextTransitionInProgress = true;
  state.currentIndex += 1;
  renderLesson(true);

  if (sourceRect.width === 0 || sourceRect.height === 0) {
    state.nextTransitionInProgress = false;
    return;
  }

  requestAnimationFrame(() => {
    const target = el.storySoFarList.querySelector(`.story-sentence[data-step="${sentence.step}"]`);
    if (!target) {
      state.nextTransitionInProgress = false;
      return;
    }

    target.classList.add("story-sentence-pending");

    const targetRect = target.getBoundingClientRect();
    const ghost = document.createElement("div");
    ghost.className = "story-flight-clone";
    ghost.textContent = formatCorrectSentence(sentence.french);
    ghost.style.left = `${sourceRect.left + 8}px`;
    ghost.style.top = `${sourceRect.top + 6}px`;
    ghost.style.width = `${Math.min(Math.max(sourceRect.width - 24, 180), 560)}px`;
    ghost.style.opacity = "0.98";
    ghost.style.transform = "scale(1)";
    document.body.appendChild(ghost);

    const finishFlight = () => {
      ghost.remove();
      target.classList.remove("story-sentence-pending");
      target.classList.add("story-sentence-landed");
      state.storyFlightCleanupTimer = setTimeout(() => {
        target.classList.remove("story-sentence-landed");
        state.storyFlightCleanupTimer = null;
      }, 420);
      state.storyFlightFinishTimer = null;
      state.nextTransitionInProgress = false;
    };

    requestAnimationFrame(() => {
      void ghost.offsetWidth;
      ghost.style.left = `${Math.max(12, targetRect.left - 10)}px`;
      ghost.style.top = `${targetRect.top - 8}px`;
      ghost.style.width = `${Math.max(targetRect.width + 20, 120)}px`;
      ghost.style.opacity = "0.12";
      ghost.style.transform = "scale(0.92)";
    });

    ghost.addEventListener("transitionend", finishFlight, { once: true });
    state.storyFlightFinishTimer = setTimeout(finishFlight, 520);
  });
}

function nextSentence() {
  if (state.nextTransitionInProgress) return;
  if (!state.lesson) return;
  if (state.currentIndex >= state.lesson.sentences.length - 1 && !state.lesson.is_complete) {
    animateCurrentSentenceIntoStory();
    return;
  }
  if (state.currentIndex < state.lesson.sentences.length - 1) {
    animateCurrentSentenceIntoStory();
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
    suggested_sentence: sentence.french,
    more_common_sentence: sentence.french,
    tips: ["Read the target answer aloud once before moving on."],
    mistakes: [],
    learner_token_labels: [],
    encouraging_note: "Skipping quickly is fine when you want to keep the lesson flowing.",
  });
}

async function addSelectedPhraseToVocab() {
  if (!selectedPhraseData) return;
  await api("/api/vocab", {
    method: "POST",
    body: JSON.stringify({
      ...selectedPhraseData,
      language: currentLanguage(),
    }),
  });
  await loadVocab();
  closePhraseExplainer();
}

async function exportVocab() {
  const csv = await api(`/api/vocab/export?language=${encodeURIComponent(currentLanguage())}`);
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
  await explainPhrase(target.dataset.phrase, target);
});
el.toggleHintsBtn.addEventListener("click", toggleVocabHints);
el.addPhraseBtn.addEventListener("click", addSelectedPhraseToVocab);
el.closePhraseBtn.addEventListener("click", closePhraseExplainer);
el.exportBtn.addEventListener("click", exportVocab);
el.restartBtn.addEventListener("click", () => renderSetupView());
el.languageFrenchBtn?.addEventListener("click", () => setLanguage("french"));
el.languageSpanishBtn?.addEventListener("click", () => setLanguage("spanish"));
el.appMasthead.addEventListener("click", () => renderSetupView());
el.sidebarHomeBtn.addEventListener("click", () => renderSetupView());
el.appMasthead.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    renderSetupView();
  }
});
document.addEventListener("click", (event) => {
  if (!el.vocabHints.classList.contains("hidden")) {
    if (!event.target.closest("#toggle-hints-btn") && !el.vocabHints.contains(event.target)) {
      state.hintsVisible = false;
      closeVocabHintsBubble();
      renderHints();
    }
  }

  if (!el.phraseExplainer.classList.contains("hidden")) {
    if (event.target.closest(".inline-phrase-btn")) {
      return;
    }
    if (!el.phraseExplainer.contains(event.target)) {
      closePhraseExplainer();
    }
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Tab" || event.altKey || event.ctrlKey || event.metaKey) {
    return;
  }
  if (el.promptPanel.classList.contains("hidden") || el.toggleHintsBtn.disabled) {
    return;
  }
  event.preventDefault();
  toggleVocabHints();
});

function handleGlobalEnter(event) {
  if (event.key === "Escape") {
    let closedOverlay = false;
    if (!el.phraseExplainer.classList.contains("hidden")) {
      closePhraseExplainer();
      closedOverlay = true;
    }
    if (!el.vocabHints.classList.contains("hidden")) {
      state.hintsVisible = false;
      closeVocabHintsBubble();
      renderHints();
      closedOverlay = true;
    }
    if (closedOverlay) {
      event.preventDefault();
      return;
    }
  }

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

  if (isPromptVisible()) {
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
    }
    evaluateCurrentAnswer();
    return;
  }

  if (isSetupVisible()) {
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
    }
    if (!el.lessonForm.querySelector("#generate-btn")?.disabled) {
      el.lessonForm.requestSubmit();
    }
    return;
  }

  if (isFeedbackVisible()) {
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
    }
    nextSentence();
    return;
  }

  if (isFinalVisible()) {
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
    }
    renderSetupView();
  }
}

document.addEventListener("keydown", handleGlobalEnter, true);

loadConfig();
loadVocab();
loadReminders();
renderStorySoFar();
updateLanguageToggle();
renderSetupView();
watchForDevReload();
