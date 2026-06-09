---
name: proton-mail
description: Proton CLI local email indexing and search pipeline.
metadata:
  {
    "openclaw":
      { "emoji": "✉️", "requires": { "bins": ["/Users/michaelahern/proton_cli/bin/proton-mail"] } },
  }
---

# Proton CLI Email Indexing & Search

Use `proton-mail` (located at `/Users/michaelahern/proton_cli/bin/proton-mail`) to interact with the local email database.

## Status

Check status:

```zsh
zsh /Users/michaelahern/proton_cli/bin/proton-mail status
```

## Ingesting Emails

Dry-run:

```zsh
zsh /Users/michaelahern/proton_cli/bin/proton-mail ingest --mailbox INBOX --limit 1 --dry-run
```

Real ingest:

```zsh
zsh /Users/michaelahern/proton_cli/bin/proton-mail ingest --mailbox INBOX --limit 25
```

## Searching Emails

Query search:

```zsh
zsh /Users/michaelahern/proton_cli/bin/proton-mail search "query" --limit 5
```

## Deleting Emails (durable)

To permanently delete emails from both the Proton Mail server (via IMAP `\Deleted` + `EXPUNGE`) and the local PostgreSQL database (cascade delete on chunks/entities):

Dry-run (check what would be deleted):

```zsh
zsh /Users/michaelahern/proton_cli/bin/proton-mail delete --delete-subject-contains "subject key" --dry-run
```

Real deletion:

```zsh
zsh /Users/michaelahern/proton_cli/bin/proton-mail delete --delete-subject-contains "subject key"
```

Available options:

- `--delete-subject "exact subject"` : Deletes by exact subject (case-insensitive).
- `--delete-subject-contains "keyword"` : Deletes by substring match in subject.
- `--delete-message-id "<id>"` : Deletes a specific email by Message-ID.
- `--uid <UID>` : Deletes an email by its IMAP UID.
- `--mailbox <Name>` : Target mailbox (default: `INBOX`).
