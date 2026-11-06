# Mochi Companion

A single-user personal AI companion that acts as a recurring character on the user's computer: chat, venting, and working alongside.

## Language

**Companion**:
The whole system: the core logic plus whichever interface the user talks through.
_Avoid_: bot, assistant, agent

**Mochi**:
The name of the Character the user talks to.
_Avoid_: the AI, the pet

**Persona**:
The editable description of Mochi's personality, plus sample exchanges, that shapes every reply.
_Avoid_: system prompt, prompt, profile

**Character**:
Mochi's on-screen presence as an animated desktop figure.
_Avoid_: avatar, mascot, sprite (sprites are only its art assets)

**Expression**:
The face Mochi shows for one reply, on the Character or the Portrait, chosen by Mochi along with that reply. It is a reaction to the moment, not a lasting mood, and neutral is one of them.
_Avoid_: emotion, mood, feeling, sprite

**Message**:
A single turn from the user or from Mochi inside a Conversation. The raw history is made of Messages, not Memories.
_Avoid_: log entry, chat line

**Memory**:
A selected, editable fact the Companion keeps about the user across Conversations. Always either Stated or Observed.
_Avoid_: history, note, context

**Stated**:
A Memory the user told Mochi directly.
_Avoid_: explicit, confirmed fact

**Observed**:
A Memory Mochi inferred from patterns and that stays tentative until the user confirms it.
_Avoid_: learned, implicit, assumption

**Conversation**:
An ordered sequence of messages between the user and Mochi that can be closed and reopened later. Each one belongs to a single Interface.
_Avoid_: session, chat, thread

**Tag**:
A short label on a Memory used to find it when it is relevant. A Stated Memory gets Tags from the user; an Observed Memory gets Tags proposed by Mochi.
_Avoid_: category, keyword, label

**Confirm**:
The user accepting an Observed Memory, which makes it Stated.
_Avoid_: approve, promote, verify

**Bubble**:
One line of a Mochi Message, shown on its own line. A Message is stored whole and may hold several Bubbles.
_Avoid_: chunk, part, split message

**Core**:
A reserved Tag that keeps a Memory in every prompt, however little room there is.
_Avoid_: pinned, always-on

**Chat Box**:
The small input that appears when the user clicks the Character, for typing a Message.
_Avoid_: chat panel, popup, input bar

**Speech Balloon**:
The balloon beside the Character that shows only Mochi's most recent reply. A Bubble is a line of a Message; a Speech Balloon is where that reply appears.
_Avoid_: chat bubble, tooltip

**Main Window**:
The full UI, opened by double-clicking the Character, that shows the Conversation history.
_Avoid_: chat panel, dashboard, full UI

**Portrait**:
Mochi's face in a corner of the Main Window's Conversation view. It takes the Character's place while the Main Window is open, so Mochi is not on screen twice.
_Avoid_: icon, avatar

**Interface**:
A way of talking to Mochi. The Character is the real app; the terminal exists for testing. Each keeps its own Conversations, and all share the same Memories.
_Avoid_: client, frontend, instance

**Recap**:
A brief, dated summary of a finished Conversation, including whether anything was left unresolved. Unlike a Memory it fades with age and is never edited.
_Avoid_: summary, history, digest
