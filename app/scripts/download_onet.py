import kagglehub
import os

def download():
    # Download latest version
    path = kagglehub.dataset_download("emarkhauser/onet-29-0-database")
    print(f"Path to dataset files: {path}")
    
    # List files to see what we have
    files = os.listdir(path)
    print("\nFiles in dataset:")
    for f in files:
        print(f"- {f}")

if __name__ == "__main__":
    download()
