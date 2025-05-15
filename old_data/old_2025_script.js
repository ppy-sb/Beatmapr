let currentUserId = null;
let lastLoadedScoreFileContent = "";

document.addEventListener("DOMContentLoaded", async () => {
  const squaresContainer = document.querySelector(".squares");
  const statusDisplay = document.getElementById("status");

  // ✅ Load user list
  let usersList = [];
  async function loadUsers() {
    const res = await fetch("users.json");
    usersList = await res.json();
  }
  await loadUsers();

  // ✅ Username suggestion logic
  const input = document.querySelector("input[name='player']");
  const suggestions = document.getElementById("user-suggestions");

  input.addEventListener("input", () => {
    const query = input.value.toLowerCase();
    suggestions.innerHTML = "";

    if (!query) return;

    const matches = usersList
      .filter(user => user.username.toLowerCase().includes(query))
      .slice(0, 10);

    matches.forEach(user => {
      const li = document.createElement("li");
      li.innerHTML = `<img src="https://a.akatsuki.gg/${user.id}.png" onerror="this.src='default.png'"> ${user.username}`;
      li.addEventListener("click", () => {
        input.value = user.id; // set ID for rest of the logic
        suggestions.innerHTML = "";
        input.form.dispatchEvent(new Event("submit"));
      });
      suggestions.appendChild(li);
    });
  });

  document.addEventListener("click", (e) => {
    if (!suggestions.contains(e.target) && e.target !== input) {
      suggestions.innerHTML = "";
    }
  });

  // ✅ Load packs and squares
  const packsResponse = await fetch("packs.json");
  const packs = await packsResponse.json();
  let beatmapIds = new Set();

  const sortedPacks = [...packs].sort((a, b) => {
    const aNum = parseInt(a.packName.replace("S", ""));
    const bNum = parseInt(b.packName.replace("S", ""));
    return aNum - bNum;
  });

  const progressText = document.createElement("div");
  progressText.className = "progress-overview";
  document.querySelector(".progress-section").appendChild(progressText);

  sortedPacks.forEach((pack) => {
    const square = document.createElement("div");
    square.classList.add("square");
    square.title = `${pack.packName}`;
    square.dataset.beatmaps = pack.beatmaps.map(b => b.beatmap_id).join(",");

    updateSquareColor(square, pack.beatmaps);
    squaresContainer.appendChild(square);

    square.addEventListener("click", () => {
      const beatmaps = pack.beatmaps.map(b => b.beatmap_id);
      showModal(beatmaps, pack.beatmaps, square);
    });
  });

  const modal = document.getElementById("beatmap-modal");
  const beatmapList = document.getElementById("beatmap-list");
  const closeModalBtn = document.querySelector(".close-btn");

  function showModal(beatmaps, fullBeatmapData, squareElement) {
    beatmapList.innerHTML = "";

    beatmaps.forEach(id => {
      const beatmapData = fullBeatmapData.find(b => b.beatmap_id === id);
      const time = beatmapData ? formatTime(beatmapData.time_duration_seconds) : "N/A";

      const container = document.createElement("div");
      container.style.display = "flex";
      container.style.alignItems = "center";
      container.style.marginBottom = "6px";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = beatmapIds.has(id);
      checkbox.style.marginRight = "10px";

      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          beatmapIds.add(id);
        } else {
          beatmapIds.delete(id);
        }
        updateSquareColor(squareElement, fullBeatmapData);
        updateCompletionText();
        link.style.color = checkbox.checked ? "#4CAF50" : "#F44336";
      });

      const link = document.createElement("a");
      link.href = `https://osu.ppy.sh/b/${id}`;
      link.textContent = `${id} - ${time}`;
      link.target = "_blank";
      link.style.color = checkbox.checked ? "#4CAF50" : "#F44336";
      link.style.textDecoration = "none";

      link.addEventListener("mouseover", () => link.style.textDecoration = "underline");
      link.addEventListener("mouseout", () => link.style.textDecoration = "none");

      container.appendChild(checkbox);
      container.appendChild(link);
      beatmapList.appendChild(container);
    });

    beatmapList.scrollTop = 0;
    modal.classList.remove("hidden");
  }

  closeModalBtn.addEventListener("click", () => modal.classList.add("hidden"));
  window.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });

  function updateSquareColor(square, beatmaps) {
    const total = beatmaps.length;
    const matched = beatmaps.filter(b => beatmapIds.has(b.beatmap_id)).length;

    if (matched === total) {
      square.style.backgroundColor = "#4CAF50";
    } else if (matched > 0) {
      square.style.backgroundColor = "#FFC107";
    } else {
      square.style.backgroundColor = "#F44336";
    }
  }

  function updateAllSquares() {
    document.querySelectorAll(".square").forEach(square => {
      const beatmapIdsArray = square.dataset.beatmaps.split(",").map(Number);
      const beatmaps = beatmapIdsArray.map(id => ({ beatmap_id: id }));
      updateSquareColor(square, beatmaps);
    });
  }

  function updateCompletionText() {
    let totalBeatmaps = 0;
    let completedBeatmaps = 0;

    sortedPacks.forEach(pack => {
      totalBeatmaps += pack.beatmaps.length;
      completedBeatmaps += pack.beatmaps.filter(b => beatmapIds.has(b.beatmap_id)).length;
    });

    const completionPercent = totalBeatmaps > 0
      ? ((completedBeatmaps / totalBeatmaps) * 100).toFixed(2)
      : 0;

    progressText.textContent = `Completion: ${completedBeatmaps}/${totalBeatmaps} (${completionPercent}%)`;
  }

  function formatTime(seconds) {
    if (seconds === "N/A") return seconds;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  }

  updateCompletionText();

  // === SEARCH + FETCH PROFILE ===
  const searchForm = document.querySelector(".search-form");
  const avatarImage = document.querySelector(".profile-avatar");
  const usernameElement = document.querySelector(".profile-info h2");
  const rankedScoreElement = document.querySelector(".profile-info p:nth-of-type(1)");
  const globalRankElement = document.querySelector(".profile-info p:nth-of-type(2)");
  const rankLineElement = document.querySelector(".rank-counts");

  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const userId = input.value.trim();
    if (!userId) return;

    currentUserId = userId;
    avatarImage.src = `https://a.akatsuki.gg/${userId}.png`;
    avatarImage.onerror = () => avatarImage.src = "default.png";

    try {
      const profileRes = await fetch(`https://akatsuki.gg/api/v1/users/full?id=${userId}`);
      const profileData = await profileRes.json();

      if (profileData?.username) {
        usernameElement.textContent = profileData.username;
        const stdStats = profileData.stats[1]?.std;
        if (stdStats) {
          rankedScoreElement.textContent = `Ranked Score: ${stdStats.ranked_score.toLocaleString()}`;
          globalRankElement.textContent = `Global Rank: ${stdStats.global_leaderboard_rank ? `#${stdStats.global_leaderboard_rank}` : "#?"}`;
        } else {
          rankedScoreElement.textContent = "Ranked Score: 0";
          globalRankElement.textContent = "Global Rank: #?";
        }
      } else {
        usernameElement.textContent = "User not found";
        rankedScoreElement.textContent = "Ranked Score: 0";
        globalRankElement.textContent = "Global Rank: #?";
      }
    } catch (err) {
      console.error("Failed to fetch user info:", err);
      usernameElement.textContent = "Error loading user";
      rankedScoreElement.textContent = "Ranked Score: 0";
      globalRankElement.textContent = "Global Rank: #?";
    }

    statusDisplay.textContent = "Fetching ranked scores...";
    try {
      await fetch(`/api/fetch-scores?id=${userId}`);
      statusDisplay.textContent = "Waiting for ranked scores file...";

      setTimeout(() => {
        autoLoadBeatmapFile(`${userId}_scores.txt`);
      }, 1500);
    } catch (err) {
      console.error("Failed to start score fetch:", err);
      statusDisplay.textContent = "Failed to fetch ranked scores.";
    }
  });

  const importButton = document.getElementById("import-button");
  const importFileInput = document.getElementById("import-file");

  importButton.addEventListener("click", () => {
    importFileInput.click();
  });

  importFileInput.addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function (e) {
      const content = e.target.result;
      lastLoadedScoreFileContent = content;

      beatmapIds.clear();
      const newIds = content.match(/\d+/g)?.map(Number) || [];
      newIds.forEach(id => beatmapIds.add(id));

      updateAllSquares();
      updateCompletionText();
    };
    reader.readAsText(file);
  });

  async function autoLoadBeatmapFile(filename) {
    try {
      const response = await fetch(filename);
      const content = await response.text();
      lastLoadedScoreFileContent = content;

      const lines = content.split('\n');
      const beatmapIdLines = lines
        .map(line => line.trim())
        .filter(line => /^\d+$/.test(line))
        .map(Number);

      beatmapIds.clear();
      beatmapIdLines.forEach(id => beatmapIds.add(id));

      updateAllSquares();
      updateCompletionText();

      const rankLine = lines.find(line =>
        line.includes("SSH:") && line.includes("SH:") && line.includes("SS:")
      );
      if (rankLine && rankLineElement) {
        rankLineElement.textContent = rankLine.trim();
      }

      statusDisplay.textContent = `Auto-loaded ${beatmapIdLines.length} beatmaps from ${filename}`;
    } catch (err) {
      console.error("Auto-load failed:", err);
      statusDisplay.textContent = `Auto-load failed: ${filename}`;
    }
  }

  setInterval(() => {
    if (currentUserId) {
      autoLoadBeatmapFile(`${currentUserId}_scores.txt`);
    }
  }, 1000000);

  const exportButton = document.getElementById("export-button");

  exportButton.addEventListener("click", () => {
    if (!lastLoadedScoreFileContent) {
      statusDisplay.textContent = "No score file loaded to export.";
      return;
    }

    const blob = new Blob([lastLoadedScoreFileContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = `${currentUserId || "scores"}_export.txt`;
    a.click();

    URL.revokeObjectURL(url);
  });
});
