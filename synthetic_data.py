import json
import pandas as pd
import requests
import re
from config import MODEL


def extract_json(text):
    """
    Extract the first JSON object or array from LLM output.
    """
    # Look for JSON array first
    match = re.search(r"(\[.*\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            # If truncated, remove last character and retry
            temp = match.group(1)
            while temp:
                try:
                    return json.loads(temp)
                except json.JSONDecodeError:
                    temp = temp[:-1]
    # fallback to object
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            temp = match.group(1)
            while temp:
                try:
                    return json.loads(temp)
                except json.JSONDecodeError:
                    temp = temp[:-1]
    raise ValueError("No valid JSON could be extracted from LLM output.")


def generate_synthetic_listings(prompt, api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 5000,
        "temperature": 0.7,
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    res_json = response.json()

    try:
        output_text = res_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise ValueError(f"Unexpected LLM response format: {res_json}")

    print("Raw LLM output:", output_text)  # Debug print

    return output_text.strip()


def save_synthetic_listings(
    raw_output,
    filename="/Users/tzx/Desktop/MMA/Colloquia/Python/Project/synthetic_listings.csv",
):
    try:
        print("Raw output:", raw_output)
        listings = extract_json(raw_output)
        print("Extracted listings:", listings)
        print("Type of listings:", type(listings))
        if isinstance(listings, str):
            listings = json.loads(listings)
        if not isinstance(listings, list) or len(listings) == 0:
            raise ValueError("No valid listings extracted from LLM output.")
    except Exception as e:
        raise ValueError(f"LLM output is not valid JSON: {e}")
    df = pd.DataFrame(listings)
    print("DataFrame shape:", df.shape)
    if df.empty:
        raise ValueError("DataFrame is empty. Check extracted listings format.")
    df.to_csv(filename, index=False)
    print(f"Synthetic listings saved to {filename}")


def merge_with_real_listings(
    real_file="/Users/tzx/Desktop/MMA/Colloquia/Python/Project/cleaned_listings.csv",
    synthetic_file="/Users/tzx/Desktop/MMA/Colloquia/Python/Project/synthetic_listings.csv",
    output_file="/Users/tzx/Desktop/MMA/Colloquia/Python/Project/merged_listings.csv",
):
    df_real = pd.read_csv(real_file)
    df_synth = pd.read_csv(synthetic_file)
    if df_synth.empty:
        raise ValueError("Synthetic listings CSV is empty. Cannot merge.")
    df_merged = pd.concat([df_real, df_synth], ignore_index=True)
    df_merged.to_csv(output_file, index=False)
    print("Merged listings saved to merged_listings.csv")
