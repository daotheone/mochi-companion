# Personal AI companion — project brief

I want to build a personal AI companion that feels like a recurring character on my computer. I can talk to it, vent, or work alongside it. It has a recognizable personality, can joke with me in English or Vietnamese, and gradually adapts to what actually helps me start and finish work.

The long-term experience is a small animated character that lives on my screen, similar to the ChatGPT pet as a desktop presence. It can react to what I tell it, notice events inside the app, offer help with a task, and eventually speak. I want the character to have some initiative, such as checking in during a study session I started or reacting when I finish something.

Its coaching style is inspired by the Pygmalion effect. It assumes I can improve and expresses that expectation through specific feedback and realistic next steps. If I’m avoiding a vague Unity task, it might recall that picking one test scene helped before and suggest a ten-minute start. It should distinguish something I told it from a pattern it thinks it has observed.

## Starting point

- Build a single-user Python terminal chat. Use DeepSeek’s hosted `deepseek-flash` as the first chat model and keep the model configurable. (Originally planned as Groq with `qwen/qwen3.8-27b`; switched to DeepSeek during Phase 2.)
- Give the character an editable persona and sample exchanges. Use SQLite for local chat history and, as the app grows, editable memories, tasks, and outcomes. I want to test personality tuning through prompts and examples before deciding whether actual fine-tuning is worth doing.
- The first sprint runs on Linux only. Keep the Python chat logic separate from its interface so the terminal and future desktop character can share it. Use PySide6 for the small animated desktop window when that phase begins. Python can handle the chat and the on-screen character without adding Rust. Test transparent-window placement and always-on-top behavior on my actual Linux desktop, especially if it uses Wayland. Add Windows sync later, then phone sync as a separate phase.
- Keep running costs near zero. A hosted model receives the context sent in each request. Local inference can be considered separately if I want conversations to stay on my machine.

## Build sequence

Terminal chat → personality tuning → desktop character → task tracking → AI task help and bounded initiative → voice.

This is the direction for the project. The separate plan lays out possible milestones so I can decide what to build and discuss the scope with Claude before committing.
