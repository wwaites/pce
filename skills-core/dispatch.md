# Dispatch

Role contracts state Read Scope and Write Scope. This document states how
those scopes stay real at the moment Editor actually invokes a reviewer,
across runtimes with very different capabilities.

## Dispatch Ladder

Three rungs, most isolated first. Use the highest rung the runtime supports
for a given dispatch.

1. **Isolated subagent.** The runtime can spawn a fresh-context subagent with
   a curated initial prompt and a structured return value. Editor composes
   the reviewer's entire initial prompt from only the files its Read Scope
   permits, and reads the reviewer's report from the subagent's return value.
   Nothing from Editor's own conversation, such as prior reviews,
   `sources/internal/**`, or editor-only notes, crosses over except what
   Editor deliberately writes into that prompt.
2. **External process spawn.** The runtime has no subagent primitive but can
   run a program through a bash or exec tool. Editor launches a fresh process
   of the same harness against a scoped workspace, per Workspace Staging
   below, and supplies the reviewer's assignment through its command line, a
   written input file, or stdin. There is no structured return channel: the
   reviewer's report exists only once it is written to the shared workflow
   directory, per the Handoff Rule in `artifacts.md`. Editor discovers
   completion by reading for the expected output file or process exit, not by
   a richer contract the runtime does not offer.
3. **Same-session role assumption.** The runtime can spawn neither a subagent
   nor a fresh process. Editor's own session temporarily behaves as the
   reviewer, applying that role's Read Scope and Rules by discipline alone.
   This is the weakest rung: the reviewer's fresh context is aspirational,
   since the session transcript already contains everything Editor read.
   Prefer escalating the runtime to rung 1 or rung 2 over treating rung 3 as
   an equal option; rely on the Contamination Protocol below as the backstop
   when rung 3 is the only one available.

## Workspace Staging

Fresh context, at rung 1 or rung 2, prevents the dispatcher's own
conversation from leaking into the reviewer. It does not prevent the reviewer
from using its own file-read tool to open something outside its Read Scope,
if the reviewer can see the whole project tree. No target runtime offers a
portable, path-scoped permission system to close that gap, so close it
structurally instead.

Before dispatching a reviewer at rung 1 or rung 2, Editor stages a scratch
directory containing only the files that reviewer's Read Scope names, such as
copies of `brief.md`, `drafts/current.md`, `sources/external/**` when
permitted, and `state.json`, and nothing else. Editor runs the reviewer with
that directory as its entire visible root, not the project root. A reviewer
given a real file-read tool can inspect its own root freely; it can only find
what Editor staged there. Editor discards the scratch directory once the
reviewer's report is written back to the real workflow directory.

Workspace staging is required at rung 1 and rung 2 whenever the reviewer's
own tools are not otherwise scoped to its Read Scope by the runtime. Where a
runtime does offer its own path-scoped permission mechanism, staging is
redundant but harmless. Do not rely on the runtime mechanism alone, since it
is not present on every target runtime.

## Contamination Protocol

A reviewer that finds material outside its Read Scope in its own context,
whether staging missed a file, rung 3 carried the whole prior transcript, or
by any other route, does not use it. It stops, writes a `contaminated`
verdict instead of its normal review output, and names what it saw. Editor
discards that review, corrects the staging or dispatch that caused the leak,
and redispatches the same reviewer fresh. A contaminated review is never
revised into a clean one; it is void.
