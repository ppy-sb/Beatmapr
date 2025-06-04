document.addEventListener("DOMContentLoaded", async () => {
  const USERS_PER_PAGE = 100;
  let currentPage = 1;
  let sortedUsers = [];

  const tbody = document.getElementById("leaderboard-body");
  const prevButton = document.getElementById("prev-page");
  const nextButton = document.getElementById("next-page");
  const pageIndicator = document.getElementById("page-indicator");

  try {
    const response = await fetch("users.json");
    const users = await response.json();

    sortedUsers = users
      .filter(user => typeof user.cleared_beatmaps === "number")
      .sort((a, b) => b.cleared_beatmaps - a.cleared_beatmaps) // descending
      .reverse();

    renderPage(currentPage);
  } catch (err) {
    console.error("Failed to load leaderboard:", err);
  }

  function renderPage(page) {
    tbody.innerHTML = "";

    const start = (page - 1) * USERS_PER_PAGE;
    const end = start + USERS_PER_PAGE;
    const usersToShow = sortedUsers.slice(start, end);

    usersToShow.forEach((user, index) => {
      const tr = document.createElement("tr");

      if (start + index === 0) tr.classList.add("leaderboard-gold");
      else if (start + index === 1) tr.classList.add("leaderboard-silver");
      else if (start + index === 2) tr.classList.add("leaderboard-bronze");

      tr.innerHTML = `
        <td>#${start + index + 1}</td>
        <td>${user.username}</td>
        <td>${user.country}</td>
        <td>${user.cleared_beatmaps.toLocaleString()} (${user.completion_percent?.toFixed(2) || "0.00"}%)</td>
      `;
      tbody.appendChild(tr);
    });

    pageIndicator.textContent = `Page ${currentPage}`;
    prevButton.disabled = currentPage === 1;
    nextButton.disabled = end >= sortedUsers.length;
  }

  prevButton.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      renderPage(currentPage);
    }
  });

  nextButton.addEventListener("click", () => {
    if ((currentPage * USERS_PER_PAGE) < sortedUsers.length) {
      currentPage++;
      renderPage(currentPage);
    }
  });
});
