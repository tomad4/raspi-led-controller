"use strict";

const buttons = [...document.querySelectorAll("[data-mode]")];
const status = document.getElementById("status");
const hrControls = document.getElementById("hr-controls");
const hrDevice = document.getElementById("hr-device");
const nightControls = document.getElementById("night-controls");
const nightColor = document.getElementById("night-color");
const nightBrightness = document.getElementById("night-brightness");
const toggleTitle = document.getElementById("toggle-title");
const toggleCopy = document.getElementById("toggle-copy");

function selectMode(mode) {
  buttons.forEach((button) => {
    const isSelected = button.dataset.mode === mode || (button.dataset.mode === "toggle" && mode === "off");
    button.setAttribute("aria-pressed", String(isSelected));
  });
  toggleTitle.textContent = mode === "off" ? "Włącz" : "Wyłącz";
  toggleCopy.textContent = mode === "off" ? "Wznów ostatni tryb" : "Zgaś ramkę";
  hrControls.hidden = mode !== "hr";
  nightControls.hidden = mode !== "night";
}

function describeState(data) {
  if (data.mode === "off") return "Ramka wyłączona.";
  if (data.mode === "hr") {
    if (data.hr !== null && data.hr !== undefined) return "Tętno: " + data.hr + " BPM" + (data.hr_connected ? "" : " · ponawiam połączenie");
    if (data.hr_connected) return "Połączono z " + data.hr_device_label + " · czekam na pomiar.";
    return "Tryb HR · szukam: " + (data.hr_device_label || "urządzenia HR") + ".";
  }
  if (data.mode === "power") {
    if (data.power_w !== null && data.power_w !== undefined) return "Moc: " + data.power_w + " W" + (data.power_connected ? "" : " · ponawiam połączenie");
    if (data.power_connected) return "Połączono z czujnikiem mocy · czekam na pomiar.";
    return "Tryb Power · szukam trenażera lub miernika BLE.";
  }
  if (data.mode === "demo") return "Animacja demo działa.";
  if (data.mode === "top_scan") return "Białe światło przesuwa się po górnej krawędzi (LED 112–151).";
  return "Lampka nocna działa.";
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) throw new Error("Sterownik LED jest niedostępny.");
    const data = await response.json();
    selectMode(data.mode);
    if (data.hr_device) hrDevice.value = data.hr_device;
    status.textContent = describeState(data);
    if (data.night_color) nightColor.value = data.night_color;
    if (data.night_brightness) nightBrightness.value = data.night_brightness;
  } catch {
    status.textContent = "Brak połączenia ze sterownikiem LED.";
  }
}

async function sendControl(mode) {
  status.textContent = "Wysyłam polecenie…";
  const payload = { mode };
  if (mode === "hr") payload.hr_device = hrDevice.value;
  if (mode === "night") {
    payload.color = nightColor.value;
    payload.brightness = Number(nightBrightness.value);
  }
  try {
    const response = await fetch("/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Nie udało się zmienić trybu.");
    selectMode(data.mode);
    status.textContent = describeState(data);
  } catch (error) {
    status.textContent = error.message || "Brak połączenia ze sterownikiem LED.";
  }
}

buttons.forEach((button) => {
  button.addEventListener("click", () => sendControl(button.dataset.mode));
});

hrDevice.addEventListener("change", () => sendControl("hr"));
nightColor.addEventListener("input", () => {
  if (!nightControls.hidden) sendControl("night");
});
nightBrightness.addEventListener("change", () => {
  if (!nightControls.hidden) sendControl("night");
});

refreshStatus();
window.setInterval(refreshStatus, 2500);
