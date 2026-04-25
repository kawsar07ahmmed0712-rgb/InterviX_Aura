const setupForm = document.getElementById("setupForm");
const answerForm = document.getElementById("answerForm");

const positionInput = document.getElementById("positionInput");
const providerSelect = document.getElementById("providerSelect");
const modelSelect = document.getElementById("modelSelect");

const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const chatBox = document.getElementById("chatBox");

const answerInput = document.getElementById("answerInput");
const sendBtn = document.getElementById("sendBtn");

let socket = null;
let isUserTurn = false;

const models = {
  gemini: [
    { label: "Gemini 2.5 Flash", value: "gemini-2.5-flash" },
    { label: "Gemini 2.5 Pro", value: "gemini-2.5-pro" },
  ],
    ollama: [
    { label: "DeepSeek V3.1 Cloud", value: "deepseek-v3.1:671b-cloud" },
    { label: "Llama 3 Latest", value: "llama3:latest" },
    { label: "Gemma 3 1B", value: "gemma3:1b" },
    { label: "Gemma 3 4B", value: "gemma3:4b" },
    { label: "GPT OSS 120B Cloud", value: "gpt-oss:120b-cloud" },
    ],
};

function refreshModelOptions() {
  const provider = providerSelect.value;
  modelSelect.innerHTML = "";

  models[provider].forEach((model) => {
    const option = document.createElement("option");
    option.value = model.value;
    option.textContent = model.label;
    modelSelect.appendChild(option);
  });
}

function clearChat() {
  chatBox.innerHTML = "";
}

function scrollToBottom() {
  chatBox.scrollTop = chatBox.scrollHeight;
}

function getMessageClass(source) {
  const normalized = source.toLowerCase();

  if (normalized.includes("interviewer")) return "interviewer";
  if (normalized.includes("candidate")) return "candidate";
  if (normalized.includes("evaluator")) return "evaluator";
  if (normalized.includes("error")) return "error";

  return "system";
}

function appendMessage(source, content) {
  const message = document.createElement("div");
  message.className = `message ${getMessageClass(source)}`;

  const sourceEl = document.createElement("span");
  sourceEl.className = "source";
  sourceEl.textContent = source;

  const contentEl = document.createElement("div");
  contentEl.textContent = content;

  message.appendChild(sourceEl);
  message.appendChild(contentEl);

  chatBox.appendChild(message);
  scrollToBottom();
}

function setUserTurn(enabled) {
  isUserTurn = enabled;
  answerInput.disabled = !enabled;
  sendBtn.disabled = !enabled;

  answerInput.placeholder = enabled
    ? "Type your answer..."
    : "Wait for your turn...";

  if (enabled) {
    answerInput.focus();
  }
}

function setInterviewRunning(running) {
  startBtn.disabled = running;
  stopBtn.disabled = !running;
  providerSelect.disabled = running;
  modelSelect.disabled = running;
  positionInput.disabled = running;
}

function parseServerMessage(rawMessage) {
  const separatorIndex = rawMessage.indexOf(":");

  if (separatorIndex === -1) {
    return {
      source: "SYSTEM",
      content: rawMessage,
    };
  }

  return {
    source: rawMessage.slice(0, separatorIndex),
    content: rawMessage.slice(separatorIndex + 1),
  };
}

function startInterview() {
  const position = positionInput.value.trim() || "AI Engineer";
  const provider = providerSelect.value;
  const model = modelSelect.value;

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";

  const wsUrl =
    `${protocol}://${window.location.host}/ws/interview` +
    `?pos=${encodeURIComponent(position)}` +
    `&provider=${encodeURIComponent(provider)}` +
    `&model=${encodeURIComponent(model)}`;

  socket = new WebSocket(wsUrl);

  clearChat();
  setInterviewRunning(true);
  setUserTurn(false);

  socket.onopen = () => {
    appendMessage("SYSTEM", "Connected. Interview is starting...");
  };

  socket.onmessage = (event) => {
    const { source, content } = parseServerMessage(event.data);

    if (source === "SYSTEM_TURN" && content === "USER") {
      appendMessage("SYSTEM", "Your turn. Answer the question.");
      setUserTurn(true);
      return;
    }

    if (source === "SYSTEM_END") {
      appendMessage("SYSTEM", `Interview ended: ${content}`);
      setUserTurn(false);
      setInterviewRunning(false);
      return;
    }

    if (source === "SYSTEM_ERROR") {
      appendMessage("SYSTEM_ERROR", content);
      setUserTurn(false);
      setInterviewRunning(false);
      return;
    }

    appendMessage(source, content);
  };

  socket.onerror = () => {
    appendMessage("SYSTEM_ERROR", "WebSocket error occurred.");
    setUserTurn(false);
    setInterviewRunning(false);
  };

  socket.onclose = () => {
    appendMessage("SYSTEM", "Connection closed.");
    setUserTurn(false);
    setInterviewRunning(false);
  };
}

function sendAnswer() {
  const answer = answerInput.value.trim();

  if (!socket || socket.readyState !== WebSocket.OPEN || !isUserTurn || !answer) {
    return;
  }

  socket.send(answer);
  answerInput.value = "";
  setUserTurn(false);
}

setupForm.addEventListener("submit", (event) => {
  event.preventDefault();
  startInterview();
});

answerForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendAnswer();
});

stopBtn.addEventListener("click", () => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
  }
});

providerSelect.addEventListener("change", refreshModelOptions);

refreshModelOptions();