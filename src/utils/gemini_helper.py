"""
Helper module for interacting with Google Gemini API via LangChain
Loads API key securely from environment variables
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables from .env file
load_dotenv()


def get_gemini_model(model_name="gemini-1.5-flash", temperature=0.7, **kwargs):
    """
    Initialize and return a Gemini model via LangChain

    Args:
        model_name: Model to use (default: gemini-1.5-flash)
                   Options: gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash-exp
        temperature: Sampling temperature (0.0 to 1.0)
        **kwargs: Additional parameters for ChatGoogleGenerativeAI

    Returns:
        ChatGoogleGenerativeAI: Configured model instance

    Raises:
        ValueError: If GEMINI_API_KEY is not set
    """
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found in environment variables. "
            "Please create a .env file with your API key:\n"
            "GEMINI_API_KEY=your_api_key_here"
        )

    model = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
        **kwargs
    )

    return model


def simple_chat(prompt, system_prompt=None, model_name="gemini-1.5-flash", **kwargs):
    """
    Simple chat interface - send a prompt and get a response

    Args:
        prompt: User message/prompt
        system_prompt: Optional system message to set context
        model_name: Model to use
        **kwargs: Additional parameters for the model

    Returns:
        str: Model response content
    """
    model = get_gemini_model(model_name=model_name, **kwargs)

    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    response = model.invoke(messages)
    return response.content


def batch_chat(prompts, system_prompt=None, model_name="gemini-1.5-flash", **kwargs):
    """
    Batch processing - send multiple prompts and get responses

    Args:
        prompts: List of user prompts
        system_prompt: Optional system message for all prompts
        model_name: Model to use
        **kwargs: Additional parameters for the model

    Returns:
        list: List of response contents
    """
    model = get_gemini_model(model_name=model_name, **kwargs)

    batch_messages = []
    for prompt in prompts:
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        batch_messages.append(messages)

    responses = model.batch(batch_messages)
    return [response.content for response in responses]


# Example usage
if __name__ == "__main__":
    # Test basic functionality
    try:
        print("Testing Gemini API connection...")

        response = simple_chat(
            prompt="Say hello and confirm you're working!",
            temperature=0.3
        )

        print(f"✓ Connection successful!")
        print(f"Response: {response}")

    except ValueError as e:
        print(f"✗ Error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
