#!/usr/bin/env python3
"""
Test script to verify the context length implementation works correctly.
"""

import sys
import os
sys.path.append('src/ll_ocl_comics')

from apis import OllamaAPI

def test_context_implementation():
    """Test the context length functionality."""
    print("Testing Ollama Context Length Implementation")
    print("=" * 50)
    
    # Initialize API
    api = OllamaAPI()
    
    try:
        # Test connection
        print("1. Testing Ollama connection...")
        connected = api.check_connection()
        if connected:
            print("   ✓ Connected to Ollama successfully")
        else:
            print("   ✗ Failed to connect to Ollama")
            return False
    except Exception as e:
        print(f"   ✗ Connection error: {e}")
        return False
    
    try:
        # Test model listing
        print("\n2. Testing model listing...")
        models = api.get_models()
        if models:
            print(f"   ✓ Found {len(models)} models: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")
        else:
            print("   ✗ No models found")
            return False
    except Exception as e:
        print(f"   ✗ Model listing error: {e}")
        return False
    
    # Test model info retrieval
    print("\n3. Testing model info retrieval...")
    for model in models[:2]:  # Test first 2 models
        try:
            max_context = api.get_model_max_context(model)
            print(f"   ✓ {model}: max context = {max_context} tokens")
        except Exception as e:
            print(f"   ✗ Error getting context for {model}: {e}")
    
    # Test config persistence
    print("\n4. Testing config persistence...")
    try:
        # Save a test context length
        test_context = 8192
        success = api.save_context_length(test_context)
        if success:
            print(f"   ✓ Saved context length: {test_context}")
        else:
            print("   ✗ Failed to save context length")
            
        # Load it back
        loaded_context = api.load_context_length()
        if loaded_context == test_context:
            print(f"   ✓ Loaded context length: {loaded_context}")
        else:
            print(f"   ✗ Context length mismatch: expected {test_context}, got {loaded_context}")
            
    except Exception as e:
        print(f"   ✗ Config persistence error: {e}")
    
    # Test generate with context length
    print("\n5. Testing generate with context length...")
    try:
        if models:
            test_model = models[0]
            test_prompt = "Hello, this is a test."
            test_context_length = 4096
            
            print(f"   Testing with model: {test_model}")
            print(f"   Context length: {test_context_length}")
            print("   Sending test request...")
            
            response = api.generate(test_model, test_prompt, context_length=test_context_length)
            if response and not response.startswith("Error:"):
                print(f"   ✓ Received response: {response[:50]}{'...' if len(response) > 50 else ''}")
            else:
                print(f"   ✗ Generate failed: {response}")
                
    except Exception as e:
        print(f"   ✗ Generate error: {e}")
    
    print("\n" + "=" * 50)
    print("Context length implementation test completed!")
    return True

if __name__ == "__main__":
    test_context_implementation()
