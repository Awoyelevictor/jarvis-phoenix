const $ = (id) => document.getElementById(id);
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let microphoneStream = null;
let mediaRecorder = null;
let recordedChunks = [];
let recorderFallback = false;
let sessionActive = false;
let voiceOutputActive = false;
let busy = false;
let finalTranscript = "";
let audioContext = null;
let analyser = null;
let playbackSource = null;
let animationFrame = 0;
let activeSpeechText = "";
let interruptionTimer = null;
let restartTimer = null;
let recognitionStartTimer = null;
let queuedUtterance = "";
let chatBusy = false;
let micAudioSource = null;
let vadFrame = 0;
let vadSpeechStarted = false;
let vadSilenceAt = 0;
let vadSegmentStartedAt = 0;

function showAlert(title, message, kind = "error") {
  const card = $("ultron-alert");
  if (!card) return;
  $("ultron-alert-title").textContent = title;
  $("ultron-alert-message").textContent = message;
  card.dataset.kind = kind;
  card.classList.add("show");
  clearTimeout(showAlert.timer);
  showAlert.timer = setTimeout(() => card.classList.remove("show"), 7200);
}
function toast(message) {
  const el = $("toast");
  if (el) {
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => el.classList.remove("show"), 4200);
  }
  const text = String(message || "");
  const quota = /quota|rate.?limit|too many requests|billing|credit|insufficient.*(credit|fund)|429/i.test(text);
  const warning = /quota|rate.?limit|too many requests|429/i.test(text);
  showAlert(quota ? "AI QUOTA / LIMIT NOTICE" : "SYSTEM ERROR", text, warning ? "warning" : "error");
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
  const indicator = $("ultron-live-indicator");
  if (indicator) {
    const active = mode === "thinking" || mode === "connecting" || mode === "speaking" || mode === "error";
    indicator.dataset.state = mode === "connecting" ? "thinking" : mode;
    indicator.classList.toggle("visible", active);
    $("ultron-live-label").textContent = mode === "speaking" ? "ULTRON SPEAKING" : mode === "error" ? "SYSTEM ERROR" : "THINKING";
  }
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
  if (!analyser || (!playbackSource && !microphoneStream)) return;
  const samples = new Float32Array(analyser.fftSize);
  const tick = () => {
    if (!playbackSource && !microphoneStream) { resetGlow(); return; }
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
    clearTimeout(recognitionStartTimer);
    if (sessionActive && !playbackSource && !busy) setMode("listening", "LISTENING", "I'm listening. Speak naturally.");
  };
  recognition.onerror = (event) => {
    if (event.error === "not-allowed") {
      sessionActive = false;
      updateControls();
      toast("Microphone permission was denied. Allow microphone access in Chrome site settings.");
      logEvent("Microphone permission denied");
    } else if (event.error !== "no-speech" && event.error !== "aborted") {
      logEvent("Speech recognition failed: " + event.error);
      activateRecorderFallback(new Error("Speech recognition unavailable: " + event.error));
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
  setMode("connecting", "ACTIVATING MICROPHONE", "Connecting to your microphone…");
  clearTimeout(recognitionStartTimer);
  try {
    recognition.start();
    // Some Android browser builds expose SpeechRecognition but never fire
    // onstart. Do not leave the HUD looking active while the mic is idle.
    recognitionStartTimer = setTimeout(() => {
      if (sessionActive && recognition && !recorderFallback) {
        logEvent("Speech recognition startup timed out");
        activateRecorderFallback(new Error("Speech recognition did not start."));
      }
    }, 3500);
  } catch (error) {
    logEvent("Browser speech recognition could not start");
    activateRecorderFallback(error);
  }
}
async function activateRecorderFallback(cause) {
  if (!sessionActive || recorderFallback) return;
  try {
    try { recognition?.abort(); } catch {}
    recognition = null;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      throw new Error("This browser cannot access microphone recording. Open ULTRON in Chrome and allow microphone access.");
    }
    if (!microphoneStream) {
      microphoneStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
    }
    if (!sessionActive) {
      microphoneStream.getTracks().forEach(track => track.stop());
      microphoneStream = null;
      return;
    }
    recorderFallback = true;
    updateControls();
    logEvent("Switched to direct microphone recording");
    startFallbackRecording();
    toast("Using direct microphone mode.");
  } catch (error) {
    sessionActive = false;
    updateControls();
    logEvent("Microphone fallback failed");
    const message = error.name === "NotAllowedError"
      ? "Microphone permission denied. Allow microphone access for this site in Chrome settings."
      : (error.message || cause?.message || "Could not activate microphone.");
    toast(message);
    setMode("error", "MICROPHONE ERROR", "Allow microphone access, then tap the head again.");
  }
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
    if (!response.ok) {
      let message = "AI request failed.";
      try { message = (await response.json()).error || message; } catch {}
      throw new Error(message);
    }
    if (!response.body?.getReader) throw new Error("This browser cannot read the live response stream. Reload ULTRON and try again.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let reply = "";
    let streamDone = false;
    pending.paragraph.textContent = "";
    while (!streamDone) {
      const {value, done} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream:true});
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() || "";
      for (const eventText of events) {
        const line = eventText.split(/\r?\n/).find(item => item.startsWith("data:"));
        if (!line) continue;
        let event;
        try { event = JSON.parse(line.slice(5).trim()); } catch { continue; }
        if (event.error) throw new Error(event.error);
        if (typeof event.delta === "string") {
          reply += event.delta;
          pending.paragraph.textContent = reply;
          const feed = $("chat-feed");
          feed.scrollTop = feed.scrollHeight;
        }
        if (event.done) streamDone = true;
      }
    }
    if (!reply.trim()) throw new Error("ULTRON ended the stream without a response.");
    pending.article.classList.remove("pending");
    logEvent("Response stream completed");
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
function pauseMicrophoneForSpeech() {
  // Do not pause capture or recognition. The operator can interrupt TTS.
  voiceOutputActive = true;
}
function resumeMicrophoneAfterSpeech() {
  voiceOutputActive = false;
  if (!sessionActive) return;
  if (recorderFallback && !vadFrame) startFallbackRecording();
  // Native SpeechRecognition is intentionally left running through playback.
  // Its onend handler restarts it only if Android Chrome ends the capture cycle.
}
async function speak(text) {
  pauseMicrophoneForSpeech();
  setMode("thinking", "GENERATING VOICE", "Preparing ULTRON's natural voice.");
  let speechStarted = false;
  try {
  const response = await fetch("/api/voice", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({text})
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Gemini voice generation failed.");
  if (!sessionActive) { resumeMicrophoneAfterSpeech(); return; }
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
  source.connect(audioContext.destination);
  source.onended = () => {
    if (playbackSource !== source) return;
    playbackSource = null;
    activeSpeechText = "";
    resetGlow();
    resumeMicrophoneAfterSpeech();
    if (sessionActive && !busy) setMode("listening", "LISTENING", "I'm listening. Speak naturally.");
    else if (!sessionActive) setMode("standby", "SYSTEM STANDBY", "Text channel active.");
  };
  setMode("speaking", "ULTRON IS SPEAKING", "Speak at any time to interrupt.");
  $("control-caption").textContent = "VOICE OUTPUT · MIC ACTIVE";
  source.start();
  speechStarted = true;
  animateAudio();
  } catch (error) {
    if (!speechStarted) resumeMicrophoneAfterSpeech();
    throw error;
  }
}
function updateControls() {
  $("mic-button")?.classList.toggle("active", sessionActive);
  $("mic-button")?.setAttribute("aria-label", sessionActive ? "End voice conversation" : "Start voice conversation");
  $("robotHeadWrapper")?.classList.toggle("voice-active",sessionActive);
  $("robotHeadWrapper")?.setAttribute("aria-pressed",String(sessionActive));
  $("robotHeadWrapper")?.setAttribute("aria-label",sessionActive?"Tap to send your voice message":"Tap to speak with ULTRON");
  $("control-caption").textContent = sessionActive ? "VOICE SESSION ACTIVE" : "ACTIVATE VOICE";
  $("stop-button").hidden = !sessionActive;
}
async function startSession() {
  try {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone API unavailable. Open ULTRON from http://127.0.0.1:8765 in Chrome.");
    }
    sessionActive = true;
    updateControls();
    setMode("connecting","REQUESTING MICROPHONE","Connecting directly to the phone microphone…");
    logEvent("Requesting microphone stream directly");
    // Acquire the real microphone stream first. SpeechRecognition alone can fail
    // silently on some Android Chrome builds and does not expose a permission prompt.
    microphoneStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    });
    logEvent("Microphone stream granted");
    try {
      if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
      if (audioContext.state === "suspended") await audioContext.resume();
      if (!analyser) { analyser = audioContext.createAnalyser(); analyser.fftSize = 2048; }
      micAudioSource = audioContext.createMediaStreamSource(microphoneStream);
      micAudioSource.connect(analyser);
      animateAudio();
    } catch (audioError) { logEvent("Audio visualizer deferred until interaction"); }
    if (!sessionActive) return;
    if (SpeechRecognition) {
      createRecognition();
      recorderFallback = false;
      logEvent("Browser speech recognition requested");
      startListening();
      return;
    }
    await activateRecorderFallback();
  } catch (error) {
    sessionActive = false;
    microphoneStream?.getTracks().forEach(track => track.stop());
    microphoneStream = null;
    micAudioSource?.disconnect(); micAudioSource = null;
    updateControls();
    logEvent("Microphone activation failed: " + (error.name || error.message || "unknown"));
    const message = error.name === "NotAllowedError" || error.name === "SecurityError"
      ? "Chrome denied microphone access. Check Android app permission and Chrome site settings, then reload."
      : error.name === "NotFoundError"
        ? "No microphone was found on this device."
        : error.message || "Could not start microphone.";
    toast(message);
    setMode("error","MICROPHONE ERROR",message);
  }
}
function startFallbackRecording() {
  if (!sessionActive || !microphoneStream || vadFrame) return;
  const samples = new Float32Array(analyser?.fftSize || 2048);
  const tick = () => {
    if (!sessionActive || !microphoneStream) { vadFrame = 0; return; }
    let rms = 0;
    if (analyser) {
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (const value of samples) sum += value * value;
      rms = Math.sqrt(sum / samples.length);
    }
    const now = Date.now();
    if (rms > 0.018) {
      vadSpeechStarted = true; vadSilenceAt = 0;
      if (!mediaRecorder) {
        recordedChunks = [];
        const mimeType = ["audio/webm;codecs=opus","audio/webm","audio/mp4"].find(type => MediaRecorder.isTypeSupported(type));
        mediaRecorder = new MediaRecorder(microphoneStream,mimeType?{mimeType}:undefined);
        mediaRecorder.ondataavailable = event => { if(event.data?.size) recordedChunks.push(event.data); };
        mediaRecorder.onerror = () => toast("Microphone recording failed.");
        mediaRecorder.onstop = async () => {
          const current=mediaRecorder; mediaRecorder=null;
          const blob=new Blob(recordedChunks,{type:current?.mimeType||"audio/webm"}); recordedChunks=[];
          vadSpeechStarted=false; vadSilenceAt=0;
          if(!blob.size||!sessionActive){if(sessionActive)startFallbackRecording();return;}
          try {
            setMode("thinking","TRANSCRIBING","I heard you. Converting your speech.");
            const audio=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]||"");reader.onerror=()=>reject(new Error("Could not read microphone audio."));reader.readAsDataURL(blob)});
            const response=await fetch("/api/transcribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({audio,mime_type:blob.type||"audio/webm"})});
            const data=await response.json(); if(!response.ok)throw new Error(data.error||"Speech transcription failed.");
            if(data.transcript?.trim())await processUtterance(data.transcript.trim());
          } catch(error){toast(error.message||"Speech transcription failed.");logEvent("Transcription failed");}
          finally{if(sessionActive){setMode("listening","LISTENING","I'm listening. Speak naturally; I'll detect when you finish.");startFallbackRecording();}}
        };
        mediaRecorder.start(); vadSegmentStartedAt=now;
        setMode("listening","LISTENING","I can hear you. Keep speaking; pause when you're done.");
      }
    } else if(mediaRecorder?.state==="recording"&&vadSpeechStarted) {
      if(!vadSilenceAt)vadSilenceAt=now;
      if(now-vadSilenceAt>1250||now-vadSegmentStartedAt>15000){try{mediaRecorder.stop()}catch{}}
    }
    document.documentElement.style.setProperty("--voice-energy",Math.min(1,rms*8).toFixed(3));
    vadFrame=requestAnimationFrame(tick);
  };
  vadFrame=requestAnimationFrame(tick);
}
async function toggleHeadVoice(){
  $("ultronAssistantConsole")?.classList.add("open");
  if(!sessionActive)return startSession();
  if(recorderFallback&&mediaRecorder?.state==="recording"){mediaRecorder.stop();return}
  stopSession();
}
function stopSession() {
  sessionActive = false;
  voiceOutputActive = false;
  busy = false;
  queuedUtterance = "";
  clearTimeout(interruptionTimer);
  clearTimeout(restartTimer);
  clearTimeout(recognitionStartTimer);
  if(vadFrame)cancelAnimationFrame(vadFrame); vadFrame=0; vadSpeechStarted=false; vadSilenceAt=0;
  try { recognition?.stop(); } catch {}
  recognition = null;
  if(mediaRecorder&&mediaRecorder.state!=="inactive"){try{mediaRecorder.stop()}catch{}}
  mediaRecorder=null;micAudioSource?.disconnect();micAudioSource=null;microphoneStream?.getTracks().forEach(track=>track.stop());microphoneStream=null;recorderFallback=false;
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
$("ultron-alert-close")?.addEventListener("click", () => $("ultron-alert")?.classList.remove("show"));
$("robotHeadWrapper")?.addEventListener("click",toggleHeadVoice);
$("mic-button")?.addEventListener("click",toggleHeadVoice);
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
// Auto-request microphone access on startup; the browser's permission prompt remains mandatory.
if (navigator.mediaDevices?.getUserMedia) {
  window.addEventListener("load", () => {
    setMode("connecting","ACTIVATING MICROPHONE","Requesting microphone access…");
    startSession();
  }, {once:true});
} else {
  setMode("error","MICROPHONE UNAVAILABLE","Open ULTRON in Chrome over localhost and enable microphone access.");
}
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
