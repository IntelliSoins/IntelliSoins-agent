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

| Dataset                       | Purpose                    |
| ----------------------------- | -------------------------- |
| `nemotron-hammerspoon/`       | macOS automation           |
| `nemotron-unified-clean/`     | cleaned unified data       |
| `nemotron-real-thinking/`     | extended thinking examples |
| `nemotron-chrome-navigation/` | browser automation         |
| `nemotron-unified-qwen3/`     | Qwen3 optimized data       |

## Tool Definitions

`pipeline/tool_definitions_openclaw.json` contains OpenAI-compatible function
schemas, including browser tooling with many parameters.

## LoRA Config Defaults

- rank: 16
- alpha: 32
- learning rate: `5e-6`
- max sequence length: 32768
- batch size: 1
