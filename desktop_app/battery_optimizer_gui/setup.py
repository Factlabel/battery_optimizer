#!/usr/bin/env python3
"""
Setup script for Battery Optimizer GUI Application

This script helps with installation and deployment of the PyQt6-based
Battery Optimizer application.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        return False
    return True

def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install dependencies: {e}")
        return False

def check_cbc_solver():
    """Check if CBC solver is available and working"""
    print("Checking CBC solver...")
    
    try:
        import pulp
        # Test CBC solver
        prob = pulp.LpProblem("test", pulp.LpMaximize)
        x = pulp.LpVariable("x", lowBound=0)
        prob += x
        prob += x <= 1
        
        # Try to solve with CBC
        result = prob.solve(pulp.PULP_CBC_CMD(msg=0))
        
        if result == pulp.LpStatusOptimal:
            print("✓ CBC solver is working correctly")
            return True
        else:
            print("✗ CBC solver test failed")
            return False
            
    except Exception as e:
        print(f"✗ CBC solver error: {e}")
        print("\nTrying to fix CBC permissions...")
        return fix_cbc_permissions()

def fix_cbc_permissions():
    """Fix CBC solver permissions on macOS"""
    if sys.platform != "darwin":
        return False
        
    try:
        import pulp
        
        # Find CBC binary path
        cbc_paths = [
            Path(pulp.__file__).parent / "solverdir" / "cbc" / "osx" / "arm64" / "cbc",
            Path(pulp.__file__).parent / "solverdir" / "cbc" / "osx" / "64" / "cbc"
        ]
        
        for cbc_path in cbc_paths:
            if cbc_path.exists():
                print(f"Found CBC at: {cbc_path}")
                os.chmod(cbc_path, 0o755)
                print("✓ Fixed CBC permissions")
                return True
                
        print("✗ CBC binary not found")
        return False
        
    except Exception as e:
        print(f"✗ Failed to fix CBC permissions: {e}")
        return False

def suggest_homebrew_cbc():
    """Suggest installing CBC via Homebrew"""
    print("\n" + "="*50)
    print("ALTERNATIVE SOLUTION:")
    print("If CBC issues persist, install via Homebrew:")
    print("  brew install cbc")
    print("="*50)

def test_import():
    """Test importing the main application"""
    print("Testing application import...")
    
    try:
        from battery_optimizer_gui.main import main
        print("✓ Application import successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def create_launcher_script():
    """Create launcher script for easy execution"""
    launcher_content = """#!/usr/bin/env python3
import sys
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from battery_optimizer_gui.main import main

if __name__ == "__main__":
    sys.exit(main())
"""
    
    launcher_path = Path("run_battery_optimizer.py")
    with open(launcher_path, "w") as f:
        f.write(launcher_content)
    
    # Make executable on Unix systems
    if sys.platform != "win32":
        os.chmod(launcher_path, 0o755)
    
    print(f"✓ Created launcher script: {launcher_path}")

def main():
    """Main setup function"""
    print("Battery Optimizer GUI Setup")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Install dependencies
    if not install_dependencies():
        return 1
    
    # Check CBC solver
    cbc_ok = check_cbc_solver()
    if not cbc_ok:
        suggest_homebrew_cbc()
    
    # Test import
    if not test_import():
        return 1
    
    # Create launcher
    create_launcher_script()
    
    print("\n" + "="*40)
    print("Setup completed!")
    print("\nTo run the application:")
    print("  python run_battery_optimizer.py")
    print("or:")
    print("  python -m battery_optimizer_gui.main")
    
    if not cbc_ok:
        print("\n⚠️  Warning: CBC solver issues detected.")
        print("   The application may still work with alternative solvers.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 