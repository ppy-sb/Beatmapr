<template>
  <NavBar />
  <main class="container">
    <section class="hero">
      <div class="hero-inner">
        <h1>Beatmapr</h1>
        <p class="tagline">
          Fetch your relax scores from Akatsuki and match them against official bancho beatmap packs.
        </p>
        <p class="description">
          Visualize your progress toward full pack completion, discover which maps are missing, and track leaderboard
          metadata.
        </p>
        <div class="actions">
          <router-link to="/users/16625" class="btn primary">Explore Beatmapr</router-link>
          <a href="https://github.com/ppy-sb/Beatmapr" target="_blank" rel="noopener" class="btn">GitHub</a>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
definePageMeta({
  title: 'Beatmapr - Track your relax scores and beatmap pack progress',
})
</script>

<style scoped>
:root {
  --bg: #071028;
  --card: #0b1930;
  --muted: #9fb0c8;
  --text: #e6f0fb;
  --accent-from: #06b6d4;
  --accent-to: #0ea5e9;
  --muted-2: #7f98ad;
}

.container {
  padding: 28px;
  max-width: 980px;
  margin: 0 auto;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
  color: var(--text);
  background: var(--bg);
  min-height: calc(100vh - 56px);
}

.hero {
  background: linear-gradient(90deg, rgba(8, 18, 34, 0.8), rgba(11, 25, 48, 0.95));
  padding: 28px;
  border-radius: 10px;
  box-shadow: 0 6px 22px rgba(2, 6, 23, 0.6);
  margin-bottom: 20px;
  border: 1px solid rgba(255, 255, 255, 0.03);
}

.hero h1 {
  margin: 0 0 8px;
  font-size: 30px;
  letter-spacing: -0.5px;
  color: var(--text);
}

.tagline {
  margin: 0 0 10px;
  color: var(--text);
  font-weight: 600;
}

.description {
  margin: 0 0 14px;
  color: var(--muted);
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.btn {
  display: inline-block;
  padding: 10px 14px;
  border-radius: 8px;
  text-decoration: none;
  color: var(--text);
  background: rgba(255, 255, 255, 0.03);
  font-weight: 600;
  font-size: 14px;
  border: 1px solid rgba(255, 255, 255, 0.04);
}

.btn.primary {
  background: linear-gradient(90deg, var(--accent-from), var(--accent-to));
  color: #fff;
  border: none;
  box-shadow: 0 6px 16px rgba(14, 165, 233, 0.12);
}

.features {
  margin: 18px 0;
}

.features h2 {
  margin-bottom: 8px;
  color: var(--text);
}

.features ul {
  margin: 0;
  padding-left: 20px;
  color: var(--muted);
}

.example h2 {
  margin-top: 12px;
  margin-bottom: 8px;
  color: var(--text);
}

.pack-card {
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  max-width: 560px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0.01));
}

.pack-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pack-info .sub {
  color: var(--muted-2);
  font-size: 13px;
}

.percent {
  font-weight: 700;
  color: var(--text);
}

.progress {
  background: rgba(255, 255, 255, 0.03);
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  margin-top: 10px;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-from), var(--accent-to));
  border-radius: 999px;
  box-shadow: 0 4px 10px rgba(6, 182, 212, 0.12) inset;
}

.note {
  color: var(--muted-2);
  margin-top: 10px;
  font-size: 13px;
}
</style>
