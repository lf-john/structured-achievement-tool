#!/bin/bash

# List of expected models (we will check if the model name contains these strings)
# From story: Qwen3 8B, Qwen2.5-Coder 7B, DeepSeek R1 8B, Nemotron Mini, nomic-embed-text
EXPECTED_MODELS=(
  "qwen"
  "deepseek"
  "nemotron"
  "nomic-embed-text"
)

# Query Ollama API for available models
response=$(curl -s http://localhost:11434/api/tags)

if [ $? -ne 0 ]; then
  echo "Error: Failed to connect to Ollama API at http://localhost:11434."
  exit 1
fi

# Extract model names from the JSON response
# The jq query '.models[].name' extracts the "name" field from each object in the "models" array.
available_models=$(echo "$response" | jq -r '.models[].name')

if [ $? -ne 0 ] || [ -z "$available_models" ]; then
  echo "Error: Failed to parse JSON response or no models found. Is jq installed and are models pulled?"
  echo "Response was: $response"
  exit 1
fi

echo "Available Ollama models:"
echo "$available_models"
echo "-------------------------"
echo "Verifying expected models..."

all_found=true
# Loop through the list of expected model substrings
for model in "${EXPECTED_MODELS[@]}"; do
  # Check if any of the available model names contain the expected substring
  if echo "$available_models" | grep -q "$model"; then
    echo "✔ Found model containing: $model"
  else
    echo "✖ Missing model containing: $model"
    all_found=false
  fi
done

echo "-------------------------"
if [ "$all_found" = true ]; then
  echo "Success: All expected Ollama models are available."
  exit 0
else
  echo "Failure: One or more expected Ollama models are missing."
  exit 1
fi
