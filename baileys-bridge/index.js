/**
 * Baileys Bridge — WhatsApp Web sidecar for Open Assistant.
 *
 * Exposes a REST API that the Python app calls to send messages, media,
 * reactions, etc.  Inbound messages are forwarded to a configurable
 * callback URL (the Python webhook).
 *
 * Auth: QR code printed to terminal on first run; session persisted to disk.
 */

import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import express from "express";
import fs from "fs";
import pino from "pino";
import qrcode from "qrcode-terminal";

// ── Config ──────────────────────────────────────────────────────────────────
const PORT = parseInt(process.env.BAILEYS_PORT || "3100", 10);
const CALLBACK_URL = process.env.BAILEYS_CALLBACK_URL || "http://localhost:8080/webhook/whatsapp/baileys";
const AUTH_DIR = process.env.BAILEYS_AUTH_DIR || "./auth_state";
const ACK_MESSAGE = process.env.BAILEYS_ACK_MESSAGE || "";

const logger = pino({ level: process.env.LOG_LEVEL || "warn" });

// ── WhatsApp connection ─────────────────────────────────────────────────────
let sock = null;

async function connectWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    logger,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    printQRInTerminal: false,
    generateHighQualityLinkPreview: true,
  });

  // QR code for linking
  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log("\n╔══════════════════════════════════════╗");
      console.log("║   Scan this QR code with WhatsApp   ║");
      console.log("╚══════════════════════════════════════╝\n");
      qrcode.generate(qr, { small: true });
    }

    if (connection === "close") {
      const code = lastDisconnect?.error?.output?.statusCode;
      if (code !== DisconnectReason.loggedOut) {
        console.log("Connection lost, reconnecting...");
        connectWhatsApp();
      } else {
        console.log("Logged out. Delete auth_state and restart to re-link.");
      }
    }

    if (connection === "open") {
      console.log("WhatsApp connected!");
    }
  });

  sock.ev.on("creds.update", saveCreds);

  // ── Inbound messages → forward to Python ────────────────────────────────
  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      if (msg.key.fromMe) continue;

      // Instant ack message (like WhatsApp Ultimate's ackMessage)
      if (ACK_MESSAGE && !msg.key.remoteJid.endsWith("@g.us")) {
        try {
          await sock.sendMessage(msg.key.remoteJid, { text: ACK_MESSAGE });
        } catch (e) {
          console.error("ack message failed:", e.message);
        }
      }

      const payload = {
        id: msg.key.id,
        from: msg.key.remoteJid,
        participant: msg.key.participant || null,
        pushName: msg.pushName || null,
        timestamp: msg.messageTimestamp,
        type: detectMessageType(msg),
        text: extractText(msg),
        media: extractMediaInfo(msg),
        quotedMessage: msg.message?.extendedTextMessage?.contextInfo?.quotedMessage
          ? { id: msg.message.extendedTextMessage.contextInfo.stanzaId }
          : null,
        raw: msg,
      };

      // Forward to Python callback
      try {
        await fetch(CALLBACK_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } catch (e) {
        console.error("Failed to forward message to callback:", e.message);
      }
    }
  });
}

function detectMessageType(msg) {
  const m = msg.message;
  if (!m) return "unknown";
  if (m.conversation || m.extendedTextMessage) return "text";
  if (m.imageMessage) return "image";
  if (m.videoMessage) return "video";
  if (m.audioMessage) return m.audioMessage.ptt ? "voice" : "audio";
  if (m.documentMessage) return "document";
  if (m.stickerMessage) return "sticker";
  if (m.pollCreationMessage || m.pollCreationMessageV3) return "poll";
  if (m.reactionMessage) return "reaction";
  return "unknown";
}

function extractText(msg) {
  const m = msg.message;
  if (!m) return null;
  return m.conversation || m.extendedTextMessage?.text || m.imageMessage?.caption || m.videoMessage?.caption || null;
}

function extractMediaInfo(msg) {
  const m = msg.message;
  if (!m) return null;
  for (const key of ["imageMessage", "videoMessage", "audioMessage", "documentMessage", "stickerMessage"]) {
    if (m[key]) {
      return {
        type: key.replace("Message", ""),
        mimetype: m[key].mimetype,
        fileLength: m[key].fileLength,
        fileName: m[key].fileName || null,
      };
    }
  }
  return null;
}

// ── REST API ────────────────────────────────────────────────────────────────
const app = express();
app.use(express.json({ limit: "50mb" }));

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: sock ? "connected" : "disconnected" });
});

// Send text message
app.post("/send/text", async (req, res) => {
  try {
    const { to, message, quotedId } = req.body;
    const jid = toJid(to);
    const opts = {};
    if (quotedId) {
      opts.quoted = { key: { remoteJid: jid, id: quotedId } };
    }
    const result = await sock.sendMessage(jid, { text: message }, opts);
    res.json({ success: true, id: result.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Send media (image, video, document, audio)
app.post("/send/media", async (req, res) => {
  try {
    const { to, filePath, caption, mimetype, asVoice, gifPlayback } = req.body;
    const jid = toJid(to);
    const buffer = fs.readFileSync(filePath);
    const ext = filePath.split(".").pop().toLowerCase();

    let msg = {};
    if (["jpg", "jpeg", "png", "webp"].includes(ext) && !gifPlayback) {
      msg = { image: buffer, caption, mimetype: mimetype || `image/${ext === "jpg" ? "jpeg" : ext}` };
    } else if (["mp4", "avi", "mkv"].includes(ext) || gifPlayback) {
      msg = { video: buffer, caption, mimetype: mimetype || "video/mp4", gifPlayback: !!gifPlayback };
    } else if (["ogg", "mp3", "wav", "m4a"].includes(ext) || asVoice) {
      msg = { audio: buffer, mimetype: mimetype || "audio/ogg; codecs=opus", ptt: !!asVoice };
    } else {
      msg = { document: buffer, mimetype: mimetype || "application/octet-stream", fileName: filePath.split("/").pop() };
    }

    const result = await sock.sendMessage(jid, msg);
    res.json({ success: true, id: result.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Send sticker
app.post("/send/sticker", async (req, res) => {
  try {
    const { to, filePath } = req.body;
    const buffer = fs.readFileSync(filePath);
    const result = await sock.sendMessage(toJid(to), { sticker: buffer });
    res.json({ success: true, id: result.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Send poll
app.post("/send/poll", async (req, res) => {
  try {
    const { to, question, options, selectableCount } = req.body;
    const result = await sock.sendMessage(toJid(to), {
      poll: { name: question, values: options, selectableCount: selectableCount || 0 },
    });
    res.json({ success: true, id: result.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// React to a message
app.post("/react", async (req, res) => {
  try {
    const { chatJid, messageId, emoji, remove } = req.body;
    const result = await sock.sendMessage(chatJid, {
      react: { text: remove ? "" : emoji, key: { remoteJid: chatJid, id: messageId } },
    });
    res.json({ success: true, id: result.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Edit a message
app.post("/edit", async (req, res) => {
  try {
    const { chatJid, messageId, message } = req.body;
    const key = { remoteJid: chatJid, id: messageId, fromMe: true };
    const result = await sock.sendMessage(chatJid, { text: message, edit: key });
    res.json({ success: true, id: result.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Unsend / delete a message
app.post("/unsend", async (req, res) => {
  try {
    const { chatJid, messageId } = req.body;
    const key = { remoteJid: chatJid, id: messageId, fromMe: true };
    const result = await sock.sendMessage(chatJid, { delete: key });
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Group management ────────────────────────────────────────────────────────

app.post("/group/create", async (req, res) => {
  try {
    const { name, participants } = req.body;
    const jids = participants.map(toJid);
    const result = await sock.groupCreate(name, jids);
    res.json({ success: true, groupId: result.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/group/rename", async (req, res) => {
  try {
    const { groupId, name } = req.body;
    await sock.groupUpdateSubject(groupId, name);
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/group/description", async (req, res) => {
  try {
    const { groupId, description } = req.body;
    await sock.groupUpdateDescription(groupId, description);
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/group/participants", async (req, res) => {
  try {
    const { groupId, participants, action } = req.body;
    const jids = participants.map(toJid);
    // action: "add" | "remove" | "promote" | "demote"
    const result = await sock.groupParticipantsUpdate(groupId, jids, action);
    res.json({ success: true, result });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/group/invite-code", async (req, res) => {
  try {
    const { groupId } = req.body;
    const code = await sock.groupInviteCode(groupId);
    res.json({ success: true, link: `https://chat.whatsapp.com/${code}` });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/group/revoke-invite", async (req, res) => {
  try {
    const { groupId } = req.body;
    const code = await sock.groupRevokeInvite(groupId);
    res.json({ success: true, link: `https://chat.whatsapp.com/${code}` });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/group/info/:groupId", async (req, res) => {
  try {
    const info = await sock.groupMetadata(req.params.groupId);
    res.json({ success: true, info });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/group/leave", async (req, res) => {
  try {
    const { groupId } = req.body;
    await sock.groupLeave(groupId);
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/group/icon", async (req, res) => {
  try {
    const { groupId, filePath } = req.body;
    const buffer = fs.readFileSync(filePath);
    await sock.updateProfilePicture(groupId, buffer);
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Helpers ─────────────────────────────────────────────────────────────────

function toJid(input) {
  if (!input) throw new Error("recipient is required");
  if (input.includes("@")) return input;
  // Strip leading + and spaces
  const num = input.replace(/[+\s-]/g, "");
  return `${num}@s.whatsapp.net`;
}

// ── Start ───────────────────────────────────────────────────────────────────
connectWhatsApp();
app.listen(PORT, () => {
  console.log(`Baileys bridge listening on port ${PORT}`);
});
