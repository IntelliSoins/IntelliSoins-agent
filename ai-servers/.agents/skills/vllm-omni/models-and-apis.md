---
description: vLLM-Omni — catalogue complet des modèles (GPU NVIDIA/AMD + NPU Ascend) et référence API (images/generations, images/edits, chat/completions, paramètres extension, SDK Python, error handling, stage config). Sous-rule de ~/.claude/rules/vllm-omni.md.
paths:
  - "**/*vllm*omni*api*"
  - "**/*vllm*omni*model*"
---

# vLLM-Omni — Models Catalog & API Reference

> Sous-rule de `~/.claude/rules/vllm-omni.md`. Transféré du skill `intellisoins-mlx:vllm-omni` (`references/models-and-apis.md`) le 2026-05-24.

Source: https://github.com/Blaizzy/vllm-omni
Docs: https://vllm-omni.readthedocs.io/

## Complete Model Catalog — NVIDIA GPU / AMD GPU

| Architecture                           | Model                 | Example HuggingFace Repo                               | Category   |
| -------------------------------------- | --------------------- | ------------------------------------------------------ | ---------- |
| `Qwen3OmniMoeForConditionalGeneration` | Qwen3-Omni            | `Qwen/Qwen3-Omni-30B-A3B-Instruct`                     | Omni       |
| `Qwen2_5OmniForConditionalGeneration`  | Qwen2.5-Omni          | `Qwen/Qwen2.5-Omni-7B`, `Qwen/Qwen2.5-Omni-3B`         | Omni       |
| `BagelForConditionalGeneration`        | BAGEL (DiT-only)      | `ByteDance-Seed/BAGEL-7B-MoT`                          | Image Gen  |
| `QwenImagePipeline`                    | Qwen-Image            | `Qwen/Qwen-Image`                                      | Image Gen  |
| `QwenImagePipeline`                    | Qwen-Image-2512       | `Qwen/Qwen-Image-2512`                                 | Image Gen  |
| `QwenImageEditPipeline`                | Qwen-Image-Edit       | `Qwen/Qwen-Image-Edit`                                 | Image Edit |
| `QwenImageEditPlusPipeline`            | Qwen-Image-Edit-2509  | `Qwen/Qwen-Image-Edit-2509`                            | Image Edit |
| `QwenImageLayeredPipeline`             | Qwen-Image-Layered    | `Qwen/Qwen-Image-Layered`                              | Image Edit |
| `ZImagePipeline`                       | Z-Image Turbo         | `Tongyi-MAI/Z-Image-Turbo`                             | Image Gen  |
| `WanPipeline`                          | Wan2.2-T2V            | `Wan-AI/Wan2.2-T2V-A14B-Diffusers`                     | Video Gen  |
| `WanPipeline`                          | Wan2.2-TI2V           | `Wan-AI/Wan2.2-TI2V-5B-Diffusers`                      | Video Gen  |
| `WanImageToVideoPipeline`              | Wan2.2-I2V            | `Wan-AI/Wan2.2-I2V-A14B-Diffusers`                     | Video Gen  |
| `OvisImagePipeline`                    | Ovis-Image            | `OvisAI/Ovis-Image`                                    | Image Gen  |
| `LongcatImagePipeline`                 | LongCat-Image         | `meituan-longcat/LongCat-Image`                        | Image Gen  |
| `LongCatImageEditPipeline`             | LongCat-Image-Edit    | `meituan-longcat/LongCat-Image-Edit`                   | Image Edit |
| `StableDiffusion3Pipeline`             | Stable-Diffusion-3.5  | `stabilityai/stable-diffusion-3.5-medium`              | Image Gen  |
| `Flux2KleinPipeline`                   | FLUX.2-klein          | `black-forest-labs/FLUX.2-klein-4B`, `FLUX.2-klein-9B` | Image Gen  |
| `FluxPipeline`                         | FLUX.1-dev            | `black-forest-labs/FLUX.1-dev`                         | Image Gen  |
| `StableAudioPipeline`                  | Stable-Audio-Open     | `stabilityai/stable-audio-open-1.0`                    | Audio Gen  |
| `Qwen3TTSForConditionalGeneration`     | Qwen3-TTS CustomVoice | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`                 | TTS        |
| `Qwen3TTSForConditionalGeneration`     | Qwen3-TTS VoiceDesign | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`                 | TTS        |
| `Qwen3TTSForConditionalGeneration`     | Qwen3-TTS Base        | `Qwen/Qwen3-TTS-12Hz-0.6B-Base`                        | TTS        |
| `(arch v0.18.0+)`                      | MammothModa2          | `bytedance-research/MammothModa2-Preview`              | Omni       |
| `(arch v0.20.0rc1+)`                   | Ming-flash-omni-2.0   | `inclusionAI/Ming-flash-omni-2.0`                      | Omni       |
| `(arch v0.20.0rc1+)`                   | Dynin-Omni            | `snu-aidas/Dynin-Omni`                                 | Omni       |
| `(arch v0.18.0+)`                      | FLUX.2-dev            | `black-forest-labs/FLUX.2-dev`                         | Image Gen  |
| `(arch v0.18.0+)`                      | FLUX.1-Kontext-dev    | `black-forest-labs/FLUX.1-Kontext-dev`                 | Image Gen  |
| `(arch v0.18.0+)`                      | Hunyuan Image3 AR     | `tencent/HunyuanImage-3.0`                             | Image Gen  |
| `(arch v0.18.0+)`                      | LTX-2                 | `Lightricks/LTX-Video`                                 | Video Gen  |
| `(arch v0.20.0rc1+)`                   | LTX-2.3               | `Lightricks/LTX-2.3`                                   | Video Gen  |
| `(arch v0.18.0+)`                      | HunyuanVideo-1.5      | `tencent/HunyuanVideo-1.5`                             | Video Gen  |
| `(arch v0.18.0+)`                      | FastGen Wan 2.1       | _NON VERIFIE — aucun match HF API_                     | Video Gen  |
| `(arch v0.18.0+)`                      | Voxtral TTS           | `mistralai/Voxtral-4B-TTS-2603`                        | TTS        |
| `(arch v0.18.0+)`                      | MiMo-Audio            | `XiaomiMiMo/MiMo-Audio-7B-Base`                        | Audio Gen  |
| `(arch v0.18.0+)`                      | Fish Speech S2 Pro    | `AEmotionStudio/fish-speech-s2-pro`                    | TTS        |
| `(arch v0.20.0rc1+)`                   | MiMo-V2.5-ASR         | `XiaomiMiMo/MiMo-V2.5-ASR`                             | ASR        |
| `(arch v0.20.0rc1+)`                   | MOSS-TTS-Nano         | `OpenMOSS-Team/MOSS-TTS-Nano-100M`                     | TTS        |
| `(arch v0.20.0rc1+)`                   | VoxCPM2               | `openbmb/VoxCPM2`                                      | TTS        |

## NPU-Supported Models

Subset of models with NPU (Ascend) support:

| Model                | HuggingFace Repo                               |
| -------------------- | ---------------------------------------------- |
| Qwen2.5-Omni         | `Qwen/Qwen2.5-Omni-7B`, `Qwen/Qwen2.5-Omni-3B` |
| Qwen-Image           | `Qwen/Qwen-Image`                              |
| Qwen-Image-2512      | `Qwen/Qwen-Image-2512`                         |
| Qwen-Image-Edit      | `Qwen/Qwen-Image-Edit`                         |
| Qwen-Image-Edit-2509 | `Qwen/Qwen-Image-Edit-2509`                    |
| Qwen-Image-Edit-2511 | `Qwen/Qwen-Image-Edit-2511`                    |
| Qwen-Image-Layered   | `Qwen/Qwen-Image-Layered`                      |
| Z-Image Turbo        | `Tongyi-MAI/Z-Image-Turbo`                     |

## API Endpoints

### 1. Image Generation — `POST /v1/images/generations`

OpenAI DALL-E compatible endpoint for text-to-image generation.

**Start server:**

```bash
vllm serve Tongyi-MAI/Z-Image-Turbo --omni --port 8000
```

**Standard Parameters:**

| Parameter         | Type    | Default       | Description                        |
| ----------------- | ------- | ------------- | ---------------------------------- |
| `prompt`          | string  | required      | Text description of desired image  |
| `model`           | string  | server model  | Optional, should match server      |
| `n`               | integer | 1             | Number of images (1-10)            |
| `size`            | string  | model default | "WIDTHxHEIGHT" (e.g., "1024x1024") |
| `response_format` | string  | "b64_json"    | Only "b64_json" supported          |

**Extension Parameters:**

| Parameter             | Type    | Default       | Description               |
| --------------------- | ------- | ------------- | ------------------------- |
| `negative_prompt`     | string  | null          | What to avoid             |
| `num_inference_steps` | integer | model default | Diffusion steps           |
| `guidance_scale`      | float   | model default | CFG scale (0.0-20.0)      |
| `true_cfg_scale`      | float   | model default | True CFG (model-specific) |
| `seed`                | integer | null          | Reproducibility seed      |

**curl example:**

```bash
curl -X POST http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a dragon laying over mountains",
    "size": "1024x1024",
    "num_inference_steps": 50,
    "guidance_scale": 4.0,
    "seed": 42
  }' | jq -r '.data[0].b64_json' | base64 -d > output.png
```

**Python example:**

```python
import requests, base64, io
from PIL import Image

response = requests.post(
    "http://localhost:8000/v1/images/generations",
    json={
        "prompt": "a black and white cat wearing a tiara",
        "size": "1024x1024",
        "num_inference_steps": 50,
        "seed": 42,
    }
)

img_data = response.json()["data"][0]["b64_json"]
img = Image.open(io.BytesIO(base64.b64decode(img_data)))
img.save("cat.png")
```

**OpenAI SDK example:**

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="none")
response = client.images.generate(
    model="Tongyi-MAI/Z-Image-Turbo",
    prompt="a horse jumping over a fence",
    n=1,
    size="1024x1024",
    response_format="b64_json"
)
# Note: Extension parameters (seed, steps, cfg) require direct HTTP requests
```

**With negative prompt:**

```python
response = requests.post(
    "http://localhost:8000/v1/images/generations",
    json={
        "prompt": "a portrait of a skier in deep powder snow",
        "negative_prompt": "blurry, low quality, distorted, ugly",
        "num_inference_steps": 100,
        "size": "1024x1024",
    }
)
```

**Multiple images:**

```bash
curl -X POST http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a steampunk city in a valley",
    "n": 4,
    "size": "1024x1024",
    "seed": 123
  }'
```

**Response format:**

```json
{
  "created": 1701234567,
  "data": [
    {
      "b64_json": "<base64-encoded PNG>",
      "url": null,
      "revised_prompt": null
    }
  ]
}
```

### 2. Image Edit — `POST /v1/images/edits`

OpenAI DALL-E compatible endpoint for image editing with diffusion models.

**Start server:**

```bash
vllm serve Qwen/Qwen-Image-Edit-2511 --omni --port 8000
```

**Standard Parameters:**

| Parameter            | Type       | Default      | Description                          |
| -------------------- | ---------- | ------------ | ------------------------------------ |
| `prompt`             | string     | required     | Edit instruction                     |
| `image`              | file/array | required     | Image(s) to edit (multipart upload)  |
| `model`              | string     | server model | Optional                             |
| `n`                  | integer    | 1            | Number of output images (1-10)       |
| `size`               | string     | "auto"       | Output size ("auto" = same as input) |
| `output_format`      | string     | "png"        | "png", "jpg", "jpeg", "webp"         |
| `output_compression` | integer    | 100          | Compression level (0-100%)           |
| `background`         | string     | "auto"       | Transparency control                 |

**Extension Parameters:** Same as image generation (negative_prompt, num_inference_steps, guidance_scale, seed) plus:

| Parameter | Type         | Description                         |
| --------- | ------------ | ----------------------------------- |
| `url`     | string/array | Image URL(s) instead of file upload |

**curl example:**

```bash
curl -X POST http://localhost:8000/v1/images/edits \
  -F "image=@input.png" \
  -F "prompt='make the bear wear sportswear'" \
  -F "size=1024x1024" \
  -F "output_format=png" \
  | jq -r '.data[0].b64_json' | base64 -d > edited.png
```

**OpenAI SDK with URL input:**

```python
from openai import OpenAI
import base64

client = OpenAI(api_key="None", base_url="http://localhost:8000/v1")

result = client.images.edit(
    image=[],
    model="Qwen-Image-Edit-2511",
    prompt="Change the bears into walking together.",
    size='512x512',
    output_format='jpeg',
    extra_body={
        "url": ["https://example.com/bear1.png", "https://example.com/bear2.png"],
        "num_inference_steps": 50,
        "guidance_scale": 1,
        "seed": 777,
    }
)

with open("edited.jpeg", "wb") as f:
    f.write(base64.b64decode(result.data[0].b64_json))
```

### 3. Chat Completions — `POST /v1/chat/completions`

For omni-modal models (Qwen2.5-Omni, Qwen3-Omni) that accept multimodal input.

**Start server:**

```bash
vllm serve Qwen/Qwen2.5-Omni-7B --omni --port 8000
```

**Usage via curl:**

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "describe this image"}
    ],
    "extra_body": {
      "height": 1024,
      "width": 1024
    }
  }'
```

## Offline Inference API

### Basic Usage

```python
from vllm_omni.entrypoints.omni import Omni

omni = Omni(model="Tongyi-MAI/Z-Image-Turbo")
outputs = omni.generate("a cup of coffee on the table")
outputs[0].request_output[0].images[0].save("coffee.png")
```

### Batch Inference

```python
from vllm_omni.entrypoints.omni import Omni

omni = Omni(model="Tongyi-MAI/Z-Image-Turbo")
prompts = [
    "a cup of coffee on a table",
    "a toy dinosaur on a sandy beach",
    "a fox waking up in bed",
]

omni_outputs = omni.generate(prompts)
for i, output in enumerate(omni_outputs):
    output.request_output[0].images[0].save(f"output_{i}.jpg")
```

Note: Batch inference does not currently provide significant performance improvement
for most diffusion models. Default `max_batch_size` is 1.

### Custom Stage Configuration

```python
omni = Omni(
    model="Tongyi-MAI/Z-Image-Turbo",
    stage_configs_path="./stage-config.yaml"
)
```

Stage config controls pipeline behavior including `runtime.max_batch_size` for models
that support internal batching.

## Error Handling

### Common HTTP Errors

| Code | Cause                                                | Solution                       |
| ---- | ---------------------------------------------------- | ------------------------------ |
| 400  | Invalid parameters (bad size format, model mismatch) | Check parameter formats        |
| 422  | Missing required fields (prompt, image)              | Include all required fields    |
| OOM  | Model too large for GPU                              | Reduce image size, fewer steps |

### OOM Troubleshooting

1. Reduce image size: `"size": "512x512"` instead of `"1024x1024"`
2. Reduce inference steps: `"num_inference_steps": 25`
3. Use a smaller model variant
4. Enable tensor parallelism for multi-GPU setups

## Server Launch Options

```bash
# Basic launch
vllm serve <model_name> --omni --port <port>

# With tensor parallelism (multi-GPU)
vllm serve <model_name> --omni --port <port> --tensor-parallel-size 2

# With specific GPU
CUDA_VISIBLE_DEVICES=0,1 vllm serve <model_name> --omni --port <port>
```

The `--omni` flag is required for all vllm-omni models. Without it, the server
falls back to standard vLLM autoregressive serving.

## Architecture Notes

### OmniConnector Pipeline

vLLM-Omni decomposes models into stages with:

- **Pipelined execution**: Stages overlap for throughput
- **Dynamic resource allocation**: GPU memory managed per stage
- **KV cache**: Inherited from vLLM for autoregressive components
- **Parallelism**: Tensor, pipeline, data, and expert parallelism supported

### Diffusion vs Autoregressive

| Aspect   | Autoregressive (vLLM) | Diffusion (vLLM-Omni)                    |
| -------- | --------------------- | ---------------------------------------- |
| Output   | Token-by-token text   | Full image/video/audio                   |
| Batching | Continuous batching   | Per-request (default batch=1)            |
| Latency  | Streaming possible    | Full generation required                 |
| Memory   | KV cache dominant     | Model weights + intermediate activations |
