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
    const energy = Math.min(1, rms * 5.5);
    const pitchNorm = pitch ? Math.max(0, Math.min(1, (pitch - 75) / 285)) : .35;
    document.documentElement.style.setProperty("--voice-energy", energy.toFixed(3));
    document.documentElement.style.setProperty("--voice-pitch", pitchNorm.toFixed(3));
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
function createRecognition() {
  recognition = new SpeechRecognition();
  recognition.lang = navigator.language || "en-NG";
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => setMode("listening", "LISTENING", "I'm listening. Speak naturally.");
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
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
    }
  };
  recognition.onend = () => {
    if (!sessionActive || busy) return;
    const spoken = finalTranscript.trim();
    finalTranscript = "";
    if (spoken) processUtterance(spoken);
    else if (sessionActive) startListening();
  };
}
function startListening() {
  if (!sessionActive || busy || !recognition) return;
  finalTranscript = "";
  try { recognition.start(); }
  catch { setTimeout(() => { if (sessionActive && !busy) startListening(); }, 450); }
}
async function processUtterance(text) {
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
      setMode("error", "CONNECTION ERROR", "Check Gemini connectivity and try speaking again.");
      await new Promise(resolve => setTimeout(resolve, 1600));
    }
  } finally {
    busy = false;
    if (sessionActive && !playbackSource) startListening();
    else if (!sessionActive) setMode("standby", "SYSTEM STANDBY", "Tap the core to begin a voice session");
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
  playbackSource = audioContext.createBufferSource();
  playbackSource.buffer = audioBuffer;
  playbackSource.connect(analyser);
  playbackSource.onended = () => {
    playbackSource = null;
    resetGlow();
    if (sessionActive && !busy) startListening();
    else if (!sessionActive) setMode("standby", "SYSTEM STANDBY", "Tap the core to begin a voice session");
  };
  setMode("speaking", "ULTRON IS SPEAKING", "Reactor responding to live voice pitch and intensity");
  $("mic-button").classList.remove("active");
  $("control-caption").textContent = "VOICE OUTPUT";
  playbackSource.start();
  animateAudio();
}
function updateControls() {
  $("mic-button").classList.toggle("active", sessionActive && !busy);
  $("mic-button").setAttribute("aria-label", sessionActive ? "End voice conversation" : "Start voice conversation");
  $("control-caption").textContent = sessionActive ? "VOICE SESSION ACTIVE" : "ACTIVATE VOICE";
  $("stop-button").hidden = !sessionActive;
}
async function startSession() {
  if (!SpeechRecognition) {
    toast("Speech recognition is unavailable. Use the latest Chrome browser.");
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
  try { recognition?.stop(); } catch {}
  if (playbackSource) {
    try { playbackSource.stop(); } catch {}
    playbackSource = null;
  }
  resetGlow();
  updateControls();
  setMode("standby", "SYSTEM STANDBY", "Tap the core to begin a voice session");
}
$("mic-button").addEventListener("click", () => sessionActive ? stopSession() : startSession());
$("stop-button").addEventListener("click", stopSession);
$("voice-engine").textContent = "GEMINI 3.8 TTS · ALGENIB";
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
