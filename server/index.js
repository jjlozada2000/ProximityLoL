require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { AccessToken } = require('livekit-server-sdk');

const app = express();
app.use(cors());
app.use(express.json());

// Health check
app.get('/', (req, res) => {
  res.json({ status: 'ProximityLoL signaling server running' });
});

// Token endpoint
// Client sends: { matchId, summonerName }
// Server returns: { token, url }
app.post('/token', async (req, res) => {
  const { matchId, summonerName } = req.body;

  if (!matchId || !summonerName) {
    return res.status(400).json({ error: 'matchId and summonerName are required' });
  }

  try {
    const roomName = `match_${matchId}`;
    const token = new AccessToken(
      process.env.LIVEKIT_API_KEY,
      process.env.LIVEKIT_API_SECRET,
      {
        identity: summonerName,
        ttl: '4h', // Enough for a full game
      }
    );

    token.addGrant({
      roomJoin: true,
      room: roomName,
      canPublish: true,
      canSubscribe: true,
    });

    const jwt = await token.toJwt();

    res.json({
      token: jwt,
      url: process.env.LIVEKIT_URL,
      room: roomName,
    });

  } catch (err) {
    console.error('Token generation failed:', err);
    res.status(500).json({ error: 'Failed to generate token' });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`ProximityLoL server running on port ${PORT}`);
});