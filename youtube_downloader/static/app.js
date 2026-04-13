(function () {
  "use strict";

  const urlInput = document.getElementById("url-input");
  const qualitySelect = document.getElementById("quality-select");
  const downloadBtn = document.getElementById("download-btn");
  const loadingIndicator = document.getElementById("loading-indicator");
  const errorMsg = document.getElementById("error-msg");
  const progressArea = document.getElementById("progress-area");
  const videoTitle = document.getElementById("video-title");
  const progressBarFill = document.getElementById("progress-bar-fill");
  const progressLabel = document.getElementById("progress-label");
  const resultArea = document.getElementById("result-area");
  const downloadLink = document.getElementById("download-link");

  let pollTimer = null;
  let currentMeta = null; // {video_id, title}
  let fetchDebounce = null;
  let lastFetchedUrl = "";

  function resetUI() {
    errorMsg.hidden = true;
    errorMsg.textContent = "";
    progressArea.hidden = true;
    resultArea.hidden = true;
    progressBarFill.style.width = "0%";
    progressLabel.textContent = "0%";
    videoTitle.textContent = "";
  }

  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.hidden = false;
  }

  function stopPolling() {
    if (pollTimer !== null) { clearInterval(pollTimer); pollTimer = null; }
  }

  // Simple check if input looks like a YouTube URL
  function isYouTubeURL(str) {
    return /(?:youtube\.com\/(?:watch|playlist|shorts)|youtu\.be\/)/.test(str);
  }

  // --- Auto-fetch metadata when a YouTube URL is detected ---
  function onURLChange() {
    const url = urlInput.value.trim();

    // If input is cleared or not a YouTube URL, hide controls
    if (!url || !isYouTubeURL(url)) {
      qualitySelect.hidden = true;
      downloadBtn.hidden = true;
      loadingIndicator.hidden = true;
      currentMeta = null;
      lastFetchedUrl = "";
      return;
    }

    // Don't re-fetch the same URL
    if (url === lastFetchedUrl) return;

    // Debounce to avoid rapid-fire requests while typing
    clearTimeout(fetchDebounce);
    fetchDebounce = setTimeout(() => fetchMetadata(url), 400);
  }

  async function fetchMetadata(url) {
    resetUI();
    qualitySelect.hidden = true;
    downloadBtn.hidden = true;
    downloadBtn.disabled = true;
    currentMeta = null;
    loadingIndicator.hidden = false;

    try {
      const res = await fetch("/api/metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();

      if (!res.ok) { showError(data.error || "Something went wrong."); return; }

      lastFetchedUrl = url;
      currentMeta = { video_id: data.video_id, title: data.title };

      // Populate dropdown
      qualitySelect.innerHTML = '<option value="" disabled selected>Select quality</option>';
      for (const r of data.resolutions) {
        const opt = document.createElement("option");
        opt.value = r.height;
        opt.textContent = r.label;
        if (r.disabled) { opt.disabled = true; opt.textContent += " (unavailable)"; }
        qualitySelect.appendChild(opt);
      }

      qualitySelect.hidden = false;
      downloadBtn.hidden = false;
      downloadBtn.disabled = true;
    } catch (_) {
      showError("Could not reach the server. Is it running?");
    } finally {
      loadingIndicator.hidden = true;
    }
  }

  // Listen for paste, input, and change events on the URL field
  urlInput.addEventListener("paste", () => setTimeout(onURLChange, 50));
  urlInput.addEventListener("input", onURLChange);

  // --- Enable download button when quality is selected ---
  qualitySelect.addEventListener("change", function () {
    downloadBtn.disabled = !qualitySelect.value;
  });

  // --- Start download ---
  downloadBtn.addEventListener("click", async function () {
    if (!currentMeta) return;
    resetUI();

    const height = parseInt(qualitySelect.value, 10);
    downloadBtn.disabled = true;
    downloadBtn.textContent = "Downloading…";

    try {
      const res = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_id: currentMeta.video_id,
          title: currentMeta.title,
          height: height,
        }),
      });
      const data = await res.json();

      if (!res.ok) { showError(data.error || "Something went wrong."); resetDownloadBtn(); return; }

      videoTitle.textContent = data.title || "";
      progressArea.hidden = false;
      pollProgress(data.task_id);
    } catch (_) {
      showError("Could not reach the server.");
      resetDownloadBtn();
    }
  });

  function resetDownloadBtn() {
    downloadBtn.disabled = false;
    downloadBtn.textContent = "Download";
  }

  function pollProgress(taskId) {
    pollTimer = setInterval(async function () {
      try {
        const res = await fetch("/api/progress/" + taskId);
        if (!res.ok) { stopPolling(); showError("Failed to check progress."); resetDownloadBtn(); return; }

        const data = await res.json();
        const pct = Math.min(100, Math.max(0, Math.round(data.percentage)));
        progressBarFill.style.width = pct + "%";
        progressLabel.textContent = pct + "%";

        if (data.status === "complete") {
          stopPolling();
          progressArea.hidden = true;
          downloadLink.href = data.download_url;
          resultArea.hidden = false;
          resetDownloadBtn();
        } else if (data.status === "error") {
          stopPolling();
          progressArea.hidden = true;
          showError(data.error || "Download failed.");
          resetDownloadBtn();
        }
      } catch (_) {
        stopPolling();
        showError("Connection lost.");
        resetDownloadBtn();
      }
    }, 1000);
  }
})();
