const express = require('express');
const fetch = require('node-fetch');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = 3000;

// Serve static files from the current directory
app.use(express.static(path.join(__dirname, '..', 'public')));

// Server data files
app.use('/data', express.static(path.join(__dirname, '..', 'data')));


// Endpoint to fetch Akatsuki user profile data
app.get('/api/user', async (req, res) => {
  const userId = req.query.id;
  if (!userId) return res.status(400).json({ error: 'Missing userId' });

  try {
    const response = await fetch(`https://akatsuki.gg/api/v1/users/full?id=${userId}`);
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error("Failed to fetch user data:", err);
    res.status(500).json({ error: 'Failed to fetch user info' });
  }
});

// Endpoint to run Python script and return ranked scores
app.get('/api/fetch-scores', (req, res) => {
  const userId = req.query.id;
  if (!userId) return res.status(400).json({ error: 'Missing userId' });

  const scriptPath = path.resolve(__dirname, 'fetch_ranked_scores.py');
  const pythonCommand = `python3.13 "${scriptPath}" ${userId}`;
  console.log(`Running: ${pythonCommand}`);

  exec(pythonCommand, (error, stdout, stderr) => {
    if (error) {
      console.error(`Python error: ${stderr}`);
      return res.status(500).json({ error: 'Failed to fetch ranked scores' });
    }

    const filePath = path.join(__dirname, '..', 'data', `${userId}_scores.txt`);
    res.sendFile(filePath);
  });
});

// In-memory cache for packs.json
let cachedPacks = null;

fs.readFile(path.join(__dirname, '..', 'public', 'packs.json'), 'utf8', (err, data) => {
  if (err) {
    console.error('Failed to read packs.json:', err);
  } else {
    cachedPacks = JSON.parse(data);
    console.log('packs.json loaded into memory');
  }
});

app.get('/packs', (req, res) => {
  if (cachedPacks) {
    res.json(cachedPacks);
  } else {
    res.status(503).json({ error: 'packs.json not loaded yet' });
  }
});

// In-memory cache for other_packs.json
let cachedOtherPacks = null;

fs.readFile(path.join(__dirname, '..', 'public', 'other_packs.json'), 'utf8', (err, data) => {
  if (err) {
    console.error('Failed to read other_packs.json:', err);
  } else {
    cachedOtherPacks = JSON.parse(data);
    console.log('other_packs.json loaded into memory');
  }
});

app.get('/other_packs', (req, res) => {
  if (cachedOtherPacks) {
    res.json(cachedOtherPacks);
  } else {
    res.status(503).json({ error: 'other_packs.json not loaded yet' });
  }
});


// Start the server
const server = app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});

// Disable timeout (or set it longer)
server.setTimeout(300000); // 5 minutes
