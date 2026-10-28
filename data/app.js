
const $ = id => document.getElementById(id);

let recognition = null;
let socket = null;
let lastGesture = "";
let reconnectTimer = null;

function speak(text) {
  if (!text || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.95;
  window.speechSynthesis.speak(u);
}

function addMessage(side, text) {
  const box = $("messages");
  if (!box) return;

  const empty = box.querySelector(".empty");
  if (empty) empty.remove();

  const row = document.createElement("div");
  row.className = "msg " + side;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.appendChild(bubble);
  box.appendChild(row);
  box.scrollTop = box.scrollHeight;

  if ($("vibrate")?.checked && navigator.vibrate) {
    navigator.vibrate(100);
  }
}

function setGesture(text, confidence = 0) {
  if (!text) return;

  // Match the firmware's gesture labels to readable text.
  const names = {
    "IM_OKAY": "I'M OKAY",
    "GOOD_FOR_YOU": "GOOD FOR YOU",
    "HAVE_A_GOOD_DAY": "HAVE A GOOD DAY",
    "THANK_YOU": "THANK YOU"
  };

  const readable = names[text] || text.replaceAll("_", " ");

  if ($("detectedText")) $("detectedText").textContent = readable;
  if ($("gestureBadge")) $("gestureBadge").textContent = "DETECTED";

  const percent = Math.round(Math.max(0, Math.min(1, confidence)) * 100);
  if ($("confidence")) $("confidence").textContent =
    confidence ? percent + "%" : "—";
  if ($("confidenceBar")) $("confidenceBar").style.width =
    confidence ? percent + "%" : "0%";

  // IDLE is the neutral position, not a spoken word.
  if (text.toUpperCase() === "IDLE") {
    lastGesture = text;
    return;
  }

  // Avoid adding the same continuously detected pose repeatedly.
  if (text !== lastGesture) {
    addMessage("glove", readable);
    if ($("autoSpeak")?.checked) speak(readable);
    lastGesture = text;
  }
}

if ($("speakDetected")) {
  $("speakDetected").onclick = () => {
    speak($("detectedText")?.textContent);
  };
}

if ($("clearBtn")) {
  $("clearBtn").onclick = () => {
    if ($("messages")) {
      $("messages").innerHTML =
        '<div class="empty">Conversation messages will appear here.</div>';
    }
    lastGesture = "";
  };
}

function setupRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SR) {
    if ($("micLabel")) $("micLabel").textContent = "Speech not supported";
    if ($("micBtn")) $("micBtn").disabled = true;
    return;
  }

  recognition = new SR();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = false;

  recognition.onstart = () => {
    if ($("micLabel")) $("micLabel").textContent = "Listening…";
    if ($("micStatus")) $("micStatus").textContent = "LISTENING";
    if ($("micBtn")) $("micBtn").style.background = "#b42318";
  };

  recognition.onresult = e => {
    let finalText = "";

    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) {
        finalText += e.results[i][0].transcript;
      } else if ($("transcript")) {
        $("transcript").textContent = e.results[i][0].transcript;
      }
    }

    if (finalText.trim()) {
      if ($("transcript")) $("transcript").textContent = finalText.trim();
      addMessage("person", finalText.trim());
    }
  };

  recognition.onerror = e => {
    if ($("transcript")) {
      $("transcript").textContent = "Microphone error: " + e.error;
    }
  };

  recognition.onend = () => {
    if ($("micLabel")) $("micLabel").textContent = "Start speaking";
    if ($("micStatus")) $("micStatus").textContent = "MIC READY";
    if ($("micBtn")) $("micBtn").style.background = "";
  };
}

setupRecognition();

if ($("micBtn")) {
  $("micBtn").onclick = () => {
    if (recognition) {
      try {
        recognition.start();
      } catch (e) {
        console.log("Speech recognition is already active.");
      }
    }
  };
}

if ($("speakTranscript")) {
  $("speakTranscript").onclick = () => speak($("transcript")?.textContent);
}

if ($("settingsBtn")) {
  $("settingsBtn").onclick = () => $("settingsDialog")?.showModal();
}

if ($("closeSettings")) {
  $("closeSettings").onclick = () => $("settingsDialog")?.close();
}

if ($("largeText")) {
  $("largeText").onchange = e =>
    document.body.classList.toggle("large-text", e.target.checked);
}

if ($("highContrast")) {
  $("highContrast").onchange = e =>
    document.body.classList.toggle("high-contrast", e.target.checked);
}

// Connection button: show the current ESP32 address.
if ($("connectBtn")) {
  $("connectBtn").onclick = () => {
    const ip = $("espIp")?.value.trim();
    if ($("ipStatus")) {
      $("ipStatus").textContent = ip
        ? "Ready to connect to " + ip
        : "Enter ESP32 IP";
    }
  };
}

function connectESP32() {
  // The webpage is served directly by the ESP32, so reuse its address.
 const ip = document.getElementById("espIp").value.trim() || location.hostname;
 const port = document.getElementById("espPort").value.trim() || "80";
 const url = `ws://${ip}:${port}/ws`;

  if ($("espIp")) $("espIp").value = ip;
  if ($("espPort")) $("espPort").value = port;

  if ($("connectionText")) $("connectionText").textContent = "Connecting...";
  if ($("statusText")) $("statusText").textContent = "Connecting to ESP32...";

  try {
    socket = new WebSocket(url);

    socket.onopen = () => {
      if ($("connectionText")) $("connectionText").textContent = "ESP32 Connected";
      if ($("connectionDot")) $("connectionDot").classList.add("online");
      if ($("statusText")) $("statusText").textContent = "ESP32 Connected";
      if ($("ipStatus")) $("ipStatus").textContent = "Connected to " + ip;
    };

    socket.onmessage = event => {
      try {
        const data = JSON.parse(event.data);

        // Current ESP32 firmware sends {"type":"sign","sign":"STOP"}.
        const sign = data.sign || data.gesture;

        // Current firmware sends five ADC values only to Serial Monitor.
        // Update finger indicators only if a future message contains them.
        ["thumb", "index", "middle", "ring", "pinky"].forEach(k => {
          if (data[k] !== undefined && $(k)) {
            $(k).textContent = Math.round(data[k]);
          }
        });

        if (data.type === "sign" && sign) {
          setGesture(sign, Number(data.confidence || 0));
        } else if (data.gesture) {
          setGesture(data.gesture, Number(data.confidence || 0));
        }
      } catch (e) {
        console.log("Could not parse ESP32 message:", event.data);
      }
    };

    socket.onerror = () => {
      if ($("connectionText")) $("connectionText").textContent = "ESP32 Connection Error";
      if ($("connectionDot")) $("connectionDot").classList.remove("online");
      if ($("statusText")) $("statusText").textContent = "ESP32 Connection Error";
    };

    socket.onclose = () => {
      if ($("connectionText")) $("connectionText").textContent = "ESP32 Offline";
      if ($("connectionDot")) $("connectionDot").classList.remove("online");
      if ($("statusText")) $("statusText").textContent = "ESP32 Offline — reconnecting";
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connectESP32, 2500);
    };
  } catch (e) {
    if ($("ipStatus")) $("ipStatus").textContent = "Invalid connection";
  }
}

// Manual connection button can reconnect if needed.
if ($("socketBtn")) {
  $("socketBtn").onclick = () => {
    if (socket) socket.close();
    else connectESP32();
  };
}

// Demo keyboard shortcuts.
document.addEventListener("keydown", e => {
  const demo = {
    "1": "HELLO",
    "2": "I NEED HELP",
    "3": "I NEED WATER",
    "4": "YES",
    "5": "NO"
  };

  if (demo[e.key]) setGesture(demo[e.key], 0.94);
});

connectESP32();
