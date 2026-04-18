const MAX_ANSWER_CHARS = window.APP_CONFIG?.answerMaxChars || 1200;

const state = {
    socket: null,
    sessionId: "",
    correlationId: "",
    role: "AI Engineer",
    provider: "auto",
    difficulty: "mid",
    interviewType: "mixed",
    companyStyle: "neutral",
    language: "English",
    questionGoal: 4,
    questionCount: 0,
    feedbackCount: 0,
    activeProvider: "auto",
    activeModel: "",
    progressLabels: [],
    transcript: [],
    summary: null,
    finished: false,
    scores: [],
    historyItems: [],
    selectedHistoryId: "",
    selectedHistorySession: null,
    timerInterval: null,
    currentQuestionSeconds: 0,
    longWaitTimeout: null,
    currentView: "live",
};

const dom = {
    body: document.body,
    jobRole: document.getElementById("jobRole"),
    providerSelect: document.getElementById("providerSelect"),
    difficultySelect: document.getElementById("difficultySelect"),
    interviewTypeSelect: document.getElementById("interviewTypeSelect"),
    companyStyleSelect: document.getElementById("companyStyleSelect"),
    languageSelect: document.getElementById("languageSelect"),
    questionCountSelect: document.getElementById("questionCountSelect"),
    sessionLength: document.getElementById("sessionLength"),
    planPreview: document.getElementById("planPreview"),
    startBtn: document.getElementById("startBtn"),
    restartBtn: document.getElementById("restartBtn"),
    resumeBtn: document.getElementById("resumeBtn"),
    openHistoryBtn: document.getElementById("openHistoryBtn"),
    setupAdvanced: document.getElementById("setupAdvanced"),
    sendBtn: document.getElementById("sendBtn"),
    msgInput: document.getElementById("msgInput"),
    charCount: document.getElementById("charCount"),
    charMax: document.getElementById("charMax"),
    messages: document.getElementById("messages"),
    typingIndicator: document.getElementById("typingIndicator"),
    systemCard: document.getElementById("systemCard"),
    questionProgressText: document.getElementById("question-progress-text"),
    feedbackCount: document.getElementById("feedback-count"),
    messageCount: document.getElementById("message-count"),
    averageScore: document.getElementById("average-score"),
    providerBadge: document.getElementById("providerBadge"),
    statusBadge: document.getElementById("statusBadge"),
    roleDisplay: document.getElementById("role-display"),
    sessionCopy: document.getElementById("session-copy"),
    progressSteps: document.getElementById("progressSteps"),
    currentLabelPill: document.getElementById("currentLabelPill"),
    strengthList: document.getElementById("strengthList"),
    weaknessList: document.getElementById("weaknessList"),
    sessionIdValue: document.getElementById("session-id-value"),
    questionTimer: document.getElementById("questionTimer"),
    themeToggleBtn: document.getElementById("themeToggleBtn"),
    sidebarToggleBtn: document.getElementById("sidebarToggleBtn"),
    sidebarCloseBtn: document.getElementById("sidebarCloseBtn"),
    sidebarBackdrop: document.getElementById("sidebarBackdrop"),
    sidebarRole: document.getElementById("sidebarRole"),
    sidebarProvider: document.getElementById("sidebarProvider"),
    sidebarProgress: document.getElementById("sidebarProgress"),
    sidebarStatus: document.getElementById("sidebarStatus"),
    exportTxtBtn: document.getElementById("exportTxtBtn"),
    exportJsonBtn: document.getElementById("exportJsonBtn"),
    exportPdfBtn: document.getElementById("exportPdfBtn"),
    copySummaryBtn: document.getElementById("copySummaryBtn"),
    tabButtons: [...document.querySelectorAll(".tab-button")],
    liveView: document.getElementById("liveView"),
    summaryView: document.getElementById("summaryView"),
    historyView: document.getElementById("historyView"),
    summaryEmpty: document.getElementById("summaryEmpty"),
    summaryContent: document.getElementById("summaryContent"),
    summaryReadiness: document.getElementById("summaryReadiness"),
    summaryClosing: document.getElementById("summaryClosing"),
    summaryScore: document.getElementById("summaryScore"),
    summaryStrengths: document.getElementById("summaryStrengths"),
    summaryWeakAreas: document.getElementById("summaryWeakAreas"),
    summaryImprovements: document.getElementById("summaryImprovements"),
    summaryRecommendations: document.getElementById("summaryRecommendations"),
    summaryTranscript: document.getElementById("summaryTranscript"),
    historyList: document.getElementById("historyList"),
    historyDetailEmpty: document.getElementById("historyDetailEmpty"),
    historyDetail: document.getElementById("historyDetail"),
    refreshHistoryBtn: document.getElementById("refreshHistoryBtn"),
    presetChips: [...document.querySelectorAll(".preset-chip")],
};

const STORAGE_KEYS = {
    theme: "intervix.theme",
    lastSession: "intervix.lastSession",
    lastConfig: "intervix.lastConfig",
};

function escapeHtml(value) {
    return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function renderMarkdown(markdown) {
    const lines = String(markdown || "").split("\n");
    const output = [];
    let listItems = [];

    const flushList = () => {
        if (!listItems.length) {
            return;
        }
        output.push(`<ul>${listItems.join("")}</ul>`);
        listItems = [];
    };

    const formatInline = (line) =>
        escapeHtml(line).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line) {
            flushList();
            continue;
        }
        if (line.startsWith("- ")) {
            listItems.push(`<li>${formatInline(line.slice(2))}</li>`);
            continue;
        }
        flushList();
        output.push(`<p>${formatInline(line)}</p>`);
    }
    flushList();
    return output.join("");
}

function formatTimestamp(isoString) {
    try {
        return new Date(isoString).toLocaleString();
    } catch {
        return isoString || "";
    }
}

function formatProviderLabel(provider, model = "") {
    const pretty = provider ? `${provider.charAt(0).toUpperCase()}${provider.slice(1)}` : "Auto";
    return model ? `${pretty} | ${model}` : pretty;
}

function formatTimer(seconds) {
    const mins = String(Math.floor(seconds / 60)).padStart(2, "0");
    const secs = String(seconds % 60).padStart(2, "0");
    return `${mins}:${secs}`;
}

function computeSessionEstimate(questionCount, interviewType) {
    const perQuestion = {
        mixed: 4,
        technical: 4,
        behavioral: 4,
        hr: 3,
        system_design: 6,
    };
    return Math.max(6, Number(questionCount) * (perQuestion[interviewType] || 4) + 2);
}

function buildProgressLabels(questionCount, interviewType, difficulty) {
    const map = {
        technical: {
            beginner: ["Foundations", "Applied Basics", "Debugging", "Trade-offs", "Delivery", "Communication", "Growth", "Wrap-up"],
            mid: ["Core Depth", "Execution", "Debugging", "Trade-offs", "Architecture", "Collaboration", "Ownership", "Growth"],
            senior: ["Depth", "Architecture", "Trade-offs", "Leadership", "Risk", "Scaling", "Influence", "Strategy"],
        },
        system_design: {
            beginner: ["Requirements", "Components", "Data Flow", "Trade-offs", "Reliability", "Scale", "Risks", "Wrap-up"],
            mid: ["Scope", "Architecture", "Interfaces", "Scale", "Reliability", "Trade-offs", "Operations", "Leadership"],
            senior: ["Product Scope", "Architecture", "Bottlenecks", "Capacity", "Trade-offs", "Failure Modes", "Roadmap", "Leadership"],
        },
        behavioral: {
            beginner: ["Context", "Actions", "Learning", "Communication", "Teamwork", "Ownership", "Growth", "Wrap-up"],
            mid: ["Situation", "Actions", "Conflict", "Ownership", "Impact", "Stakeholders", "Reflection", "Growth"],
            senior: ["Leadership", "Conflict", "Decision Quality", "Influence", "Hiring", "Prioritization", "Reflection", "Growth"],
        },
        hr: {
            beginner: ["Motivation", "Fit", "Strengths", "Weak Spots", "Team Style", "Communication", "Growth", "Wrap-up"],
            mid: ["Motivation", "Role Fit", "Career Story", "Pressure", "Stakeholders", "Feedback", "Growth", "Wrap-up"],
            senior: ["Leadership Fit", "Strategy", "Influence", "Pressure", "Communication", "Hiring", "Growth", "Closing"],
        },
        mixed: {
            beginner: ["Foundations", "Execution", "Learning", "Communication", "Teamwork", "Trade-offs", "Growth", "Wrap-up"],
            mid: ["Core Depth", "Execution", "Trade-offs", "Communication", "Ownership", "Growth", "Leadership", "Wrap-up"],
            senior: ["Depth", "Trade-offs", "Architecture", "Leadership", "Influence", "Risk", "Strategy", "Closing"],
        },
    };
    return (map[interviewType]?.[difficulty] || map.mixed.mid).slice(0, Number(questionCount));
}

function getCurrentConfig() {
    return {
        role: dom.jobRole.value.trim() || "AI Engineer",
        provider: dom.providerSelect.value,
        difficulty: dom.difficultySelect.value,
        interviewType: dom.interviewTypeSelect.value,
        companyStyle: dom.companyStyleSelect.value,
        language: dom.languageSelect.value,
        questionCount: Number(dom.questionCountSelect.value),
    };
}

function persistLastConfig(config) {
    localStorage.setItem(STORAGE_KEYS.lastConfig, JSON.stringify(config));
}

function getLastConfig() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEYS.lastConfig) || "null");
    } catch {
        return null;
    }
}

function persistSessionMeta(data) {
    localStorage.setItem(STORAGE_KEYS.lastSession, JSON.stringify(data));
}

function getPersistedSessionMeta() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEYS.lastSession) || "null");
    } catch {
        return null;
    }
}

function syncConfigPreview() {
    const config = getCurrentConfig();
    const labels = buildProgressLabels(config.questionCount, config.interviewType, config.difficulty);
    dom.sessionLength.textContent = `~${computeSessionEstimate(config.questionCount, config.interviewType)} min`;
    dom.planPreview.textContent = labels.join(" / ");
    renderProgressSteps(labels, state.questionCount);
    state.questionGoal = config.questionCount;
}

function renderProgressSteps(labels, current = 0) {
    state.progressLabels = labels;
    dom.progressSteps.innerHTML = labels
        .map((label, index) => {
            const stepNumber = index + 1;
            const classes = [
                "progress-step",
                stepNumber <= current ? "is-active" : "",
                stepNumber === current && current !== 0 ? "is-current" : "",
            ]
                .filter(Boolean)
                .join(" ");
            return `<div class="${classes}">${escapeHtml(label)}</div>`;
        })
        .join("");
    dom.questionProgressText.textContent = `${current} / ${labels.length || state.questionGoal}`;
    dom.currentLabelPill.textContent = current > 0 ? labels[current - 1] : "Waiting";
}

function setStatus(label, variant = "idle") {
    dom.statusBadge.textContent = label;
    dom.statusBadge.className = `status-badge ${variant}`;
}

function setSystemCard(message) {
    dom.systemCard.textContent = message;
}

function startQuestionTimer() {
    stopQuestionTimer();
    state.currentQuestionSeconds = 0;
    dom.questionTimer.textContent = "00:00";
    state.timerInterval = window.setInterval(() => {
        state.currentQuestionSeconds += 1;
        dom.questionTimer.textContent = formatTimer(state.currentQuestionSeconds);
    }, 1000);
}

function stopQuestionTimer() {
    if (state.timerInterval) {
        window.clearInterval(state.timerInterval);
        state.timerInterval = null;
    }
}

function setTyping(visible) {
    dom.typingIndicator.classList.toggle("hidden", !visible);
    if (state.longWaitTimeout) {
        window.clearTimeout(state.longWaitTimeout);
        state.longWaitTimeout = null;
    }
    if (visible) {
        state.longWaitTimeout = window.setTimeout(() => {
            setSystemCard("The model is taking longer than usual. The session is still running.");
        }, 12000);
    }
}

function updateProviderBadge(provider, model = "") {
    state.activeProvider = provider || "auto";
    state.activeModel = model || "";
    dom.providerBadge.textContent = formatProviderLabel(state.activeProvider, state.activeModel);
}

function updateCounters() {
    dom.questionProgressText.textContent = `${state.questionCount} / ${state.progressLabels.length || state.questionGoal}`;
    dom.feedbackCount.textContent = String(state.feedbackCount);
    dom.messageCount.textContent = String(state.transcript.length);
    const average = state.scores.length
        ? (state.scores.reduce((sum, value) => sum + value, 0) / state.scores.length).toFixed(1)
        : "0.0";
    dom.averageScore.textContent = average;
    updateSidebarInfo();
}

function setPreset(role) {
    dom.presetChips.forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.role === role);
    });
}

function enableComposer(enabled, prompt = "") {
    dom.msgInput.disabled = !enabled;
    dom.sendBtn.disabled = !enabled;
    dom.msgInput.placeholder = enabled
        ? prompt || "Write your answer and press Enter to send."
        : "Your answer will unlock when the interviewer asks a question.";
    if (enabled) {
        dom.msgInput.focus();
        startQuestionTimer();
    } else {
        stopQuestionTimer();
    }
}

function updateCharCounter() {
    dom.charCount.textContent = String(dom.msgInput.value.length);
}

function updateSidebarInfo() {
    if (!dom.sidebarRole) {
        return;
    }
    dom.sidebarRole.textContent = state.role || "AI Engineer";
    dom.sidebarProvider.textContent = formatProviderLabel(state.provider, state.activeModel);
    dom.sidebarProgress.textContent = `${state.questionCount} / ${state.questionGoal}`;
    dom.sidebarStatus.textContent = dom.statusBadge?.textContent || "Idle";
}

function setSidebarOpen(open) {
    dom.body.classList.toggle("sidebar-open", open);
    if (dom.sidebarPanel) {
        dom.sidebarPanel.setAttribute("aria-hidden", String(!open));
    }
    updateSidebarInfo();
}

function toggleSidebar() {
    setSidebarOpen(!dom.body.classList.contains("sidebar-open"));
}

function closeSidebar() {
    setSidebarOpen(false);
}

function setView(viewName) {
    state.currentView = viewName;
    dom.body.dataset.view = viewName;
    const mapping = {
        live: dom.liveView,
        summary: dom.summaryView,
        history: dom.historyView,
    };
    Object.entries(mapping).forEach(([name, node]) => {
        node.classList.toggle("is-active", name === viewName);
    });
    dom.tabButtons.forEach((button) => {
        const selected = button.dataset.view === viewName;
        button.classList.toggle("is-active", selected);
        button.setAttribute("aria-selected", String(selected));
    });
}

function resetTranscriptView() {
    dom.messages.innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">+</div>
            <h3>Start a smarter interview</h3>
            <p>
                Your interviewer question, your answer, the coach rubric, and live session insights will appear here.
                Try <button class="inline-example" type="button" data-role-example="Frontend Developer">Frontend Developer</button>
                or <button class="inline-example" type="button" data-role-example="Data Analyst">Data Analyst</button>.
            </p>
        </div>
    `;
    state.transcript = [];
    state.scores = [];
    state.questionCount = 0;
    state.feedbackCount = 0;
    state.finished = false;
    updateCounters();
    renderProgressSteps(buildProgressLabels(state.questionGoal, state.interviewType, state.difficulty), 0);
    dom.exportTxtBtn.disabled = true;
    dom.exportJsonBtn.disabled = true;
    dom.exportPdfBtn.disabled = true;
}

function removeEmptyState() {
    const emptyState = dom.messages.querySelector(".empty-state");
    if (emptyState) {
        emptyState.remove();
    }
}

async function copyText(text, successMessage = "Copied to clipboard.") {
    try {
        await navigator.clipboard.writeText(text);
        setSystemCard(successMessage);
    } catch {
        setSystemCard("Copy failed in this browser.");
    }
}

function pushTranscript(item) {
    state.transcript.push({
        ...item,
        timestamp: new Date().toISOString(),
    });
    dom.exportTxtBtn.disabled = false;
    dom.exportJsonBtn.disabled = false;
    dom.exportPdfBtn.disabled = false;
    updateCounters();
}

function createBubble({ actor, content, role, meta = "", markdown = false }, skipStore = false) {
    removeEmptyState();

    const bubble = document.createElement("article");
    bubble.className = `bubble ${role}`;

    const head = document.createElement("div");
    head.className = "bubble-head";

    const left = document.createElement("div");
    left.className = "bubble-head-left";

    const actorEl = document.createElement("span");
    actorEl.className = "bubble-actor";
    actorEl.textContent = actor;

    const metaEl = document.createElement("span");
    metaEl.className = "bubble-meta";
    metaEl.textContent = meta;

    const copyBtn = document.createElement("button");
    copyBtn.className = "bubble-copy";
    copyBtn.type = "button";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", () => copyText(content, `${actor} bubble copied.`));

    left.append(actorEl, metaEl);
    head.append(left, copyBtn);

    const contentEl = document.createElement("div");
    contentEl.className = "bubble-content";
    if (markdown) {
        contentEl.innerHTML = renderMarkdown(content);
    } else {
        contentEl.textContent = content;
    }

    bubble.append(head, contentEl);
    dom.messages.appendChild(bubble);
    dom.messages.scrollTop = dom.messages.scrollHeight;

    if (!skipStore) {
        pushTranscript({ actor, content, role, meta, markdown });
    }
}

function addSpecialBubble(text, type = "note") {
    createBubble(
        {
            actor: type === "error" ? "System Error" : "System",
            content: text,
            role: type,
            meta: "",
            markdown: false,
        },
        false,
    );
}

function hydrateTranscript(items) {
    dom.messages.innerHTML = "";
    state.transcript = [];
    items.forEach((item) => {
        createBubble(
            {
                actor: item.actor,
                content: item.content,
                role: item.role,
                meta: item.meta || "",
                markdown: item.role === "evaluator",
            },
            false,
        );
    });
}

function renderInsightList(node, items, emptyMessage) {
    node.innerHTML = items.length
        ? items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
        : `<li>${escapeHtml(emptyMessage)}</li>`;
}

function renderSummary(summary) {
    state.summary = summary;
    dom.summaryEmpty.classList.add("hidden");
    dom.summaryContent.classList.remove("hidden");
    dom.summaryReadiness.textContent = summary.readiness || "Session complete";
    dom.summaryClosing.textContent = summary.closing_message || "";
    dom.summaryScore.textContent = String(summary.final_score ?? 0);
    renderInsightList(dom.summaryStrengths, summary.strengths || [], "No strengths captured.");
    renderInsightList(dom.summaryWeakAreas, summary.weak_areas || [], "No weak areas captured.");
    renderInsightList(dom.summaryImprovements, summary.top_improvements || [], "No improvements captured.");
    renderInsightList(dom.summaryRecommendations, summary.recommendations || [], "No recommendations captured.");
    dom.summaryTranscript.innerHTML = state.transcript
        .map((item) => {
            const body = item.markdown ? renderMarkdown(item.content) : `<p>${escapeHtml(item.content)}</p>`;
            return `
                <div class="summary-transcript-block">
                    <strong>${escapeHtml(item.actor)}${item.meta ? ` | ${escapeHtml(item.meta)}` : ""}</strong>
                    ${body}
                </div>
            `;
        })
        .join("");
}

function getExportPayload() {
    return {
        sessionId: state.sessionId,
        correlationId: state.correlationId,
        role: state.role,
        provider: state.activeProvider,
        model: state.activeModel,
        difficulty: state.difficulty,
        interviewType: state.interviewType,
        companyStyle: state.companyStyle,
        language: state.language,
        questionGoal: state.questionGoal,
        transcript: state.transcript,
        summary: state.summary,
        exportedAt: new Date().toISOString(),
    };
}

function downloadBlob(filename, contents, type) {
    const blob = new Blob([contents], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
}

function exportTxt() {
    if (!state.transcript.length) {
        setSystemCard("There is no transcript to export yet.");
        return;
    }
    const transcript = state.transcript
        .map((item) => `[${formatTimestamp(item.timestamp)}] ${item.actor}${item.meta ? ` (${item.meta})` : ""}: ${item.content}`)
        .join("\n\n");
    const summary = state.summary
        ? `\n\nFinal score: ${state.summary.final_score}\nStrengths: ${(state.summary.strengths || []).join("; ")}\nWeak areas: ${(state.summary.weak_areas || []).join("; ")}\nRecommendations: ${(state.summary.recommendations || []).join("; ")}`
        : "";
    downloadBlob(
        `${state.role.toLowerCase().replace(/\s+/g, "-")}-interview.txt`,
        transcript + summary,
        "text/plain;charset=utf-8",
    );
    setSystemCard("TXT export ready.");
}

function exportJson() {
    if (!state.transcript.length) {
        setSystemCard("There is no transcript to export yet.");
        return;
    }
    downloadBlob(
        `${state.role.toLowerCase().replace(/\s+/g, "-")}-interview.json`,
        JSON.stringify(getExportPayload(), null, 2),
        "application/json;charset=utf-8",
    );
    setSystemCard("JSON export ready.");
}

function exportPdf() {
    if (!state.transcript.length) {
        setSystemCard("There is no transcript to export yet.");
        return;
    }
    const popup = window.open("", "_blank", "width=960,height=800");
    if (!popup) {
        setSystemCard("Popup blocked. Allow popups to export PDF.");
        return;
    }

    const summaryHtml = state.summary
        ? `
            <section>
                <h2>Final Summary</h2>
                <p><strong>Final score:</strong> ${state.summary.final_score}</p>
                <p><strong>Readiness:</strong> ${escapeHtml(state.summary.readiness || "")}</p>
                <p>${escapeHtml(state.summary.closing_message || "")}</p>
                <h3>Strengths</h3>
                <ul>${(state.summary.strengths || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
                <h3>Weak Areas</h3>
                <ul>${(state.summary.weak_areas || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
                <h3>Recommendations</h3>
                <ul>${(state.summary.recommendations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </section>
        `
        : "";

    const transcriptHtml = state.transcript
        .map((item) => {
            const body = item.markdown ? renderMarkdown(item.content) : `<p>${escapeHtml(item.content)}</p>`;
            return `
                <article style="padding: 14px; border: 1px solid #dbe4ea; border-radius: 12px; margin-bottom: 10px;">
                    <strong>${escapeHtml(item.actor)}${item.meta ? ` | ${escapeHtml(item.meta)}` : ""}</strong>
                    ${body}
                </article>
            `;
        })
        .join("");

    popup.document.write(`
        <html>
            <head>
                <title>${escapeHtml(state.role)} interview report</title>
                <style>
                    body { font-family: Arial, sans-serif; padding: 28px; color: #111827; }
                    h1, h2, h3 { margin-bottom: 10px; }
                    p, li { line-height: 1.6; }
                    ul { padding-left: 20px; }
                </style>
            </head>
            <body>
                <h1>${escapeHtml(state.role)} Interview Report</h1>
                <p><strong>Provider:</strong> ${escapeHtml(formatProviderLabel(state.activeProvider, state.activeModel))}</p>
                <p><strong>Difficulty:</strong> ${escapeHtml(state.difficulty)}</p>
                <p><strong>Type:</strong> ${escapeHtml(state.interviewType)}</p>
                ${summaryHtml}
                <section>
                    <h2>Transcript</h2>
                    ${transcriptHtml}
                </section>
            </body>
        </html>
    `);
    popup.document.close();
    popup.focus();
    popup.print();
    setSystemCard("PDF print view opened.");
}

function closeExistingSocket() {
    if (state.socket && state.socket.readyState < WebSocket.CLOSING) {
        state.socket.close();
    }
}

function refreshResumeButton() {
    const meta = getPersistedSessionMeta();
    dom.resumeBtn.disabled = !(meta && meta.sessionId && !meta.completed);
}

function resetInsights() {
    renderInsightList(dom.strengthList, [], "No feedback yet.");
    renderInsightList(dom.weaknessList, [], "No feedback yet.");
    dom.averageScore.textContent = "0.0";
    dom.sessionIdValue.textContent = "-";
}

function applyConfigToForm(config) {
    if (!config) {
        return;
    }
    dom.jobRole.value = config.role || "AI Engineer";
    dom.providerSelect.value = config.provider || "auto";
    dom.difficultySelect.value = config.difficulty || "mid";
    dom.interviewTypeSelect.value = config.interviewType || "mixed";
    dom.companyStyleSelect.value = config.companyStyle || "neutral";
    dom.languageSelect.value = config.language || "English";
    dom.questionCountSelect.value = String(config.questionCount || 4);
    setPreset(dom.jobRole.value.trim());
    syncConfigPreview();
}

function startInterview({ sessionId = "", config = null } = {}) {
    const resolvedConfig = config || getCurrentConfig();
    if (!resolvedConfig.role) {
        setSystemCard("Enter a target role before starting.");
        dom.jobRole.focus();
        return;
    }

    closeExistingSocket();
    resetTranscriptView();
    resetInsights();
    state.summary = null;
    dom.summaryContent.classList.add("hidden");
    dom.summaryEmpty.classList.remove("hidden");

    state.role = resolvedConfig.role;
    state.provider = resolvedConfig.provider;
    state.difficulty = resolvedConfig.difficulty;
    state.interviewType = resolvedConfig.interviewType;
    state.companyStyle = resolvedConfig.companyStyle;
    state.language = resolvedConfig.language;
    state.questionGoal = Number(resolvedConfig.questionCount);
    state.finished = false;
    persistLastConfig(resolvedConfig);
    if (dom.setupAdvanced) {
        dom.setupAdvanced.open = false;
    }

    dom.roleDisplay.textContent = `${resolvedConfig.role} Interview`;
    dom.sessionCopy.textContent = `Live ${resolvedConfig.interviewType.replace("_", " ")} interview practice for ${resolvedConfig.role} at ${resolvedConfig.difficulty} difficulty.`;
    setPreset(resolvedConfig.role);
    renderProgressSteps(buildProgressLabels(resolvedConfig.questionCount, resolvedConfig.interviewType, resolvedConfig.difficulty), 0);
    updateProviderBadge(resolvedConfig.provider);
    setStatus("Connecting", "pending");
    setSystemCard(`Starting a ${resolvedConfig.role} interview using ${resolvedConfig.provider}.`);
    enableComposer(false);
    setTyping(true);
    dom.startBtn.disabled = true;
    dom.restartBtn.disabled = false;
    setView("live");

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const params = new URLSearchParams({
        role: resolvedConfig.role,
        provider: resolvedConfig.provider,
        question_count: String(resolvedConfig.questionCount),
        difficulty: resolvedConfig.difficulty,
        interview_type: resolvedConfig.interviewType,
        company_style: resolvedConfig.companyStyle,
        language: resolvedConfig.language,
    });
    if (sessionId) {
        params.set("session_id", sessionId);
    }

    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/interview?${params.toString()}`);
    state.socket = socket;

    socket.onopen = () => {
        if (socket !== state.socket) {
            return;
        }
        setStatus("Starting", "pending");
    };

    socket.onmessage = (event) => {
        if (socket !== state.socket) {
            return;
        }
        try {
            const payload = JSON.parse(event.data);
            handleSocketEvent(payload);
        } catch (error) {
            console.error("Invalid socket payload:", error);
        }
    };

    socket.onclose = () => {
        if (socket !== state.socket) {
            return;
        }
        dom.startBtn.disabled = false;
        setTyping(false);
        enableComposer(false);
        if (!state.finished) {
            setStatus("Disconnected", "offline");
            setSystemCard("The session disconnected. Use Resume Last Session to continue.");
        }
        refreshResumeButton();
    };

    socket.onerror = () => {
        if (socket !== state.socket) {
            return;
        }
        setTyping(false);
        setStatus("Issue", "error");
        setSystemCard("The connection failed before the interview started.");
        dom.startBtn.disabled = false;
    };
}

function handleSocketEvent(payload) {
    switch (payload.type) {
        case "session":
            state.sessionId = payload.sessionId || "";
            state.correlationId = payload.correlationId || "";
            state.progressLabels = payload.progressLabels || state.progressLabels;
            state.questionGoal = payload.totalQuestions || state.questionGoal;
            dom.sessionIdValue.textContent = state.sessionId ? state.sessionId.slice(0, 8) : "-";
            dom.sessionCopy.textContent = `Live ${String(payload.interviewType || state.interviewType).replace("_", " ")} interview practice for ${payload.role} using ${payload.provider} on ${payload.model}. Estimated session length: ~${payload.estimatedMinutes} min.`;
            updateProviderBadge(payload.provider, payload.model);
            renderProgressSteps(payload.progressLabels || state.progressLabels, state.questionCount);
            persistSessionMeta({
                sessionId: state.sessionId,
                completed: false,
                config: {
                    role: payload.role,
                    provider: payload.requestedProvider || state.provider,
                    difficulty: payload.difficulty,
                    interviewType: payload.interviewType,
                    companyStyle: payload.companyStyle,
                    language: payload.language,
                    questionCount: payload.totalQuestions,
                },
            });
            refreshResumeButton();
            setSystemCard(`Session ready for ${payload.role}.`);
            break;

        case "history_sync":
            hydrateTranscript(payload.transcript || []);
            break;

        case "provider_update":
            updateProviderBadge(payload.provider, payload.model);
            addSpecialBubble(payload.reason || `Switched to ${payload.provider}.`, "note");
            setSystemCard(payload.reason || `Switched to ${payload.provider}.`);
            break;

        case "status": {
            const variantMap = {
                starting: "pending",
                awaiting_candidate: "live",
                ready: "live",
                evaluating: "coach",
            };
            setStatus(payload.label || "Live", variantMap[payload.state] || "pending");
            setSystemCard(payload.message || "Session update received.");
            if (payload.state === "awaiting_candidate") {
                setTyping(false);
            }
            break;
        }

        case "progress":
            state.questionCount = payload.current || 0;
            renderProgressSteps(payload.labels || state.progressLabels, state.questionCount);
            dom.currentLabelPill.textContent = payload.currentLabel || dom.currentLabelPill.textContent;
            updateCounters();
            break;

        case "feedback":
            state.feedbackCount = payload.count || state.feedbackCount;
            if (payload.scores?.average) {
                state.scores.push(Number(payload.scores.average));
            }
            updateCounters();
            break;

        case "mini_summary":
            renderInsightList(dom.strengthList, payload.strengths || [], "No feedback yet.");
            renderInsightList(dom.weaknessList, payload.weakAreas || [], "No feedback yet.");
            if (payload.averageScore) {
                dom.averageScore.textContent = Number(payload.averageScore).toFixed(1);
            }
            break;

        case "input_request":
            enableComposer(Boolean(payload.enabled), payload.prompt || "");
            dom.msgInput.maxLength = Number(payload.maxChars || MAX_ANSWER_CHARS);
            dom.charMax.textContent = String(payload.maxChars || MAX_ANSWER_CHARS);
            if (payload.enabled) {
                dom.msgInput.value = "";
                updateCharCounter();
            }
            setTyping(!payload.enabled);
            break;

        case "validation_error":
            addSpecialBubble(payload.message || "Validation error.", "error");
            setSystemCard(payload.message || "Validation error.");
            break;

        case "message":
            setTyping(false);
            createBubble({
                actor: payload.actor,
                content: payload.content,
                role: payload.role,
                meta: payload.meta || "",
                markdown: payload.role === "evaluator",
            });
            break;

        case "note":
            addSpecialBubble(payload.message || "System note.", "note");
            break;

        case "summary":
            renderSummary(payload.summary || {});
            setView("summary");
            fetchHistory();
            break;

        case "error":
            state.finished = true;
            setTyping(false);
            setStatus("Issue", "error");
            enableComposer(false);
            dom.startBtn.disabled = false;
            addSpecialBubble(payload.message || "Unexpected session error.", "error");
            setSystemCard(payload.message || "Unexpected session error.");
            break;

        case "complete": {
            state.finished = true;
            setTyping(false);
            enableComposer(false);
            dom.startBtn.disabled = false;
            setStatus("Finished", "finished");
            setSystemCard("Interview finished. Review the summary, export the report, or restart the same role.");
            const meta = getPersistedSessionMeta();
            if (meta && meta.sessionId === payload.sessionId) {
                meta.completed = true;
                persistSessionMeta(meta);
            }
            refreshResumeButton();
            if (state.socket && state.socket.readyState < WebSocket.CLOSING) {
                state.socket.close();
            }
            break;
        }

        default:
            console.warn("Unhandled socket event:", payload);
    }
}

function sendMsg() {
    const text = dom.msgInput.value.trim();
    if (!text || !state.socket || state.socket.readyState !== WebSocket.OPEN) {
        return;
    }

    createBubble({
        actor: "Candidate",
        content: text,
        role: "user",
        meta: "Your answer",
        markdown: false,
    });

    state.socket.send(text);
    dom.msgInput.value = "";
    updateCharCounter();
    enableComposer(false);
    setTyping(true);
    setStatus("Thinking", "pending");
    setSystemCard("Answer sent. Waiting for the next AI turn.");
}

async function fetchHistory() {
    dom.historyList.innerHTML = '<div class="history-empty">Loading session history...</div>';
    try {
        const response = await fetch("/api/sessions?limit=40");
        const data = await response.json();
        state.historyItems = data.items || [];
        renderHistoryList();
    } catch (error) {
        dom.historyList.innerHTML = '<div class="history-empty">Failed to load saved sessions.</div>';
        console.error(error);
    }
}

function renderHistoryList() {
    if (!state.historyItems.length) {
        dom.historyList.innerHTML = '<div class="history-empty">No saved sessions yet.</div>';
        return;
    }

    dom.historyList.innerHTML = state.historyItems
        .map((item) => {
            const isSelected = item.session_id === state.selectedHistoryId;
            const type = String(item.interview_type || "").replace("_", " ");
            return `
                <button class="history-item ${isSelected ? "is-selected" : ""}" type="button" data-session-id="${item.session_id}">
                    <div class="history-item-head">
                        <p class="history-item-role">${escapeHtml(item.role)}</p>
                        <span class="subtle-pill">${item.final_score ?? "--"}</span>
                    </div>
                    <div class="history-item-copy">
                        ${escapeHtml(type)} | ${escapeHtml(item.difficulty)} | ${item.question_count} questions
                    </div>
                    <div class="history-item-copy">
                        ${escapeHtml(item.status)} | ${formatTimestamp(item.updated_at)}
                    </div>
                </button>
            `;
        })
        .join("");
}

async function loadHistoryDetail(sessionId) {
    state.selectedHistoryId = sessionId;
    state.selectedHistorySession = null;
    renderHistoryList();
    dom.historyDetailEmpty.classList.add("hidden");
    dom.historyDetail.classList.remove("hidden");
    dom.historyDetail.innerHTML = '<div class="history-empty">Loading session details...</div>';

    try {
        const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
        const data = await response.json();
        if (!data.ok) {
            dom.historyDetail.innerHTML = `<div class="history-empty">${escapeHtml(data.message || "Session not found.")}</div>`;
            return;
        }
        const session = data.session;
        state.selectedHistorySession = session;
        const summary = session.summary || {};
        const transcript = session.transcript || [];
        const resumeButton = session.status !== "completed"
            ? `<button class="primary-button" type="button" data-resume-history="${escapeHtml(session.session_id)}">Resume This Session</button>`
            : "";

        dom.historyDetail.innerHTML = `
            <section class="history-detail-card">
                <div class="summary-card-head">
                    <div>
                        <p class="eyebrow">Saved session</p>
                        <h3>${escapeHtml(session.config.role)}</h3>
                    </div>
                    ${resumeButton}
                </div>
                <p class="history-detail-meta">
                    ${escapeHtml(String(session.config.interview_type).replace("_", " "))} | ${escapeHtml(session.config.difficulty)} | ${session.config.question_count} questions | ${escapeHtml(session.status)}
                </p>
                <p class="history-detail-meta">Session id: ${escapeHtml(session.session_id)} | Updated: ${formatTimestamp(session.updated_at)}</p>
            </section>

            <section class="history-detail-card">
                <h4>Summary</h4>
                <p><strong>Final score:</strong> ${summary.final_score ?? "--"}</p>
                <p>${escapeHtml(summary.closing_message || "No final summary stored yet.")}</p>
                <h4>Top improvements</h4>
                <ul>${(summary.top_improvements || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No improvements recorded yet.</li>"}</ul>
            </section>

            <section class="history-detail-card">
                <h4>Transcript</h4>
                <div class="summary-transcript">
                    ${transcript
                        .map((item) => {
                            const body = item.role === "evaluator"
                                ? renderMarkdown(item.content)
                                : `<p>${escapeHtml(item.content)}</p>`;
                            return `
                                <div class="summary-transcript-block">
                                    <strong>${escapeHtml(item.actor)}${item.meta ? ` | ${escapeHtml(item.meta)}` : ""}</strong>
                                    ${body}
                                </div>
                            `;
                        })
                        .join("")}
                </div>
            </section>
        `;
    } catch (error) {
        dom.historyDetail.innerHTML = '<div class="history-empty">Failed to load session details.</div>';
        console.error(error);
    }
}

function resumeLastSession() {
    const meta = getPersistedSessionMeta();
    if (!meta || !meta.sessionId || meta.completed) {
        setSystemCard("There is no unfinished session to resume.");
        return;
    }
    applyConfigToForm(meta.config);
    startInterview({ sessionId: meta.sessionId, config: meta.config });
}

function restartSameRole() {
    const config = getLastConfig() || getCurrentConfig();
    applyConfigToForm(config);
    startInterview({ config });
}

function toggleTheme() {
    const nextTheme = dom.body.dataset.theme === "dark" ? "light" : "dark";
    dom.body.dataset.theme = nextTheme;
    localStorage.setItem(STORAGE_KEYS.theme, nextTheme);
}

function bootTheme() {
    dom.body.dataset.theme = localStorage.getItem(STORAGE_KEYS.theme) || "light";
}

function openHistoryView() {
    setView("history");
    fetchHistory();
}

dom.startBtn.addEventListener("click", () => startInterview());
dom.restartBtn.addEventListener("click", restartSameRole);
dom.resumeBtn.addEventListener("click", resumeLastSession);
dom.openHistoryBtn.addEventListener("click", openHistoryView);
dom.sendBtn.addEventListener("click", sendMsg);
dom.msgInput.addEventListener("input", updateCharCounter);
dom.msgInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMsg();
    }
});
dom.themeToggleBtn.addEventListener("click", toggleTheme);
dom.sidebarToggleBtn.addEventListener("click", toggleSidebar);
dom.sidebarCloseBtn.addEventListener("click", closeSidebar);
dom.sidebarBackdrop.addEventListener("click", closeSidebar);
dom.exportTxtBtn.addEventListener("click", exportTxt);
dom.exportJsonBtn.addEventListener("click", exportJson);
dom.exportPdfBtn.addEventListener("click", exportPdf);
dom.copySummaryBtn.addEventListener("click", () => copyText(JSON.stringify(getExportPayload(), null, 2), "Summary report copied."));
dom.refreshHistoryBtn.addEventListener("click", fetchHistory);

[
    dom.jobRole,
    dom.providerSelect,
    dom.difficultySelect,
    dom.interviewTypeSelect,
    dom.companyStyleSelect,
    dom.languageSelect,
    dom.questionCountSelect,
].forEach((node) => {
    node.addEventListener("input", syncConfigPreview);
    node.addEventListener("change", syncConfigPreview);
});

dom.presetChips.forEach((chip) => {
    chip.addEventListener("click", () => {
        const role = chip.dataset.role || "AI Engineer";
        dom.jobRole.value = role;
        setPreset(role);
        syncConfigPreview();
    });
});

dom.tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const view = button.dataset.view;
        setView(view);
        if (view === "history") {
            fetchHistory();
        }
    });
});

dom.messages.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
        return;
    }
    if (target.dataset.roleExample) {
        dom.jobRole.value = target.dataset.roleExample;
        setPreset(target.dataset.roleExample);
        syncConfigPreview();
    }
});

dom.historyList.addEventListener("click", (event) => {
    const target = event.target.closest("[data-session-id]");
    if (target) {
        loadHistoryDetail(target.dataset.sessionId);
    }
});

dom.historyDetail.addEventListener("click", (event) => {
    const target = event.target.closest("[data-resume-history]");
    if (target) {
        const sessionMeta = state.selectedHistorySession;
        const config = sessionMeta
            ? {
                role: sessionMeta.config.role,
                provider: sessionMeta.config.provider || getCurrentConfig().provider,
                difficulty: sessionMeta.config.difficulty,
                interviewType: sessionMeta.config.interview_type,
                companyStyle: sessionMeta.config.company_style,
                language: sessionMeta.config.language,
                questionCount: sessionMeta.config.question_count,
            }
            : getCurrentConfig();
        applyConfigToForm(config);
        persistSessionMeta({
            sessionId: target.dataset.resumeHistory,
            completed: false,
            config,
        });
        startInterview({ sessionId: target.dataset.resumeHistory, config });
    }
});

dom.msgInput.maxLength = MAX_ANSWER_CHARS;
dom.charMax.textContent = String(MAX_ANSWER_CHARS);
dom.restartBtn.disabled = true;
dom.sendBtn.disabled = true;
dom.exportTxtBtn.disabled = true;
dom.exportJsonBtn.disabled = true;
dom.exportPdfBtn.disabled = true;
bootTheme();
applyConfigToForm(getLastConfig() || getCurrentConfig());
setPreset(dom.jobRole.value.trim());
updateProviderBadge("auto");
syncConfigPreview();
updateCharCounter();
refreshResumeButton();
fetchHistory();
setView("live");
