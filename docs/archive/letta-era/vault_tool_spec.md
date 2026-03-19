# Vault Tool Call Specification

## Overview

These are the tool calls Dot uses to interact with its Obsidian-compatible knowledge base. The tools are backend-agnostic: they present the same interface whether backed by the Obsidian sidecar (indexed, fast) or raw filesystem operations (degraded, functional). The backend is a deployment configuration detail, not something Dot needs to manage.

All paths are relative to the vault root. The vault root maps to a K3s persistent volume mounted in both the Letta agent container and the Obsidian sidecar container.

---

## Primitive Operations

### vault_read

Read a note and its metadata.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| path | string | yes | File path relative to vault root |

**Returns:**

```json
{
  "path": "research/ahmed-cultural-politics-of-emotion.md",
  "exists": true,
  "content": "---\ntype: research-note\n...\n---\n\nAhmed argues that...",
  "frontmatter": {
    "type": "research-note",
    "related_interests": ["sociolinguistics", "audience-response"],
    "created": "2026-03-08",
    "status": "developing"
  },
  "body": "Ahmed argues that...",
  "modified": "2026-03-08T14:32:00Z"
}
```

**Notes:**
- `content` is the full raw file including frontmatter delimiters
- `body` is the markdown content with frontmatter stripped
- `frontmatter` is the parsed YAML as a dict
- If the file does not exist, returns `{"exists": false, "path": "..."}` — not an empty string
- Backend: sidecar uses `GET /vault/{path}`; filesystem uses file read + YAML parse

---

### vault_write

Create a new note or overwrite an existing one.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| path | string | yes | File path relative to vault root |
| body | string | yes | Markdown content (without frontmatter delimiters) |
| frontmatter | dict | no | Key-value pairs serialized as YAML header |
| overwrite | bool | no | Must be `true` to overwrite an existing file. Default: `false` |

**Returns:**

```json
{
  "path": "research/new-note.md",
  "created": true,
  "overwritten": false
}
```

**Behavior:**
- If `frontmatter` is provided, the tool assembles the full file: `---\n{yaml}\n---\n\n{body}`
- If `frontmatter` is omitted, the file contains only the body
- If the path already exists and `overwrite` is not `true`, returns an error:
  ```json
  {
    "path": "research/existing-note.md",
    "error": "file_exists",
    "message": "File already exists. Set overwrite=true to replace.",
    "existing_modified": "2026-03-07T10:15:00Z"
  }
  ```
- Parent directories are created automatically if they don't exist
- The tool automatically sets `created` and `modified` dates in frontmatter if not explicitly provided
- Backend: sidecar uses `PUT /vault/{path}`; filesystem uses file write

---

### vault_append

Add content to the end of an existing note.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| path | string | yes | File path relative to vault root |
| content | string | yes | Markdown content to append |
| separator | string | no | Separator before appended content. Default: `"\n\n"` (blank line) |

**Returns:**

```json
{
  "path": "research/ahmed-cultural-politics-of-emotion.md",
  "appended": true,
  "new_length": 4523
}
```

**Behavior:**
- Inserts `separator` before the appended content so new material starts a fresh paragraph
- If the file does not exist, returns an error (use `vault_write` to create)
- Does not modify frontmatter
- Backend: sidecar uses `POST /vault/{path}`; filesystem uses open-append-close

---

### vault_delete

Remove a note from the vault.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| path | string | yes | File path relative to vault root |

**Returns:**

```json
{
  "path": "scratchpad/obsolete-note.md",
  "deleted": true
}
```

**Behavior:**
- Returns error if file does not exist
- Does not remove empty parent directories (cleanup is a housekeeping task)
- Telemetry note: log what was deleted and why, since this is irreversible

---

### vault_rename

Move or rename a note.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| old_path | string | yes | Current file path |
| new_path | string | yes | Target file path |

**Returns:**

```json
{
  "old_path": "inbox/untitled.md",
  "new_path": "research/meyrowitz-no-sense-of-place.md",
  "renamed": true,
  "backlinks_updated": true,
  "backend": "indexed"
}
```

**Behavior:**
- With sidecar: Obsidian updates all wikilinks pointing to the old path. `backlinks_updated` is `true`.
- Without sidecar: file is moved but backlinks break. `backlinks_updated` is `false`. Dot should log this in telemetry and consider manually searching for `[[old_filename]]` references to fix.
- Parent directories for new_path are created automatically
- Returns error if old_path doesn't exist or new_path already exists

---

## Search and Discovery

### vault_search

Search vault contents with optional structured filters.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| query | string | no | Full-text search string. Omit for filter-only queries. |
| tags | list[str] | no | Filter to notes with all listed tags |
| type | string | no | Filter by frontmatter `type` field |
| related_interests | list[str] | no | Filter by frontmatter `related_interests` (any match) |
| status | string | no | Filter by frontmatter `status` field |
| directory | string | no | Scope search to a subdirectory |
| limit | int | no | Max results. Default: 20 |

**Returns:**

```json
{
  "results": [
    {
      "path": "research/halttunen-murder-most-foul.md",
      "score": 0.87,
      "snippet": "...the social construction of violence-as-spectacle in nineteenth-century...",
      "frontmatter": {
        "type": "research-note",
        "related_interests": ["horror-fiction", "visuality"],
        "status": "stable"
      }
    }
  ],
  "total": 12,
  "returned": 10,
  "backend": "indexed"
}
```

**Backend behavior:**

| Feature | Indexed (sidecar) | Filesystem (fallback) |
|---------|-------------------|----------------------|
| Full-text query | Obsidian search index | ripgrep or BM25 over file contents |
| Tag filtering | JsonLogic on indexed metadata | YAML frontmatter parse + filter |
| Type/status/interest filters | JsonLogic on indexed metadata | YAML frontmatter parse + filter |
| Relevance scoring | Obsidian's ranking algorithm | BM25 or match count |
| Speed (5k note vault) | ~0.3s | ~2-5s depending on filter complexity |

The `backend` field in the response tells Dot what quality of results it received. If Dot is doing a critical research query and gets `"filesystem"` back, it can note in telemetry that results may be incomplete.

---

### vault_backlinks

Find all notes that link to a given note.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| path | string | yes | Path of the target note |

**Returns:**

```json
{
  "target": "concepts/audience-response.md",
  "backlinks": [
    {
      "path": "research/halttunen-murder-most-foul.md",
      "context": "...this connects to [[audience-response]] through the spectacle framework...",
      "line": 42
    },
    {
      "path": "reflections/2026-w10.md",
      "context": "...Cyrus's horror scholarship is grounded in [[audience-response]]...",
      "line": 15
    }
  ],
  "count": 7,
  "backend": "indexed"
}
```

**Backend behavior:**

| Feature | Indexed (sidecar) | Filesystem (fallback) |
|---------|-------------------|----------------------|
| Detection | Full link resolution (aliases, display text) | Regex for `[[filename]]` patterns |
| Context snippets | Surrounding text from index | Line containing the match |
| Speed (5k notes) | ~0.3s | ~5-15s (full vault scan) |
| Accuracy | Catches aliased links, embeds, renamed references | Misses aliases and non-standard link formats |

This is the highest-value sidecar operation. For a zettelkasten-style knowledge base where the connections between notes are the primary intellectual value, fast backlink resolution is what makes Dot's research workflow fluid rather than expensive.

---

### vault_list

List vault structure and contents.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| directory | string | no | Subdirectory to list. Default: vault root. |
| pattern | string | no | Glob pattern to filter (e.g., `"*.md"`, `"concept-*"`) |
| recursive | bool | no | Include subdirectories recursively. Default: `false` |

**Returns:**

```json
{
  "path": "research/",
  "entries": [
    {"type": "directory", "name": "horror", "count": 15, "modified": "2026-03-07T18:00:00Z"},
    {"type": "directory", "name": "sociolinguistics", "count": 8, "modified": "2026-03-05T12:00:00Z"},
    {"type": "file", "name": "ahmed-cultural-politics-of-emotion.md", "modified": "2026-03-08T14:32:00Z"},
    {"type": "file", "name": "clover-men-women-chainsaws.md", "modified": "2026-02-20T09:15:00Z"}
  ],
  "total_files": 34,
  "total_directories": 5
}
```

**Notes:**
- Directory entries include `count` (number of files, non-recursive) for structural reasoning
- Sorted: directories first (alphabetical), then files (alphabetical)
- Backend: same behavior either way (filesystem operation)

---

## Convenience Operations

### vault_stats

Get an overview of vault structure and content distribution.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| None | | | |

**Returns:**

```json
{
  "total_notes": 247,
  "by_type": {
    "research-note": 89,
    "reflection": 24,
    "concept": 31,
    "reading-summary": 45,
    "conversation-note": 38,
    "blog-draft": 8,
    "interest-annotation": 7,
    "scratchpad": 5
  },
  "by_status": {
    "seed": 52,
    "developing": 94,
    "stable": 87,
    "published": 14
  },
  "by_directory": {
    "research": 89,
    "concepts": 31,
    "reflections": 24,
    "readings": 45,
    "conversations": 38,
    "blog": 8,
    "meta": 7,
    "inbox": 5
  },
  "most_linked": [
    {"path": "concepts/audience-response.md", "backlink_count": 34},
    {"path": "concepts/visuality.md", "backlink_count": 28},
    {"path": "concepts/spectacle-of-violence.md", "backlink_count": 22}
  ],
  "orphans": [
    "inbox/untitled-2026-03-07.md",
    "scratchpad/random-thought.md"
  ],
  "recently_modified": [
    {"path": "research/new-paper.md", "modified": "2026-03-08T16:00:00Z"},
    {"path": "reflections/2026-w10.md", "modified": "2026-03-08T12:00:00Z"}
  ],
  "backend": "indexed"
}
```

**Behavior:**
- With sidecar: uses index for backlink counts, orphan detection, and most-linked calculation. Fast.
- Without sidecar: frontmatter stats come from scanning and parsing all files. Backlink counts and orphan detection require a full vault scan. Expensive on large vaults — consider caching results and only refreshing periodically.
- This is the primary input for updating the vault schema memory block. Dot should call this during reflection cycles, not every session.

---

### vault_related

Find notes related to a given note based on shared metadata, links, and content.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| path | string | yes | Path of the reference note |
| limit | int | no | Max results. Default: 10 |

**Returns:**

```json
{
  "reference": "research/ahmed-cultural-politics-of-emotion.md",
  "related": [
    {
      "path": "concepts/audience-response.md",
      "relevance": 0.92,
      "reasons": ["shared_interest:audience-response", "backlink", "shared_tag:affect"]
    },
    {
      "path": "research/halttunen-murder-most-foul.md",
      "relevance": 0.85,
      "reasons": ["shared_interest:visuality", "shared_interest:horror-fiction", "shared_tag:spectacle"]
    }
  ],
  "backend": "indexed"
}
```

**Behavior:**
- Relevance is computed from: shared `related_interests` fields, shared tags, direct wikilinks between notes, backlink overlap (notes that link to the same things), and content similarity if available.
- With sidecar: can use Obsidian's graph data and Dataview for structured similarity. Fast.
- Without sidecar: heuristic based on frontmatter overlap and shared wikilinks. Slower and less accurate but still useful.
- The `reasons` array tells Dot *why* notes are related — this is useful for its own reasoning about knowledge connections and for generating blog posts about its research process.

---

## Frontmatter Schema

All vault notes should include YAML frontmatter. Dot starts with this base schema and can evolve it through the vault schema memory block.

### Required fields

```yaml
type: <note-type>
created: <ISO date>
```

### Standard fields

```yaml
type: research-note | reflection | interest-annotation | blog-draft |
      reading-summary | concept | conversation-note | scratchpad
source: conversation | independent-research | feed-monitoring | calibration
related_interests: []    # entries from interests:cyrus or interests:dot memory blocks
created: 2026-03-08      # set automatically by vault_write if omitted
modified: 2026-03-08     # updated automatically on write/append
status: seed | developing | stable | published
tags: []                 # freeform tags, complementary to type and interests
```

### Field definitions

**type** classifies the note's purpose:
- `research-note`: analysis of a source, paper, or text
- `reflection`: output from a reflection cycle (operational, weekly, or monthly)
- `interest-annotation`: enrichment of an entry in an interests memory block
- `blog-draft`: content being developed for public posting
- `reading-summary`: notes from processing a document during research time
- `concept`: a standing reference note for a recurring idea or framework
- `conversation-note`: knowledge captured from an admin conversation
- `scratchpad`: temporary working notes, inbox items, unprocessed captures

**source** records how the note originated:
- `conversation`: emerged from an admin interaction
- `independent-research`: produced during free-time research
- `feed-monitoring`: triggered by RSS, Bluesky, or other monitored feeds
- `calibration`: created during the calibration period

**related_interests** links the note back to the memory block architecture. Values should match entries in the interests:cyrus or interests:dot blocks. This field is what makes `vault_search(related_interests=["horror-fiction"])` work, and it's how Dot maintains awareness of which interests are actively producing knowledge.

**status** tracks the note's lifecycle:
- `seed`: initial capture, may be incomplete or unprocessed
- `developing`: actively being built out with new content
- `stable`: Dot considers the content reliable and well-developed
- `published`: has been used as the basis for a blog post or public reflection

**tags** are freeform and complementary. Use for concepts that cross-cut the structured fields — things like `affect`, `spectacle`, `code-switching`, `19th-century`, `methodology`. Tags emerge organically; interests are curated.

### Schema evolution

The frontmatter schema is documented in Dot's vault schema memory block. Dot can add new fields as its knowledge practices develop — for instance, a `confidence` field on research notes, a `superseded_by` field for notes that have been replaced, or domain-specific fields for particular research areas. When Dot adds a new field, it should update the schema block and ideally backfill existing notes (as a free-time task, not a blocking operation).

---

## Degraded Mode Behavior Summary

All tools function without the Obsidian sidecar, with these limitations:

| Tool | Full (indexed) | Degraded (filesystem) |
|------|---------------|----------------------|
| vault_read | REST API | File read + YAML parse |
| vault_write | REST API | File write |
| vault_append | REST API | File append |
| vault_delete | REST API | File delete |
| vault_rename | REST API + backlink update | File move, backlinks break |
| vault_search | Obsidian index, JsonLogic filters | ripgrep + YAML scan |
| vault_backlinks | Index resolution, alias-aware | Regex scan, misses aliases |
| vault_list | Filesystem (same either way) | Filesystem |
| vault_stats | Index for graph metrics | Full vault scan, cache recommended |
| vault_related | Graph data + structured similarity | Frontmatter heuristic |

The `backend` field in search/discovery responses lets Dot reason about result quality. The general principle: primitives (read/write/append/delete) work identically either way; search and graph operations are where the sidecar adds value.

---

## Implementation Notes

### For Letta tool registration

Each tool should be registered as a Letta tool with:
- A clear docstring explaining what it does and when to use it (this is what Dot sees in its tool list)
- Parameter validation before making backend calls
- Consistent error handling: return structured error dicts, never raise exceptions into agent context

### Backend switching

Implement as a backend abstraction layer:
- `VaultBackend` base class with methods matching each tool
- `IndexedVaultBackend(VaultBackend)` — calls Obsidian REST API
- `FilesystemVaultBackend(VaultBackend)` — raw file operations
- Backend selected at startup based on whether the sidecar health check passes
- If the sidecar goes down mid-session, fall back gracefully with a telemetry note

### Concurrency

The sidecar handles concurrency via Obsidian's internal model. For filesystem mode, vault operations should use file-level locking to prevent corruption if multiple processes write simultaneously (unlikely in practice for a single-agent setup, but worth guarding against).

### Encoding

All files are UTF-8. Tool calls accept and return Unicode strings. Frontmatter values are strings, lists of strings, or ISO dates — no nested objects.