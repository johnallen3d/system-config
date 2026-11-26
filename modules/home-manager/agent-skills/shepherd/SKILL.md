---
name: shepherd
description: Spawn child tasks, guide them to merge, then deploy.
---

# Shepherd work through child tasks

You coordinate. Child tasks do the implementation. When John asks you to
shepherd, that authorizes the steps below, including telling children to
`/wrap` and running the final `system-config` deployment.

1. **Plan.** Split the work into one task per project or independent change.
   Create a card for each one in that project's tracker.
2. **Spawn.** Start one Switchyard child task per card with `spawn_task`,
   passing your `parent_block` (or `parent_url`) so it reports back. In the
   first prompt, give the card, the goal, the scope, and anything it depends
   on. Say that you are the coordinator and that it should bring questions to
   you.
3. **Guide.** Wait for notifications instead of polling. Use `read_task` to
   see where a child stands. Answer with `message_task`. Make the calls you
   can make yourself, and bring only real decisions to John. Keep dependent
   tasks in order: a child that needs another child's work waits until that
   work has merged.
4. **Wrap.** When a child's work is done and verified, tell it to `/wrap`.
5. **Confirm.** Make sure each child's commits are merged into `main` and
   pushed, and its card is closed. If anything is blocked, help the child
   unblock it.
6. **Deploy.** When all the work is merged, deploy `system-config`: relock
   any changed inputs, then deploy to every host as its `AGENTS.md`
   describes.
7. **Report.** Tell John it's complete. For each task, give its card, what
   merged, and anything still open. Report deployment status for each host.
