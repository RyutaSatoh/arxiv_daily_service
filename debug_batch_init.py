import os
import sys
# Add parent dir to path to find batch_processor
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    print("Attempting to import BatchProcessor...")
    from batch_processor import BatchProcessor
    print("Import successful.")
    
    print("Attempting to initialize BatchProcessor...")
    os.environ["GEMINI_API_KEY"] = "AIzaSyCK4Sw_80KvJ0rDTVqbGZTdCPAPP7zGnmU"
    bp = BatchProcessor()
    print("Initialization successful.")
    
    print("Attempting to check jobs...")
    bp.check_jobs()
    print("Check jobs finished.")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
