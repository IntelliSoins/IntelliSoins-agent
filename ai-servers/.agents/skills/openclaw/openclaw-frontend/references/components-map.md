# OpenClaw Control UI Components

## Views

| File            | Component         | Purpose            |
| --------------- | ----------------- | ------------------ |
| `overview.ts`   | `<oc-overview>`   | Dashboard          |
| `chat.ts`       | `<oc-chat>`       | Chat interface     |
| `agents.ts`     | `<oc-agents>`     | Agent config       |
| `channels.ts`   | `<oc-channels>`   | Channel config     |
| `config.ts`     | `<oc-config>`     | System config      |
| `sessions.ts`   | `<oc-sessions>`   | Session management |
| `skills.ts`     | `<oc-skills>`     | Skills catalog     |
| `cron.ts`       | `<oc-cron>`       | Scheduled tasks    |
| `nodes.ts`      | `<oc-nodes>`      | Distributed nodes  |
| `usage.ts`      | `<oc-usage>`      | Metrics            |
| `logs.ts`       | `<oc-logs>`       | Logs               |
| `instances.ts`  | `<oc-instances>`  | Running instances  |
| `debug.ts`      | `<oc-debug>`      | Debug tools        |
| `login-gate.ts` | `<oc-login-gate>` | Auth gate          |

## Shared Components

| File                  | Component       | Purpose            |
| --------------------- | --------------- | ------------------ |
| `dashboard-header.ts` | `<oc-header>`   | Header             |
| `sidebar.ts`          | `<oc-sidebar>`  | Navigation         |
| `toast.ts`            | `<oc-toast>`    | Notifications      |
| `modal.ts`            | `<oc-modal>`    | Dialogs            |
| `markdown.ts`         | `<oc-markdown>` | Markdown rendering |

## Controllers

| Controller         | Gateway methods                                 |
| ------------------ | ----------------------------------------------- |
| ChatController     | `chat.send`, `chat.history`, `chat.abort`       |
| AgentsController   | `agents.list`, `agents.create`, `agents.update` |
| ChannelsController | channel config methods                          |
| ConfigController   | `config.get`, `config.set`, `config.schema`     |
| CronController     | `cron.list`, `cron.add`, `cron.run`             |
| SessionsController | `sessions.list`, `sessions.delete`              |
| DevicesController  | device pairing                                  |
