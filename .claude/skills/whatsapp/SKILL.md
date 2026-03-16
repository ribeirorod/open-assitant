---
name: whatsapp
description: Send and receive WhatsApp messages, media, polls, reactions, and manage groups via the Baileys bridge. Use when the user mentions WhatsApp, wants to message someone, or manage WhatsApp groups.
---

# WhatsApp — Baileys Bridge

Full WhatsApp capability via direct WhatsApp Web protocol (Baileys).
The bridge runs at `http://localhost:3100`. Use `curl` via Bash to call it.

## JID Formats

| Type | Format | Example |
|------|--------|---------|
| Individual | `<number>@s.whatsapp.net` | `34612345678@s.whatsapp.net` |
| Group | `<id>@g.us` | `120363012345678901@g.us` |

The `to` field auto-converts phone numbers like `+34612345678` to JIDs.
For reactions/edit/unsend, use the full JID.

---

## Messaging

### Send Text
```bash
curl -s -X POST http://localhost:3100/send/text \
  -H 'Content-Type: application/json' \
  -d '{"to": "+34612345678", "message": "Hello!"}'
```

### Reply / Quote a Message
```bash
curl -s -X POST http://localhost:3100/send/text \
  -H 'Content-Type: application/json' \
  -d '{"to": "+34612345678", "message": "Replying!", "quotedId": "MSG_ID_HERE"}'
```

### Send Image / Video / Document
```bash
curl -s -X POST http://localhost:3100/send/media \
  -H 'Content-Type: application/json' \
  -d '{"to": "+34612345678", "filePath": "/path/to/photo.jpg", "caption": "Check this out"}'
```
Supported: JPG, PNG, MP4, PDF, DOC, any file type.

### Send Voice Note
```bash
curl -s -X POST http://localhost:3100/send/media \
  -H 'Content-Type: application/json' \
  -d '{"to": "+34612345678", "filePath": "/path/to/audio.ogg", "asVoice": true}'
```
**Critical:** Voice notes MUST be OGG/Opus format. Convert first:
```bash
ffmpeg -i input.wav -c:a libopus -b:a 64k output.ogg
```

### Send GIF
```bash
curl -s -X POST http://localhost:3100/send/media \
  -H 'Content-Type: application/json' \
  -d '{"to": "+34612345678", "filePath": "/path/to/animation.mp4", "gifPlayback": true}'
```
WhatsApp requires MP4 for GIFs. Convert first:
```bash
ffmpeg -i input.gif -movflags faststart -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" output.mp4 -y
```

### Send Sticker
```bash
curl -s -X POST http://localhost:3100/send/sticker \
  -H 'Content-Type: application/json' \
  -d '{"to": "+34612345678", "filePath": "/path/to/sticker.webp"}'
```
Must be WebP format, ideally 512×512. Convert:
```bash
ffmpeg -i input.png -vf "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000" output.webp
```

### Send Poll
```bash
curl -s -X POST http://localhost:3100/send/poll \
  -H 'Content-Type: application/json' \
  -d '{"to": "+34612345678", "question": "What time works?", "options": ["3pm", "4pm", "5pm"], "selectableCount": 1}'
```
`selectableCount`: 0 = multi-select, 1+ = limited select.

---

## Interactions

### React to a Message
```bash
curl -s -X POST http://localhost:3100/react \
  -H 'Content-Type: application/json' \
  -d '{"chatJid": "34612345678@s.whatsapp.net", "messageId": "MSG_ID", "emoji": "🚀"}'
```

### Remove a Reaction
```bash
curl -s -X POST http://localhost:3100/react \
  -H 'Content-Type: application/json' \
  -d '{"chatJid": "34612345678@s.whatsapp.net", "messageId": "MSG_ID", "remove": true}'
```

### Edit a Sent Message (Own Messages Only)
```bash
curl -s -X POST http://localhost:3100/edit \
  -H 'Content-Type: application/json' \
  -d '{"chatJid": "34612345678@s.whatsapp.net", "messageId": "MSG_ID", "message": "Updated text"}'
```

### Unsend / Delete a Message
```bash
curl -s -X POST http://localhost:3100/unsend \
  -H 'Content-Type: application/json' \
  -d '{"chatJid": "34612345678@s.whatsapp.net", "messageId": "MSG_ID"}'
```

---

## Group Management

### Create Group
```bash
curl -s -X POST http://localhost:3100/group/create \
  -H 'Content-Type: application/json' \
  -d '{"name": "Project Team", "participants": ["+34612345678", "+34687654321"]}'
```

### Rename Group
```bash
curl -s -X POST http://localhost:3100/group/rename \
  -H 'Content-Type: application/json' \
  -d '{"groupId": "120363012345678901@g.us", "name": "New Name"}'
```

### Set Group Description
```bash
curl -s -X POST http://localhost:3100/group/description \
  -H 'Content-Type: application/json' \
  -d '{"groupId": "120363012345678901@g.us", "description": "Team chat for Q1"}'
```

### Set Group Icon
```bash
curl -s -X POST http://localhost:3100/group/icon \
  -H 'Content-Type: application/json' \
  -d '{"groupId": "120363012345678901@g.us", "filePath": "/path/to/icon.jpg"}'
```

### Add / Remove / Promote / Demote Participants
```bash
curl -s -X POST http://localhost:3100/group/participants \
  -H 'Content-Type: application/json' \
  -d '{"groupId": "120363012345678901@g.us", "participants": ["+34612345678"], "action": "add"}'
```
Actions: `add`, `remove`, `promote`, `demote`

### Get Invite Link
```bash
curl -s -X POST http://localhost:3100/group/invite-code \
  -H 'Content-Type: application/json' \
  -d '{"groupId": "120363012345678901@g.us"}'
```

### Revoke Invite Link
```bash
curl -s -X POST http://localhost:3100/group/revoke-invite \
  -H 'Content-Type: application/json' \
  -d '{"groupId": "120363012345678901@g.us"}'
```

### Get Group Info
```bash
curl -s http://localhost:3100/group/info/120363012345678901@g.us
```
Returns: name, description, participants, admins, creation date.

### Leave Group
```bash
curl -s -X POST http://localhost:3100/group/leave \
  -H 'Content-Type: application/json' \
  -d '{"groupId": "120363012345678901@g.us"}'
```

---

## Confirmation

Always confirm before: sending messages to new contacts, unsending messages, removing participants, leaving groups, revoking invite links. One sentence: "Ready — confirm?"

## Rate Limits

WhatsApp has anti-spam measures. Never:
- Bulk-message many contacts
- Rapid-fire messages
- Message contacts who haven't messaged first

## Message IDs

Needed for reactions, edit, unsend. Inbound messages include the ID in the event payload. Sent message responses return the ID in `{"success": true, "id": "..."}`.

## Media Format Reference

| Type | Format | Notes |
|------|--------|-------|
| Voice note | OGG/Opus | `ffmpeg -i input.wav -c:a libopus -b:a 64k output.ogg` |
| Sticker | WebP 512×512 | `ffmpeg -i input.png -vf "scale=512:512:..." output.webp` |
| GIF | MP4 | `ffmpeg -i input.gif -movflags faststart ... output.mp4` |
| Image | JPG/PNG | Native support |
| Video | MP4 | Native support |
| Document | Any | Sent as file attachment |
