# Explaining Git Merge Conflicts in Plain English

This guide breaks down the deliberate merge conflict exercise conducted in Task H9 of the Patient FAQ Chatbot project. It explains the mechanics of Git branching, fast-forward merges, 3-way conflicts, conflict markers, and how rebase differs from merge.

---

## 1. What Happened: The Conflict Story

We created two independent feature branches off `dev`:
1. **`feature/prompt-friendly`**: Updated Rule 7 of `prompts/system_prompt.md` to:
   ```markdown
   Rule 7: Keep answers warm, friendly, and under 120 words in empathetic plain language with no medical jargon.
   ```
2. **`feature/prompt-concise`**: Branched from the original `dev` commit and updated the exact same line (Rule 7) to:
   ```markdown
   Rule 7: Keep answers strictly under 80 words, concise, factual, with no filler or medical jargon.
   ```

When we switched back to `dev` and merged `feature/prompt-friendly`, Git executed a **fast-forward merge** because `dev` had not moved since branching.

When we then merged `feature/prompt-concise` into `dev`, Git could not automatically reconcile two divergent edits to the exact same line. Git halted the merge, marked `prompts/system_prompt.md` as conflicted, and inserted conflict markers for manual resolution.

---

## 2. Why the First Merge Succeeded Without Conflict and the Second Failed

### The First Merge (`dev <- feature/prompt-friendly`)
- Before the merge, `feature/prompt-friendly` directly descended from `dev`. `dev` had received zero new commits in the interim.
- Because `feature/prompt-friendly` was a straight, linear continuation of `dev`, Git simply advanced the `dev` branch pointer forward to match `feature/prompt-friendly`.
- This is called a **Fast-Forward Merge**. No files were compared against divergent histories, so a conflict was impossible.

### The Second Merge (`dev <- feature/prompt-concise`)
- By merging `feature/prompt-friendly`, `dev` moved forward by one commit.
- `feature/prompt-concise` was branched from the *older* common ancestor commit, not the new tip of `dev`.
- Both branches modified line 19 of `prompts/system_prompt.md` differently.
- Git’s 3-way merge algorithm compared:
  1. **Base:** Original `dev` (under 120 words, plain language)
  2. **Ours (`HEAD` / Current):** `feature/prompt-friendly` (warm, friendly, under 120 words)
  3. **Theirs (`Incoming`):** `feature/prompt-concise` (strictly under 80 words, concise, factual)
- Because both sides made contradictory changes to the identical line relative to Base, Git stopped and asked a human to choose or synthesize the solution.

---

## 3. What Each Conflict Marker Means

When a merge conflict occurs, Git writes three boundary markers directly into the affected file:

```text
<<<<<<< HEAD
Rule 7: Keep answers warm, friendly, and under 120 words in empathetic plain language with no medical jargon.
=======
Rule 7: Keep answers strictly under 80 words, concise, factual, with no filler or medical jargon.
>>>>>>> feature/prompt-concise
```

1. **`<<<<<<< HEAD` (Current change start):**
   - Marks the start of the conflict.
   - Everything between `<<<<<<< HEAD` and `=======` represents what currently exists on the branch you are standing on (`dev`, which had accepted `feature/prompt-friendly`).
2. **`=======` (Conflict separator):**
   - The dividing line between the two conflicting branches.
3. **`>>>>>>> <branch-name>` (Incoming change end):**
   - Marks the end of the conflict.
   - Everything between `=======` and `>>>>>>> feature/prompt-concise` represents the incoming change you are attempting to merge in.

### How We Resolved It
We took the best of both perspectives (warmth and conciseness) and replaced all markers with a clean synthesis:
```markdown
Rule 7: Keep answers warm, friendly, and concise (under 100 words), using factual, empathetic plain language with no medical jargon.
```

---

## 4. Visualizing the Merge Resolution in VS Code

Below is the 3-way merge editor visualization saved at `docs/screenshots/merge-conflict-resolution.png`:

![Merge Conflict Resolution in VS Code](screenshots/merge-conflict-resolution.png)

---

## 5. What Would a Rebase Have Done Differently?

If we used `git switch feature/prompt-concise && git rebase dev` instead of `git merge`:
- **Linear History vs. True Graph:** Rebase rewinds the commits on `feature/prompt-concise`, fast-forwards `feature/prompt-concise` to the tip of `dev`, and replays each commit one-by-one on top.
- **Conflict Occurrence:** The conflict would still occur during the replay step, requiring the same manual resolution.
- **Resulting Commits:** 
  - `git rebase` creates a completely flat, linear commit log with new commit SHAs (rewriting history) and **no merge commit**.
  - `git merge` preserves both original commit histories and creates a **distinct non-fast-forward merge commit** with two parent hashes.
- **Why Merge Commit Was Required Here:** Hands-On 1 specifically assesses the ability to demonstrate branching, concurrent feature development, and explicit merge resolution evidence visible via `git log --graph --oneline`. Rebase would erase that audit trail.

---

## 6. Git Graph Verification

Running `git log --graph --oneline` clearly proves the non-fast-forward merge:

```text
*   d8a9e1f (HEAD -> dev) Merge branch 'feature/prompt-concise' into dev
|\  
| * 64ee326 (feature/prompt-concise) feat(prompt): use stricter answer-length wording
* | 0fd60db (feature/prompt-friendly) feat(prompt): use friendlier answer-length wording
|/  
* 71a2241 (origin/dev) docs(readme): add comprehensive documentation, architecture, and decisions
```
Both branch heads are cleanly merged, preserving full traceability.
