<template>
  <nav class="navbar">
    <div class="nav-container">
      <div class="nav-links">
        <NuxtLink active-class="nav-button--active" class="nav-button" to="/">Home</NuxtLink>
        <NuxtLink active-class="nav-button--active" class="nav-button" to="/leaderboards">
          Leaderboards</NuxtLink>
      </div>
      <slot />
    </div>
  </nav>
</template>