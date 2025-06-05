let currentUserId = null;
let lastLoadedScoreFileContent = "";

document.addEventListener("DOMContentLoaded", async () => {
  const standardSquaresContainer = document.getElementById("standard-squares");
  const otherSquaresContainer = document.getElementById("other-squares");
  const statusDisplay = document.getElementById("status");
  const tooltip = document.getElementById("custom-tooltip");

  let usersList = [];
  async function loadUsers() {
    const res = await fetch("users.json");
    usersList = await res.json();
  }
  await loadUsers();

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
      li.innerHTML = `<img src="https://a.akatsuki.gg/${user.id}.png" onerror="this.src='images/default.png'"> ${user.username}`;
      li.addEventListener("click", () => {
        input.value = user.id;
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

  const packsResponse = await fetch("/packs");
  const packs = await packsResponse.json();
  console.log("Standard packs loaded:", packs);
  let beatmapIds = new Set();

  const otherPacksResponse = await fetch("/other_packs");
  const otherPacksRaw = await otherPacksResponse.json();
  // Flatten all sections into one array
  const otherPacks = [
    ...(otherPacksRaw.featured || []),
    ...(otherPacksRaw.tournament || []),
    ...(otherPacksRaw.loved || []),
    ...(otherPacksRaw.chart || []),
    ...(otherPacksRaw.theme || []),
    ...(otherPacksRaw.artist || [])
  ];
  console.log("otherPacks loaded:", otherPacks);

  otherPacks.forEach((pack) => {
    const square = document.createElement("div");
    square.classList.add("square");
    square.dataset.beatmaps = pack.beatmaps.map(b => b.beatmap_id).join(",");

    updateSquareColor(square, pack.beatmaps);
    updateSquareTooltip(square, pack.packName, pack.beatmaps);
    otherSquaresContainer.appendChild(square);

    square.addEventListener("click", () => {
      const beatmaps = pack.beatmaps.map(b => b.beatmap_id);
      showModal(beatmaps, pack.beatmaps, square, pack.packName, false);
    });

    square.addEventListener("mousemove", (e) => {
      tooltip.classList.remove("hidden");
      tooltip.textContent = square.dataset.tooltip;

      const tooltipWidth = tooltip.offsetWidth;
      const tooltipHeight = tooltip.offsetHeight;
      const padding = 10;
      const pageWidth = window.innerWidth;
      const pageHeight = window.innerHeight;

      let left = e.pageX + padding;
      let top = e.pageY + padding;

      if (left + tooltipWidth > pageWidth) {
        left = e.pageX - tooltipWidth - padding;
      }

      if (top + tooltipHeight > pageHeight) {
        top = e.pageY - tooltipHeight - padding;
      }

      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    });

    square.addEventListener("mouseleave", () => {
      tooltip.classList.add("hidden");
    });
  });

  function updateOtherPackCompletionStats(otherPacks) {
    let totalBeatmaps = 0;
    let clearedBeatmaps = 0;
    let totalPacks = otherPacks.length;
    let clearedPacks = 0;

    otherPacks.forEach(pack => {
      totalBeatmaps += pack.beatmaps.length;
      const clearedInPack = pack.beatmaps.filter(b => beatmapIds.has(b.beatmap_id)).length;
      clearedBeatmaps += clearedInPack;

      if (clearedInPack === pack.beatmaps.length) {
        clearedPacks++;
      }
    });

    const beatmapPercent = totalBeatmaps > 0 ? ((clearedBeatmaps / totalBeatmaps) * 100).toFixed(2) : "0.00";
    const packPercent = totalPacks > 0 ? ((clearedPacks / totalPacks) * 100).toFixed(2) : "0.00";

    document.getElementById("other-completed-count").textContent = clearedBeatmaps;
    document.getElementById("other-total-count").textContent = totalBeatmaps;
    document.getElementById("other-completion-percent").textContent = beatmapPercent;

    document.getElementById("other-completed-packs").textContent = clearedPacks;
    document.getElementById("other-total-packs").textContent = totalPacks;
    document.getElementById("other-pack-percent").textContent = packPercent;
  }

  function updateStandardPackCompletionStats() {
    let totalBeatmaps = 0;
    let clearedBeatmaps = 0;
    let totalPacks = sortedPacks.length;
    let clearedPacks = 0;

    sortedPacks.forEach(pack => {
      totalBeatmaps += pack.beatmaps.length;
      const clearedInPack = pack.beatmaps.filter(b => standardBeatmapIds.has(b.beatmap_id)).length;
      clearedBeatmaps += clearedInPack;

      if (clearedInPack === pack.beatmaps.length) {
        clearedPacks++;
      }
    });

    const beatmapPercent = totalBeatmaps > 0 ? ((clearedBeatmaps / totalBeatmaps) * 100).toFixed(2) : "0.00";
    const packPercent = totalPacks > 0 ? ((clearedPacks / totalPacks) * 100).toFixed(2) : "0.00";

    document.getElementById("standard-completed-count").textContent = clearedBeatmaps;
    document.getElementById("standard-total-count").textContent = totalBeatmaps;
    document.getElementById("standard-completion-percent").textContent = beatmapPercent;

    document.getElementById("standard-completed-packs").textContent = clearedPacks;
    document.getElementById("standard-total-packs").textContent = totalPacks;
  }





  const sortedPacks = [...packs].sort((a, b) => {
    const aNum = parseInt(a.packName.replace("S", ""));
    const bNum = parseInt(b.packName.replace("S", ""));
    return aNum - bNum;
  });

  document.getElementById("total-pack-count").textContent = sortedPacks.length;

  function updateCompletedPackCount() {
    const completedCount = sortedPacks.filter(pack =>
      pack.beatmaps.every(b => beatmapIds.has(b.beatmap_id))
    ).length;

    document.getElementById("completed-pack-count").textContent = completedCount;
  }

  const progressText = document.createElement("div");
  progressText.className = "progress-overview";
  document.querySelector(".progress-section").appendChild(progressText);

  sortedPacks.forEach((pack) => {
    const square = document.createElement("div");
    square.classList.add("square");
    square.dataset.beatmaps = pack.beatmaps.map(b => b.beatmap_id).join(",");

    updateSquareColor(square, pack.beatmaps);
    updateSquareTooltip(square, pack.packName, pack.beatmaps);
    standardSquaresContainer.appendChild(square);

    square.addEventListener("click", () => {
      const beatmaps = pack.beatmaps.map(b => b.beatmap_id);
      showModal(beatmaps, pack.beatmaps, square, pack.packName, true);
    });

    // Tooltip logic
  square.addEventListener("mousemove", (e) => {
    tooltip.classList.remove("hidden");
    tooltip.textContent = square.dataset.tooltip;

    const tooltipWidth = tooltip.offsetWidth;
    const tooltipHeight = tooltip.offsetHeight;
    const padding = 10;
    const pageWidth = window.innerWidth;
    const pageHeight = window.innerHeight;

    let left = e.pageX + padding;
    let top = e.pageY + padding;

    if (left + tooltipWidth > pageWidth) {
      left = e.pageX - tooltipWidth - padding;
    }

    if (top + tooltipHeight > pageHeight) {
      top = e.pageY - tooltipHeight - padding;
    }

    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  });

    square.addEventListener("mouseleave", () => {
      tooltip.classList.add("hidden");
    });
  });

  const modal = document.getElementById("beatmap-modal");
  const beatmapList = document.getElementById("beatmap-list");
  const closeModalBtn = document.querySelector(".close-btn");

  function showModal(beatmaps, fullBeatmapData, squareElement, packName, isStandard = true) {
    beatmapList.innerHTML = "";

    beatmaps.forEach(id => {
      const beatmapData = fullBeatmapData.find(b => b.beatmap_id === id);
      const time = beatmapData ? formatTime(beatmapData.time_duration_seconds) : "N/A";
      const beatmapsetId = beatmapData?.beatmapset_id;

      const container = document.createElement("div");
      container.classList.add("beatmap-tile");

      const overlay = document.createElement("div");
      overlay.classList.add("beatmap-overlay");

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = beatmapIds.has(id);
      checkbox.classList.add("beatmap-tile-checkbox");

      const label = document.createElement("div");
      label.classList.add("beatmap-label");
      
      //Beatmap Card Content such
      if (beatmapData) {
        const idSpan = document.createElement("span");
        idSpan.textContent = ` ${beatmapData.title} [${beatmapData.version}] - ${time}`;
        if (beatmapData.star_rating) {
          idSpan.textContent += ` (${parseFloat(beatmapData.star_rating).toFixed(2)}★)`;
        }
        
        const copyLink = document.createElement("span");
        copyLink.textContent = `${id}`;
        copyLink.style.color = "#03A9F4";
        copyLink.style.textDecoration = "underline";
        copyLink.style.cursor = "pointer";
        copyLink.title = "Click to copy ID";
        copyLink.addEventListener("click", (e) => {
          e.stopPropagation();
          e.preventDefault();
          navigator.clipboard.writeText(id);
          copyLink.textContent = "Copied!";
          setTimeout(() => (copyLink.textContent = `${id}`), 1000);
        });

        const playBtn = document.createElement("span");
        playBtn.textContent = "▶️";
        playBtn.classList.add("preview-toggle");
        playBtn.title = "Play preview";

        const audio = document.getElementById("preview-player");
        audio.volume = 0.1;

        playBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          e.preventDefault();

          const src = `https://b.ppy.sh/preview/${beatmapsetId}.mp3`;
          const isSame = audio.src === src;
          const isPaused = audio.paused;

          // Reset all buttons
          document.querySelectorAll(".preview-toggle").forEach(btn => {
            btn.textContent = "▶️";
          });

          // Detach old onended
          audio.onended = null;

          if (!isPaused && isSame) {
            fadeOutAudio(audio, () => {
              playBtn.textContent = "▶️";
            });
          } else {
            audio.src = src;
            audio.play().then(() => {
              playBtn.textContent = "⏸️";
              fadeInAudio(audio);

              // Reset icon when audio ends
              audio.onended = () => {
                playBtn.textContent = "▶️";
              };
            }).catch(err => {
              console.error("Preview play error:", err);
            });
          }
        });

        function fadeInAudio(audio, targetVolume = 0.1, step = 0.01, interval = 30) {
          audio.volume = 0;
          const fade = setInterval(() => {
            if (audio.volume < targetVolume) {
              audio.volume = Math.min(audio.volume + step, targetVolume);
            } else {
              clearInterval(fade);
            }
          }, interval);
        }

        function fadeOutAudio(audio, onDone, step = 0.01, interval = 30) {
          const fade = setInterval(() => {
            if (audio.volume > step) {
              audio.volume = Math.max(audio.volume - step, 0);
            } else {
              clearInterval(fade);
              audio.pause();
              audio.currentTime = 0;
              if (onDone) onDone();
            }
          }, interval);
        }



        label.appendChild(playBtn);
        label.appendChild(copyLink);
        label.appendChild(idSpan);
      } else {
        label.textContent = `${id} - ${time}`;
      }

      label.style.color = checkbox.checked ? "#4CAF50" : "#F44336";

      checkbox.addEventListener("change", () => {
        if (isStandard) {
          if (checkbox.checked) {
            beatmapIds.add(id);
          } else {
            beatmapIds.delete(id);
          }

          updateSquareColor(squareElement, fullBeatmapData);
          updateCompletionText();
          updateSquareTooltip(squareElement, packName, fullBeatmapData);
          updateCompletedPackCount();
          updateStandardPackCompletionStats();
        } else {
          // ⚠️ FIX: ensure beatmapIds is still updated for tracking
          if (checkbox.checked) {
            beatmapIds.add(id);
          } else {
            beatmapIds.delete(id);
          }

          updateSquareColor(squareElement, fullBeatmapData);
          updateSquareTooltip(squareElement, packName, fullBeatmapData);
          updateOtherPackCompletionStats(otherPacks);
        }

        label.style.color = checkbox.checked ? "#4CAF50" : "#F44336";
      });


      overlay.appendChild(checkbox);
      overlay.appendChild(label);
      container.appendChild(overlay);

      const coverUrl = beatmapsetId
        ? `https://assets.ppy.sh/beatmaps/${beatmapsetId}/covers/cover.jpg`
        : "default_cover.jpg";

      const img = new Image();
      img.onload = () => {
        container.style.backgroundImage = `url('${coverUrl}')`;
      };
      img.onerror = () => {
        container.style.backgroundImage = "url('images/default_cover.jpg')";
      };
      img.src = coverUrl;

      const tileLink = document.createElement("a");
      tileLink.href = `https://osu.ppy.sh/b/${id}`;
      tileLink.target = "_blank";
      tileLink.rel = "noopener noreferrer";
      tileLink.style.textDecoration = "none";
      tileLink.appendChild(container);

      beatmapList.appendChild(tileLink);
    });

    beatmapList.scrollTop = 0;
    modal.classList.remove("hidden");
  }

  closeModalBtn.addEventListener("click", () => {
    modal.classList.add("hidden");

    // Stop preview audio if playing
    const audio = document.getElementById("preview-player");
    if (!audio.paused) {
      audio.pause();
      audio.currentTime = 0;
    }

    // Reset all preview buttons to ▶️
    document.querySelectorAll(".preview-toggle").forEach(btn => {
      btn.textContent = "▶️";
    });
  });
  window.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.add("hidden");

      // Stop preview audio if playing
      const audio = document.getElementById("preview-player");
      if (!audio.paused) {
        audio.pause();
        audio.currentTime = 0;
      }

      // Reset all preview buttons to ▶️
      document.querySelectorAll(".preview-toggle").forEach(btn => {
        btn.textContent = "▶️";
      });
    }
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

  function updateSquareTooltip(square, packName, beatmaps) {
    const total = beatmaps.length;
    const matched = beatmaps.filter(b => beatmapIds.has(b.beatmap_id)).length;
    const percent = total > 0 ? ((matched / total) * 100).toFixed(1) : 0;

    square.dataset.tooltip = `${packName} (osu! Beatmap Pack #${packName.replace("S", "")})
Completion: ${percent}%
${matched} / ${total}`;
  }

  function updateAllSquares() {
    document.querySelectorAll(".square").forEach(square => {
      const beatmapIdsArray = square.dataset.beatmaps.split(",").map(Number);
      const beatmaps = beatmapIdsArray.map(id => ({ beatmap_id: id }));
      updateSquareColor(square, beatmaps);

      const packName = square.dataset.tooltip?.split(" ")[0] || "S?";
      updateSquareTooltip(square, packName, beatmaps);
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

  const searchForm = document.querySelector(".search-form");
  const avatarImage = document.querySelector(".profile-avatar");
  const usernameElement = document.querySelector(".profile-info h2");
  const rankedScoreElement = document.querySelector(".profile-info p:nth-of-type(1)");
  const globalRankElement = document.querySelector(".profile-info p:nth-of-type(2)");
  const rankLineElement = document.querySelector(".rank-counts");

  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    let inputValue = input.value.trim();
    let matchedUser = usersList.find(u =>
      u.id.toString() === inputValue || u.username.toLowerCase() === inputValue.toLowerCase()
    );

    if (!matchedUser) {
      statusDisplay.textContent = "User not found.";
      return;
    }

    const userId = matchedUser.id.toString();
    currentUserId = userId;
    if (!userId) return;

    currentUserId = userId;
    avatarImage.src = `https://a.akatsuki.gg/${userId}.png`;
    avatarImage.onerror = () => avatarImage.src = "default.png";

    try {
      const profileRes = await fetch(`/api/user?id=${userId}`);
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
        autoLoadBeatmapFile(`data/${userId}_scores.txt`);
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

  importFileInput.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async function (e) {
      const content = e.target.result;
      lastLoadedScoreFileContent = content;

      beatmapIds.clear();
      const lines = content.split('\n').map(line => line.trim());

      const beatmapIdLines = lines.filter(line => /^\d+$/.test(line)).map(Number);
      beatmapIdLines.forEach(id => beatmapIds.add(id));

      updateAllSquares();
      updateCompletionText();
      updateCompletedPackCount();
      updateOtherPackCompletionStats(otherPacks);

      // Extract user ID from filename
      const idFromFilename = file.name.match(/^(\d+)_((scores|export))\.txt$/)?.[1];
      if (!idFromFilename) {
        statusDisplay.textContent = "Could not determine user ID from filename.";
        return;
      }

      const userId = idFromFilename;
      currentUserId = userId;

      // Load local users list if not already loaded
      if (!usersList.length) {
        const res = await fetch("users.json");
        usersList = await res.json();
      }

      // Find user locally
      const user = usersList.find(u => u.id.toString() === userId);
      if (user) {
        avatarImage.src = `https://a.akatsuki.gg/${user.id}.png`;
        avatarImage.onerror = () => avatarImage.src = "default.png";
        usernameElement.textContent = user.username;
      } else {
        usernameElement.textContent = "Unknown User";
      }

      // Fetch detailed stats from Akatsuki API
      try {
        const profileRes = await fetch(`https://akatsuki.gg/api/v1/users/full?id=${userId}`);
        const profileData = await profileRes.json();

        if (profileData?.username) {
          const stdStats = profileData.stats[1]?.std;
          if (stdStats) {
            rankedScoreElement.textContent = `Ranked Score: ${stdStats.ranked_score.toLocaleString()}`;
            globalRankElement.textContent = `Global Rank: ${stdStats.global_leaderboard_rank ? `#${stdStats.global_leaderboard_rank}` : "#?"}`;
          } else {
            rankedScoreElement.textContent = "Ranked Score: 0";
            globalRankElement.textContent = "Global Rank: #?";
          }
        } else {
          rankedScoreElement.textContent = "Ranked Score: 0";
          globalRankElement.textContent = "Global Rank: #?";
        }
      } catch (err) {
        console.error("Failed to fetch user stats:", err);
        rankedScoreElement.textContent = "Ranked Score: 0";
        globalRankElement.textContent = "Global Rank: #?";
      }

      // Try to show rank breakdown from file if present
      const rankLine = lines.find(line =>
        line.includes("SSH:") && line.includes("SH:") && line.includes("SS:")
      );
      if (rankLine) {
        const rankCounts = {};
        ["SSH", "SH", "SS", "S", "A", "B", "C", "D"].forEach(rank => {
          const match = rankLine.match(new RegExp(`\\b${rank}:\\s*(\\d+)\\b`));
          rankCounts[rank] = match ? parseInt(match[1]) : 0;
        });

        document.getElementById("ssh-count").textContent = rankCounts.SSH;
        document.getElementById("sh-count").textContent = rankCounts.SH;
        document.getElementById("ss-count").textContent = rankCounts.SS;
        document.getElementById("s-count").textContent = rankCounts.S;
        document.getElementById("a-count").textContent = rankCounts.A;
        document.getElementById("b-count").textContent = rankCounts.B;
        document.getElementById("c-count").textContent = rankCounts.C;
        document.getElementById("d-count").textContent = rankCounts.D;
      }
    
      statusDisplay.textContent = `Imported ${beatmapIdLines.length} beatmaps from ${file.name}`;
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
      updateCompletedPackCount();
      updateOtherPackCompletionStats(otherPacks);

      const rankLine = lines.find(line =>
        line.includes("SSH:") && line.includes("SH:") && line.includes("SS:")
      );
      if (rankLine) {
        const rankCounts = {};
        ["SSH", "SH", "SS", "S", "A", "B", "C", "D"].forEach(rank => {
          const match = rankLine.match(new RegExp(`\\b${rank}:\\s*(\\d+)\\b`));
          rankCounts[rank] = match ? parseInt(match[1]) : 0;
        });

        document.getElementById("ssh-count").textContent = rankCounts.SSH;
        document.getElementById("sh-count").textContent = rankCounts.SH;
        document.getElementById("ss-count").textContent = rankCounts.SS;
        document.getElementById("s-count").textContent = rankCounts.S;
        document.getElementById("a-count").textContent = rankCounts.A;
        document.getElementById("b-count").textContent = rankCounts.B;
        document.getElementById("c-count").textContent = rankCounts.C;
        document.getElementById("d-count").textContent = rankCounts.D;
      }

      statusDisplay.textContent = `Auto-loaded ${beatmapIdLines.length} beatmaps from ${filename}`;
    } catch (err) {
      console.error("Auto-load failed:", err);
      statusDisplay.textContent = `Auto-load failed: ${filename}`;
    }
  }

  setInterval(() => {
    if (currentUserId) {
      autoLoadBeatmapFile(`data/${currentUserId}_scores.txt`);
    }
  }, 1000000);

  const exportButton = document.getElementById("export-button");

  exportButton.addEventListener("click", () => {
    const squares = document.querySelectorAll(".square");
    const packGroups = {};

    squares.forEach(square => {
      const packNameMatch = square.dataset.tooltip?.match(/^(\S+)/); // Get the pack name like "S1"
      const packName = packNameMatch ? packNameMatch[1] : "Unknown Pack";

      const beatmapIdsInPack = square.dataset.beatmaps
        .split(",")
        .map(id => parseInt(id.trim(), 10))
        .filter(id => !beatmapIds.has(id)); // only UNCLEARED beatmaps

      if (beatmapIdsInPack.length > 0) {
        packGroups[packName] = beatmapIdsInPack;
      }
    });

    let exportText = "";
    for (const [pack, ids] of Object.entries(packGroups)) {
      exportText += `${pack}\n`;
      exportText += `${ids.join(",")}\n\n`;
    }

    if (!exportText.trim()) {
      statusDisplay.textContent = "No unchecked beatmaps to export.";
      return;
    }

    const blob = new Blob([exportText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = `${currentUserId || "unchecked"}_beatmaps.txt`;
    a.click();

    URL.revokeObjectURL(url);
    statusDisplay.textContent = "Unchecked beatmaps exported.";
  });
});
