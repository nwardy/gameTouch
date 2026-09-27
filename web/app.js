// Page setup ---------------------------------------------------------------
const originalVideo = document.querySelector("#original-video");
const generatedVideo = document.querySelector("#generated-video");
const originalUpload = document.querySelector("#original-upload");
const generatedUpload = document.querySelector("#generated-upload");
const originalPlaceholder = document.querySelector("#original-placeholder");
const generatedPlaceholder = document.querySelector("#generated-placeholder");
const originalName = document.querySelector("#original-name");
const generatedName = document.querySelector("#generated-name");
const startButton = document.querySelector("#start-button");
const pauseButton = document.querySelector("#pause-button");
const cueDescription = document.querySelector("#cue-description");
const statusText = document.querySelector("#status-text");

const isServerMode = window.location.protocol !== "file:";
const selectedUrls = new Map();
const v3GoalPreviewUrl = isServerMode ? "/assets/field-view.webm" : "assets/field-view.webm";

if (isServerMode) {
  cueDescription.textContent = "Starts both videos and sends a five-second cue to an armed Jetson.";
}

// Video upload boxes -------------------------------------------------------
function loadVideo(input, video, placeholder, nameLabel, useV3Fallback = false) {
  const [file] = input.files;
  if (!file) return;
  const previousUrl = selectedUrls.get(video);
  if (previousUrl) URL.revokeObjectURL(previousUrl);
  const objectUrl = URL.createObjectURL(file);
  selectedUrls.set(video, objectUrl);
  video.pause();
  video.addEventListener("error", () => {
    if (useV3Fallback && file.name.toLowerCase() === "v3goal.mp4") {
      video.src = v3GoalPreviewUrl;
      video.load();
      nameLabel.textContent = "v3goal.mp4 · browser preview";
      statusText.textContent = "Loaded browser-safe V3 preview";
      return;
    }
    statusText.textContent = "This video format is not supported by your browser";
  }, { once: true });
  video.src = objectUrl;
  video.load();
  video.hidden = false;
  placeholder.hidden = true;
  nameLabel.textContent = file.name;
  updateReadyState();
}

function updateReadyState() {
  const bothVideosLoaded = selectedUrls.has(originalVideo) && selectedUrls.has(generatedVideo);
  startButton.disabled = !bothVideosLoaded;
  statusText.textContent = bothVideosLoaded ? "Ready to play" : "Add both videos";
}

originalUpload.addEventListener("change", () => loadVideo(originalUpload, originalVideo, originalPlaceholder, originalName));
generatedUpload.addEventListener("change", () => loadVideo(generatedUpload, generatedVideo, generatedPlaceholder, generatedName, true));

// Synchronized playback ---------------------------------------------------
async function startDemo() {
  startButton.disabled = true;
  if (!isServerMode) {
    statusText.textContent = "Playing locally";
    playTogether();
    startButton.disabled = false;
    return;
  }

  try {
    const response = await fetch("/api/playback/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ countdown_seconds: 5 }),
    });
    if (!response.ok) throw new Error("The demo server did not accept the cue.");
    const cue = await response.json();
    statusText.textContent = "Jetson cue sent";
    window.setTimeout(() => {
      playTogether();
      startButton.disabled = false;
      statusText.textContent = "Playing";
    }, Math.max(0, cue.start_at * 1000 - Date.now()));
  } catch (error) {
    statusText.textContent = "Playing locally — Jetson not connected";
    playTogether();
    startButton.disabled = false;
    console.error(error);
  }
}

function playTogether() {
  for (const video of [originalVideo, generatedVideo]) {
    video.pause();
    video.currentTime = 0;
    video.play().catch(() => {
      statusText.textContent = "Choose videos that your browser can play";
    });
  }
  pauseButton.disabled = false;
  pauseButton.textContent = "Pause";
}

function togglePause() {
  const videos = [originalVideo, generatedVideo];
  const shouldResume = videos.some((video) => video.paused);
  for (const video of videos) shouldResume ? video.play() : video.pause();
  pauseButton.textContent = shouldResume ? "Pause" : "Resume";
  statusText.textContent = shouldResume ? "Playing" : "Paused";
}

startButton.addEventListener("click", startDemo);
pauseButton.addEventListener("click", togglePause);
window.addEventListener("beforeunload", () => {
  for (const objectUrl of selectedUrls.values()) URL.revokeObjectURL(objectUrl);
});
