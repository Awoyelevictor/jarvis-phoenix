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

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 4200);
}
function setMode(mode, label, hint) {
  document.body.dataset.mode = mode;
  $("voice-state").textContent = label;
  $("voice-hint").textContent = hint;
  $("state-label").textContent = mode.toUpperCase();
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
      setMode("listening", "INTERRUPTED", "I have the floor back. Go ahead, Creator.");
      clearTimeout(interruptionTimer);
      interruptionTimer = setTimeout(() => {
        if (sessionActive && !finalTranscript.trim() && !busy) {
          speak("I thought you were saying something, Creator. Do continue.");
        }
      }, 2600);
    }

    if (finalTranscript.trim()) {
      const spoken = finalTranscript.trim();
      finalTranscript = "";
      clearTimeout(interruptionTimer);
      if (playbackSource && looksLikeEcho(spoken)) return;
      if (playbackSource) stopUltronSpeech();
      if (sessionActive && !busy) processUtterance(spoken);
      else if (sessionActive && busy) {
        // An active request is still being generated; queue the interruption.
        queuedUtterance = spoken;
      }
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
let queuedUtterance = "";
function startListening() {
  if (!sessionActive || !recognition) return;
  try { recognition.start(); } catch {}
}
async function processUtterance(text) {
  if (busy) { queuedUtterance = text; return; }
  busy = true;
  setMode("thinking", "PROCESSING", "One moment. I'm working on that.");
  try {
    const response = await fetch("/api/chat", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({prompt: text})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "AI request failed.");
    if (!sessionActive) return;
    await speak(data.reply || "I don't have a response for that.");
  } catch (error) {
    if (sessionActive) {
      toast(error.message);
      setMode("error", "CONNECTION ERROR", "Check your AI provider and try speaking again.");
      await new Promise(resolve => setTimeout(resolve, 1400));
    }
  } finally {
    busy = false;
    if (sessionActive && queuedUtterance) {
      const next = queuedUtterance;
      queuedUtterance = "";
      processUtterance(next);
    } else if (sessionActive && !playbackSource) {
      setMode("listening", "LISTENING", "I'm listening. You can speak at any time.");
    } else if (!sessionActive) {
      setMode("standby", "SYSTEM STANDBY", "Tap the core to begin a voice session");
    }
  }
}
async function speak(text) {
  setMode("thinking", "GENERATING VOICE", "Preparing ULTRON's natural voice.");
  const response = await fetch("/api/voice", {
    method: "POST", headers: {"Content-Type": "application/json"},
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
    else if (!sessionActive) setMode("standby", "SYSTEM STANDBY", "Tap the core to begin a voice session");
  };
  setMode("speaking", "ULTRON IS SPEAKING", "Speak at any time to interrupt.");
  $("mic-button").classList.remove("active");
  $("control-caption").textContent = "VOICE OUTPUT · MIC ACTIVE";
  source.start();
  animateAudio();
}
function updateControls() {
  $("mic-button").classList.toggle("active", sessionActive);
  $("mic-button").setAttribute("aria-label", sessionActive ? "End voice conversation" : "Start voice conversation");
  $("control-caption").textContent = sessionActive ? "ALWAYS LISTENING" : "ACTIVATE VOICE";
  $("stop-button").hidden = !sessionActive;
}
async function startSession() {
  if (!SpeechRecognition) {
    toast("Continuous speech recognition is unavailable in this browser. Try the latest Chrome.");
    return;
  }
  try {
    await prepareAudio();
    createRecognition();
    sessionActive = true;
    updateControls();
    startListening();
  } catch (error) {
    toast(error.message || "Could not start voice session.");
  }
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
  setMode("standby", "SYSTEM STANDBY", "Tap the core to begin a voice session");
}
$("mic-button").addEventListener("click", () => sessionActive ? stopSession() : startSession());
$("stop-button").addEventListener("click", stopSession);
$("voice-engine").textContent = "GEMINI TTS · ALGENIB · INTERRUPTIBLE";
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
