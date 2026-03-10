#!/usr/bin/env python3
import sys

def test_import(module_name):
    try:
        __import__(module_name)
        print(f"✓ {module_name} imported successfully")
        return True
    except ImportError as e:
        print(f"✗ {module_name} failed: {e}")
        return False

modules = [
    'cv2',
    'gtts',
    'pyzbar',
    'numpy',
    'PIL',
    'flask'
]

print("Testing imports...")
success = all(test_import(m) for m in modules)

if success:
    print("\nAll modules loaded successfully!")
    sys.exit(0)
else:
    print("\nSome modules failed to load")
    sys.exit(1)