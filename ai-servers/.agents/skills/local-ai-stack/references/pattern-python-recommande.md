## Pattern Python recommandé

```python
import subprocess
from openai import OpenAI

def litellm_client():
    master = subprocess.check_output([
        "security", "find-generic-password",
        "-a", "michaelahern", "-s", "litellm-master-key", "-w"
    ]).decode().strip()
    return OpenAI(base_url="http://127.0.0.1:8092/v1", api_key=master)
```
