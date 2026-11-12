const $ = (id) => document.getElementById(id);
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let sessionActive = false;
let busy = false;
let finalTranscript = "";
let audioContext = null;
let analyser = null;
let playbackSource = null;
let animationFrame = 0;
let activeSpeechText = "";
let interruptionTimer = null;
let restartTimer = null;
let queuedUtterance = "";
let chatBusy = false;

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 4200);
}
function logEvent(message) {
  const host = $("system-log-lines");
  if (!host) return;
  const p = document.createElement("p");
  const time = document.createElement("time");
  const label = document.createElement("span");
  time.textContent = new Date().toLocaleTimeString([], {hour12:false});
  label.textContent = message.toUpperCase();
  p.append(time, label);
  host.prepend(p);
  while (host.children.length > 4) host.lastElementChild.remove();
}
function setMode(mode, label, hint) {
  document.body.dataset.mode = mode;
  $("voice-state").textContent = label;
  $("voice-hint").textContent = hint;
  $("state-label").textContent = mode.toUpperCase();
  $("overall-status").textContent = mode === "standby" ? "STANDBY" : mode.toUpperCase();
  $("overall-detail").textContent = mode === "listening" ? "Microphone active" : mode === "speaking" ? "Voice output active" : mode === "thinking" ? "Processing request" : mode === "error" ? "Check system connection" : "Awaiting activation";
}
function resetGlow() {
  cancelAnimationFrame(animationFrame);
  document.documentElement.style.setProperty("--voice-energy", "0");
  document.documentElement.style.setProperty("--voice-pitch", ".5");
}
function estimatePitch(samples, sampleRate) {
  let bestLag = 0, bestCorrelation = 0;
  const minLag = Math.floor(sampleRate / 360);
  const maxLag = Math.min(Math.floor(sampleRate / 75), samples.length - 1);
  for (let lag = minLag; lag <= maxLag; lag += 2) {
    let correlation = 0;
    for (let i = 0; i < samples.length - lag; i += 4) correlation += samples[i] * samples[i + lag];
    if (correlation > bestCorrelation) { bestCorrelation = correlation; bestLag = lag; }
  }
  return bestLag ? sampleRate / bestLag : 0;
}
function animateAudio() {
  if (!analyser || !playbackSource) return;
  const samples = new Float32Array(analyser.fftSize);
  const tick = () => {
    if (!playbackSource) return;
    analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (const value of samples) sum += value * value;
    const rms = Math.sqrt(sum / samples.length);
    const pitch = estimatePitch(samples, audioContext.sampleRate);
    document.documentElement.style.setProperty("--voice-energy", Math.min(1, rms * 5.5).toFixed(3));
    document.documentElement.style.setProperty("--voice-pitch", (pitch ? Math.max(0, Math.min(1, (pitch - 75) / 285)) : .35).toFixed(3));
    animationFrame = requestAnimationFrame(tick);
  };
  cancelAnimationFrame(animationFrame);
  animationFrame = requestAnimationFrame(tick);
}
async function prepareAudio() {
  if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
  if (audioContext.state === "suspended") await audioContext.resume();
  if (!analyser) {
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    analyser.connect(audioContext.destination);
  }
}
function normalized(text) {
  return (text || "").toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
}
function looksLikeEcho(text) {
  const heard = normalized(text);
  const spoken = normalized(activeSpeechText);
  return heard.length > 5 && spoken && (spoken.includes(heard) || heard.includes(spoken));
}
function stopUltronSpeech() {
  if (!playbackSource) return;
  const source = playbackSource;
  playbackSource = null;
  try { source.stop(); } catch {}
  resetGlow();
}
function createRecognition() {
  recognition = new SpeechRecognition();
  recognition.lang = navigator.language || "en-NG";
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => {
    if (sessionActive && !playbackSource && !busy) setMode("listening", "LISTENING", "I'm listening. Speak naturally.");
  };
  recognition.onerror = (event) => {
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      sessionActive = false;
      updateControls();
      toast("Microphone permission was denied. Allow microphone access in Chrome site settings.");
      logEvent("Microphone permission denied");
    } else if (event.error !== "no-speech" && event.error !== "aborted") {
      toast("Microphone issue: " + event.error);
    }
  };
  recognition.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript.trim();
      if (event.results[i].isFinal) finalTranscript += (finalTranscript ? " " : "") + transcript;
      else interim += " " + transcript;
    }
    if (playbackSource && interim.trim() && !looksLikeEcho(interim)) {
      stopUltronSpeech();
      setMode("listening", "INTERRUPTED", "I have the floor back. Go ahead.");
      clearTimeout(interruptionTimer);
      interruptionTimer = setTimeout(() => {
        if (sessionActive && !finalTranscript.trim() && !busy) speak("I thought you were saying something. Do continue.").catch(() => {});
      }, 2600);
    }
    if (finalTranscript.trim()) {
      const spoken = finalTranscript.trim();
      finalTranscript = "";
      clearTimeout(interruptionTimer);
      if (playbackSource && looksLikeEcho(spoken)) return;
      if (playbackSource) stopUltronSpeech();
      if (sessionActive && !busy) processUtterance(spoken);
      else if (sessionActive && busy) queuedUtterance = spoken;
    }
  };
  recognition.onend = () => {
    if (!sessionActive) return;
    clearTimeout(restartTimer);
    restartTimer = setTimeout(() => {
      if (!sessionActive || !recognition) return;
      try { recognition.start(); } catch {}
    }, 250);
  };
}
function startListening() {
  if (!sessionActive || !recognition) return;
  try { recognition.start(); } catch {}
}
function addMessage(role, text, pending = false) {
  const feed = $("chat-feed");
  $("empty-chat")?.remove();
  const article = document.createElement("article");
  article.className = `message ${role}${pending ? " pending" : ""}`;
  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? "YOU / COMMAND" : "ULTRON / RESPONSE";
  const p = document.createElement("p");
  p.textContent = text;
  article.append(meta, p);
  feed.append(article);
  feed.scrollTop = feed.scrollHeight;
  return {article, paragraph:p};
}
async function sendChatMessage(text, fromVoice = false) {
  const prompt = (text || "").trim();
  if (!prompt || chatBusy) return;
  chatBusy = true;
  $("send-button").disabled = true;
  addMessage("user", prompt);
  const pending = addMessage("assistant", "Establishing response…", true);
  setMode("thinking", "PROCESSING", "Analysing your command.");
  logEvent("Incoming command received");
  try {
    const response = await fetch("/api/chat", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({prompt})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "AI request failed.");
    const reply = data.reply || "I don't have a response for that.";
    pending.paragraph.textContent = reply;
    pending.article.classList.remove("pending");
    logEvent("Response generated successfully");
    if (fromVoice && sessionActive) await speak(reply);
    else if (sessionActive && !playbackSource) setMode("listening", "LISTENING", "I'm listening. You can interrupt me at any time.");
    else if (!sessionActive) setMode("standby", "SYSTEM STANDBY", "Text channel active. Activate voice whenever you're ready.");
  } catch (error) {
    pending.paragraph.textContent = "Request failed: " + error.message;
    pending.article.classList.remove("pending");
    logEvent("AI request failed");
    toast(error.message);
    setMode("error", "CONNECTION ERROR", "Check your AI provider and try again.");
  } finally {
    chatBusy = false;
    $("send-button").disabled = false;
    if (sessionActive && queuedUtterance && !busy) {
      const next = queuedUtterance;
      queuedUtterance = "";
      processUtterance(next);
    }
  }
}
async function processUtterance(text) {
  if (busy) { queuedUtterance = text; return; }
  busy = true;
  try { await sendChatMessage(text, true); }
  finally {
    busy = false;
    if (sessionActive && queuedUtterance) {
      const next = queuedUtterance;
      queuedUtterance = "";
      processUtterance(next);
    } else if (sessionActive && !playbackSource) {
      setMode("listening", "LISTENING", "I'm listening. You can interrupt me at any time.");
    } else if (!sessionActive) {
      setMode("standby", "SYSTEM STANDBY", "Text channel active. Activate voice whenever you're ready.");
    }
  }
}
async function speak(text) {
  setMode("thinking", "GENERATING VOICE", "Preparing ULTRON's natural voice.");
  const response = await fetch("/api/voice", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({text})
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Gemini voice generation failed.");
  if (!sessionActive) return;
  await prepareAudio();
  const binary = atob(data.audio);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const audioBuffer = await audioContext.decodeAudioData(bytes.buffer);
  if (!sessionActive) return;
  activeSpeechText = text;
  playbackSource = audioContext.createBufferSource();
  const source = playbackSource;
  source.buffer = audioBuffer;
  source.connect(analyser);
  source.onended = () => {
    if (playbackSource !== source) return;
    playbackSource = null;
    activeSpeechText = "";
    resetGlow();
    if (sessionActive && !busy) setMode("listening", "LISTENING", "I'm listening. You can interrupt me at any time.");
    else if (!sessionActive) setMode("standby", "SYSTEM STANDBY", "Text channel active.");
  };
  setMode("speaking", "ULTRON IS SPEAKING", "Speak at any time to interrupt.");
  $("control-caption").textContent = "VOICE OUTPUT · MIC ACTIVE";
  source.start();
  animateAudio();
}
function updateControls() {
  $("mic-button").classList.toggle("active", sessionActive);
  $("mic-button").setAttribute("aria-label", sessionActive ? "End voice conversation" : "Start voice conversation");
  $("control-caption").textContent = sessionActive ? "VOICE SESSION ACTIVE" : "ACTIVATE VOICE";
  $("stop-button").hidden = !sessionActive;
}
async function startSession() {
  if (!SpeechRecognition) {
    toast("Continuous speech recognition is unavailable here. Try the latest Chrome browser.");
    return;
  }
  try {
    await prepareAudio();
    createRecognition();
    sessionActive = true;
    updateControls();
    logEvent("Voice session activated");
    startListening();
  } catch (error) { toast(error.message || "Could not start voice session."); }
}
function stopSession() {
  sessionActive = false;
  busy = false;
  queuedUtterance = "";
  clearTimeout(interruptionTimer);
  clearTimeout(restartTimer);
  try { recognition?.stop(); } catch {}
  recognition = null;
  stopUltronSpeech();
  resetGlow();
  updateControls();
  setMode("standby", "SYSTEM STANDBY", "Text channel active. Activate voice whenever you're ready.");
  logEvent("Voice session ended");
}
async function loadStatus() {
  try {
    const response = await fetch("/api/status", {cache:"no-store"});
    if (!response.ok) throw new Error("Status unavailable");
    const data = await response.json();
    const cloud = (data.providers || []).find(item => item.name.toLowerCase().includes("cloud"));
    const localMemory = data.local_memory === true;
    setMetric("cloud-status", "cloud-bar", cloud?.ready, cloud?.ready ? "ONLINE" : "OFFLINE");
    setMetric("voice-status", "voice-bar", data.voice_ready, data.voice_ready ? "READY" : "OFFLINE");
    setMetric("memory-status", "memory-bar", localMemory, localMemory ? "ACTIVE" : "OFFLINE");
    $("model-name").textContent = data.cloud_model || "NOT SET";
    $("voice-name").textContent = data.tts_voice || "NOT SET";
    $("memory-sync").textContent = data.cloud_memory ? "CLOUD + LOCAL" : "LOCAL ONLY";
    $("listen-capability").textContent = data.continuous_listening ? "SUPPORTED" : "LIMITED";
    logEvent(cloud?.ready ? "Cloud intelligence configured" : "Cloud intelligence unavailable");
    logEvent(data.voice_ready ? "Gemini voice configured" : "Voice provider unavailable");
    if (!cloud?.ready) $("overall-detail").textContent = "Cloud provider needs attention";
  } catch {
    ["cloud-status","voice-status","memory-status"].forEach(id => $(id).textContent = "UNKNOWN");
    logEvent("Unable to retrieve system status");
  }
}
function setMetric(labelId, barId, ready, label) {
  const el = $(labelId), bar = $(barId);
  el.textContent = label;
  el.classList.toggle("ready", !!ready);
  el.classList.toggle("offline", !ready);
  bar.style.width = ready ? "100%" : "12%";
}
async function resetConversation() {
  if (!confirm("Reset the current conversation? Persistent saved memories will be preserved.")) return;
  try {
    const response = await fetch("/api/reset", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Reset failed");
    $("chat-feed").innerHTML = '<div class="empty-chat" id="empty-chat"><span class="empty-mark">⌁</span><strong>CHANNEL READY</strong><p>Conversation reset. Send a new command.</p></div>';
    logEvent("Conversation context reset");
    toast("Conversation reset. Saved memories were preserved.");
  } catch (error) { toast(error.message); }
}
$("mic-button").addEventListener("click", () => sessionActive ? stopSession() : startSession());
$("stop-button").addEventListener("click", stopSession);
$("chat-form").addEventListener("submit", event => {
  event.preventDefault();
  const input = $("chat-input");
  const message = input.value.trim();
  if (!message || chatBusy) return;
  input.value = "";
  sendChatMessage(message, false);
});
$("reset-button").addEventListener("click", resetConversation);
$("voice-engine")?.replaceChildren();
function updateClock() { $("clock").textContent = new Date().toLocaleTimeString([], {hour12:false}); }
updateClock();
setInterval(updateClock, 1000);
loadStatus();
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
