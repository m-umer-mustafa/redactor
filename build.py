import PyInstaller.__main__
import os
import shutil

if __name__ == '__main__':
    print("Cleaning previous builds...")
    for clean_dir in ['build', 'dist']:
        if os.path.exists(clean_dir):
            shutil.rmtree(clean_dir)

    print("Starting PyInstaller compilation...")
    PyInstaller.__main__.run([
        'main.py',
        '--name=Redactor',
        '--windowed',
        '--icon=icon.ico',
        '--onedir',
        '--noconfirm',
        '--hidden-import=spacy',
        '--hidden-import=en_core_web_lg',
        '--hidden-import=presidio_analyzer',
        '--hidden-import=presidio_anonymizer',
        '--collect-data=spacy',
        '--collect-data=en_core_web_lg',
        '--collect-data=presidio_analyzer',
        '--collect-data=presidio_anonymizer',
        '--copy-metadata=spacy',
        '--copy-metadata=en_core_web_lg',
        '--copy-metadata=presidio_analyzer',
        '--hidden-import=fitz',
        '--hidden-import=docx',
        '--exclude-module=torch',
        '--exclude-module=tensorflow',
        '--exclude-module=tensorboard',
        '--add-data=icon.ico;.'
    ])

    # Brute-force cleanup of problematic heavy libraries that we DON'T need
    # This ensures they are never bundled even if sub-dependencies pull them in
    internal_dir = os.path.join('dist', 'Redactor', '_internal')
    if os.path.exists(internal_dir):
        import shutil
        to_delete = ['torch', 'tensorflow', 'tensorboard', 'torchvision', 'torchaudio', 'nvidia']
        for lib in to_delete:
            lib_path = os.path.join(internal_dir, lib)
            if os.path.exists(lib_path):
                print(f"Cleaning up: {lib}...")
                shutil.rmtree(lib_path, ignore_errors=True)
            # Also check for .py files or .pyd files starting with these names
            for item in os.listdir(internal_dir):
                if any(item.startswith(l) for l in to_delete):
                    item_path = os.path.join(internal_dir, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)

    print("Build complete! Check the dist/Redactor folder.")
