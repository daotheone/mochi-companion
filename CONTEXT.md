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
An ordered sequence of messages between the user and Mochi that can be closed and reopened later.
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
