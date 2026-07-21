# OpenClaw Fine-Tuning Dataset Inventory

## Main Dataset

`pipeline/training-data/openclaw-agentic/`

- 4,658 examples
- 4,641 organic examples plus 17 synthetic OpenClaw examples
- Split: 4,176 train / 226 valid / 256 test
- Around 64.5M tokens total
- OpenAI JSON format with tool calls and tool role messages
- Thinking blocks preserved where available

## Other Dataset Variants

| Dataset                       | Purpose                                                                                                                                                                       |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nemotron-hammerspoon/`       | macOS automation                                                                                                                                                              |
| `nemotron-unified-clean/`     | cleaned unified data                                                                                                                                                          |
| `nemotron-real-thinking/`     | extended thinking examples                                                                                                                                                    |
| `nemotron-chrome-navigation/` | browser automation                                                                                                                                                            |
| `nemotron-unified-qwen3/`     | Qwen3 optimized data                                                                                                                                                          |
| `dgx-fable5-mix/`             | Fable 5 agentic mix for Qwen3.6-35B-A3B (Claude + OpenCode fable-5 sessions, pubmed prod, chrome-nav, computeruse-vision, imessage/email style; long context up to ~350K tok) |
| `dgx-fable5-mix-gemma4/`      | Same mix converted to Gemma 4 house format (`convert_dgx_to_gemma4.py`: tool calls as JSON array, tool role name+content, think stripped)                                     |
| `computeruse-vision/`         | screenshot -> next action pairs (web navigation computer use, LLaMA-Factory shape)                                                                                            |

OpenCode fable-5 sessions are extracted from `~/.local/share/opencode/opencode.db`
via `extract_opencode_sessions.py --model-filter fable` and feed the
`fable5-opencode` lane of `build_dgx_dataset.py` (refresh 2026-07-09: 234 examples).

## Tool Definitions

`pipeline/tool_definitions_openclaw.json` contains OpenAI-compatible function
schemas, including browser tooling with many parameters.

## LoRA Config Defaults

- rank: 16
- alpha: 32
- learning rate: `5e-6`
- max sequence length: 32768
- batch size: 1
