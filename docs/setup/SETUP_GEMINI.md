# Setting Up Google Gemini API

## 1. Get Your API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy your API key

## 2. Create `.env` File

Create a file named `.env` in the project root:

```bash
# Copy the example file
cp .env.example .env
```

Then edit `.env` and add your API key:

```bash
GEMINI_API_KEY=your_actual_api_key_here
```

**Important:** The `.env` file is already in `.gitignore` and will NOT be committed to git.

## 3. Verify Setup

Test your configuration:

```bash
source unit_builder/bin/activate
python -m src.utils.gemini_helper
```

You should see:
```
✓ Connection successful!
Response: Hello! I'm working perfectly. ...
```

## 4. Usage in Code

```python
from src.utils.gemini_helper import get_gemini_model, simple_chat

# Simple chat
response = simple_chat("Explain regex in one sentence")
print(response)

# With system prompt
response = simple_chat(
    prompt="Extract the unit info from this text: '505 regt, 3 bn, Co C'",
    system_prompt="You are a military records extraction expert.",
    temperature=0.3
)

# Get model directly for more control
model = get_gemini_model(model_name="gemini-1.5-flash")
from langchain_core.messages import HumanMessage
response = model.invoke([HumanMessage(content="Hello")])
```

## Available Models

- `gemini-1.5-flash` - Fast, cost-effective (default)
- `gemini-1.5-pro` - Most capable, higher quality
- `gemini-2.0-flash-exp` - Experimental next-gen model

## Rate Limits

Free tier limits:
- 15 requests per minute
- 1 million tokens per minute
- 1,500 requests per day

See [pricing](https://ai.google.dev/pricing) for details.

## Troubleshooting

**Error: "GEMINI_API_KEY not found"**
- Make sure `.env` file exists in project root
- Check that `.env` contains `GEMINI_API_KEY=...`
- Verify no extra spaces around the `=`

**Error: "Invalid API key"**
- Confirm key is copied correctly from Google AI Studio
- Try regenerating the key

**Error: "Rate limit exceeded"**
- Wait a minute and try again
- Consider upgrading to paid tier for higher limits
