const state = {
  session: null,
  loading: false,
};

const el = {
  startForm: document.querySelector("#start-form"),
  actionForm: document.querySelector("#action-form"),
  startBtn: document.querySelector("#start-btn"),
  actBtn: document.querySelector("#act-btn"),
  difficulty: document.querySelector("#difficulty"),
  theme: document.querySelector("#theme"),
  setting: document.querySelector("#setting"),
  playerName: document.querySelector("#player-name"),
  learnerInput: document.querySelector("#learner-input"),
  sourcePill: document.querySelector("#source-pill"),
  adventureTitle: document.querySelector("#adventure-title"),
  turnCount: document.querySelector("#turn-count"),
  locationName: document.querySelector("#location-name"),
  locationDescription: document.querySelector("#location-description"),
  visualMotif: document.querySelector("#visual-motif"),
  ambience: document.querySelector("#ambience"),
  objective: document.querySelector("#objective"),
  playerPrompt: document.querySelector("#player-prompt"),
  npcName: document.querySelector("#npc-name"),
  npcRole: document.querySelector("#npc-role"),
  npcFrench: document.querySelector("#npc-french"),
  npcEnglish: document.querySelector("#npc-english"),
  statusCopy: document.querySelector("#status-copy"),
  feedbackPanel: document.querySelector("#feedback-panel"),
  feedbackScore: document.querySelector("#feedback-score"),
  feedbackNote: document.querySelector("#feedback-note"),
  feedbackCorrection: document.querySelector("#feedback-correction"),
  feedbackEncouragement: document.querySelector("#feedback-encouragement"),
  transcriptList: document.querySelector("#transcript-list"),
  charactersList: document.querySelector("#characters-list"),
  tasksList: document.querySelector("#tasks-list"),
  inventoryList: document.querySelector("#inventory-list"),
  brainOutput: document.querySelector("#brain-output"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json();
}

function setLoading(loading, label) {
  state.loading = loading;
  el.startBtn.disabled = loading;
  el.actBtn.disabled = loading || !state.session;
  el.statusCopy.textContent = label;
}

function renderList(container, items, mapper) {
  container.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "stack-item";
    empty.textContent = "Nothing here yet.";
    container.appendChild(empty);
    return;
  }
  items.forEach((item) => container.appendChild(mapper(item)));
}

function appendLines(node, lines) {
  lines.filter(Boolean).forEach((line, index) => {
    if (index > 0) {
      node.appendChild(document.createElement("br"));
    }
    node.appendChild(document.createTextNode(line));
  });
}

function renderSession(session) {
  state.session = session;
  el.sourcePill.textContent = session.source === "openai" ? "LLM Live" : "Fallback Story Engine";
  el.adventureTitle.textContent = session.title;
  el.turnCount.textContent = String(session.turn);
  el.locationName.textContent = session.scene.location_name;
  el.locationDescription.textContent = session.scene.location_description;
  el.visualMotif.textContent = session.scene.visual_motif;
  el.ambience.textContent = session.scene.ambience;
  el.objective.textContent = session.scene.objective;
  el.playerPrompt.textContent = session.scene.player_prompt;
  el.npcName.textContent = session.scene.npc_name;
  el.npcRole.textContent = session.scene.npc_role;
  el.npcFrench.textContent = session.scene.npc_message_french;
  el.npcEnglish.textContent = session.scene.npc_message_english || "";
  el.brainOutput.textContent = session.brain_markdown || "# Adventure Brain";

  renderList(el.charactersList, session.characters || [], (character) => {
    const node = document.createElement("div");
    node.className = "stack-item";
    const strong = document.createElement("strong");
    strong.textContent = character.name;
    node.appendChild(strong);
    appendLines(node, [character.role, character.mood || "", character.note || ""]);
    return node;
  });

  renderList(el.tasksList, session.tasks || [], (task) => {
    const node = document.createElement("div");
    node.className = `stack-item ${task.status === "complete" ? "complete" : ""}`;
    const strong = document.createElement("strong");
    strong.textContent = task.title;
    node.appendChild(strong);
    appendLines(node, [task.description]);
    return node;
  });

  renderList(el.inventoryList, session.inventory || [], (item) => {
    const node = document.createElement("div");
    node.className = "stack-item";
    node.textContent = item;
    return node;
  });

  renderList(el.transcriptList, session.transcript || [], (line) => {
    const node = document.createElement("div");
    node.className = "transcript-line";
    const parts = line.split(":");
    if (parts.length > 1) {
      const speaker = parts.shift();
      const strong = document.createElement("strong");
      strong.textContent = `${speaker}:`;
      node.appendChild(strong);
      node.appendChild(document.createTextNode(parts.join(":")));
    } else {
      node.textContent = line;
    }
    return node;
  });

  if (session.feedback) {
    el.feedbackPanel.classList.remove("hidden");
    el.feedbackScore.textContent = `${session.feedback.score}`;
    el.feedbackScore.style.color = session.feedback.accepted ? "var(--success)" : "var(--danger)";
    el.feedbackNote.textContent = session.feedback.teacher_note;
    el.feedbackCorrection.textContent = session.feedback.correction_french;
    el.feedbackEncouragement.textContent = session.feedback.encouragement || "";
  } else {
    el.feedbackPanel.classList.add("hidden");
  }

  el.actBtn.disabled = false;
}

async function startAdventure(event) {
  event.preventDefault();
  setLoading(true, "Generating a new French world...");
  try {
    const session = await api("/api/adventure/start", {
      method: "POST",
      body: JSON.stringify({
        difficulty: el.difficulty.value,
        theme: el.theme.value.trim() || "missing festival lanterns",
        setting: el.setting.value.trim() || "rainy seaside town",
        player_name: el.playerName.value.trim() || "Camille",
      }),
    });
    renderSession(session);
    el.learnerInput.value = "";
    el.learnerInput.focus();
    setLoading(false, "Adventure ready. Type French to speak or act.");
  } catch (error) {
    setLoading(false, `Could not start adventure: ${error.message}`);
  }
}

async function submitAction(event) {
  event.preventDefault();
  if (!state.session) {
    return;
  }
  const learnerFrench = el.learnerInput.value.trim();
  if (!learnerFrench) {
    el.statusCopy.textContent = "Type some French first.";
    return;
  }

  setLoading(true, "The world is reacting to your French...");
  try {
    const session = await api("/api/adventure/action", {
      method: "POST",
      body: JSON.stringify({
        session_id: state.session.session_id,
        learner_french: learnerFrench,
      }),
    });
    renderSession(session);
    el.learnerInput.value = "";
    el.learnerInput.focus();
    setLoading(false, "Turn complete. Keep the conversation moving in French.");
  } catch (error) {
    setLoading(false, `Could not submit action: ${error.message}`);
  }
}

el.startForm.addEventListener("submit", startAdventure);
el.actionForm.addEventListener("submit", submitAction);
