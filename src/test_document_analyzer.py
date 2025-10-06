#!/usr/bin/env python3
"""
Test script for Azure AI Content Understanding Document Analyzer

This script demonstrates how to use the analyze_document_bytes function
from the utils module to analyze documents.
"""

import os
import sys
from pathlib import Path

# Add the src directory to the Python path so we can import utils
sys.path.append(str(Path(__file__).parent))

from utils import analyze_document_bytes


def test_document_analysis():
    """Test the document analysis function with a sample document."""
    
    # Example 1: Using environment variables (recommended approach)
    print("=" * 60)
    print("Testing with environment variables")
    print("=" * 60)
    
    # Path to your test document (you'll need to provide this)
    document_path = "test_document.pdf"  # Change this to your actual document path
    
    if not os.path.exists(document_path):
        print(f"❌ Test document not found: {document_path}")
        print("Please create a test document or update the path.")
        return False
    
    try:
        # Read the document as bytes
        with open(document_path, 'rb') as f:
            document_content = f.read()
        
        print(f"📄 Analyzing document: {document_path}")
        print(f"📊 Document size: {len(document_content)} bytes")
        
        # Analyze the document (using environment variables for credentials)
        results = analyze_document_bytes(
            document_content=document_content,
            content_type="application/pdf"  # Change based on your document type
        )
        
        print("✅ Analysis completed successfully!")
        print(f"📋 Result keys: {list(results.keys())}")
        
        # Print a sample of the results (first few keys and their types)
        print("\n📊 Sample results:")
        for key, value in list(results.items())[:3]:
            print(f"  {key}: {type(value).__name__}")
            if isinstance(value, (str, int, float)) and len(str(value)) < 100:
                print(f"    Value: {value}")
        
        return True
        
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        return False
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return False


def test_with_explicit_credentials():
    """Test with explicit credentials (alternative approach)."""
    
    print("\n" + "=" * 60)
    print("Testing with explicit credentials")
    print("=" * 60)
    
    # Example credentials (you'll need to provide actual values)
    endpoint = "https://your-service.cognitiveservices.azure.com/"
    api_key = "your-api-key-here"
    analyzer_name = "your-analyzer-name"
    
    document_path = "test_document.pdf"
    
    if not os.path.exists(document_path):
        print(f"❌ Test document not found: {document_path}")
        return False
    
    try:
        with open(document_path, 'rb') as f:
            document_content = f.read()
        
        # This will fail with dummy credentials, but shows the usage pattern
        results = analyze_document_bytes(
            document_content=document_content,
            content_type="application/pdf",
            endpoint=endpoint,
            api_key=api_key,
            analyzer_name=analyzer_name
        )
        
        print("✅ Analysis completed!")
        return True
        
    except Exception as e:
        print(f"ℹ️  Expected failure with dummy credentials: {e}")
        return False


def check_environment_variables():
    """Check if required environment variables are set."""
    
    print("=" * 60)
    print("Environment Variables Check")
    print("=" * 60)
    
    required_vars = [
        "CONTENT_UNDERSTANDING_ENDPOINT",
        "CONTENT_UNDERSTANDING_KEY", 
        "ANALYZER_NAME"
    ]
    
    all_set = True
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            # Mask sensitive values
            if "KEY" in var:
                display_value = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: Not set")
            all_set = False
    
    return all_set


def main():
    """Main test function."""
    
    print("🚀 Azure AI Content Understanding Test")
    print("=" * 60)
    
    # Check environment variables
    env_vars_ok = check_environment_variables()
    
    if env_vars_ok:
        print("\n✅ All environment variables are set!")
        # Run the actual test
        success = test_document_analysis()
        if success:
            print("\n🎉 Test completed successfully!")
        else:
            print("\n❌ Test failed. Check your configuration and document.")
    else:
        print("\n⚠️  Environment variables missing. You can either:")
        print("   1. Set the environment variables and run again")
        print("   2. Use explicit credentials in the function call")
        
        print("\n🔧 Testing explicit credentials approach...")
        test_with_explicit_credentials()


if __name__ == "__main__":
    main()