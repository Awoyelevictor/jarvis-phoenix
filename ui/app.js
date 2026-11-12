const $ = (id) => document.getElementById(id);
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let recognitionFatalError = false;
let microphoneStream = null;
let mediaRecorder = null;
let recordedChunks = [];
let recorderFallback = false;
let sessionActive = false;
let voiceOutputActive = false;
let speechMicPaused = false;
let microphoneResumePromise = null;
let busy = false;
let finalTranscript = "";
let audioContext = null;
let analyser = null;
let playbackCompressor = null;
let playbackGain = null;
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
let forceTimedRecorder = false;
let latestSystemError = null;
let latestSystemStatus = null;
let liveIndicatorDismissed = false;

function describeFailure(message) {
  const value = String(message || "Unknown system error");
  if (/429|quota|rate.?limit|too many requests|billing|credit/i.test(value)) return {source:"AI provider / API quota",cause:"The provider may have reached its request limit, daily quota, or billing allowance.",action:"Check the provider's usage and quota, then retry after the limit resets."};
  if (/401|unauthori[sz]ed|invalid.*key|api.?key/i.test(value)) return {source:"API authentication",cause:"The API key may be missing, invalid, or not accepted by the selected provider.",action:"Check the relevant API key in the Termux session that starts ULTRON. Never share the key."};
  if (/403|forbidden|permission/i.test(value)) return {source:"Provider access / permissions",cause:"The service refused access, or a required browser permission was denied.",action:"Check API access and Android/Chrome microphone permissions."};
  if (/network|fetch|failed to fetch|connection|timeout|offline|502|503|504/i.test(value)) return {source:"Network / cloud connection",cause:"ULTRON could not complete a request to the local server or cloud provider.",action:"Check your internet connection and confirm the ULTRON Termux server is still running."};
  if (/microphone|speech recognition|recording|audio input|notallowed|notfound/i.test(value)) return {source:"Microphone / audio input",cause:"The browser could not start or access microphone input.",action:"Allow microphone access for Chrome and ULTRON, then reload the page."};
  if (/voice|speech|tts|audio/i.test(value)) return {source:"Voice generation (TTS)",cause:"The ULTRON Voice API failed to generate or decode audio.",action:"Check the ULTRON Voice API gateway, its reference-audio secret file, and the network. Chat may still work without voice."};
  return {source:"ULTRON application",cause:"The application reported an error. The original message is shown below.",action:"Use the details here and the Termux log to identify the failing component."};
}
function recordSystemError(message, component = "ULTRON") {
  const detail = describeFailure(message);
  latestSystemError = {message:String(message || "Unknown error"),component, ...detail, time:new Date().toLocaleString()};
  const indicator = $("ultron-live-indicator");
  if (indicator) indicator.dataset.state = "error";
}
function ensureDiagnosticsPanel() {
  if ($("ultron-diagnostics")) return $("ultron-diagnostics");
  const style = document.createElement("style");
  style.textContent = `
    #ultron-live-indicator{pointer-events:auto;cursor:pointer}
    #ultron-live-indicator:focus-visible{outline:2px solid #ff796b;outline-offset:4px}
    #ultron-diagnostics{position:fixed;z-index:160;top:62px;right:18px;width:min(390px,calc(100vw - 28px));max-height:min(72dvh,620px);overflow:auto;padding:16px;background:rgba(7,8,12,.97);border:1px solid rgba(255,65,45,.72);box-shadow:0 14px 42px rgba(0,0,0,.65),0 0 28px rgba(255,35,20,.2);backdrop-filter:blur(18px);color:#e8edf2;font-family:'Rajdhani',sans-serif;display:none}
    #ultron-diagnostics.open{display:block}
    #ultron-diagnostics .diag-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
    #ultron-diagnostics .diag-title{font:12px 'Orbitron',sans-serif;letter-spacing:.12em;color:#ff715d}
    #ultron-diagnostics .diag-close{background:transparent;border:1px solid #555;color:#eee;padding:3px 8px}
    #ultron-diagnostics .diag-row{padding:9px 0;border-top:1px solid rgba(255,255,255,.09)}
    #ultron-diagnostics .diag-label{font:10px 'Share Tech Mono',monospace;letter-spacing:.12em;color:#ff9b8d;margin-bottom:4px}
    #ultron-diagnostics .diag-value{font-size:14px;line-height:1.35;overflow-wrap:anywhere;color:#e8edf2;white-space:pre-wrap}
    #ultron-diagnostics .diag-muted{color:#aab5c2}
    @media(max-width:768px){#ultron-diagnostics{top:54px;right:12px}}
  `;
  document.head.append(style);
  const panel = document.createElement("aside");
  panel.id = "ultron-diagnostics";
  panel.setAttribute("role","dialog");
  panel.setAttribute("aria-label","System diagnostics");
  panel.innerHTML = '<div class="diag-head"><div class="diag-title">ULTRON // DIAGNOSTICS</div><button class="diag-close" type="button" aria-label="Close diagnostics">×</button></div><div id="ultron-diagnostics-content"></div>';
  document.body.append(panel);
  panel.querySelector(".diag-close").addEventListener("click",()=>panel.classList.remove("open"));
  document.addEventListener("keydown",event=>{if(event.key==="Escape")panel.classList.remove("open")});
  return panel;
}
function openDiagnostics() {
  const panel = ensureDiagnosticsPanel();
  const content = $("ultron-diagnostics-content");
  const status = latestSystemStatus || {};
  const cloud = (status.providers || []).find(item => String(item.name).toLowerCase().includes("cloud"));
  const rows = [];
  const add = (label,value,muted=false) => rows.push({label,value:value || "Not available",muted});
  add("OVERALL STATE",document.body.dataset.mode === "error" ? "ERROR — attention required" : "Live status details");
  if (latestSystemError) {
    add("LATEST ERROR",latestSystemError.message);
    add("COMPONENT",latestSystemError.component);
    add("LIKELY CAUSE",latestSystemError.cause);
    add("RECOMMENDED ACTION",latestSystemError.action);
    add("OCCURRED",latestSystemError.time,true);
  } else {
    add("LATEST ERROR","No error has been recorded in this session.",true);
  }
  add("CLOUD AI",cloud ? (cloud.ready ? "Configured" : "Not configured") + " — " + cloud.detail : "Status not returned");
  add("VOICE / TTS",status.voice_ready ? (status.voice_provider || "Configured") + " — " + (status.tts_model || "model not reported") + " / " + (status.tts_voice || "voice not reported") : "Not configured or unavailable");
  add("LOCAL MEMORY",status.local_memory ? "Active" : "Unavailable");
  add("CLOUD MEMORY",status.cloud_memory ? "Configured" : "Not configured (local memory remains available)");
  add("MICROPHONE",sessionActive ? (recorderFallback ? "Active — recording and transcription mode" : "Voice session active") : "Not currently active");
  add("VOICE INPUT PATH",recorderFallback ? "MediaRecorder → Gemini transcription → OpenRouter AI chat" : "Not active");
  add("CLOUD TRANSCRIPTION",status.transcription_ready ? (status.transcription_provider || "Configured") : "Unavailable — check GEMINI_API_KEY and server settings");
  add("SERVER", "Local ULTRON API: " + location.origin);
  content.replaceChildren();
  for (const row of rows) {
    const wrap=document.createElement("div");wrap.className="diag-row";
    const label=document.createElement("div");label.className="diag-label";label.textContent=row.label;
    const value=document.createElement("div");value.className="diag-value"+(row.muted?" diag-muted":"");value.textContent=row.value;
    wrap.append(label,value);content.append(wrap);
  }
  panel.classList.add("open");
}
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
  const informational = /^(using direct microphone mode|conversation reset\.)/i.test(String(message || "").trim());
  if (!informational) recordSystemError(message, /microphone|speech recognition|recording/i.test(String(message)) ? "Microphone" : /voice|speech|tts|audio/i.test(String(message)) ? "Voice / TTS" : "Chat / system");
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
    $("ultron-live-label").textContent = mode === "speaking" ? "ULTRON SPEAKING" : mode === "error" ? "SYSTEM ERROR" : mode === "connecting" ? "CONNECTING" : mode === "thinking" ? "THINKING" : mode.toUpperCase();
    indicator.setAttribute("role","button"); indicator.setAttribute("tabindex","0"); indicator.setAttribute("aria-label","Open ULTRON system diagnostics");
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
  if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)({latencyHint:"playback"});  if (audioContext.state === "suspended") await audioContext.resume();
  if (!analyser) {
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
  }
  if (!playbackCompressor) {
    playbackCompressor = audioContext.createDynamicsCompressor();
    playbackCompressor.threshold.value = -18;
    playbackCompressor.knee.value = 12;
    playbackCompressor.ratio.value = 4;
    playbackCompressor.attack.value = 0.004;
    playbackCompressor.release.value = 0.22;
    playbackGain = audioContext.createGain();
    playbackGain.gain.value = 1.35;
    playbackCompressor.connect(playbackGain);
    playbackGain.connect(audioContext.destination);
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
  recognition.lang = "en-US";
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => {
    clearTimeout(recognitionStartTimer);
    if (sessionActive && !playbackSource && !busy) setMode("listening", "LISTENING", "I'm listening. Speak naturally.");
  };
  recognition.onerror = (event) => {
    if (event.error === "no-speech" || event.error === "aborted") return;
    const fatal = event.error === "not-allowed" || event.error === "service-not-allowed";
    if (fatal) recognitionFatalError = true;
    const detail = fatal
      ? "Android Chrome's built-in speech recognition service refused the request. ULTRON uses the same browser-native speech input as Phoenix AI Evo; no paid Whisper transcription is called."
      : "Browser speech recognition reported: " + event.error + ". ULTRON will attempt to reconnect.";
    logEvent("Browser speech recognition error: " + event.error);
    recordSystemError(detail, "Browser speech recognition");
    setMode("error", "SPEECH RECOGNITION ERROR", detail);
    if (fatal) toast(detail);
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
      if (!sessionActive || !recognition || recognitionFatalError) return;
      try { recognition.start(); } catch {
        logEvent("Speech recognition reconnect is waiting for the browser");
      }
    }, 500);
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
        recognitionFatalError = true;
        const detail = "Android Chrome did not start its built-in speech recognition service. No cloud transcription or paid Whisper fallback will be used.";
        logEvent("Browser speech recognition startup timed out");
        recordSystemError(detail, "Browser speech recognition");
        setMode("error", "SPEECH SERVICE UNAVAILABLE", detail);
        toast(detail);
      }
    }, 8000);
  } catch (error) {
    recognitionFatalError = true;
    const detail = "Browser speech recognition could not start: " + (error.message || "unknown browser error");
    logEvent(detail);
    recordSystemError(detail, "Browser speech recognition");
    setMode("error", "SPEECH SERVICE UNAVAILABLE", detail);
    toast(detail);
  }
}
async function activateRecorderFallback(cause) {
  if (!sessionActive || !microphoneStream) return;
  if (!window.MediaRecorder || !window.requestAnimationFrame) {
    sessionActive = false;
    microphoneStream.getTracks().forEach(track => track.stop());
    microphoneStream = null;
    micAudioSource?.disconnect(); micAudioSource = null;
    updateControls();
    const detail = "This browser does not support the recording fallback required for reliable voice input.";
    recordSystemError(detail, "Speech recognition");
    setMode("error", "VOICE INPUT UNAVAILABLE", detail);
    toast(detail);
    return;
  }
  try { recognition?.abort(); } catch {}
  recognition = null;
  recorderFallback = true;
  clearTimeout(recognitionStartTimer);
  logEvent("Switching to microphone recording fallback");
  const detail = cause?.message || "Using the compatible microphone recording path.";
  setMode("listening", "LISTENING", "Microphone is active. Speak naturally, then pause briefly so ULTRON can process your command.");
  updateControls();
  startFallbackRecording();
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
  setMode("thinking", "PROCESSING", "Analysing your command. ULTRON will answer by voice.");
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
        }
        if (event.done) streamDone = true;
      }
    }
    if (!reply.trim()) throw new Error("ULTRON ended the stream without a response.");    logEvent("Response stream completed; preparing voice output");
    try {
      await speak(reply);
    } catch (speechError) {
      logEvent("Voice output failed: " + (speechError.message || "unknown error"));
      toast("ULTRON could not speak the response: " + (speechError.message || "Voice service unavailable."));
      setMode("error", "VOICE OUTPUT ERROR", "Check the configured speech provider and try again.");
      await resumeMicrophoneAfterSpeech();
    }
  } catch (error) {
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
async function pauseMicrophoneForSpeech() {
  voiceOutputActive = true;
  if (!sessionActive || !microphoneStream) return;
  speechMicPaused = true;
  if (vadFrame) cancelAnimationFrame(vadFrame);
  vadFrame = 0;
  vadSpeechStarted = false;
  vadSilenceAt = 0;
  // The command is already captured. Discard any partial segment and release
  // the input track while ULTRON speaks so Android can leave communication mode.
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    try { mediaRecorder.stop(); } catch {}
  }
  mediaRecorder = null;
  recordedChunks = [];
  micAudioSource?.disconnect();
  micAudioSource = null;
  const stream = microphoneStream;
  microphoneStream = null;
  stream.getTracks().forEach(track => track.stop());
  logEvent("Microphone released during playback to request Android media audio routing");
  await new Promise(resolve => setTimeout(resolve, 450));
}
async function resumeMicrophoneAfterSpeech() {
  voiceOutputActive = false;
  if (!sessionActive || !speechMicPaused || microphoneResumePromise) return microphoneResumePromise;
  speechMicPaused = false;
  microphoneResumePromise = (async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: true, autoGainControl: true }
      });
      if (!sessionActive) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      microphoneStream = stream;
      if (audioContext && analyser) {
        micAudioSource = audioContext.createMediaStreamSource(microphoneStream);
        micAudioSource.connect(analyser);
        animateAudio();
      }
      logEvent("Microphone reacquired after voice playback");
      if (recorderFallback) startFallbackRecording();
      setMode("listening", "LISTENING", "I'm listening again. Speak naturally.");
    } catch (error) {
      speechMicPaused = true;
      const detail = "ULTRON finished speaking but could not reopen the microphone: " + (error.message || "microphone unavailable");
      logEvent(detail);
      recordSystemError(detail, "Microphone restart");
      setMode("error", "MICROPHONE RESTART FAILED", detail);
      toast(detail);
    } finally {
      microphoneResumePromise = null;
    }
  })();
  return microphoneResumePromise;
}
async function speak(text) {
  await pauseMicrophoneForSpeech();
  setMode("thinking", "GENERATING VOICE", "Preparing ULTRON's deep synthetic voice.");
  try {
    const response = await fetch("/api/voice", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({text})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "ULTRON voice generation failed.");
    await prepareAudio();
    const binary = atob(data.audio);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const audioBuffer = await audioContext.decodeAudioData(bytes.buffer);
    activeSpeechText = text;
    playbackSource = audioContext.createBufferSource();
    const source = playbackSource;
    source.buffer = audioBuffer;
    source.connect(analyser);
    source.connect(playbackCompressor);
    source.onended = () => {
      if (playbackSource !== source) return;
      playbackSource = null;
      activeSpeechText = "";
      resetGlow();
      resumeMicrophoneAfterSpeech().catch(error => logEvent("Microphone restart failed: " + (error.message || "unknown error")));
      if (sessionActive && !busy) setMode("listening", "LISTENING", "I'm listening. Speak naturally.");
      else if (!sessionActive) setMode("standby", "SYSTEM STANDBY", "Text channel active.");
    };
    setMode("speaking", "ULTRON IS SPEAKING", "Speak at any time to interrupt.");
    $("control-caption").textContent = "ULTRON VOICE API · MEDIA SPEAKER";
    source.start();
    animateAudio();
  } catch (error) {
    await resumeMicrophoneAfterSpeech();
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
      throw new Error("Microphone API unavailable. Open ULTRON in Chrome using its HTTPS Render address or localhost.");
    }
    if (!window.MediaRecorder) {
      throw new Error("This browser does not support microphone recording. Update Chrome and allow microphone access.");
    }
    sessionActive = true;
    forceTimedRecorder = false;
    updateControls();
    setMode("connecting","REQUESTING MICROPHONE","Opening the phone microphone…");
    logEvent("Starting direct microphone capture; browser speech recognition is bypassed.");
    // Use one predictable path on Android: capture audio, send it to
    // Google Gemini, then send the transcript to ULTRON's chat model.
    microphoneStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: true, autoGainControl: true }
    });
    if (!sessionActive) {
      microphoneStream.getTracks().forEach(track => track.stop());
      microphoneStream = null;
      return;
    }
    logEvent("Microphone stream granted; preparing audio capture");
    try {
      if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
      if (audioContext.state === "suspended") await audioContext.resume();
      if (!analyser) { analyser = audioContext.createAnalyser(); analyser.fftSize = 2048; }
      micAudioSource = audioContext.createMediaStreamSource(microphoneStream);
      micAudioSource.connect(analyser);
      animateAudio();
    } catch (audioError) {
      logEvent("Audio visualizer unavailable: " + (audioError.message || "unknown error"));
    }
    await activateRecorderFallback(new Error("Gemini microphone transcription mode is active."));
  } catch (error) {
    sessionActive = false;
    try { recognition?.abort(); } catch {}
    recognition = null;
    clearTimeout(recognitionStartTimer);
    microphoneStream?.getTracks().forEach(track => track.stop());
    microphoneStream = null;
    micAudioSource?.disconnect(); micAudioSource = null;
    if (vadFrame) cancelAnimationFrame(vadFrame);
    vadFrame = 0;
    updateControls();

    const errorName = String(error?.name || "UnknownError");
    const rawMessage = String(error?.message || error || "No browser error message was provided.");
    const secureContext = window.isSecureContext === true;
    const environment = `name=${errorName}; message=${rawMessage}; secureContext=${secureContext}; mediaDevices=${Boolean(navigator.mediaDevices?.getUserMedia)}; origin=${location.origin}`;
    logEvent("Microphone activation failed: " + environment);
    const message = errorName === "NotAllowedError" || errorName === "SecurityError"
      ? "Chrome or Android denied microphone access. Allow microphone permission for this site, then reload ULTRON."
      : errorName === "NotFoundError" || errorName === "DevicesNotFoundError"
        ? "No microphone input was found on this device."
        : errorName === "NotReadableError" || errorName === "TrackStartError"
          ? "The microphone is busy or could not be opened. Close other apps using it and retry."
          : !window.isSecureContext
            ? "Microphone capture requires HTTPS or localhost. Open the HTTPS Render URL."
            : rawMessage;
    toast(message);
    recordSystemError(environment, "Microphone");
    setMode("error","MICROPHONE ERROR",message);
  }
}
function startFallbackRecording() {
  if (!sessionActive || !microphoneStream || vadFrame) return;

  const transcribeRecordedBlob = async (blob) => {
    if (!blob?.size || !sessionActive) return;
    let transcriptionFailed = false;
    try {
      setMode("thinking", "TRANSCRIBING", "I heard you. Gemini is converting your speech.");
      logEvent("Audio segment captured; sending to Gemini transcription");
      const audio = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
        reader.onerror = () => reject(new Error("Could not read microphone audio."));
        reader.readAsDataURL(blob);
      });
      if (!audio) throw new Error("The microphone recording was empty.");
      const response = await fetch("/api/transcribe", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({audio, mime_type: blob.type || "audio/webm"})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Gemini speech transcription failed.");
      if (data.transcript?.trim()) {
        logEvent("Gemini transcript received; sending message to ULTRON chat");
        await processUtterance(data.transcript.trim());
      } else {
        logEvent("Gemini returned no intelligible speech for this audio segment");
      }
    } catch (error) {
      transcriptionFailed = true;
      logEvent("Transcription failed: " + (error.message || "unknown error"));
      recordSystemError(error.message || "Speech transcription failed.", "Gemini speech transcription");
      setMode("error", "TRANSCRIPTION FAILED", error.message || "Speech transcription failed. Open diagnostics for details.");
      toast(error.message || "Speech transcription failed.");    } finally {
      if (sessionActive && !chatBusy && !busy && !transcriptionFailed) {
        setMode("listening", "LISTENING", "I'm listening. Speak naturally.");
      }
    }
  };

  const hasAnalyser = !forceTimedRecorder && Boolean(analyser && audioContext && audioContext.state === "running");
  const samples = new Float32Array(analyser?.fftSize || 2048);

  // If Android suspends or refuses the Web Audio analyser, still capture audio.
  // This timed MediaRecorder path deliberately does not depend on RMS/VAD.
  if (!hasAnalyser) {
    logEvent("Audio analyser unavailable; using timed microphone recording fallback");
    try {
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]
        .find(type => MediaRecorder.isTypeSupported(type));
      mediaRecorder = new MediaRecorder(microphoneStream, mimeType ? {mimeType} : undefined);
      recordedChunks = [];
      mediaRecorder.ondataavailable = event => { if (event.data?.size) recordedChunks.push(event.data); };
      mediaRecorder.onerror = event => {
        const message = event.error?.message || "Microphone recording failed.";
        recordSystemError(message, "MediaRecorder");
        toast(message);
      };
      mediaRecorder.onstop = async () => {
        const current = mediaRecorder;
        mediaRecorder = null;
        const blob = new Blob(recordedChunks, {type: current?.mimeType || "audio/webm"});
        recordedChunks = [];
        if (!sessionActive || speechMicPaused) return;
        await transcribeRecordedBlob(blob);
        if (sessionActive && !speechMicPaused) startFallbackRecording();
      };
      mediaRecorder.start();
      setMode("listening", "LISTENING", "Microphone is recording. Speak, then pause briefly.");
      vadFrame = requestAnimationFrame(() => {
        vadFrame = 0;
        if (!sessionActive || !mediaRecorder || mediaRecorder.state !== "recording") return;
        // A short bounded segment keeps requests small and prevents a dead VAD
        // from silently leaving the microphone open without sending anything.
        setTimeout(() => {
          if (sessionActive && mediaRecorder?.state === "recording") {
            try { mediaRecorder.stop(); } catch {}
          }
        }, 6500);
      });
    } catch (error) {
      recordSystemError(error.message || "Could not start microphone recording.", "MediaRecorder");
      setMode("error", "RECORDING FAILED", error.message || "Could not start microphone recording.");
      toast(error.message || "Could not start microphone recording.");
    }
    return;
  }

  const noSignalStartedAt = Date.now();
  const tick = () => {
    if (!sessionActive || !microphoneStream) { vadFrame = 0; return; }
    let rms = 0;
    analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (const value of samples) sum += value * value;
    rms = Math.sqrt(sum / samples.length);
    const now = Date.now();

    if (voiceOutputActive || chatBusy || busy) {
      document.documentElement.style.setProperty("--voice-energy", "0");
      vadFrame = requestAnimationFrame(tick);
      return;
    }
    if (!mediaRecorder && rms < 0.001 && now - noSignalStartedAt > 3000) {
      logEvent("Microphone analyser detected no usable input; switching to timed recording fallback");
      forceTimedRecorder = true;
      cancelAnimationFrame(vadFrame);
      vadFrame = 0;
      startFallbackRecording();
      return;
    }
    if (rms > 0.006) {
      vadSpeechStarted = true;
      vadSilenceAt = 0;
      if (!mediaRecorder) {
        recordedChunks = [];
        const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]
          .find(type => MediaRecorder.isTypeSupported(type));
        mediaRecorder = new MediaRecorder(microphoneStream, mimeType ? {mimeType} : undefined);
        mediaRecorder.ondataavailable = event => { if (event.data?.size) recordedChunks.push(event.data); };
        mediaRecorder.onerror = event => toast(event.error?.message || "Microphone recording failed.");
        mediaRecorder.onstop = async () => {
          const current = mediaRecorder;
          mediaRecorder = null;
          const blob = new Blob(recordedChunks, {type: current?.mimeType || "audio/webm"});
          recordedChunks = [];
          vadSpeechStarted = false;
          vadSilenceAt = 0;
          if (!sessionActive || speechMicPaused) return;
          await transcribeRecordedBlob(blob);
          if (sessionActive && !speechMicPaused) startFallbackRecording();
        };
        mediaRecorder.start();
        vadSegmentStartedAt = now;
        setMode("listening", "LISTENING", "I can hear you. Keep speaking; pause when you're done.");
      }
    } else if (mediaRecorder?.state === "recording" && vadSpeechStarted) {
      if (!vadSilenceAt) vadSilenceAt = now;
      if (now - vadSilenceAt > 1100 || now - vadSegmentStartedAt > 12000) {
        try { mediaRecorder.stop(); } catch {}
      }
    }
    document.documentElement.style.setProperty("--voice-energy", Math.min(1, rms * 8).toFixed(3));
    vadFrame = requestAnimationFrame(tick);
  };
  vadFrame = requestAnimationFrame(tick);
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
  speechMicPaused = false;
  busy = false;
  queuedUtterance = "";
  clearTimeout(interruptionTimer);
  clearTimeout(restartTimer);
  clearTimeout(recognitionStartTimer);
  if(vadFrame)cancelAnimationFrame(vadFrame); vadFrame=0; vadSpeechStarted=false; vadSilenceAt=0;
  recognitionFatalError = false;
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
    latestSystemStatus = data;
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
    logEvent(data.voice_ready ? (data.voice_provider || "Voice provider") + " configured" : "Voice provider unavailable");
    if (!cloud?.ready) $("overall-detail").textContent = "Cloud provider needs attention";
  } catch (error) {
    recordSystemError(error.message || "Unable to retrieve system status", "Status API");
    ["cloud-status","voice-status","memory-status"].forEach(id => $(id).textContent = "UNKNOWN");
    logEvent("Unable to retrieve system status: " + (error.message || "unknown error"));
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
$("ultron-live-close")?.addEventListener("click", event => { event.stopPropagation(); liveIndicatorDismissed = true; $("ultron-live-indicator")?.classList.remove("visible"); });
$("ultron-live-indicator")?.addEventListener("click", openDiagnostics);
$("ultron-live-indicator")?.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openDiagnostics(); } });
$("robotHeadWrapper")?.addEventListener("click",toggleHeadVoice);
$("mic-button")?.addEventListener("click",toggleHeadVoice);
$("stop-button").addEventListener("click", stopSession);
$("chat-form").addEventListener("submit", event => {
  event.preventDefault();
  const input = $("chat-input");
  const message = input.value.trim();
  if (!message || chatBusy) return;
  input.value = "";
  // Unlock Web Audio directly inside the send-button gesture so the later
  // network response can be played without mobile autoplay blocking.
  prepareAudio().catch(error => logEvent("Audio output could not unlock: " + (error.message || "unknown error")));
  sendChatMessage(message, false);
});
$("reset-button").addEventListener("click", resetConversation);
$("voice-engine")?.replaceChildren();
function updateClock() { $("clock").textContent = new Date().toLocaleTimeString([], {hour12:false}); }
updateClock();
setInterval(updateClock, 1000);
loadStatus();
// On Android Chrome, start microphone + Web Speech only after a deliberate
// user tap. Automatic page-load startup can be rejected by speech services.
if (navigator.mediaDevices?.getUserMedia) {
  setMode("standby","SYSTEM STANDBY","Tap the ULTRON head or microphone button to activate voice.");
} else {
  setMode("error","MICROPHONE UNAVAILABLE","This browser does not expose microphone access. Open ULTRON in a supported browser.");
}
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));